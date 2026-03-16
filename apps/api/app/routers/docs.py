import json
import os
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.context import RequestContext, get_request_context
from app.db import get_document, update_document_status
from app.rbac import has_permission
from app.services.document_service import (
    process_document_background,
    process_document_upload_async,
)

router = APIRouter()

# FR-015: Maximum retry attempts before requiring manual intervention
MAX_RETRY_COUNT = 3


def _sanitize_error_for_client(error_message: str | None) -> str:
    """Return a safe error category without internal details."""
    if not error_message:
        return "Processing failed."
    if "PARSE_FAILED" in error_message:
        return "Document parsing failed. The file may be corrupted or unsupported."
    if "INDEX_FAILED" in error_message:
        return "Document indexing failed. Please retry."
    return "Processing failed. Please retry or contact support."


@router.post("/v1/docs/upload", status_code=202)
async def upload_doc(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    """Upload a document for async processing (FR-001, FR-002, FR-003, FR-015).

    Returns 202 Accepted immediately with doc_id and status='queued'.
    Background task handles parsing, chunking, and indexing.
    Poll GET /v1/docs/{doc_id}/status for progress.
    """
    # RBAC check (FR-003): Only admin, attorney, paralegal can upload
    if not has_permission(context.user_role, "upload"):
        raise HTTPException(
            status_code=403,
            detail="Permission denied: upload requires one of ['admin', 'attorney', 'paralegal']",
        )

    result = await process_document_upload_async(
        file,
        tenant_id=context.tenant_id,
        matter_id=context.matter_id,
    )

    # Queue background processing (FR-015)
    background_tasks.add_task(
        process_document_background,
        doc_id=result["doc_id"],
        doc_sha256=result["doc_sha256"],
        docs_snapshot_id=result["docs_snapshot_id"],
        storage_path=result["storage_path"],
        filename=file.filename or "upload.pdf",
        tenant_id=context.tenant_id,
        matter_id=context.matter_id,
    )

    # Don't expose storage_path to client
    return {
        "doc_id": result["doc_id"],
        "doc_sha256": result["doc_sha256"],
        "docs_snapshot_id": result["docs_snapshot_id"],
        "status": result["status"],
    }


@router.get("/v1/docs/{doc_id}/status")
async def get_doc_status(
    doc_id: str,
    context: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    """Get document ingestion status (FR-015).

    Returns current status: queued, processing, ready, or failed.
    If failed, includes sanitized error_message and retry_count.
    """
    # RBAC check (FR-003): Any role with query permission can check status
    if not has_permission(context.user_role, "query"):
        raise HTTPException(
            status_code=403,
            detail="Permission denied.",
        )

    doc = get_document(doc_id, tenant_id=context.tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    result: dict[str, Any] = {
        "doc_id": doc.doc_id,
        "status": doc.status,
        "doc_name": doc.doc_name,
        "retry_count": doc.retry_count or 0,
    }

    if doc.status == "failed":
        # Sanitize error message — don't expose internal details
        result["error_message"] = _sanitize_error_for_client(doc.error_message)
    else:
        result["error_message"] = None

    if doc.status == "ready":
        result["docs_snapshot_id"] = doc.docs_snapshot_id

    return result


@router.post("/v1/docs/{doc_id}/retry")
async def retry_doc_upload(
    doc_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    """Retry a failed document upload (FR-015).

    Only works for documents in 'failed' status. Max 3 retries.
    Re-queues the document for background processing.
    """
    # RBAC check (FR-003): Same permission as upload
    if not has_permission(context.user_role, "upload"):
        raise HTTPException(
            status_code=403,
            detail="Permission denied: retry requires upload permission.",
        )

    doc = get_document(doc_id, tenant_id=context.tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"Document is '{doc.status}', not 'failed'. Only failed documents can be retried.",
        )

    # Enforce retry limit
    current_retries = doc.retry_count or 0
    if current_retries >= MAX_RETRY_COUNT:
        raise HTTPException(
            status_code=429,
            detail=f"Maximum retry attempts ({MAX_RETRY_COUNT}) exceeded. Please re-upload the document.",
        )

    # Reset status to queued with tenant isolation
    update_document_status(
        doc_id, "queued",
        tenant_id=context.tenant_id,
        error_message=None,
        increment_retry=True,
    )

    # Re-queue background processing
    background_tasks.add_task(
        process_document_background,
        doc_id=doc.doc_id,
        doc_sha256=doc.doc_sha256,
        docs_snapshot_id=doc.docs_snapshot_id,
        storage_path=doc.storage_path,
        filename=doc.doc_name,
        tenant_id=context.tenant_id,
        matter_id=context.matter_id,
    )

    return {
        "doc_id": doc.doc_id,
        "status": "queued",
        "retry_count": current_retries + 1,
        "message": "Document re-queued for processing.",
    }


@router.get("/v1/docs/{doc_id}")
async def get_doc_metadata(
    doc_id: str,
    context: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    """Get document metadata by ID with tenant isolation (FR-001, FR-031).

    Returns document name, page count, and storage info for PDF viewer.
    """
    doc = get_document(doc_id, tenant_id=context.tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # FR-014: Include parsed metadata (title, author, page_count, etc.)
    metadata: dict[str, Any] = {}
    if doc.metadata_json:
        try:
            metadata = json.loads(doc.metadata_json)
        except (json.JSONDecodeError, TypeError):
            metadata = {}

    return {
        "doc_id": doc.doc_id,
        "doc_name": doc.doc_name,
        "doc_sha256": doc.doc_sha256,
        "docs_snapshot_id": doc.docs_snapshot_id,
        "ingested_at_utc": doc.ingested_at_utc,
        "status": doc.status,
        "metadata": metadata,
    }


@router.get("/v1/docs/{doc_id}/view")
async def view_doc(
    doc_id: str,
    context: RequestContext = Depends(get_request_context),
) -> FileResponse:
    """Serve document file for PDF viewer with tenant isolation (FR-001, FR-031).

    Returns the raw document file for rendering in the frontend PDF viewer.
    The frontend can use the page_num from citations to scroll to the right page.
    """
    doc = get_document(doc_id, tenant_id=context.tenant_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    storage_path = doc.storage_path
    if not os.path.exists(storage_path):
        raise HTTPException(
            status_code=404,
            detail="Document file not found on disk",
        )

    # Determine media type from extension
    ext = storage_path.rsplit(".", 1)[-1].lower() if "." in storage_path else ""
    media_types = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "tiff": "image/tiff",
        "tif": "image/tiff",
    }
    media_type = media_types.get(ext, "application/octet-stream")

    return FileResponse(
        path=storage_path,
        media_type=media_type,
        filename=doc.doc_name,
    )
