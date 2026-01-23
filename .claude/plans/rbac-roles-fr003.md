# FR-003: RBAC with Roles

## Requirement
> FR-003: RBAC with roles: Admin, Attorney, Paralegal, Viewer | Role checked on every API call; permissions enforced

## Current State
- ✅ Tenant/matter isolation complete (FR-001/FR-002)
- ✅ RequestContext extracts X-Tenant-Id/X-Matter-Id headers
- 🔴 No user authentication or role checking
- 🔴 No User model in database

## Design Decisions

### Roles Hierarchy
```
Admin > Attorney > Paralegal > Viewer
```

| Role | Can Query | Can Upload | Can Export | Can Delete | Can Manage Users |
|------|-----------|------------|------------|------------|------------------|
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| Attorney | ✅ | ✅ | ✅ | ❌ | ❌ |
| Paralegal | ✅ | ✅ | ✅ | ❌ | ❌ |
| Viewer | ✅ | ❌ | ✅ | ❌ | ❌ |

### MVP Approach
For MVP, extract user info from headers (same pattern as tenant/matter):
- `X-User-Id`: User ID
- `X-User-Role`: Role (admin/attorney/paralegal/viewer)

Future: JWT token validation with role claims.

---

## Implementation Plan

### Phase 1: Database Models

**Add to `apps/api/app/db.py`:**

```python
class User(Base):
    """User model for RBAC (FR-003)."""
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # admin, attorney, paralegal, viewer
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at_utc: Mapped[str] = mapped_column(String, nullable=False)
```

**Alembic migration:** `0005_add_users_table.py`

### Phase 2: Role Enum and Permissions

**Create `apps/api/app/rbac.py`:**

```python
from enum import Enum
from functools import wraps
from fastapi import HTTPException

class Role(str, Enum):
    ADMIN = "admin"
    ATTORNEY = "attorney"
    PARALEGAL = "paralegal"
    VIEWER = "viewer"

# Permission definitions
PERMISSIONS = {
    "query": [Role.ADMIN, Role.ATTORNEY, Role.PARALEGAL, Role.VIEWER],
    "upload": [Role.ADMIN, Role.ATTORNEY, Role.PARALEGAL],
    "export": [Role.ADMIN, Role.ATTORNEY, Role.PARALEGAL, Role.VIEWER],
    "delete": [Role.ADMIN],
    "manage_users": [Role.ADMIN],
}

def has_permission(role: Role, permission: str) -> bool:
    """Check if role has permission."""
    allowed_roles = PERMISSIONS.get(permission, [])
    return role in allowed_roles

def require_permission(permission: str):
    """Decorator to require permission for endpoint."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, context=None, **kwargs):
            if context is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            if not has_permission(context.user_role, permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission denied: {permission} requires {PERMISSIONS[permission]}"
                )
            return await func(*args, context=context, **kwargs)
        return wrapper
    return decorator
```

### Phase 3: Extend RequestContext

**Update `apps/api/app/context.py`:**

```python
from app.rbac import Role

class RequestContext:
    """Request context with tenant, matter, and user info (FR-001, FR-002, FR-003)."""

    def __init__(
        self,
        tenant_id: str,
        matter_id: str,
        user_id: str,
        user_role: Role,
    ):
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
    """Extract request context from headers (FR-001, FR-002, FR-003)."""
    if not x_tenant_id or not x_matter_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id and X-Matter-Id headers required")
    if not x_user_id or not x_user_role:
        raise HTTPException(status_code=401, detail="X-User-Id and X-User-Role headers required")

    try:
        role = Role(x_user_role.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {x_user_role}")

    return RequestContext(
        tenant_id=x_tenant_id,
        matter_id=x_matter_id,
        user_id=x_user_id,
        user_role=role,
    )
```

### Phase 4: Apply Permissions to Routers

**Update `apps/api/app/routers/ask.py`:**
```python
# No change needed - query permission allows all roles
```

**Update `apps/api/app/routers/docs.py`:**
```python
from app.rbac import require_permission

@router.post("/v1/docs/upload")
@require_permission("upload")
async def upload_doc(...):
    ...
```

**Update `apps/api/app/routers/export.py`:**
```python
# No change needed - export permission allows all roles
```

### Phase 5: Add User to Telemetry/Audit

**Update telemetry to include user_id:**
- Add `user_id` to Telemetry model
- Log user_id in request traces

---

## File Changes Summary

| File | Action | Changes |
|------|--------|---------|
| `apps/api/app/rbac.py` | **NEW** | Role enum, permissions, require_permission decorator |
| `apps/api/app/db.py` | UPDATE | Add User model |
| `apps/api/app/context.py` | UPDATE | Add user_id, user_role to RequestContext |
| `apps/api/app/routers/docs.py` | UPDATE | Add @require_permission("upload") |
| `alembic/versions/0005_add_users_table.py` | **NEW** | Migration for users table |
| `tests/test_rbac.py` | **NEW** | RBAC tests |

---

## Tests (TDD)

**New file: `tests/test_rbac.py`**

```python
class TestRoleEnum:
    def test_role_values()
    def test_invalid_role_raises()

class TestPermissions:
    def test_admin_has_all_permissions()
    def test_attorney_cannot_delete()
    def test_viewer_cannot_upload()
    def test_viewer_can_query()
    def test_viewer_can_export()

class TestRequestContext:
    def test_context_extracts_user_headers()
    def test_missing_user_id_returns_401()
    def test_missing_role_returns_401()
    def test_invalid_role_returns_400()

class TestEndpointPermissions:
    def test_upload_requires_upload_permission()
    def test_viewer_cannot_upload()
    def test_attorney_can_upload()
    def test_all_roles_can_query()
```

---

## Verification Steps

1. `ruff check apps/` — passes
2. `mypy apps/api/app --strict` — passes
3. `pytest tests/test_rbac.py -v` — all RBAC tests pass
4. `pytest tests/ -v` — all tests pass (update existing tests for new headers)
5. Manual test:
   - Request without X-User-Id → 401 error
   - Request with role=viewer, POST /upload → 403 error
   - Request with role=attorney, POST /upload → success

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking changes to RequestContext | Existing tests fail | Update all tests with user headers |
| Header-based auth is insecure | Security risk in prod | Document as MVP; JWT in Phase 4 |
| Role hierarchy not enforced | Confusion | Clear documentation + tests |

---

## Implementation Order

1. Write failing tests (TDD RED)
2. Create `rbac.py` with Role enum and permissions
3. Update `context.py` with user fields
4. Create Alembic migration for users table
5. Update `db.py` with User model
6. Apply @require_permission to routers
7. Run tests (TDD GREEN)
8. Update existing tests with user headers
9. Run full verification suite
