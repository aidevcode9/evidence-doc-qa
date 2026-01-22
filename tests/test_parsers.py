"""Tests for parser module (FR-010, FR-012, NFR-036).

Tests the ParserClient abstraction and implementations.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.parsers.base import PageContent, ParseResult


def run_async(coro):
    """Helper to run async functions in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestPageContent:
    """Test PageContent dataclass."""

    def test_page_content_creation(self):
        """PageContent should store all fields."""
        page = PageContent(
            page_number=1,
            text="Hello world",
            char_start=0,
            char_end=11,
        )

        assert page.page_number == 1
        assert page.text == "Hello world"
        assert page.char_start == 0
        assert page.char_end == 11


class TestParseResult:
    """Test ParseResult dataclass."""

    def test_parse_result_creation(self):
        """ParseResult should store all fields."""
        pages = [
            PageContent(page_number=1, text="Page 1", char_start=0, char_end=6),
            PageContent(page_number=2, text="Page 2", char_start=7, char_end=13),
        ]

        result = ParseResult(
            text="Page 1 Page 2",
            pages=pages,
            tables=[{"data": "table1"}],
            metadata={"page_count": 2},
            parse_time_ms=100,
            provider="test",
            cached=True,
        )

        assert result.text == "Page 1 Page 2"
        assert len(result.pages) == 2
        assert result.tables == [{"data": "table1"}]
        assert result.metadata == {"page_count": 2}
        assert result.parse_time_ms == 100
        assert result.provider == "test"
        assert result.cached is True

    def test_parse_result_defaults(self):
        """ParseResult should have sensible defaults."""
        result = ParseResult(
            text="Test",
            pages=[],
        )

        assert result.tables == []
        assert result.metadata == {}
        assert result.parse_time_ms == 0
        assert result.provider == ""
        assert result.cached is False


class TestPyPdfParser:
    """Test PyPdfParser implementation."""

    def test_supported_extensions(self):
        """PyPdfParser should only support PDF."""
        from app.parsers.pypdf_parser import PyPdfParser

        parser = PyPdfParser()
        assert parser.supported_extensions == {"pdf"}

    def test_parse_nonexistent_file(self):
        """Should raise FileNotFoundError for missing file."""
        from app.parsers.pypdf_parser import PyPdfParser

        parser = PyPdfParser()

        with pytest.raises(FileNotFoundError):
            run_async(parser.parse("/nonexistent/file.pdf"))

    def test_parse_unsupported_extension(self):
        """Should raise ValueError for unsupported file type."""
        from app.parsers.pypdf_parser import PyPdfParser

        parser = PyPdfParser()

        # Create a temp file with wrong extension
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake image data")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                run_async(parser.parse(temp_path))
        finally:
            os.unlink(temp_path)

    def test_parse_pdf_returns_parse_result(self):
        """Should return ParseResult with correct structure."""
        from app.parsers.pypdf_parser import PyPdfParser

        parser = PyPdfParser()

        # Create a minimal PDF for testing
        # Using a mock instead since creating real PDFs is complex
        with patch("app.parsers.pypdf_parser._extract_pages_sync") as mock_extract:
            mock_extract.return_value = (
                [
                    PageContent(
                        page_number=1,
                        text="Test content",
                        char_start=0,
                        char_end=12,
                    )
                ],
                {"page_count": 1},
            )

            # Create temp PDF file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4 fake pdf")
                temp_path = f.name

            try:
                result = run_async(parser.parse(temp_path))

                assert isinstance(result, ParseResult)
                assert result.provider == "pypdf"
                assert len(result.pages) == 1
                assert result.pages[0].text == "Test content"
                assert result.metadata["page_count"] == 1
            finally:
                os.unlink(temp_path)


class TestParserFactory:
    """Test parser factory function."""

    def test_get_pypdf_parser(self):
        """Factory should return PyPdfParser when configured."""
        with patch("app.config.PARSER_PROVIDER", "pypdf"):
            from app.parsers.pypdf_parser import PyPdfParser

            # Need to reload to pick up patched config
            import importlib

            import app.parsers

            importlib.reload(app.parsers)

            from app.parsers import get_parser_client

            parser = get_parser_client()
            assert isinstance(parser, PyPdfParser)

    def test_get_marker_parser_import_error(self):
        """MarkerParser should be returned when configured."""
        with patch("app.config.PARSER_PROVIDER", "marker"):
            with patch("app.config.MARKER_USE_LLM", False):
                with patch("app.config.MARKER_FORCE_OCR", False):
                    import importlib

                    import app.parsers

                    importlib.reload(app.parsers)

                    from app.parsers import get_parser_client
                    from app.parsers.marker_parser import MarkerParser

                    # This will work but actual parse() will fail without marker installed
                    parser = get_parser_client()
                    assert isinstance(parser, MarkerParser)

    def test_get_llamaparse_parser_requires_api_key(self):
        """LlamaParseParser should require API key."""
        with patch("app.config.PARSER_PROVIDER", "llamaparse"):
            with patch("app.config.LLAMAPARSE_API_KEY", ""):
                import importlib

                import app.parsers

                importlib.reload(app.parsers)

                from app.parsers import get_parser_client

                with pytest.raises(ValueError, match="LLAMAPARSE_API_KEY is required"):
                    get_parser_client()

    def test_unknown_provider_raises_error(self):
        """Factory should raise ValueError for unknown provider."""
        with patch("app.config.PARSER_PROVIDER", "unknown"):
            import importlib

            import app.parsers

            importlib.reload(app.parsers)

            from app.parsers import get_parser_client

            with pytest.raises(ValueError, match="Unknown parser provider"):
                get_parser_client()


