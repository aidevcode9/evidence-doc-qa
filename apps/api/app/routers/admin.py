"""Admin dashboard router for FR-052.

Provides endpoints for:
- GET /v1/admin/users - List users with pagination
- POST /v1/admin/users - Create new user
- PATCH /v1/admin/users/{user_id} - Update user (role, is_active)
- DELETE /v1/admin/users/{user_id} - Deactivate user (soft delete)
- GET /v1/admin/users/{user_id}/matters - List user's matter assignments
- POST /v1/admin/users/{user_id}/matters/{matter_id} - Grant matter access
- DELETE /v1/admin/users/{user_id}/matters/{matter_id} - Revoke matter access

All endpoints require admin role (manage_users permission).

Security:
- Uses JWT claims for auth when AUTH_MODE=jwt (not trusting headers)
- Falls back to headers mode for backward compatibility
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, EmailStr

from app.config import AUTH_MODE
from app.db import (
    create_user,
    deactivate_user,
    get_user_by_email,
    get_user_by_id,
    get_user_matters,
    grant_matter_access,
    list_users,
    revoke_matter_access,
    update_user,
)
from app.rbac import Role, has_permission

router = APIRouter(prefix="/v1/admin", tags=["admin"])


# Request/Response schemas


class CreateUserRequest(BaseModel):
    """Request to create a new user."""

    email: EmailStr
    display_name: str | None = None
    role: str = "viewer"


class UpdateUserRequest(BaseModel):
    """Request to update a user."""

    role: str | None = None
    display_name: str | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    """User information response."""

    user_id: str
    email: str
    role: str
    display_name: str | None
    tenant_id: str
    is_active: bool
    auth_provider: str


class PaginatedUsersResponse(BaseModel):
    """Paginated list of users."""

    items: list[UserResponse]
    total: int
    offset: int
    limit: int


class UserMattersResponse(BaseModel):
    """List of matter IDs a user can access."""

    matters: list[str]


def _user_to_response(user: Any) -> UserResponse:
    """Convert User model to response."""
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        role=user.role,
        display_name=user.display_name,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
        auth_provider=user.auth_provider,
    )


def _require_admin_from_jwt(
    authorization: str = Header(..., alias="Authorization"),
) -> tuple[str, str]:
    """Extract admin context from JWT token.

    Security: Validates role from JWT claims, not trusting headers.

    Returns:
        Tuple of (tenant_id, user_id) for the admin user
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

    # Extract from JWT claims
    user_id = claims.get("sub", "")
    tenant_id = claims.get("tenant_id", "")
    role_str = claims.get("role", "")

    # Parse and validate role from JWT (not from headers!)
    try:
        role = Role(role_str.lower())
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid role in token")

    if not has_permission(role, "manage_users"):
        raise HTTPException(
            status_code=403, detail="Admin role required for this operation"
        )

    return tenant_id, user_id


