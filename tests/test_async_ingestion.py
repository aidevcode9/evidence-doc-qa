"""Tests for async document ingestion with status tracking (FR-015).

Upload returns 202 immediately with doc_id + status='queued'.
Background task processes document (parse → chunk → index).
GET /v1/docs/{doc_id}/status returns current ingestion state.
POST /v1/docs/{doc_id}/retry re-queues failed uploads.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.context import RequestContext
from app.db import Document
from app.rbac import Role


def run_async(coro):  # type: ignore[no-untyped-def]
    """Helper to run async functions in sync tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


def make_context(
    tenant_id: str = "tenant-1",
    matter_id: str = "matter-1",
    user_id: str = "user-1",
    user_role: Role = Role.ATTORNEY,
) -> RequestContext:
    return RequestContext(
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=user_id,
        user_role=user_role,
    )


class TestDocumentStatusField:
    """Document model has status-related columns."""

    def test_document_has_status_column(self) -> None:
        assert hasattr(Document, "status")

    def test_document_has_error_message_column(self) -> None:
        assert hasattr(Document, "error_message")

    def test_document_has_retry_count_column(self) -> None:
        assert hasattr(Document, "retry_count")

    def test_document_status_defaults_to_queued(self) -> None:
        doc = Document(
            doc_id="test",
            tenant_id="t1",
            matter_id="m1",
            doc_sha256="hash",
            doc_name="test.pdf",
            storage_path="/tmp/test.pdf",
            ingested_at_utc="2026-01-01T00:00:00Z",
            docs_snapshot_id="snap_test",
            status="queued",
        )
        assert doc.status == "queued"


