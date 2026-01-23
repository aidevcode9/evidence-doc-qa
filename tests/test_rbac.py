# tests/test_rbac.py
"""Tests for RBAC with roles (FR-003)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class TestRoleEnum:
    """Tests for Role enum."""

    def test_role_values_exist(self) -> None:
        """Role enum has expected values."""
        from app.rbac import Role

        assert Role.ADMIN.value == "admin"
        assert Role.ATTORNEY.value == "attorney"
        assert Role.PARALEGAL.value == "paralegal"
        assert Role.VIEWER.value == "viewer"

    def test_role_from_string(self) -> None:
        """Role can be created from string."""
        from app.rbac import Role

        assert Role("admin") == Role.ADMIN
        assert Role("attorney") == Role.ATTORNEY
        assert Role("paralegal") == Role.PARALEGAL
        assert Role("viewer") == Role.VIEWER

    def test_invalid_role_raises(self) -> None:
        """Invalid role string raises ValueError."""
        from app.rbac import Role

        with pytest.raises(ValueError):
            Role("invalid_role")


class TestPermissions:
    """Tests for permission checking."""

    def test_admin_has_all_permissions(self) -> None:
        """Admin role has all permissions."""
        from app.rbac import Role, has_permission

        assert has_permission(Role.ADMIN, "query")
        assert has_permission(Role.ADMIN, "upload")
        assert has_permission(Role.ADMIN, "export")
        assert has_permission(Role.ADMIN, "delete")
        assert has_permission(Role.ADMIN, "manage_users")

    def test_attorney_permissions(self) -> None:
        """Attorney can query, upload, export but not delete or manage users."""
        from app.rbac import Role, has_permission

        assert has_permission(Role.ATTORNEY, "query")
        assert has_permission(Role.ATTORNEY, "upload")
        assert has_permission(Role.ATTORNEY, "export")
        assert not has_permission(Role.ATTORNEY, "delete")
        assert not has_permission(Role.ATTORNEY, "manage_users")

    def test_paralegal_permissions(self) -> None:
        """Paralegal can query, upload, export but not delete or manage users."""
        from app.rbac import Role, has_permission

        assert has_permission(Role.PARALEGAL, "query")
        assert has_permission(Role.PARALEGAL, "upload")
        assert has_permission(Role.PARALEGAL, "export")
        assert not has_permission(Role.PARALEGAL, "delete")
        assert not has_permission(Role.PARALEGAL, "manage_users")

    def test_viewer_cannot_upload(self) -> None:
        """Viewer cannot upload documents."""
        from app.rbac import Role, has_permission

        assert not has_permission(Role.VIEWER, "upload")

    def test_viewer_cannot_delete(self) -> None:
        """Viewer cannot delete documents."""
        from app.rbac import Role, has_permission

        assert not has_permission(Role.VIEWER, "delete")

    def test_viewer_can_query(self) -> None:
        """Viewer can query documents."""
        from app.rbac import Role, has_permission

        assert has_permission(Role.VIEWER, "query")

    def test_viewer_can_export(self) -> None:
        """Viewer can export sessions."""
        from app.rbac import Role, has_permission

        assert has_permission(Role.VIEWER, "export")

    def test_unknown_permission_returns_false(self) -> None:
        """Unknown permission returns False for all roles."""
        from app.rbac import Role, has_permission

        assert not has_permission(Role.ADMIN, "unknown_permission")
        assert not has_permission(Role.VIEWER, "unknown_permission")


class TestRequestContextWithUser:
    """Tests for RequestContext with user fields."""

    def test_context_has_user_id(self) -> None:
        """RequestContext has user_id attribute."""
        from app.context import RequestContext
        from app.rbac import Role

        context = RequestContext(
            tenant_id="tenant-1",
            matter_id="matter-1",
            user_id="user-123",
            user_role=Role.ATTORNEY,
        )
        assert context.user_id == "user-123"

    def test_context_has_user_role(self) -> None:
        """RequestContext has user_role attribute."""
        from app.context import RequestContext
        from app.rbac import Role

        context = RequestContext(
            tenant_id="tenant-1",
            matter_id="matter-1",
            user_id="user-123",
            user_role=Role.VIEWER,
        )
        assert context.user_role == Role.VIEWER


class TestGetRequestContextWithUser:
    """Tests for get_request_context with user headers."""

    def test_extracts_user_headers(self) -> None:
        """get_request_context extracts X-User-Id and X-User-Role."""
        from app.context import get_request_context
        from app.rbac import Role

        context = get_request_context(
            x_tenant_id="tenant-1",
            x_matter_id="matter-1",
            x_user_id="user-123",
            x_user_role="attorney",
        )

        assert context.user_id == "user-123"
        assert context.user_role == Role.ATTORNEY

    def test_missing_user_id_returns_401(self) -> None:
        """Missing X-User-Id header returns 401."""
        from fastapi import HTTPException

        from app.context import get_request_context

        with pytest.raises(HTTPException) as exc_info:
            get_request_context(
                x_tenant_id="tenant-1",
                x_matter_id="matter-1",
                x_user_id="",  # Empty
                x_user_role="attorney",
            )
        assert exc_info.value.status_code == 401

    def test_missing_role_returns_401(self) -> None:
        """Missing X-User-Role header returns 401."""
        from fastapi import HTTPException

        from app.context import get_request_context

        with pytest.raises(HTTPException) as exc_info:
            get_request_context(
                x_tenant_id="tenant-1",
                x_matter_id="matter-1",
                x_user_id="user-123",
                x_user_role="",  # Empty
            )
        assert exc_info.value.status_code == 401

    def test_invalid_role_returns_400(self) -> None:
        """Invalid X-User-Role returns 400."""
        from fastapi import HTTPException

        from app.context import get_request_context

        with pytest.raises(HTTPException) as exc_info:
            get_request_context(
                x_tenant_id="tenant-1",
                x_matter_id="matter-1",
                x_user_id="user-123",
                x_user_role="invalid_role",
            )
        assert exc_info.value.status_code == 400
        assert "Invalid role" in str(exc_info.value.detail)

    def test_role_case_insensitive(self) -> None:
        """Role parsing is case insensitive."""
        from app.context import get_request_context
        from app.rbac import Role

        context = get_request_context(
            x_tenant_id="tenant-1",
            x_matter_id="matter-1",
            x_user_id="user-123",
            x_user_role="ATTORNEY",  # Uppercase
        )
        assert context.user_role == Role.ATTORNEY


class TestRequirePermissionDecorator:
    """Tests for @require_permission decorator."""

    def test_decorator_allows_permitted_role(self) -> None:
        """Decorator allows role with permission."""
        from app.context import RequestContext
        from app.rbac import Role, require_permission

        @require_permission("upload")
        async def upload_doc(context: RequestContext) -> str:
            return "uploaded"

        context = RequestContext(
            tenant_id="t1",
            matter_id="m1",
            user_id="u1",
            user_role=Role.ATTORNEY,
        )

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(upload_doc(context=context))
        assert result == "uploaded"

    def test_decorator_blocks_unpermitted_role(self) -> None:
        """Decorator blocks role without permission."""
        from fastapi import HTTPException

        from app.context import RequestContext
        from app.rbac import Role, require_permission

        @require_permission("upload")
        async def upload_doc(context: RequestContext) -> str:
            return "uploaded"

        context = RequestContext(
            tenant_id="t1",
            matter_id="m1",
            user_id="u1",
            user_role=Role.VIEWER,  # Viewer cannot upload
        )

        import asyncio

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(upload_doc(context=context))
        assert exc_info.value.status_code == 403
        assert "Permission denied" in str(exc_info.value.detail)

    def test_decorator_requires_context(self) -> None:
        """Decorator raises 401 if context is None."""
        from fastapi import HTTPException

        from app.rbac import require_permission

        @require_permission("upload")
        async def upload_doc(context: None = None) -> str:
            return "uploaded"

        import asyncio

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(upload_doc(context=None))
        assert exc_info.value.status_code == 401


class TestUserModel:
    """Tests for User database model."""

    def test_user_model_exists(self) -> None:
        """User model exists with expected columns."""
        from app.db import User

        # Check model has expected attributes
        assert hasattr(User, "user_id")
        assert hasattr(User, "tenant_id")
        assert hasattr(User, "email")
        assert hasattr(User, "role")
        assert hasattr(User, "display_name")
        assert hasattr(User, "created_at_utc")

    def test_user_model_tablename(self) -> None:
        """User model has correct table name."""
        from app.db import User

        assert User.__tablename__ == "users"


class TestEndpointPermissionEnforcement:
    """Tests that endpoints enforce RBAC permissions (FR-003).

    These tests verify that the @require_permission decorator is actually
    applied to endpoints, not just that it works in isolation.
    """

    def test_upload_endpoint_blocks_viewer(self) -> None:
        """Upload endpoint returns 403 for viewer role."""
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/v1/docs/upload",
            headers={
                "X-Tenant-Id": "tenant-1",
                "X-Matter-Id": "matter-1",
                "X-User-Id": "user-123",
                "X-User-Role": "viewer",  # Viewer cannot upload
            },
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
        )
        assert response.status_code == 403
        assert "Permission denied" in response.json()["detail"]

    def test_upload_endpoint_allows_attorney(self) -> None:
        """Upload endpoint allows attorney role (may fail on other validation)."""
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        response = client.post(
            "/v1/docs/upload",
            headers={
                "X-Tenant-Id": "tenant-1",
                "X-Matter-Id": "matter-1",
                "X-User-Id": "user-123",
                "X-User-Role": "attorney",
            },
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
        )
        # Should NOT be 403 - may be other error but not permission denied
        assert response.status_code != 403

    def test_ask_endpoint_allows_viewer(self) -> None:
        """Ask endpoint allows viewer role (query permission)."""
        from unittest.mock import MagicMock, patch

        from fastapi.testclient import TestClient

        from app.main import app
        from app.schemas import AskResponse, VersionSnapshot

        client = TestClient(app)
        # Create proper mock response matching AskResponse schema
        mock_response = AskResponse(
            request_id="test-request-id",
            answer_text="test answer",
            citations=[],
            version_snapshot=VersionSnapshot(
                request_id="test-request-id",
                docs_snapshot_id="test-snapshot",
                prompt_version="1.0",
                retrieval_version="1.0",
                model_id="gpt-4o",
                parser_mode="marker",
            ),
        )
        # Mock execute_ask to avoid needing full RAG pipeline
        with patch("app.routers.ask.execute_ask") as mock_ask:
            mock_ask.return_value = mock_response
            response = client.post(
                "/v1/ask",
                headers={
                    "X-Tenant-Id": "tenant-1",
                    "X-Matter-Id": "matter-1",
                    "X-User-Id": "user-123",
                    "X-User-Role": "viewer",  # Viewer CAN query
                },
                json={"question": "test question"},
            )
        # Should NOT be 403 - viewer has query permission
        assert response.status_code != 403

    def test_export_endpoint_allows_viewer(self) -> None:
        """Export endpoint allows viewer role (export permission)."""
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        # Mock to avoid needing actual session
        with patch("app.routers.export.get_qa_session") as mock_session:
            mock_session.return_value = None  # Will 404, but not 403
            response = client.get(
                "/v1/sessions/test-session/export",
                headers={
                    "X-Tenant-Id": "tenant-1",
                    "X-Matter-Id": "matter-1",
                    "X-User-Id": "user-123",
                    "X-User-Role": "viewer",  # Viewer CAN export
                    "X-DocQA-Session": "test-session",
                },
            )
        # Should be 404 (session not found), not 403 (permission denied)
        assert response.status_code == 404
