"""Request context for tenant and matter isolation (FR-001, FR-002).

This module provides FastAPI dependencies to extract tenant_id and matter_id
from request headers. These are required for multi-tenant data isolation.

MVP Implementation:
- Extracts from X-Tenant-Id and X-Matter-Id headers
- Future: Extract from JWT token after auth service is implemented (Phase 4)
"""

from __future__ import annotations

from fastapi import Header, HTTPException


class RequestContext:
    """Tenant and matter context extracted from request headers.

    Attributes:
        tenant_id: The tenant identifier for data isolation (FR-001)
        matter_id: The matter identifier for data isolation (FR-002)
    """

    def __init__(self, tenant_id: str, matter_id: str) -> None:
        self.tenant_id = tenant_id
        self.matter_id = matter_id


def get_request_context(
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_matter_id: str = Header(..., alias="X-Matter-Id"),
) -> RequestContext:
    """FastAPI dependency to extract tenant/matter context from headers.

    Args:
        x_tenant_id: Tenant ID from X-Tenant-Id header (required)
        x_matter_id: Matter ID from X-Matter-Id header (required)

    Returns:
        RequestContext with tenant_id and matter_id

    Raises:
        HTTPException: 400 if headers are missing or empty
    """
    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-Id header is required",
        )
    if not x_matter_id or not x_matter_id.strip():
        raise HTTPException(
            status_code=400,
            detail="X-Matter-Id header is required",
        )
    return RequestContext(
        tenant_id=x_tenant_id.strip(),
        matter_id=x_matter_id.strip(),
    )
