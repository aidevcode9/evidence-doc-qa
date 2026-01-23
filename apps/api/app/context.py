"""Request context for tenant, matter, and user isolation (FR-001, FR-002, FR-003, FR-004).

This module provides FastAPI dependencies to extract tenant_id, matter_id,
user_id, and user_role from request headers. These are required for
multi-tenant data isolation, RBAC, and matter-level permissions.

MVP Implementation:
- Extracts from X-Tenant-Id, X-Matter-Id, X-User-Id, X-User-Role headers
- Validates user has access to the requested matter (FR-004)
- Future: Extract from JWT token after auth service is implemented (Phase 4)
"""

from __future__ import annotations

import re

from fastapi import Header, HTTPException

from app.db import user_has_matter_access
from app.rbac import Role

# UUID pattern: alphanumeric with optional hyphens (standard UUID format)
# Prevents filter injection attacks in Azure Search queries
_UUID_PATTERN = re.compile(r"^[a-zA-Z0-9][-a-zA-Z0-9]{0,63}$")


def _is_valid_identifier(value: str) -> bool:
    """Validate that a value is a safe identifier (alphanumeric with hyphens).

    This prevents filter injection attacks when IDs are interpolated into
    Azure Search filter strings.

    Args:
        value: The identifier to validate

    Returns:
        True if the value is safe to use in filters, False otherwise
    """
    if not value or len(value) > 64:
        return False
    return _UUID_PATTERN.match(value) is not None


class RequestContext:
    """Tenant, matter, and user context extracted from request headers.

    Attributes:
        tenant_id: The tenant identifier for data isolation (FR-001)
        matter_id: The matter identifier for data isolation (FR-002)
        user_id: The user identifier for RBAC (FR-003)
        user_role: The user's role for permission checking (FR-003)
    """

    def __init__(
        self,
        tenant_id: str,
        matter_id: str,
        user_id: str,
        user_role: Role,
    ) -> None:
        self.tenant_id = tenant_id
        self.matter_id = matter_id
        self.user_id = user_id
        self.user_role = user_role


def get_request_context(
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_matter_id: str = Header(..., alias="X-Matter-Id"),
    x_user_id: str = Header(..., alias="X-User-Id"),
    x_user_role: str = Header(..., alias="X-User-Role"),
) -> RequestContext:
    """FastAPI dependency to extract tenant/matter/user context from headers.

    Args:
        x_tenant_id: Tenant ID from X-Tenant-Id header (required)
        x_matter_id: Matter ID from X-Matter-Id header (required)
        x_user_id: User ID from X-User-Id header (required)
        x_user_role: User role from X-User-Role header (required)

    Returns:
        RequestContext with tenant_id, matter_id, user_id, and user_role

    Raises:
        HTTPException: 400 if tenant/matter headers missing or invalid role
        HTTPException: 401 if user headers missing
    """
    # Validate tenant/matter (FR-001, FR-002)
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

    # Validate user (FR-003)
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=401,
            detail="X-User-Id header is required for authentication",
        )
    if not x_user_role or not x_user_role.strip():
        raise HTTPException(
            status_code=401,
            detail="X-User-Role header is required for authentication",
        )

    # Parse role (case insensitive)
    try:
        role = Role(x_user_role.strip().lower())
    except ValueError:
        valid_roles = [r.value for r in Role]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {x_user_role}. Must be one of {valid_roles}",
        )

    tenant_id = x_tenant_id.strip()
    matter_id = x_matter_id.strip()
    user_id = x_user_id.strip()

    # Validate identifier format to prevent filter injection (SECURITY)
    if not _is_valid_identifier(tenant_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid tenant_id format: must be alphanumeric with optional hyphens (max 64 chars)",
        )
    if not _is_valid_identifier(matter_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid matter_id format: must be alphanumeric with optional hyphens (max 64 chars)",
        )
    if not _is_valid_identifier(user_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid user_id format: must be alphanumeric with optional hyphens (max 64 chars)",
        )

    # Validate matter access (FR-004)
    if not user_has_matter_access(
        user_id=user_id,
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_role=role,
    ):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: user does not have access to matter {matter_id}",
        )

    return RequestContext(
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=user_id,
        user_role=role,
    )
