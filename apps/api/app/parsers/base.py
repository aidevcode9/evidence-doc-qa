"""Parser interface and data models for document parsing (NFR-036).

This module defines the ParserClient abstract base class and data structures
used by all parser implementations (pypdf, marker, llamaparse).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PageContent:
    """Content extracted from a single page.

    Attributes:
        page_number: 1-indexed page number.
        text: Extracted text content.
        char_start: Absolute character offset from start of document.
        char_end: Absolute character offset of end of page content.
    """

    page_number: int
    text: str
    char_start: int
    char_end: int


@dataclass
class ParseResult:
    """Result of parsing a document.

    Attributes:
        text: Full concatenated text from all pages.
        pages: Per-page content with character offsets.
        tables: Structured table data (if extracted).
        metadata: Document metadata (title, author, page_count, etc.).
        parse_time_ms: Time taken to parse in milliseconds.
        provider: Parser provider name ('pypdf', 'marker', 'llamaparse').
        cached: Whether result was retrieved from cache.
    """

    text: str
    pages: list[PageContent]
    tables: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    parse_time_ms: int = 0
    provider: str = ""
    cached: bool = False


class ParserClient(ABC):
    """Abstract base class for document parsers.

    Implementations must provide:
    - parse(): Async method to parse a document file.
    - supported_extensions: Property returning set of supported file extensions.
    """

    @abstractmethod
    async def parse(self, file_path: str, *, force_ocr: bool = False) -> ParseResult:
        """Parse a document and return structured result.

        Args:
            file_path: Path to the document file.
            force_ocr: Force OCR even on digital documents (if supported).

        Returns:
            ParseResult with extracted text, pages, and metadata.

        Raises:
            ValueError: If file type is not supported.
            FileNotFoundError: If file does not exist.
        """
        pass

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return set of supported file extensions (without dots).

        Example: {"pdf", "png", "jpg", "jpeg", "tiff", "tif"}
        """
        pass
