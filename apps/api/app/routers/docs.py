import os
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.context import RequestContext, get_request_context
from app.db import get_document
from app.services.document_service import process_document_upload

router = APIRouter()


@router.post("/v1/docs/upload")
async def upload_doc(
    file: UploadFile = File(...),
    context: RequestContext = Depends(get_request_context),
) -> dict[str, Any]:
    """Upload a document with tenant/matter isolation (FR-001, FR-002)."""
    result = await process_document_upload(
        file,
        tenant_id=context.tenant_id,
        matter_id=context.matter_id,
    )
    return result


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

    return {
        "doc_id": doc.doc_id,
        "doc_name": doc.doc_name,
        "doc_sha256": doc.doc_sha256,
        "docs_snapshot_id": doc.docs_snapshot_id,
        "ingested_at_utc": doc.ingested_at_utc,
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
