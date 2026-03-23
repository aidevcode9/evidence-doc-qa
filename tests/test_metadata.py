"""Tests for PDF metadata extraction (FR-014).

Extract title, author, page_count from PDF metadata during ingestion.
Store as metadata_json on Document model. Return in GET /v1/docs/{doc_id}.
"""

import json
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.db import Document


class TestDocumentModelMetadata:
    """Document model should have metadata_json column."""

    def test_document_has_metadata_json_column(self):
        """Document model must have metadata_json field (FR-014)."""
        doc = Document(
            doc_id="test",
            tenant_id="t1",
            matter_id="m1",
            doc_sha256="abc",
            doc_name="test.pdf",
            storage_path="/tmp/test.pdf",
            ingested_at_utc="2026-01-01T00:00:00Z",
            docs_snapshot_id="snap_abc",
            metadata_json=None,
        )
        assert hasattr(doc, "metadata_json")

    def test_metadata_json_is_nullable(self):
        """metadata_json should be nullable for backward compat with old docs."""
        doc = Document(
            doc_id="test",
            tenant_id="t1",
            matter_id="m1",
            doc_sha256="abc",
            doc_name="test.pdf",
            storage_path="/tmp/test.pdf",
            ingested_at_utc="2026-01-01T00:00:00Z",
            docs_snapshot_id="snap_abc",
        )
        assert doc.metadata_json is None


class TestMetadataInUpload:
    """Upload pipeline should store parser metadata as JSON."""

    @pytest.mark.asyncio
    async def test_upload_stores_metadata_from_parser(self):
        """process_document_upload should store parse_result.metadata as JSON."""
        from app.services.document_service import process_document_upload

        pdf_bytes = b"%PDF-1.4 metadata test content"

        mock_file = AsyncMock()
        mock_file.read.return_value = pdf_bytes
        mock_file.filename = "contract.pdf"

        captured_doc: list[Document] = []

        def capture_insert(doc: Document) -> None:
            captured_doc.append(doc)

        # Track metadata set during background processing via session_scope
        metadata_written: list[str] = []
        mock_doc_row = MagicMock()

        def track_metadata(val: str) -> None:
            metadata_written.append(val)

        type(mock_doc_row).metadata_json = property(
            lambda self: metadata_written[-1] if metadata_written else None,
            lambda self, v: track_metadata(v),
        )

        mock_session = MagicMock()
        mock_session.get.return_value = mock_doc_row
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda self: mock_session
        mock_ctx.__exit__ = lambda self, *a: None

        with (
            patch("app.services.document_service.get_document_by_sha256", return_value=None),
            patch("app.services.document_service.get_parser_client") as mock_parser,
            patch("app.services.document_service.ingestion") as mock_ingestion,
            patch("app.services.document_service.indexing"),
            patch("app.services.document_service.insert_chunks"),
            patch("app.services.document_service.insert_document", side_effect=capture_insert),
            patch("app.services.document_service.update_document_status"),
            patch("app.db.session_scope", return_value=mock_ctx),
        ):
            mock_ingestion.compute_sha256.return_value = "fakehash"
            mock_ingestion.docs_snapshot_id_for.return_value = "snap_fakehash"
            mock_ingestion.save_raw_pdf.return_value = "/tmp/contract.pdf"
            mock_ingestion.utc_now.return_value = "2026-01-01T00:00:00Z"

            mock_parse_result = MagicMock()
            mock_parse_result.pages = []
            mock_parse_result.provider = "pypdf"
            mock_parse_result.metadata = {
                "title": "Service Agreement",
                "author": "Legal Dept",
                "page_count": 5,
            }
            mock_ingestion.parse_document = AsyncMock(return_value=mock_parse_result)

            parser_instance = MagicMock()
            parser_instance.supported_extensions = {"pdf", "png", "jpg", "jpeg", "tiff", "bmp"}
            mock_parser.return_value = parser_instance

            await process_document_upload(
                mock_file, tenant_id="t1", matter_id="m1"
            )

        assert len(metadata_written) == 1
        meta = json.loads(metadata_written[0])
        assert meta["title"] == "Service Agreement"
        assert meta["author"] == "Legal Dept"
        assert meta["page_count"] == 5

    @pytest.mark.asyncio
    async def test_upload_stores_empty_metadata_when_none(self):
        """If parser returns empty metadata, store empty JSON object."""
        from app.services.document_service import process_document_upload

        pdf_bytes = b"%PDF-1.4 no metadata test"

        mock_file = AsyncMock()
        mock_file.read.return_value = pdf_bytes
        mock_file.filename = "plain.pdf"

        # Track metadata set during background processing via session_scope
        metadata_written: list[str] = []
        mock_doc_row = MagicMock()

        def track_metadata(val: str) -> None:
            metadata_written.append(val)

        type(mock_doc_row).metadata_json = property(
            lambda self: metadata_written[-1] if metadata_written else None,
            lambda self, v: track_metadata(v),
        )

        mock_session = MagicMock()
        mock_session.get.return_value = mock_doc_row
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = lambda self: mock_session
        mock_ctx.__exit__ = lambda self, *a: None

        with (
            patch("app.services.document_service.get_document_by_sha256", return_value=None),
            patch("app.services.document_service.get_parser_client") as mock_parser,
            patch("app.services.document_service.ingestion") as mock_ingestion,
            patch("app.services.document_service.indexing"),
            patch("app.services.document_service.insert_chunks"),
            patch("app.services.document_service.insert_document"),
            patch("app.services.document_service.update_document_status"),
            patch("app.db.session_scope", return_value=mock_ctx),
        ):
            mock_ingestion.compute_sha256.return_value = "hash2"
            mock_ingestion.docs_snapshot_id_for.return_value = "snap_hash2"
            mock_ingestion.save_raw_pdf.return_value = "/tmp/plain.pdf"
            mock_ingestion.utc_now.return_value = "2026-01-01T00:00:00Z"

            mock_parse_result = MagicMock()
            mock_parse_result.pages = []
            mock_parse_result.provider = "pypdf"
            mock_parse_result.metadata = {}
            mock_ingestion.parse_document = AsyncMock(return_value=mock_parse_result)

            parser_instance = MagicMock()
            parser_instance.supported_extensions = {"pdf", "png", "jpg", "jpeg", "tiff", "bmp"}
            mock_parser.return_value = parser_instance

            await process_document_upload(
                mock_file, tenant_id="t1", matter_id="m1"
            )

        assert len(metadata_written) == 1
        meta = json.loads(metadata_written[0])
        assert meta == {}


