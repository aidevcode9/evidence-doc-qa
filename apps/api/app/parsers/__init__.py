"""Parser factory and exports.

This module provides the factory function for creating parser instances
based on configuration.

Usage:
    from app.parsers import get_parser_client
    parser = get_parser_client()
    result = await parser.parse("document.pdf")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.parsers.base import PageContent, ParseResult, ParserClient

if TYPE_CHECKING:
    pass

__all__ = [
    "get_parser_client",
    "PageContent",
    "ParseResult",
    "ParserClient",
]


def get_parser_client() -> ParserClient:
    """Get the configured parser client.

    Returns parser based on PARSER_PROVIDER environment variable:
    - "pypdf": PyPDF parser (digital PDFs only, no OCR)
    - "marker": Marker parser (OCR support, default)
    - "llamaparse": LlamaParse cloud parser (best OCR, requires API key)

    Returns:
        Configured ParserClient instance.

    Raises:
        ValueError: If PARSER_PROVIDER is not recognized.
    """
    from app.config import PARSER_PROVIDER

    if PARSER_PROVIDER == "pypdf":
        from app.parsers.pypdf_parser import PyPdfParser

        return PyPdfParser()

    elif PARSER_PROVIDER == "marker":
        from app.parsers.marker_parser import MarkerParser

        return MarkerParser()

    elif PARSER_PROVIDER == "llamaparse":
        from app.parsers.llamaparse_parser import LlamaParseParser

        return LlamaParseParser()

    else:
        raise ValueError(
            f"Unknown parser provider: {PARSER_PROVIDER}. "
            f"Valid options: pypdf, marker, llamaparse"
        )
