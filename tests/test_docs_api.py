# tests/test_docs_api.py
"""Tests for document API endpoints (FR-030, FR-031)."""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.context import RequestContext
from app.db import Document


def run_async(coro):  # type: ignore[no-untyped-def]
    """Helper to run async functions in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


def make_context(tenant_id: str = "tenant-1", matter_id: str = "matter-1") -> RequestContext:
    """Create a test request context."""
    return RequestContext(tenant_id=tenant_id, matter_id=matter_id)


class TestGetDocMetadata:
    """Tests for GET /v1/docs/{doc_id} endpoint."""

    def test_get_doc_metadata_returns_document_info(self) -> None:
        """Document metadata endpoint returns expected fields."""
        mock_doc = MagicMock(spec=Document)
        mock_doc.doc_id = "test-doc-123"
        mock_doc.doc_name = "contract.pdf"
        mock_doc.doc_sha256 = "abc123"
        mock_doc.docs_snapshot_id = "snap_abc123"
        mock_doc.ingested_at_utc = "2026-01-21T12:00:00Z"

        with patch("app.routers.docs.get_document", return_value=mock_doc):
            from app.routers.docs import get_doc_metadata

            context = make_context()
            result = run_async(get_doc_metadata("test-doc-123", context=context))

            assert result["doc_id"] == "test-doc-123"
            assert result["doc_name"] == "contract.pdf"
            assert result["doc_sha256"] == "abc123"
            assert result["docs_snapshot_id"] == "snap_abc123"

    def test_get_doc_metadata_not_found_raises_404(self) -> None:
        """Non-existent document returns 404."""
        with patch("app.routers.docs.get_document", return_value=None):
            from app.routers.docs import get_doc_metadata
            from fastapi import HTTPException

            context = make_context()
            with pytest.raises(HTTPException) as exc_info:
                run_async(get_doc_metadata("nonexistent-doc", context=context))
            assert exc_info.value.status_code == 404


class TestViewDoc:
    """Tests for GET /v1/docs/{doc_id}/view endpoint."""

    def test_view_doc_returns_file_response(self) -> None:
        """Document view endpoint returns file response for existing file."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, mode="wb"
        ) as f:
            f.write(b"%PDF-1.4 test content")
            temp_path = f.name

        try:
            mock_doc = MagicMock(spec=Document)
            mock_doc.doc_id = "test-doc-123"
            mock_doc.doc_name = "contract.pdf"
            mock_doc.storage_path = temp_path

            with patch("app.routers.docs.get_document", return_value=mock_doc):
                from app.routers.docs import view_doc

                context = make_context()
                result = run_async(view_doc("test-doc-123", context=context))

                assert result.media_type == "application/pdf"
                assert result.filename == "contract.pdf"
        finally:
            os.unlink(temp_path)

    def test_view_doc_not_found_raises_404(self) -> None:
        """Non-existent document returns 404."""
        with patch("app.routers.docs.get_document", return_value=None):
            from app.routers.docs import view_doc
            from fastapi import HTTPException

            context = make_context()
            with pytest.raises(HTTPException) as exc_info:
                run_async(view_doc("nonexistent-doc", context=context))
            assert exc_info.value.status_code == 404

    def test_view_doc_file_missing_raises_404(self) -> None:
        """Document with missing file on disk returns 404."""
        mock_doc = MagicMock(spec=Document)
        mock_doc.doc_id = "test-doc-123"
        mock_doc.doc_name = "contract.pdf"
        mock_doc.storage_path = "/nonexistent/path/to/file.pdf"

        with patch("app.routers.docs.get_document", return_value=mock_doc):
            from app.routers.docs import view_doc
            from fastapi import HTTPException

            context = make_context()
            with pytest.raises(HTTPException) as exc_info:
                run_async(view_doc("test-doc-123", context=context))
            assert exc_info.value.status_code == 404
            assert "not found on disk" in str(exc_info.value.detail)

    def test_view_doc_correct_media_type_for_images(self) -> None:
        """Image files return correct media types."""
        test_cases = [
            (".png", "image/png"),
            (".jpg", "image/jpeg"),
            (".jpeg", "image/jpeg"),
            (".tiff", "image/tiff"),
        ]

        for ext, expected_media_type in test_cases:
            with tempfile.NamedTemporaryFile(
                suffix=ext, delete=False, mode="wb"
            ) as f:
                f.write(b"test image content")
                temp_path = f.name

            try:
                mock_doc = MagicMock(spec=Document)
                mock_doc.doc_id = "test-doc"
                mock_doc.doc_name = f"image{ext}"
                mock_doc.storage_path = temp_path

                with patch("app.routers.docs.get_document", return_value=mock_doc):
                    from app.routers.docs import view_doc

                    context = make_context()
                    result = run_async(view_doc("test-doc", context=context))

                    assert result.media_type == expected_media_type, (
                        f"Expected {expected_media_type} for {ext}"
                    )
            finally:
                os.unlink(temp_path)
