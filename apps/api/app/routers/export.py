# app/routers/export.py
"""Export router for Q&A session export (FR-032)."""

from __future__ import annotations

import tempfile
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.db import get_qa_session, get_session_messages
from app.services.export_service import generate_pdf_export, generate_docx_export

router = APIRouter(tags=["export"])


@router.get("/v1/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: Literal["pdf", "docx"] = Query("pdf", description="Export format"),
) -> FileResponse:
    """Export Q&A session to PDF or DOCX.

    Args:
        session_id: The session ID to export
        format: Export format (pdf or docx)

    Returns:
        FileResponse with the exported document
    """
    session = get_qa_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = get_session_messages(session_id)
    if not messages:
        raise HTTPException(status_code=400, detail="Session has no messages")

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

    return FileResponse(
        path=temp_path,
        media_type=media_type,
        filename=filename,
    )
