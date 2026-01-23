# app/routers/export.py
"""Export router for Q&A session export (FR-032)."""

from __future__ import annotations

import os
import tempfile
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse

from app.context import RequestContext, get_request_context
from app.db import get_qa_session, get_session_messages
from app.rbac import has_permission
from app.services.export_service import generate_pdf_export, generate_docx_export

router = APIRouter(tags=["export"])

# Maximum messages to include in export to prevent OOM
MAX_EXPORT_MESSAGES = 500


def _cleanup_temp_file(path: str) -> None:
    """Remove temporary file after response is sent."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass  # Best effort cleanup


@router.get("/v1/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    context: RequestContext = Depends(get_request_context),
    format: Literal["pdf", "docx"] = Query("pdf", description="Export format"),
    x_docqa_session: str | None = Header(default=None),
) -> FileResponse:
    """Export Q&A session to PDF or DOCX with tenant isolation and RBAC (FR-001, FR-003, FR-032).

    Args:
        session_id: The session ID to export
        context: Request context with tenant_id for isolation
        format: Export format (pdf or docx)
        x_docqa_session: Session header for ownership validation

    Returns:
        FileResponse with the exported document

    Raises:
        HTTPException 403: If session header is missing, doesn't match, or permission denied
        HTTPException 404: If session not found
        HTTPException 400: If session has no messages
    """
    # RBAC check (FR-003): All roles can export
    if not has_permission(context.user_role, "export"):
        raise HTTPException(
            status_code=403,
            detail="Permission denied: export requires authentication",
        )

    # Security: Require session header to match path session_id (prevents IDOR)
    if not x_docqa_session:
        raise HTTPException(
            status_code=403,
            detail="Session header required for export. Include X-DocQA-Session header.",
        )

    if x_docqa_session != session_id:
        raise HTTPException(
            status_code=403,
            detail="Session mismatch. You can only export your own sessions.",
        )

    # Get session with tenant isolation (FR-001)
    session = get_qa_session(session_id, tenant_id=context.tenant_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get messages with tenant isolation (FR-001)
    messages = get_session_messages(session_id, tenant_id=context.tenant_id)
    if not messages:
        raise HTTPException(status_code=400, detail="Session has no messages")

    # Limit messages to prevent OOM on large sessions
    if len(messages) > MAX_EXPORT_MESSAGES:
        messages = messages[:MAX_EXPORT_MESSAGES]

    # Generate export
    if format == "pdf":
        content = generate_pdf_export(session, messages)
        media_type = "application/pdf"
        suffix = ".pdf"
    else:
        content = generate_docx_export(session, messages)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        suffix = ".docx"

    # Write to temp file
    session_short = session_id[:8] if len(session_id) > 8 else session_id
    filename = f"qa-export-{session_short}{suffix}"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        f.write(content)
        temp_path = f.name

    # Schedule temp file cleanup after response is sent
    background_tasks.add_task(_cleanup_temp_file, temp_path)

    return FileResponse(
        path=temp_path,
        media_type=media_type,
        filename=filename,
    )
