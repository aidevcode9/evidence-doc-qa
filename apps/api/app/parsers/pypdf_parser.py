"""PyPDF parser implementation.

This parser wraps the existing pypdf-based extraction logic.
It only supports digital PDFs (no OCR for scanned documents).
"""

from __future__ import annotations

import asyncio
import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from pypdf import PdfReader

from app.parsers.base import PageContent, ParseResult, ParserClient

if TYPE_CHECKING:
    pass

_executor = ThreadPoolExecutor(max_workers=4)


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text."""
    return " ".join(text.split())


def _extract_pages_sync(file_path: str) -> tuple[list[PageContent], dict[str, object]]:
    """Synchronous page extraction using pypdf.

    Returns:
        Tuple of (pages, metadata).
    """
    reader = PdfReader(file_path)
    pages: list[PageContent] = []
    char_offset = 0

    for page_num, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        text = _normalize_whitespace(raw_text)

        char_start = char_offset
        char_end = char_offset + len(text)

        pages.append(
            PageContent(
                page_number=page_num,
                text=text,
                char_start=char_start,
                char_end=char_end,
            )
        )

        char_offset = char_end + 1  # +1 for page separator

    metadata: dict[str, object] = {
        "page_count": len(reader.pages),
    }

    # Extract PDF metadata if available
    if reader.metadata:
        if reader.metadata.title:
            metadata["title"] = reader.metadata.title
        if reader.metadata.author:
            metadata["author"] = reader.metadata.author

    return pages, metadata


class PyPdfParser(ParserClient):
    """PyPDF-based parser for digital PDFs.

    This parser uses pypdf for text extraction. It does not support OCR,
    so scanned PDFs will return empty or minimal text.

    Supported formats: PDF only.
    """

    @property
    def supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {"pdf"}

    async def parse(self, file_path: str, *, force_ocr: bool = False) -> ParseResult:
        """Parse a PDF document.

        Args:
            file_path: Path to the PDF file.
            force_ocr: Ignored (pypdf does not support OCR).

        Returns:
            ParseResult with extracted text and page information.

        Raises:
            ValueError: If file is not a PDF.
            FileNotFoundError: If file does not exist.
        """
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Validate extension
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
        if ext not in self.supported_extensions:
            raise ValueError(f"Unsupported file type: {ext}. PyPDF only supports PDF files.")

        start_time = time.perf_counter()

        # Run extraction in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        pages, metadata = await loop.run_in_executor(
            _executor, _extract_pages_sync, file_path
        )

        # Build full text from pages
        full_text = " ".join(page.text for page in pages)

        parse_time_ms = int((time.perf_counter() - start_time) * 1000)

        return ParseResult(
            text=full_text,
            pages=pages,
            tables=[],
            metadata=metadata,
            parse_time_ms=parse_time_ms,
            provider="pypdf",
            cached=False,
        )
