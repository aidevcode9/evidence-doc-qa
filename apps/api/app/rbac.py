# app/rbac.py
"""Role-based access control (FR-003).

Defines roles and permissions for the application. Every API call
checks the user's role against required permissions.

Roles:
    - admin: Full access (manage users, delete documents)
    - attorney: Query, upload, export (no delete, no user management)
    - paralegal: Query, upload, export (same as attorney)
    - viewer: Query, export only (read-only access)
"""

from __future__ import annotations

from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Coroutine, TypeVar

from fastapi import HTTPException

if TYPE_CHECKING:
    from app.context import RequestContext

T = TypeVar("T")


class Role(str, Enum):
    """User roles for RBAC (FR-003)."""

    ADMIN = "admin"
    ATTORNEY = "attorney"
    PARALEGAL = "paralegal"
    VIEWER = "viewer"


# Permission definitions: which roles can perform each action
PERMISSIONS: dict[str, list[Role]] = {
    "query": [Role.ADMIN, Role.ATTORNEY, Role.PARALEGAL, Role.VIEWER],
    "upload": [Role.ADMIN, Role.ATTORNEY, Role.PARALEGAL],
    "export": [Role.ADMIN, Role.ATTORNEY, Role.PARALEGAL, Role.VIEWER],
    "delete": [Role.ADMIN],
    "manage_users": [Role.ADMIN],
}


def has_permission(role: Role, permission: str) -> bool:
    """Check if a role has a specific permission.

    Args:
        role: The user's role
        permission: The permission to check (e.g., "upload", "delete")

    Returns:
        True if the role has the permission, False otherwise
    """
    allowed_roles = PERMISSIONS.get(permission, [])
    return role in allowed_roles


def require_permission(
    permission: str,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, T]]],
    Callable[..., Coroutine[Any, Any, T]],
]:
    """Decorator to require a specific permission for an endpoint.

    Usage:
        @require_permission("upload")
        async def upload_doc(context: RequestContext) -> dict:
            ...

    Args:
        permission: The required permission (e.g., "upload", "delete")

    Returns:
        Decorator function

    Raises:
        HTTPException 401: If context is None (unauthenticated)
        HTTPException 403: If user lacks the required permission
    """

    def decorator(
        func: Callable[..., Coroutine[Any, Any, T]],
    ) -> Callable[..., Coroutine[Any, Any, T]]:
        @wraps(func)
        async def wrapper(
            *args: Any,
            context: RequestContext | None = None,
            **kwargs: Any,
        ) -> T:
            if context is None:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required",
                )

            if not has_permission(context.user_role, permission):
                allowed = [r.value for r in PERMISSIONS.get(permission, [])]
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {permission} requires one of {allowed}",
                )

            return await func(*args, context=context, **kwargs)

        return wrapper

    return decorator