class TestMetadataInGetEndpoint:
    """GET /v1/docs/{doc_id} should return metadata_json."""

    def test_get_doc_metadata_includes_metadata(self):
        """Docs router should return parsed metadata in response."""
        from app.routers.docs import get_doc_metadata

        meta = {"title": "Deposition", "author": "Smith", "page_count": 12}
        fake_doc = Document(
            doc_id="doc-1",
            tenant_id="t1",
            matter_id="m1",
            doc_sha256="abc",
            doc_name="deposition.pdf",
            storage_path="/tmp/deposition.pdf",
            ingested_at_utc="2026-01-01T00:00:00Z",
            docs_snapshot_id="snap_abc",
            metadata_json=json.dumps(meta),
        )

        with patch("app.routers.docs.get_document", return_value=fake_doc):
            import asyncio

            mock_ctx = MagicMock()
            mock_ctx.tenant_id = "t1"
            result = asyncio.get_event_loop().run_until_complete(
                get_doc_metadata("doc-1", context=mock_ctx)
            )

        assert "metadata" in result
        assert result["metadata"]["title"] == "Deposition"
        assert result["metadata"]["author"] == "Smith"

    def test_get_doc_metadata_handles_null_metadata(self):
        """Old docs without metadata_json should return empty dict."""
        from app.routers.docs import get_doc_metadata

        fake_doc = Document(
            doc_id="doc-old",
            tenant_id="t1",
            matter_id="m1",
            doc_sha256="abc",
            doc_name="old.pdf",
            storage_path="/tmp/old.pdf",
            ingested_at_utc="2026-01-01T00:00:00Z",
            docs_snapshot_id="snap_abc",
            metadata_json=None,
        )

        with patch("app.routers.docs.get_document", return_value=fake_doc):
            import asyncio

            mock_ctx = MagicMock()
            mock_ctx.tenant_id = "t1"
            result = asyncio.get_event_loop().run_until_complete(
                get_doc_metadata("doc-old", context=mock_ctx)
            )

        assert result["metadata"] == {}


class TestPyPdfMetadataExtraction:
    """PyPDF parser should extract title and author from PDF metadata."""

    def test_pypdf_parser_extracts_metadata(self):
        """Verify PyPdfParser populates ParseResult.metadata."""
        from app.parsers.base import ParseResult

        # ParseResult should have metadata field
        result = ParseResult(text="", pages=[], metadata={"title": "Test", "author": "Author"})
        assert result.metadata["title"] == "Test"
        assert result.metadata["author"] == "Author"