def _require_admin_from_headers(
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    x_user_id: str = Header(..., alias="X-User-Id"),
    x_user_role: str = Header(..., alias="X-User-Role"),
) -> tuple[str, str]:
    """Extract admin context from headers (backward compatible mode).

    Returns:
        Tuple of (tenant_id, user_id) for the admin user
    """
    try:
        role = Role(x_user_role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {x_user_role}")

    if not has_permission(role, "manage_users"):
        raise HTTPException(
            status_code=403, detail="Admin role required for this operation"
        )

    return x_tenant_id, x_user_id


def _require_admin(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> tuple[str, str]:
    """Dependency to require admin role.

    Uses JWT claims when AUTH_MODE=jwt, headers otherwise.

    Returns:
        Tuple of (tenant_id, user_id) for the admin user
    """
    if AUTH_MODE == "jwt":
        if not authorization:
            raise HTTPException(
                status_code=401,
                detail="Authorization header is required",
            )
        return _require_admin_from_jwt(authorization)
    else:
        # Headers mode
        if not x_tenant_id or not x_user_id or not x_user_role:
            raise HTTPException(
                status_code=400,
                detail="X-Tenant-Id, X-User-Id, and X-User-Role headers are required",
            )
        return _require_admin_from_headers(x_tenant_id, x_user_id, x_user_role)


# User list endpoint


@router.get("/users", response_model=PaginatedUsersResponse)
def list_users_endpoint(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: str | None = Query(None),
    admin: tuple[str, str] = Depends(_require_admin),
) -> PaginatedUsersResponse:
    """List users with pagination.

    Args:
        offset: Number of records to skip
        limit: Maximum number of records to return (max 100)
        search: Optional search term for email/display_name
        admin: Admin context (tenant_id, user_id)

    Returns:
        Paginated list of users
    """
    tenant_id, _ = admin
    users, total = list_users(
        tenant_id=tenant_id,
        offset=offset,
        limit=limit,
        search=search,
    )

    return PaginatedUsersResponse(
        items=[_user_to_response(u) for u in users],
        total=total,
        offset=offset,
        limit=limit,
    )


# User CRUD endpoints


@router.post("/users", response_model=UserResponse, status_code=201)
def create_user_endpoint(
    request: CreateUserRequest,
    admin: tuple[str, str] = Depends(_require_admin),
) -> UserResponse:
    """Create a new user.

    Args:
        request: User creation request
        admin: Admin context (tenant_id, user_id)

    Returns:
        Created user info
    """
    tenant_id, _ = admin

    # Check if email is already taken
    existing = get_user_by_email(request.email, tenant_id)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Validate role
    try:
        Role(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")

    # Create user
    user = create_user(
        user_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        email=request.email,
        role=request.role,
        display_name=request.display_name,
        auth_provider="local",
        password_hash=None,  # Admin-created users need to set password later
    )

    return _user_to_response(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user_endpoint(
    user_id: str,
    request: UpdateUserRequest,
    admin: tuple[str, str] = Depends(_require_admin),
) -> UserResponse:
    """Update a user.

    Args:
        user_id: User ID to update
        request: Update request
        admin: Admin context (tenant_id, user_id)

    Returns:
        Updated user info
    """
    tenant_id, _ = admin

    # Check user exists
    user = get_user_by_id(user_id, tenant_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate role if provided
    if request.role:
        try:
            Role(request.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")

    # Update user
    updated = update_user(
        user_id=user_id,
        tenant_id=tenant_id,
        role=request.role,
        display_name=request.display_name,
        is_active=request.is_active,
    )

    if not updated:
        raise HTTPException(status_code=404, detail="User not found")

    return _user_to_response(updated)


@router.delete("/users/{user_id}", status_code=204, response_model=None)
def delete_user_endpoint(
    user_id: str,
    admin: tuple[str, str] = Depends(_require_admin),
) -> None:
    """Deactivate a user (soft delete).

    Args:
        user_id: User ID to deactivate
        admin: Admin context (tenant_id, user_id)
    """
    tenant_id, admin_user_id = admin

    # Prevent self-deactivation
    if user_id == admin_user_id:
        raise HTTPException(
            status_code=400, detail="Cannot deactivate your own account"
        )

    # Check user exists
    user = get_user_by_id(user_id, tenant_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Deactivate
    deactivate_user(user_id, tenant_id)


# Matter access endpoints


@router.get("/users/{user_id}/matters", response_model=UserMattersResponse)
def list_user_matters_endpoint(
    user_id: str,
    admin: tuple[str, str] = Depends(_require_admin),
) -> UserMattersResponse:
    """List matters a user has access to.

    Args:
        user_id: User ID
        admin: Admin context (tenant_id, user_id)

    Returns:
        List of matter IDs
    """
    tenant_id, _ = admin

    # Check user exists
    user = get_user_by_id(user_id, tenant_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    matters = get_user_matters(user_id, tenant_id)
    return UserMattersResponse(matters=matters)


@router.post("/users/{user_id}/matters/{matter_id}", status_code=201)
def grant_matter_endpoint(
    user_id: str,
    matter_id: str,
    admin: tuple[str, str] = Depends(_require_admin),
) -> dict[str, str]:
    """Grant a user access to a matter.

    Args:
        user_id: User ID to grant access to
        matter_id: Matter ID to grant access to
        admin: Admin context (tenant_id, user_id)

    Returns:
        Confirmation message
    """
    tenant_id, admin_user_id = admin

    # Check user exists
    user = get_user_by_id(user_id, tenant_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Grant access
    grant_matter_access(
        user_id=user_id,
        tenant_id=tenant_id,
        matter_id=matter_id,
        granted_by=admin_user_id,
    )

    return {"message": f"Granted access to matter {matter_id}"}


@router.delete("/users/{user_id}/matters/{matter_id}", status_code=204, response_model=None)
def revoke_matter_endpoint(
    user_id: str,
    matter_id: str,
    admin: tuple[str, str] = Depends(_require_admin),
) -> None:
    """Revoke a user's access to a matter.

    Args:
        user_id: User ID to revoke access from
        matter_id: Matter ID to revoke access to
        admin: Admin context (tenant_id, user_id)
    """
    tenant_id, _ = admin

    # Check user exists
    user = get_user_by_id(user_id, tenant_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Revoke access
    revoke_matter_access(user_id, tenant_id, matter_id)
