"""Matters router — Case Picker + Document Library endpoints.

Provides endpoints for listing available matters (cases) and their documents.
Used by the frontend CasePicker and DocumentStrip components.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.context import TenantContext, get_tenant_context
from pydantic import BaseModel

import re

from app.db import ensure_matter_exists, get_matter_last_questions, list_documents_for_matter, list_matters_for_tenant, update_matter_display_name, user_has_matter_access
from app.rbac import has_permission

router = APIRouter()


@router.get("/v1/matters")
async def list_matters(
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[dict[str, Any]]:
    """List all matters (cases) the user can access.

    Returns matter_id, display_name, doc_count, and latest_snapshot_id
    for each matter. Admin users see all matters; others see only their
    assigned matters.
    """
    if not has_permission(ctx.user_role, "query"):
        raise HTTPException(status_code=403, detail="Permission denied.")

    matters = list_matters_for_tenant(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        user_role=ctx.user_role.value,
    )

    matter_ids = [m["matter_id"] for m in matters]
    last_questions = get_matter_last_questions(
        tenant_id=ctx.tenant_id,
        matter_ids=matter_ids,
    )

    for matter in matters:
        mid = matter["matter_id"]
        q_data = last_questions.get(mid, {"last_question_at": None, "last_question_preview": None})
        matter["last_question_at"] = q_data["last_question_at"]
        matter["last_question_preview"] = q_data["last_question_preview"]

    return matters


@router.get("/v1/matters/{matter_id}/docs")
async def list_matter_docs(
    matter_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
) -> list[dict[str, Any]]:
    """List all documents for a specific matter.

    Returns doc_id, doc_name, status, ingested_at_utc, and page_count.
    Non-admin users must have matter access via matter_assignments.
    """
    if not has_permission(ctx.user_role, "query"):
        raise HTTPException(status_code=403, detail="Permission denied.")

    # Check matter access for non-admin users
    if not user_has_matter_access(
        user_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        matter_id=matter_id,
        user_role=ctx.user_role,
    ):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: user does not have access to matter {matter_id}",
        )

    docs = list_documents_for_matter(
        tenant_id=ctx.tenant_id,
        matter_id=matter_id,
    )

    result: list[dict[str, Any]] = []
    for doc in docs:
        page_count: int | None = None
        if doc.metadata_json:
            try:
                meta = json.loads(doc.metadata_json)
                page_count = meta.get("page_count")
            except (json.JSONDecodeError, TypeError):
                pass

        result.append({
            "doc_id": doc.doc_id,
            "doc_name": doc.doc_name,
            "status": doc.status,
            "ingested_at_utc": doc.ingested_at_utc,
            "page_count": page_count,
        })

    return result


_MATTER_ID_RE = re.compile(r"^[a-zA-Z0-9][-_a-zA-Z0-9]{0,63}$")


@router.post("/v1/matters", status_code=201)
async def create_matter(
    body: "CreateMatterRequest",
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, str]:
    """Create a matter with a user-provided display name.

    Idempotent — if the matter already exists, this is a no-op.
    Called by the frontend when a user creates a new case via CasePicker.
    """
    if not has_permission(ctx.user_role, "query"):
        raise HTTPException(status_code=403, detail="Permission denied.")

    if not _MATTER_ID_RE.match(body.matter_id):
        raise HTTPException(
            status_code=400,
            detail="matter_id must be alphanumeric with hyphens/underscores (max 64 chars).",
        )

    display_name = body.display_name.strip()
    if not display_name or len(display_name) > 100:
        raise HTTPException(status_code=400, detail="Display name must be 1-100 characters.")

    ensure_matter_exists(body.matter_id, ctx.tenant_id, display_name)

    return {"matter_id": body.matter_id, "display_name": display_name}


class CreateMatterRequest(BaseModel):
    matter_id: str
    display_name: str


class RenameMatterRequest(BaseModel):
    display_name: str


@router.put("/v1/matters/{matter_id}/name")
async def rename_matter(
    matter_id: str,
    body: RenameMatterRequest,
    ctx: TenantContext = Depends(get_tenant_context),
) -> dict[str, str]:
    """Rename a matter's display name."""
    if not has_permission(ctx.user_role, "query"):
        raise HTTPException(status_code=403, detail="Permission denied.")

    if not user_has_matter_access(
        user_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        matter_id=matter_id,
        user_role=ctx.user_role,
    ):
        raise HTTPException(status_code=403, detail="Access denied.")

    display_name = body.display_name.strip()
    if not display_name or len(display_name) > 100:
        raise HTTPException(status_code=400, detail="Display name must be 1-100 characters.")

    updated = update_matter_display_name(matter_id, ctx.tenant_id, display_name)
    if not updated:
        raise HTTPException(status_code=404, detail="Matter not found.")

    return {"matter_id": matter_id, "display_name": display_name}
