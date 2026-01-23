# tests/test_matter_permissions.py
"""Tests for matter-level permissions (FR-004).

FR-004: Matter-level permissions: users granted/removed per matter.
User can only access matters they're assigned to.
"""

import sys
from pathlib import Path

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class TestMatterAssignmentModel:
    """Tests for MatterAssignment database model."""

    def test_matter_assignment_model_exists(self) -> None:
        """MatterAssignment model exists with expected columns."""
        from app.db import MatterAssignment

        # Check model has expected attributes
        assert hasattr(MatterAssignment, "assignment_id")
        assert hasattr(MatterAssignment, "user_id")
        assert hasattr(MatterAssignment, "tenant_id")
        assert hasattr(MatterAssignment, "matter_id")
        assert hasattr(MatterAssignment, "granted_by")
        assert hasattr(MatterAssignment, "granted_at_utc")

    def test_matter_assignment_tablename(self) -> None:
        """MatterAssignment model has correct table name."""
        from app.db import MatterAssignment

        assert MatterAssignment.__tablename__ == "matter_assignments"


class TestUserMatterAccess:
    """Tests for user_has_matter_access function."""

    def test_user_has_matter_access_function_exists(self) -> None:
        """user_has_matter_access function exists."""
        from app.db import user_has_matter_access

        assert callable(user_has_matter_access)

    def test_user_has_matter_access_signature(self) -> None:
        """user_has_matter_access has correct signature."""
        import inspect

        from app.db import user_has_matter_access

        sig = inspect.signature(user_has_matter_access)
        params = list(sig.parameters.keys())
        assert "user_id" in params
        assert "tenant_id" in params
        assert "matter_id" in params
        assert "user_role" in params


class TestAdminBypassesMatterPermissions:
    """Tests that admin role bypasses matter-level permission checks."""

    def test_admin_can_access_any_matter(self) -> None:
        """Admin role bypasses matter permission check."""
        from app.db import user_has_matter_access
        from app.rbac import Role

        # Admin should have access even without explicit assignment
        has_access = user_has_matter_access(
            user_id="admin-user",
            tenant_id="tenant-1",
            matter_id="any-matter",
            user_role=Role.ADMIN,
        )
        assert has_access is True


class TestRequestContextMatterValidation:
    """Tests that RequestContext validates matter access."""

    def test_context_rejects_user_without_matter_access(self) -> None:
        """get_request_context raises 403 if user lacks matter access."""
        from unittest.mock import patch

        from fastapi import HTTPException

        from app.context import get_request_context

        # Mock user_has_matter_access to return False
        with patch("app.context.user_has_matter_access") as mock_access:
            mock_access.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                get_request_context(
                    x_tenant_id="tenant-1",
                    x_matter_id="matter-1",
                    x_user_id="user-no-access",
                    x_user_role="attorney",
                )

            assert exc_info.value.status_code == 403
            assert "matter" in str(exc_info.value.detail).lower()

    def test_context_allows_user_with_matter_access(self) -> None:
        """get_request_context succeeds if user has matter access."""
        from unittest.mock import patch

        from app.context import get_request_context
        from app.rbac import Role

        # Mock user_has_matter_access to return True
        with patch("app.context.user_has_matter_access") as mock_access:
            mock_access.return_value = True

            context = get_request_context(
                x_tenant_id="tenant-1",
                x_matter_id="matter-1",
                x_user_id="user-123",
                x_user_role="attorney",
            )

            assert context.tenant_id == "tenant-1"
            assert context.matter_id == "matter-1"
            assert context.user_id == "user-123"
            assert context.user_role == Role.ATTORNEY


class TestMatterAssignmentCRUD:
    """Tests for matter assignment CRUD operations."""

    def test_grant_matter_access_function_exists(self) -> None:
        """grant_matter_access function exists."""
        from app.db import grant_matter_access

        assert callable(grant_matter_access)

    def test_revoke_matter_access_function_exists(self) -> None:
        """revoke_matter_access function exists."""
        from app.db import revoke_matter_access

        assert callable(revoke_matter_access)

    def test_get_user_matters_function_exists(self) -> None:
        """get_user_matters function exists."""
        from app.db import get_user_matters

        assert callable(get_user_matters)


class TestEndpointMatterEnforcement:
    """Tests that endpoints enforce matter-level permissions."""

    def test_ask_endpoint_rejects_user_without_matter_access(self) -> None:
        """Ask endpoint returns 403 for user without matter access."""
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)

        # Mock user_has_matter_access to return False
        with patch("app.context.user_has_matter_access") as mock_access:
            mock_access.return_value = False

            response = client.post(
                "/v1/ask",
                headers={
                    "X-Tenant-Id": "tenant-1",
                    "X-Matter-Id": "matter-no-access",
                    "X-User-Id": "user-123",
                    "X-User-Role": "attorney",
                },
                json={"question": "test question"},
            )

        assert response.status_code == 403
        assert "matter" in response.json()["detail"].lower()

    def test_upload_endpoint_rejects_user_without_matter_access(self) -> None:
        """Upload endpoint returns 403 for user without matter access."""
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)

        # Mock user_has_matter_access to return False
        with patch("app.context.user_has_matter_access") as mock_access:
            mock_access.return_value = False

            response = client.post(
                "/v1/docs/upload",
                headers={
                    "X-Tenant-Id": "tenant-1",
                    "X-Matter-Id": "matter-no-access",
                    "X-User-Id": "user-123",
                    "X-User-Role": "attorney",
                },
                files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
            )

        assert response.status_code == 403
        assert "matter" in response.json()["detail"].lower()
