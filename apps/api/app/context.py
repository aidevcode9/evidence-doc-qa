"""Request context for tenant, matter, and user isolation (FR-001, FR-002, FR-003, FR-004).

This module provides FastAPI dependencies to extract tenant_id, matter_id,
user_id, and user_role from request headers or JWT tokens. These are required for
multi-tenant data isolation, RBAC, and matter-level permissions.

Implementation (FR-050):
- AUTH_MODE='jwt': Extracts tenant_id, user_id, role from JWT Bearer token
- AUTH_MODE='headers': Extracts from X-Tenant-Id, X-Matter-Id, X-User-Id, X-User-Role headers
- Both modes validate user has access to the requested matter (FR-004)
"""

from __future__ import annotations

import re

from fastapi import Header, HTTPException

from app.config import AUTH_MODE
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
    """Tenant, matter, and user context extracted from request headers or JWT.

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


def _get_context_from_jwt(
    authorization: str | None,
    matter_id: str,
) -> RequestContext:
    """Extract context from JWT Bearer token (FR-050).

    Args:
        authorization: Authorization header value (e.g., "Bearer <token>")
        matter_id: Matter ID from X-Matter-Id header (required even in JWT mode)

    Returns:
        RequestContext with user info from JWT and matter_id from header

    Raises:
        HTTPException: 401 if token missing/invalid/expired
        HTTPException: 403 if user doesn't have matter access
    """
    from app.security import decode_access_token

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is required",
        )

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

    # Extract from JWT claims
    user_id = claims.get("sub", "")
    tenant_id = claims.get("tenant_id", "")
    role_str = claims.get("role", "")

    # Parse role
    try:
        role = Role(role_str.lower())
    except ValueError:
        valid_roles = [r.value for r in Role]
        raise HTTPException(
            status_code=401,
            detail=f"Invalid role in token: {role_str}. Must be one of {valid_roles}",
        )

    # Validate identifiers
    if not _is_valid_identifier(tenant_id):
        raise HTTPException(
            status_code=401,
            detail="Invalid tenant_id in token",
        )
    if not _is_valid_identifier(matter_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid matter_id format: must be alphanumeric with optional hyphens (max 64 chars)",
        )
    if not _is_valid_identifier(user_id):
        raise HTTPException(
            status_code=401,
            detail="Invalid user_id in token",
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


def _get_context_from_headers(
    x_tenant_id: str | None,
    x_matter_id: str,
    x_user_id: str | None,
    x_user_role: str | None,
) -> RequestContext:
    """Extract context from X-* headers (backward compatible mode).

    Args:
        x_tenant_id: Tenant ID from X-Tenant-Id header
        x_matter_id: Matter ID from X-Matter-Id header
        x_user_id: User ID from X-User-Id header
        x_user_role: User role from X-User-Role header

    Returns:
        RequestContext with all fields from headers

    Raises:
        HTTPException: 400 if tenant/matter headers missing or invalid role
        HTTPException: 401 if user headers missing
        HTTPException: 403 if user doesn't have matter access
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


def get_request_context(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_matter_id: str = Header(..., alias="X-Matter-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> RequestContext:
    """FastAPI dependency to extract tenant/matter/user context.

    Supports two modes controlled by AUTH_MODE config:
    - 'jwt': Extract from JWT Bearer token in Authorization header
    - 'headers': Extract from X-Tenant-Id, X-User-Id, X-User-Role headers

    In both modes, X-Matter-Id header is required to specify the matter context.

    Args:
        x_tenant_id: Tenant ID from X-Tenant-Id header (headers mode only)
        x_matter_id: Matter ID from X-Matter-Id header (required in both modes)
        x_user_id: User ID from X-User-Id header (headers mode only)
        x_user_role: User role from X-User-Role header (headers mode only)
        authorization: Authorization header with Bearer token (jwt mode only)

    Returns:
        RequestContext with tenant_id, matter_id, user_id, and user_role

    Raises:
        HTTPException: 400 if required headers missing or invalid format
        HTTPException: 401 if authentication fails
        HTTPException: 403 if user doesn't have matter access
    """
    if AUTH_MODE == "jwt":
        return _get_context_from_jwt(authorization, x_matter_id)
    else:
        # Default to headers mode for backward compatibility
        return _get_context_from_headers(
            x_tenant_id, x_matter_id, x_user_id, x_user_role
        )
