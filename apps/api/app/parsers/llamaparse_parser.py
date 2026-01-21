"""LlamaParse parser implementation.

LlamaParse is a cloud-based document parser with best-in-class VLM-powered OCR.
It requires an API key from LlamaIndex.

Features:
- Best VLM-powered OCR accuracy
- Handles complex layouts and tables
- Cloud-based (no local GPU required)
- Cost: ~$0.003 per page
"""

from __future__ import annotations

import os
import time
from typing import Any

from app.parsers.base import PageContent, ParseResult, ParserClient


def _normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text."""
    return " ".join(text.split())


class LlamaParseParser(ParserClient):
    """LlamaParse cloud-based parser with VLM-powered OCR.

    This parser uses LlamaIndex's LlamaParse API for document extraction.
    It provides the highest OCR accuracy but requires an API key.

    Supported formats: PDF, PNG, JPG, TIFF

    Configuration via environment variables:
    - LLAMAPARSE_API_KEY: Required API key for LlamaParse
    """

    def __init__(self) -> None:
        """Initialize LlamaParseParser with config."""
        from app.config import LLAMAPARSE_API_KEY

        self._api_key = LLAMAPARSE_API_KEY
        if not self._api_key:
            raise ValueError(
                "LLAMAPARSE_API_KEY is required for LlamaParseParser. "
                "Get an API key from https://cloud.llamaindex.ai/"
            )

    @property
    def supported_extensions(self) -> set[str]:
        """Return supported file extensions."""
        return {"pdf", "png", "jpg", "jpeg", "tiff", "tif"}

    async def parse(self, file_path: str, *, force_ocr: bool = False) -> ParseResult:
        """Parse a document using LlamaParse cloud API.

        Args:
            file_path: Path to the document file.
            force_ocr: Ignored (LlamaParse always uses VLM-based extraction).

        Returns:
            ParseResult with extracted text and page information.

        Raises:
            ValueError: If file type is not supported or API key missing.
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
                f"LlamaParse supports: {', '.join(sorted(self.supported_extensions))}"
            )

        start_time = time.perf_counter()

        # Lazy import to avoid loading unless needed
        try:
            from llama_parse import LlamaParse
        except ImportError as e:
            raise ImportError(
                "llama-parse is not installed. Install with: pip install llama-parse"
            ) from e

        # Create parser instance
        parser = LlamaParse(
            api_key=self._api_key,
            result_type="markdown",
            verbose=False,
        )

        # Parse document (async)
        documents = await parser.aload_data(file_path)

        # Extract pages with character offsets
        pages: list[PageContent] = []
        char_offset = 0

        for doc_num, doc in enumerate(documents, start=1):
            page_text = _normalize_whitespace(doc.text)
            char_start = char_offset
            char_end = char_offset + len(page_text)

            pages.append(
                PageContent(
                    page_number=doc_num,
                    text=page_text,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
            char_offset = char_end + 1

        # Build full text
        full_text = " ".join(page.text for page in pages)

        # Extract metadata
        metadata: dict[str, Any] = {
            "page_count": len(pages),
        }

        # LlamaParse may provide additional metadata
        if documents and hasattr(documents[0], "metadata"):
            metadata.update(documents[0].metadata)

        parse_time_ms = int((time.perf_counter() - start_time) * 1000)

        return ParseResult(
            text=full_text,
            pages=pages,
            tables=[],  # LlamaParse returns tables inline in markdown
            metadata=metadata,
            parse_time_ms=parse_time_ms,
            provider="llamaparse",
            cached=False,
        )