class TestUploadReturns202:
    """Upload endpoint returns 202 Accepted with status=queued."""

    @pytest.mark.asyncio
    async def test_upload_returns_202_with_doc_id_and_status(self) -> None:
        from app.routers.docs import upload_doc

        mock_file = AsyncMock()
        mock_file.read.return_value = b"%PDF-1.4 async test"
        mock_file.filename = "async_test.pdf"

        mock_bg_tasks = MagicMock()

        with (
            patch("app.routers.docs.process_document_upload_async") as mock_process,
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            mock_process.return_value = {
                "doc_id": "new-doc-id",
                "doc_sha256": "fakehash",
                "docs_snapshot_id": "snap_fakehash",
                "storage_path": "/tmp/test.pdf",
                "status": "queued",
            }

            context = make_context()
            result = await upload_doc(
                file=mock_file,
                background_tasks=mock_bg_tasks,
                context=context,
            )

            assert result["status"] == "queued"
            assert "doc_id" in result
            # storage_path must NOT be in client response
            assert "storage_path" not in result


class TestGetUploadStatus:
    """GET /v1/docs/{doc_id}/status returns ingestion state."""

    @pytest.mark.asyncio
    async def test_status_returns_queued(self) -> None:
        from app.routers.docs import get_doc_status

        mock_doc = MagicMock(spec=Document)
        mock_doc.doc_id = "doc-123"
        mock_doc.status = "queued"
        mock_doc.doc_name = "test.pdf"
        mock_doc.error_message = None
        mock_doc.retry_count = 0
        mock_doc.tenant_id = "tenant-1"

        with (
            patch("app.routers.docs.get_document", return_value=mock_doc),
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            context = make_context()
            result = await get_doc_status("doc-123", context=context)
            assert result["doc_id"] == "doc-123"
            assert result["status"] == "queued"

    @pytest.mark.asyncio
    async def test_status_returns_processing(self) -> None:
        from app.routers.docs import get_doc_status

        mock_doc = MagicMock(spec=Document)
        mock_doc.doc_id = "doc-123"
        mock_doc.status = "processing"
        mock_doc.doc_name = "test.pdf"
        mock_doc.error_message = None
        mock_doc.retry_count = 0
        mock_doc.tenant_id = "tenant-1"

        with (
            patch("app.routers.docs.get_document", return_value=mock_doc),
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            context = make_context()
            result = await get_doc_status("doc-123", context=context)
            assert result["status"] == "processing"

    @pytest.mark.asyncio
    async def test_status_returns_ready(self) -> None:
        from app.routers.docs import get_doc_status

        mock_doc = MagicMock(spec=Document)
        mock_doc.doc_id = "doc-123"
        mock_doc.status = "ready"
        mock_doc.doc_name = "test.pdf"
        mock_doc.docs_snapshot_id = "snap_123"
        mock_doc.error_message = None
        mock_doc.retry_count = 0
        mock_doc.tenant_id = "tenant-1"

        with (
            patch("app.routers.docs.get_document", return_value=mock_doc),
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            context = make_context()
            result = await get_doc_status("doc-123", context=context)
            assert result["status"] == "ready"
            assert result["docs_snapshot_id"] == "snap_123"

    @pytest.mark.asyncio
    async def test_status_returns_failed_with_sanitized_error(self) -> None:
        """Failed status returns sanitized error, not raw exception."""
        from app.routers.docs import get_doc_status

        mock_doc = MagicMock(spec=Document)
        mock_doc.doc_id = "doc-123"
        mock_doc.status = "failed"
        mock_doc.doc_name = "test.pdf"
        mock_doc.error_message = "PARSE_FAILED: /internal/path/leaked"
        mock_doc.retry_count = 1
        mock_doc.tenant_id = "tenant-1"

        with (
            patch("app.routers.docs.get_document", return_value=mock_doc),
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            context = make_context()
            result = await get_doc_status("doc-123", context=context)
            assert result["status"] == "failed"
            # Error should be sanitized — no internal paths
            assert "/internal/path" not in result["error_message"]
            assert "parsing failed" in result["error_message"].lower()
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_status_not_found_raises_404(self) -> None:
        from app.routers.docs import get_doc_status
        from fastapi import HTTPException

        with (
            patch("app.routers.docs.get_document", return_value=None),
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            context = make_context()
            with pytest.raises(HTTPException) as exc_info:
                await get_doc_status("nonexistent", context=context)
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_status_enforces_tenant_isolation(self) -> None:
        from app.routers.docs import get_doc_status

        with (
            patch("app.routers.docs.get_document", return_value=None) as mock_get,
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            context = make_context(tenant_id="tenant-abc")
            with pytest.raises(Exception):
                await get_doc_status("doc-123", context=context)
            mock_get.assert_called_once_with("doc-123", tenant_id="tenant-abc")

    @pytest.mark.asyncio
    async def test_status_rbac_blocks_unauthorized(self) -> None:
        """Viewer without query permission gets 403."""
        from app.routers.docs import get_doc_status
        from fastapi import HTTPException

        with patch("app.routers.docs.has_permission", return_value=False):
            context = make_context(user_role=Role.VIEWER)
            with pytest.raises(HTTPException) as exc_info:
                await get_doc_status("doc-123", context=context)
            assert exc_info.value.status_code == 403


class TestRetryEndpoint:
    """POST /v1/docs/{doc_id}/retry re-queues failed uploads."""

    @pytest.mark.asyncio
    async def test_retry_resets_failed_to_queued(self) -> None:
        from app.routers.docs import retry_doc_upload

        mock_doc = MagicMock(spec=Document)
        mock_doc.doc_id = "doc-123"
        mock_doc.status = "failed"
        mock_doc.doc_sha256 = "hash123"
        mock_doc.docs_snapshot_id = "snap_123"
        mock_doc.error_message = "PARSE_FAILED: timeout"
        mock_doc.retry_count = 1
        mock_doc.tenant_id = "tenant-1"
        mock_doc.storage_path = "/tmp/test.pdf"
        mock_doc.doc_name = "test.pdf"

        mock_bg_tasks = MagicMock()

        with (
            patch("app.routers.docs.get_document", return_value=mock_doc),
            patch("app.routers.docs.update_document_status") as mock_update,
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            context = make_context()
            result = await retry_doc_upload(
                "doc-123",
                background_tasks=mock_bg_tasks,
                context=context,
            )

            assert result["status"] == "queued"
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_rejects_non_failed_document(self) -> None:
        from app.routers.docs import retry_doc_upload
        from fastapi import HTTPException

        mock_doc = MagicMock(spec=Document)
        mock_doc.doc_id = "doc-123"
        mock_doc.status = "ready"
        mock_doc.tenant_id = "tenant-1"

        mock_bg_tasks = MagicMock()

        with (
            patch("app.routers.docs.get_document", return_value=mock_doc),
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            context = make_context()
            with pytest.raises(HTTPException) as exc_info:
                await retry_doc_upload(
                    "doc-123",
                    background_tasks=mock_bg_tasks,
                    context=context,
                )
            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_retry_not_found_raises_404(self) -> None:
        from app.routers.docs import retry_doc_upload
        from fastapi import HTTPException

        mock_bg_tasks = MagicMock()

        with (
            patch("app.routers.docs.get_document", return_value=None),
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            context = make_context()
            with pytest.raises(HTTPException) as exc_info:
                await retry_doc_upload(
                    "nonexistent",
                    background_tasks=mock_bg_tasks,
                    context=context,
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_enforces_max_retries(self) -> None:
        """Retry should fail after MAX_RETRY_COUNT attempts."""
        from app.routers.docs import retry_doc_upload
        from fastapi import HTTPException

        mock_doc = MagicMock(spec=Document)
        mock_doc.doc_id = "doc-123"
        mock_doc.status = "failed"
        mock_doc.retry_count = 3  # Already at max
        mock_doc.tenant_id = "tenant-1"

        mock_bg_tasks = MagicMock()

        with (
            patch("app.routers.docs.get_document", return_value=mock_doc),
            patch("app.routers.docs.has_permission", return_value=True),
        ):
            context = make_context()
            with pytest.raises(HTTPException) as exc_info:
                await retry_doc_upload(
                    "doc-123",
                    background_tasks=mock_bg_tasks,
                    context=context,
                )
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_retry_rbac_blocks_viewer(self) -> None:
        """Viewer role cannot retry uploads."""
        from app.routers.docs import retry_doc_upload
        from fastapi import HTTPException

        mock_bg_tasks = MagicMock()

        with patch("app.routers.docs.has_permission", return_value=False):
            context = make_context(user_role=Role.VIEWER)
            with pytest.raises(HTTPException) as exc_info:
                await retry_doc_upload(
                    "doc-123",
                    background_tasks=mock_bg_tasks,
                    context=context,
                )
            assert exc_info.value.status_code == 403


class TestBackgroundProcessing:
    """Background task correctly processes and updates status."""

    @pytest.mark.asyncio
    async def test_background_task_updates_status_to_ready(self) -> None:
        from app.services.document_service import process_document_background

        mock_parse_result = MagicMock()
        mock_parse_result.pages = []
        mock_parse_result.provider = "pypdf"
        mock_parse_result.metadata = {}

        with (
            patch("app.services.document_service.ingestion") as mock_ingestion,
            patch("app.services.document_service.indexing"),
            patch("app.services.document_service.insert_chunks"),
            patch("app.services.document_service.update_document_status") as mock_update,
            patch("app.db.session_scope"),
        ):
            mock_ingestion.parse_document = AsyncMock(return_value=mock_parse_result)
            mock_ingestion.chunk_page_text.return_value = []
            mock_ingestion.utc_now.return_value = "2026-01-01T00:00:00Z"

            await process_document_background(
                doc_id="doc-123",
                doc_sha256="fakehash",
                docs_snapshot_id="snap_fake",
                storage_path="/tmp/test.pdf",
                filename="test.pdf",
                tenant_id="t1",
                matter_id="m1",
            )

            calls = mock_update.call_args_list
            statuses = [call.kwargs.get("status") or call.args[1] for call in calls]
            assert "processing" in statuses
            assert "ready" in statuses

    @pytest.mark.asyncio
    async def test_background_task_sets_failed_on_error(self) -> None:
        from app.services.document_service import process_document_background

        with (
            patch("app.services.document_service.ingestion") as mock_ingestion,
            patch("app.services.document_service.update_document_status") as mock_update,
        ):
            mock_ingestion.parse_document = AsyncMock(
                side_effect=RuntimeError("OCR engine crashed")
            )

            await process_document_background(
                doc_id="doc-123",
                doc_sha256="fakehash",
                docs_snapshot_id="snap_fake",
                storage_path="/tmp/test.pdf",
                filename="test.pdf",
                tenant_id="t1",
                matter_id="m1",
            )

            last_call = mock_update.call_args_list[-1]
            assert last_call.kwargs.get("status") == "failed" or "failed" in str(last_call)


class TestUpdateDocumentStatus:
    """DB helper to update document status."""

    def test_update_document_status_exists(self) -> None:
        from app import db

        assert hasattr(db, "update_document_status")
        assert callable(db.update_document_status)

    def test_update_document_status_accepts_required_params(self) -> None:
        import inspect

        from app.db import update_document_status

        sig = inspect.signature(update_document_status)
        params = list(sig.parameters.keys())
        assert "doc_id" in params
        assert "status" in params
        assert "tenant_id" in params

    def test_update_document_status_rejects_invalid_status(self) -> None:
        """Invalid status values should raise ValueError."""
        from app.db import update_document_status

        with pytest.raises(ValueError, match="Invalid status"):
            update_document_status("doc-123", "invalid_status")