class TestMarkerParser:
    """Test MarkerParser implementation."""

    def test_supported_extensions(self):
        """MarkerParser should support PDFs and images."""
        with patch("app.config.MARKER_USE_LLM", False):
            with patch("app.config.MARKER_FORCE_OCR", False):
                from app.parsers.marker_parser import MarkerParser

                parser = MarkerParser()
                expected = {"pdf", "png", "jpg", "jpeg", "tiff", "tif"}
                assert parser.supported_extensions == expected

    def test_parse_nonexistent_file(self):
        """Should raise FileNotFoundError for missing file."""
        with patch("app.config.MARKER_USE_LLM", False):
            with patch("app.config.MARKER_FORCE_OCR", False):
                from app.parsers.marker_parser import MarkerParser

                parser = MarkerParser()

                with pytest.raises(FileNotFoundError):
                    run_async(parser.parse("/nonexistent/file.pdf"))

    def test_parse_unsupported_extension(self):
        """Should raise ValueError for unsupported file type."""
        with patch("app.config.MARKER_USE_LLM", False):
            with patch("app.config.MARKER_FORCE_OCR", False):
                from app.parsers.marker_parser import MarkerParser

                parser = MarkerParser()

                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
                    f.write(b"fake docx data")
                    temp_path = f.name

                try:
                    with pytest.raises(ValueError, match="Unsupported file type"):
                        run_async(parser.parse(temp_path))
                finally:
                    os.unlink(temp_path)


class TestLlamaParseParser:
    """Test LlamaParseParser implementation."""

    def test_requires_api_key(self):
        """Should raise ValueError if API key not set."""
        with patch("app.config.LLAMAPARSE_API_KEY", ""):
            # Force reimport
            import importlib

            import app.parsers.llamaparse_parser

            importlib.reload(app.parsers.llamaparse_parser)

            from app.parsers.llamaparse_parser import LlamaParseParser

            with pytest.raises(ValueError, match="LLAMAPARSE_API_KEY is required"):
                LlamaParseParser()

    def test_supported_extensions(self):
        """LlamaParseParser should support PDFs and images."""
        with patch("app.config.LLAMAPARSE_API_KEY", "test-key"):
            # Force reimport
            import importlib

            import app.parsers.llamaparse_parser

            importlib.reload(app.parsers.llamaparse_parser)

            from app.parsers.llamaparse_parser import LlamaParseParser

            parser = LlamaParseParser()
            expected = {"pdf", "png", "jpg", "jpeg", "tiff", "tif"}
            assert parser.supported_extensions == expected

    def test_parse_nonexistent_file(self):
        """Should raise FileNotFoundError for missing file."""
        with patch("app.config.LLAMAPARSE_API_KEY", "test-key"):
            # Force reimport
            import importlib

            import app.parsers.llamaparse_parser

            importlib.reload(app.parsers.llamaparse_parser)

            from app.parsers.llamaparse_parser import LlamaParseParser

            parser = LlamaParseParser()

            with pytest.raises(FileNotFoundError):
                run_async(parser.parse("/nonexistent/file.pdf"))


class TestIngestionIntegration:
    """Test integration with ingestion module."""

    def test_parse_document_uses_factory(self):
        """parse_document() should use configured parser."""
        with patch("app.config.PARSER_PROVIDER", "pypdf"):
            import importlib

            import app.parsers

            importlib.reload(app.parsers)

            from app.ingestion import parse_document

            # Mock the parser
            mock_result = ParseResult(
                text="Test content",
                pages=[
                    PageContent(
                        page_number=1,
                        text="Test content",
                        char_start=0,
                        char_end=12,
                    )
                ],
                provider="pypdf",
            )

            with patch(
                "app.parsers.pypdf_parser.PyPdfParser.parse", new_callable=AsyncMock
            ) as mock_parse:
                mock_parse.return_value = mock_result

                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                    f.write(b"%PDF-1.4")
                    temp_path = f.name

                try:
                    result = run_async(parse_document(temp_path))
                    assert result.provider == "pypdf"
                finally:
                    os.unlink(temp_path)
