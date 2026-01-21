"""Marker parser implementation.

Marker is a fast document parser with OCR support. It can process PDFs
(both digital and scanned) as well as images.

Features:
- Fast processing (25pg/s on GPU)
- OCR for scanned documents and images
- Optional LLM enhancement for better quality
- Works on CPU (slower) if GPU not available
"""

from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.parsers.base import PageContent, ParseResult, ParserClient

_executor = ThreadPoolExecutor(max_workers=2)


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text."""
    return " ".join(text.split())


def _extract_with_marker_sync(
    file_path: str,
    force_ocr: bool,
    use_llm: bool,
) -> tuple[list[PageContent], list[dict[str, Any]], dict[str, Any]]:
    """Synchronous extraction using Marker.

    Args:
        file_path: Path to document.
        force_ocr: Force OCR even on digital PDFs.
        use_llm: Use LLM for enhanced extraction quality.

    Returns:
        Tuple of (pages, tables, metadata).
    """
    # Lazy import to avoid loading marker unless needed
    try:
        from marker.config.parser import ConfigParser
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
    except ImportError as e:
        raise ImportError(
            "marker-pdf is not installed. Install with: pip install marker-pdf"
        ) from e

    # Build config dict for Marker 1.10+
    config_dict: dict[str, Any] = {
        "output_format": "markdown",
    }
    if force_ocr:
        config_dict["force_ocr"] = True
    if use_llm:
        config_dict["use_llm"] = True

    # Create converter using ConfigParser (Marker 1.10+ API)
    config_parser = ConfigParser(config_dict)
    models = create_model_dict()

    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
    )

    # Run conversion
    result = converter(file_path)

    # Extract pages with character offsets
    pages: list[PageContent] = []
    char_offset = 0

    # Marker returns markdown text, we need to parse it
    # For now, treat entire document as single page for images
    # or extract per-page for PDFs
    full_text = result.markdown if hasattr(result, "markdown") else str(result)
    full_text = _normalize_whitespace(full_text)

    # Check if result has page information
    if hasattr(result, "pages") and result.pages:
        for page_num, page_data in enumerate(result.pages, start=1):
            page_text = _normalize_whitespace(
                page_data.text if hasattr(page_data, "text") else str(page_data)
            )
            char_start = char_offset
            char_end = char_offset + len(page_text)

            pages.append(
                PageContent(
                    page_number=page_num,
                    text=page_text,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
            char_offset = char_end + 1
    else:
        # Single page (image or simple document)
        pages.append(
            PageContent(
                page_number=1,
                text=full_text,
                char_start=0,
                char_end=len(full_text),
            )
        )

    # Extract tables if available
    tables: list[dict[str, Any]] = []
    if hasattr(result, "tables"):
        for table in result.tables:
            tables.append({"data": table})

    # Build metadata
    metadata: dict[str, Any] = {
        "page_count": len(pages),
    }
    if hasattr(result, "metadata") and result.metadata:
        metadata.update(result.metadata)

    return pages, tables, metadata


class MarkerParser(ParserClient):
    """Marker-based parser with OCR support.

    This parser uses Marker for document extraction. It supports:
    - Digital PDFs (text extraction)
    - Scanned PDFs (OCR)
    - Images (PNG, JPG, TIFF)

    Configuration via environment variables:
    - MARKER_USE_LLM: Use LLM for better extraction quality (default: false)
    - MARKER_FORCE_OCR: Force OCR even on digital PDFs (default: false)
    """

    def __init__(self) -> None:
        """Initialize MarkerParser with config."""
        # Import config lazily to avoid circular imports
        from app.config import MARKER_FORCE_OCR, MARKER_USE_LLM

        self._use_llm = MARKER_USE_LLM
        self._force_ocr = MARKER_FORCE_OCR

    @property
    def supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {"pdf", "png", "jpg", "jpeg", "tiff", "tif"}

    async def parse(self, file_path: str, *, force_ocr: bool = False) -> ParseResult:
        """Parse a document using Marker.

        Args:
            file_path: Path to the document file.
            force_ocr: Force OCR even on digital documents.

        Returns:
            ParseResult with extracted text and page information.

        Raises:
            ValueError: If file type is not supported.
            FileNotFoundError: If file does not exist.
        """
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Validate extension
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        if ext not in self.supported_extensions:
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Marker supports: {', '.join(sorted(self.supported_extensions))}"
            )

        start_time = time.perf_counter()

        # Use force_ocr from param or config
        should_force_ocr = force_ocr or self._force_ocr

        # Run extraction in thread pool
        loop = asyncio.get_event_loop()
        pages, tables, metadata = await loop.run_in_executor(
            _executor,
            _extract_with_marker_sync,
            file_path,
            should_force_ocr,
            self._use_llm,
        )

        # Build full text
        full_text = " ".join(page.text for page in pages)

        parse_time_ms = int((time.perf_counter() - start_time) * 1000)

        return ParseResult(
            text=full_text,
            pages=pages,
            tables=tables,
            metadata=metadata,
            parse_time_ms=parse_time_ms,
            provider="marker",
            cached=False,
        )
