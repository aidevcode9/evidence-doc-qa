"""Tests for document deduplication (FR-011).

Same file uploaded twice to the same matter → rejected (HTTP 409).
Same file in different matters → allowed (matter-level isolation).
"""

import hashlib
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from app.db import Document, get_document_by_sha256


class TestGetDocumentBySha256:
    """Unit tests for the get_document_by_sha256 query function."""

    def test_get_document_by_sha256_exists(self):
        """Function should exist in db module."""
        from app import db

        assert hasattr(db, "get_document_by_sha256")
        assert callable(db.get_document_by_sha256)

    def test_get_document_by_sha256_requires_tenant_and_matter(self):
        """Function must require tenant_id and matter_id for isolation."""
        import inspect

        sig = inspect.signature(get_document_by_sha256)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params, "tenant_id required (FR-001)"
        assert "matter_id" in params, "matter_id required (FR-002)"
        assert "doc_sha256" in params

    @patch("app.db.session_scope")
    def test_get_document_by_sha256_finds_match(self, mock_scope: MagicMock):
        """Should return Document when matching hash exists in same matter."""
        fake_doc = Document(
            doc_id="doc-123",
            tenant_id="t1",
            matter_id="m1",
            doc_sha256="abc123",
            doc_name="test.pdf",
            storage_path="/tmp/test.pdf",
            ingested_at_utc="2026-01-01T00:00:00Z",
            docs_snapshot_id="snap_abc123",
        )
        mock_session = MagicMock()
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.scalars.return_value.first.return_value = fake_doc

        result = get_document_by_sha256("t1", "m1", "abc123")
        assert result is not None
        assert result.doc_id == "doc-123"

    @patch("app.db.session_scope")
    def test_get_document_by_sha256_no_match_returns_none(self, mock_scope: MagicMock):
        """Should return None when no matching hash in matter."""
        mock_session = MagicMock()
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.scalars.return_value.first.return_value = None

        result = get_document_by_sha256("t1", "m1", "nonexistent")
        assert result is None

    @patch("app.db.session_scope")
    def test_get_document_by_sha256_wrong_tenant_returns_none(self, mock_scope: MagicMock):
        """Should not return docs from different tenant (FR-001)."""
        mock_session = MagicMock()
        mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_session.scalars.return_value.first.return_value = None

        result = get_document_by_sha256("wrong-tenant", "m1", "abc123")
        assert result is None


