"""Audit router for FR-040 and FR-041.

Provides endpoints for:
- GET /v1/audit/events - List audit events with filters (admin only)
- GET /v1/audit/events/export - Export audit events as CSV (admin only)

All endpoints require admin role (manage_users permission).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import AUTH_MODE
from app.db import AuditEvent, count_audit_events, list_audit_events
from app.rbac import Role, has_permission

router = APIRouter(prefix="/v1/audit", tags=["audit"])


# Response schemas


class AuditEventResponse(BaseModel):
    """Audit event response."""

    event_id: str
    tenant_id: str
    matter_id: str | None
    user_id: str
    event_type: str
    event_data: dict[str, Any]
    response_id: str | None
    created_at_utc: str


class PaginatedAuditEventsResponse(BaseModel):
    """Paginated audit events response."""

    items: list[AuditEventResponse]
    total: int
    offset: int
    limit: int


def _event_to_response(event: AuditEvent) -> AuditEventResponse:
    """Convert AuditEvent model to response."""
    return AuditEventResponse(
        event_id=event.event_id,
        tenant_id=event.tenant_id,
        matter_id=event.matter_id,
        user_id=event.user_id,
        event_type=event.event_type,
        event_data=json.loads(event.event_json),
        response_id=event.response_id,
        created_at_utc=event.created_at_utc,
    )


def _require_admin_from_jwt(
    authorization: str = Header(..., alias="Authorization"),
) -> str:
    """Extract admin context from JWT token.

    Returns:
        tenant_id for the admin user
    """
    from app.security import decode_access_token

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <token>",
        )

    token = authorization[7:]  # Remove "Bearer " prefix
    claims = decode_access_token(token)

    if claims is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired access token",
        )

    tenant_id: str = str(claims.get("tenant_id", ""))
    role_str: str = str(claims.get("role", ""))

    try:
        role = Role(role_str.lower())
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid role in token")

    if not has_permission(role, "manage_users"):
        raise HTTPException(
            status_code=403, detail="Admin role required for audit access"
        )

    return tenant_id


def _require_admin_from_headers(
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_user_role: str = Header(..., alias="X-User-Role"),
) -> str:
    """Extract admin context from headers.

    Returns:
        tenant_id for the admin user
    """
    try:
        role = Role(x_user_role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {x_user_role}")

    if not has_permission(role, "manage_users"):
        raise HTTPException(
            status_code=403, detail="Admin role required for audit access"
        )

    return x_tenant_id


def _require_admin(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    """Dependency to require admin role.

    Returns:
        tenant_id for the admin user
    """
    if AUTH_MODE == "jwt":
        if not authorization:
            raise HTTPException(
                status_code=401,
                detail="Authorization header is required",
            )
        return _require_admin_from_jwt(authorization)
    else:
        if not x_tenant_id or not x_user_role:
            raise HTTPException(
                status_code=400,
                detail="X-Tenant-Id and X-User-Role headers are required",
            )
        return _require_admin_from_headers(x_tenant_id, x_user_role)


@router.get("/events", response_model=PaginatedAuditEventsResponse)
def list_events_endpoint(
    matter_id: str | None = Query(None, description="Filter by matter ID"),
    event_type: str | None = Query(None, description="Filter by event type"),
    user_id: str | None = Query(None, description="Filter by user ID"),
    start_date: str | None = Query(None, description="Start date (ISO format)"),
    end_date: str | None = Query(None, description="End date (ISO format)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tenant_id: str = Depends(_require_admin),
) -> PaginatedAuditEventsResponse:
    """List audit events with filters.

    Requires admin role. Returns paginated audit events filtered by
    matter, event type, user, and/or date range.

    Args:
        matter_id: Filter by matter ID
        event_type: Filter by event type (query, upload, export, etc.)
        user_id: Filter by user ID
        start_date: Filter by created_at >= start_date
        end_date: Filter by created_at <= end_date
        offset: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        Paginated list of audit events
    """
    events = list_audit_events(
        tenant_id=tenant_id,
        matter_id=matter_id,
        event_type=event_type,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        offset=offset,
        limit=limit,
    )

    total = count_audit_events(
        tenant_id=tenant_id,
        matter_id=matter_id,
        event_type=event_type,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    return PaginatedAuditEventsResponse(
        items=[_event_to_response(e) for e in events],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/events/export")
def export_events_endpoint(
    matter_id: str | None = Query(None, description="Filter by matter ID"),
    event_type: str | None = Query(None, description="Filter by event type"),
    user_id: str | None = Query(None, description="Filter by user ID"),
    start_date: str | None = Query(None, description="Start date (ISO format)"),
    end_date: str | None = Query(None, description="End date (ISO format)"),
    tenant_id: str = Depends(_require_admin),
) -> StreamingResponse:
    """Export audit events as CSV (FR-041).

    Requires admin role. Exports all matching audit events as a
    downloadable CSV file.

    Args:
        matter_id: Filter by matter ID
        event_type: Filter by event type
        user_id: Filter by user ID
        start_date: Filter by created_at >= start_date
        end_date: Filter by created_at <= end_date

    Returns:
        CSV file download
    """
    # Get all events (no pagination for export)
    events = list_audit_events(
        tenant_id=tenant_id,
        matter_id=matter_id,
        event_type=event_type,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        offset=0,
        limit=100000,  # High limit for export
    )

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "event_id",
        "tenant_id",
        "matter_id",
        "user_id",
        "event_type",
        "event_data",
        "response_id",
        "created_at_utc",
    ])

    # Data rows
    for event in events:
        writer.writerow([
            event.event_id,
            event.tenant_id,
            event.matter_id or "",
            event.user_id,
            event.event_type,
            event.event_json,
            event.response_id or "",
            event.created_at_utc,
        ])

    output.seek(0)

    # Generate filename with date range
    filename = "audit_events"
    if start_date:
        filename += f"_from_{start_date[:10]}"
    if end_date:
        filename += f"_to_{end_date[:10]}"
    filename += ".csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