class TestDedupInUpload:
    """Tests for deduplication check during document upload."""

    @pytest.mark.asyncio
    async def test_dedup_same_file_same_matter_returns_409(self):
        """Uploading same file to same matter should return 409 Conflict."""
        from app.services.document_service import process_document_upload

        pdf_bytes = b"%PDF-1.4 fake content for dedup test"
        sha = hashlib.sha256(pdf_bytes).hexdigest()

        existing_doc = Document(
            doc_id="existing-doc-id",
            tenant_id="t1",
            matter_id="m1",
            doc_sha256=sha,
            doc_name="original.pdf",
            storage_path="/tmp/original.pdf",
            ingested_at_utc="2026-01-01T00:00:00Z",
            docs_snapshot_id=f"snap_{sha[:12]}",
        )

        mock_file = AsyncMock()
        mock_file.read.return_value = pdf_bytes
        mock_file.filename = "duplicate.pdf"

        with patch("app.services.document_service.get_document_by_sha256", return_value=existing_doc):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await process_document_upload(
                    mock_file, tenant_id="t1", matter_id="m1"
                )
            assert exc_info.value.status_code == 409
            assert "existing-doc-id" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_dedup_same_file_different_matter_succeeds(self):
        """Same file in different matter should succeed (matter isolation)."""
        from app.services.document_service import process_document_upload

        pdf_bytes = b"%PDF-1.4 fake content for cross-matter test"

        mock_file = AsyncMock()
        mock_file.read.return_value = pdf_bytes
        mock_file.filename = "test.pdf"

        with (
            patch("app.services.document_service.get_document_by_sha256", return_value=None),
            patch("app.services.document_service.get_parser_client") as mock_parser,
            patch("app.services.document_service.ingestion") as mock_ingestion,
            patch("app.services.document_service.indexing"),
            patch("app.services.document_service.insert_chunks"),
            patch("app.services.document_service.insert_document"),
        ):
            mock_ingestion.compute_sha256.return_value = "fakehash"
            mock_ingestion.docs_snapshot_id_for.return_value = "snap_fakehash"
            mock_ingestion.save_raw_pdf.return_value = "/tmp/test.pdf"
            mock_ingestion.utc_now.return_value = "2026-01-01T00:00:00Z"

            mock_parse_result = MagicMock()
            mock_parse_result.pages = []
            mock_parse_result.provider = "pypdf"
            mock_parse_result.metadata = {}
            mock_ingestion.parse_document = AsyncMock(return_value=mock_parse_result)

            parser_instance = MagicMock()
            parser_instance.supported_extensions = {"pdf", "png", "jpg", "jpeg", "tiff", "bmp"}
            mock_parser.return_value = parser_instance

            result = await process_document_upload(
                mock_file, tenant_id="t1", matter_id="m2"
            )
            assert "doc_id" in result
            assert result["doc_sha256"] == "fakehash"

    @pytest.mark.asyncio
    async def test_dedup_different_file_same_matter_succeeds(self):
        """Different file in same matter should succeed normally."""
        from app.services.document_service import process_document_upload

        pdf_bytes = b"%PDF-1.4 unique content"

        mock_file = AsyncMock()
        mock_file.read.return_value = pdf_bytes
        mock_file.filename = "unique.pdf"

        with (
            patch("app.services.document_service.get_document_by_sha256", return_value=None),
            patch("app.services.document_service.get_parser_client") as mock_parser,
            patch("app.services.document_service.ingestion") as mock_ingestion,
            patch("app.services.document_service.indexing"),
            patch("app.services.document_service.insert_chunks"),
            patch("app.services.document_service.insert_document"),
        ):
            mock_ingestion.compute_sha256.return_value = "uniquehash"
            mock_ingestion.docs_snapshot_id_for.return_value = "snap_uniquehash"
            mock_ingestion.save_raw_pdf.return_value = "/tmp/unique.pdf"
            mock_ingestion.utc_now.return_value = "2026-01-01T00:00:00Z"

            mock_parse_result = MagicMock()
            mock_parse_result.pages = []
            mock_parse_result.provider = "pypdf"
            mock_parse_result.metadata = {}
            mock_ingestion.parse_document = AsyncMock(return_value=mock_parse_result)

            parser_instance = MagicMock()
            parser_instance.supported_extensions = {"pdf", "png", "jpg", "jpeg", "tiff", "bmp"}
            mock_parser.return_value = parser_instance

            result = await process_document_upload(
                mock_file, tenant_id="t1", matter_id="m1"
            )
            assert "doc_id" in result

    @pytest.mark.asyncio
    async def test_dedup_409_includes_existing_doc_info(self):
        """409 response should include existing doc_id and snapshot for client use."""
        from app.services.document_service import process_document_upload

        pdf_bytes = b"%PDF-1.4 duplicate info test"
        sha = hashlib.sha256(pdf_bytes).hexdigest()

        existing_doc = Document(
            doc_id="orig-id",
            tenant_id="t1",
            matter_id="m1",
            doc_sha256=sha,
            doc_name="original.pdf",
            storage_path="/tmp/original.pdf",
            ingested_at_utc="2026-01-01T00:00:00Z",
            docs_snapshot_id="snap_orig",
        )

        mock_file = AsyncMock()
        mock_file.read.return_value = pdf_bytes
        mock_file.filename = "dup.pdf"

        with patch("app.services.document_service.get_document_by_sha256", return_value=existing_doc):
            from fastapi import HTTPException

            with pytest.raises(HTTPException) as exc_info:
                await process_document_upload(
                    mock_file, tenant_id="t1", matter_id="m1"
                )
            detail = exc_info.value.detail
            assert "orig-id" in str(detail)
            assert "snap_orig" in str(detail)
