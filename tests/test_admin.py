"""Tests for Admin Dashboard (FR-052).

Tests cover:
- Admin user list with pagination
- Admin user CRUD (create, read, update, delete)
- Matter access management (grant/revoke)
- Permission enforcement (require admin role)
"""

from __future__ import annotations

from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def admin_app() -> Generator[TestClient, None, None]:
    """Create app with admin router."""
    with patch.multiple(
        "app.config",
        AUTH_MODE="headers",  # Use headers mode for testing
        JWT_SECRET_KEY="test-secret-key-for-jwt-tokens",
        JWT_ALGORITHM="HS256",
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
    ):
        from app.routers.admin import router

        app = FastAPI()
        app.include_router(router)
        yield TestClient(app, raise_server_exceptions=False)


def _admin_headers(tenant_id: str = "test-tenant") -> dict[str, str]:
    """Generate headers for admin user."""
    return {
        "X-Tenant-Id": tenant_id,
        "X-Matter-Id": "test-matter",
        "X-User-Id": "admin-user-id",
        "X-User-Role": "admin",
    }


def _non_admin_headers(tenant_id: str = "test-tenant") -> dict[str, str]:
    """Generate headers for non-admin user."""
    return {
        "X-Tenant-Id": tenant_id,
        "X-Matter-Id": "test-matter",
        "X-User-Id": "viewer-user-id",
        "X-User-Role": "viewer",
    }


class TestAdminUserList:
    """Tests for admin user list endpoint."""

    def test_list_users_requires_admin(self, admin_app: TestClient) -> None:
        """List users should require admin role."""
        response = admin_app.get(
            "/v1/admin/users",
            headers=_non_admin_headers(),
        )

        assert response.status_code == 403

    def test_list_users_returns_paginated(self, admin_app: TestClient) -> None:
        """List users should return paginated results."""
        mock_users = [
            MagicMock(
                user_id=f"user-{i}",
                email=f"user{i}@firm.com",
                role="attorney",
                display_name=f"User {i}",
                tenant_id="test-tenant",
                is_active=True,
                auth_provider="local",
            )
            for i in range(5)
        ]

        with patch("app.routers.admin.list_users") as mock_list:
            mock_list.return_value = (mock_users, 15)  # 15 total users

            response = admin_app.get(
                "/v1/admin/users",
                params={"offset": 0, "limit": 5},
                headers=_admin_headers(),
            )

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "offset" in data
            assert "limit" in data
            assert len(data["items"]) == 5
            assert data["total"] == 15

    def test_list_users_filters_by_tenant(self, admin_app: TestClient) -> None:
        """List users should only return users from same tenant."""
        with patch("app.routers.admin.list_users") as mock_list:
            mock_list.return_value = ([], 0)

            admin_app.get(
                "/v1/admin/users",
                headers=_admin_headers("my-tenant"),
            )

            # Verify tenant_id was passed to list_users
            mock_list.assert_called_once()
            call_kwargs = mock_list.call_args.kwargs
            assert call_kwargs["tenant_id"] == "my-tenant"

    def test_list_users_search_works(self, admin_app: TestClient) -> None:
        """List users should support search parameter."""
        with patch("app.routers.admin.list_users") as mock_list:
            mock_list.return_value = ([], 0)

            admin_app.get(
                "/v1/admin/users",
                params={"search": "john"},
                headers=_admin_headers(),
            )

            # Verify search was passed
            mock_list.assert_called_once()
            call_kwargs = mock_list.call_args.kwargs
            assert call_kwargs["search"] == "john"


class TestAdminUserCRUD:
    """Tests for admin user CRUD operations."""

    def test_create_user_returns_user_info(self, admin_app: TestClient) -> None:
        """Create user should return the new user info."""
        new_user = MagicMock(
            user_id="new-user-id",
            email="newuser@firm.com",
            role="viewer",
            display_name="New User",
            tenant_id="test-tenant",
            is_active=True,
            auth_provider="local",
        )

        with patch("app.routers.admin.get_user_by_email") as mock_get:
            with patch("app.routers.admin.create_user") as mock_create:
                mock_get.return_value = None  # Email not taken
                mock_create.return_value = new_user

                response = admin_app.post(
                    "/v1/admin/users",
                    json={
                        "email": "newuser@firm.com",
                        "display_name": "New User",
                        "role": "viewer",
                    },
                    headers=_admin_headers(),
                )

                assert response.status_code == 201
                data = response.json()
                assert data["email"] == "newuser@firm.com"
                assert data["role"] == "viewer"

    def test_create_user_rejects_duplicate_email(self, admin_app: TestClient) -> None:
        """Create user should reject duplicate email."""
        existing_user = MagicMock(
            user_id="existing-id",
            email="existing@firm.com",
        )

        with patch("app.routers.admin.get_user_by_email") as mock_get:
            mock_get.return_value = existing_user

            response = admin_app.post(
                "/v1/admin/users",
                json={
                    "email": "existing@firm.com",
                    "display_name": "Duplicate",
                    "role": "viewer",
                },
                headers=_admin_headers(),
            )

            assert response.status_code == 409

    def test_update_user_changes_role(self, admin_app: TestClient) -> None:
        """Update user should change role."""
        existing_user = MagicMock(
            user_id="user-id",
            email="user@firm.com",
            role="viewer",
            display_name="User",
            tenant_id="test-tenant",
            is_active=True,
            auth_provider="local",
        )

        with patch("app.routers.admin.get_user_by_id") as mock_get:
            with patch("app.routers.admin.update_user") as mock_update:
                mock_get.return_value = existing_user
                # Update should return modified user
                updated_user = MagicMock(
                    user_id="user-id",
                    email="user@firm.com",
                    role="attorney",
                    display_name="User",
                    tenant_id="test-tenant",
                    is_active=True,
                    auth_provider="local",
                )
                mock_update.return_value = updated_user

                response = admin_app.patch(
                    "/v1/admin/users/user-id",
                    json={"role": "attorney"},
                    headers=_admin_headers(),
                )

                assert response.status_code == 200
                data = response.json()
                assert data["role"] == "attorney"

    def test_deactivate_user_sets_is_active_false(self, admin_app: TestClient) -> None:
        """Delete user should set is_active=False (soft delete)."""
        existing_user = MagicMock(
            user_id="user-id",
            email="user@firm.com",
            role="viewer",
            tenant_id="test-tenant",
            is_active=True,
        )

        with patch("app.routers.admin.get_user_by_id") as mock_get:
            with patch("app.routers.admin.deactivate_user") as mock_deactivate:
                mock_get.return_value = existing_user
                mock_deactivate.return_value = True

                response = admin_app.delete(
                    "/v1/admin/users/user-id",
                    headers=_admin_headers(),
                )

                assert response.status_code == 204
                mock_deactivate.assert_called_once_with("user-id", "test-tenant")

    def test_cannot_deactivate_self(self, admin_app: TestClient) -> None:
        """Admin cannot deactivate their own account."""
        response = admin_app.delete(
            "/v1/admin/users/admin-user-id",  # Same as X-User-Id in headers
            headers=_admin_headers(),
        )

        assert response.status_code == 400
        assert "cannot" in response.json().get("detail", "").lower()


class TestAdminMatterAccess:
    """Tests for admin matter access management."""

    def test_grant_matter_access_creates_assignment(
        self, admin_app: TestClient
    ) -> None:
        """Grant matter access should create assignment."""
        with patch("app.routers.admin.get_user_by_id") as mock_get_user:
            with patch("app.routers.admin.grant_matter_access") as mock_grant:
                mock_get_user.return_value = MagicMock(
                    user_id="user-id",
                    tenant_id="test-tenant",
                )
                mock_grant.return_value = MagicMock(
                    assignment_id="assignment-id",
                    user_id="user-id",
                    matter_id="matter-123",
                )

                response = admin_app.post(
                    "/v1/admin/users/user-id/matters/matter-123",
                    headers=_admin_headers(),
                )

                assert response.status_code == 201
                mock_grant.assert_called_once()

    def test_revoke_matter_access_deletes_assignment(
        self, admin_app: TestClient
    ) -> None:
        """Revoke matter access should delete assignment."""
        with patch("app.routers.admin.get_user_by_id") as mock_get_user:
            with patch("app.routers.admin.revoke_matter_access") as mock_revoke:
                mock_get_user.return_value = MagicMock(
                    user_id="user-id",
                    tenant_id="test-tenant",
                )
                mock_revoke.return_value = True

                response = admin_app.delete(
                    "/v1/admin/users/user-id/matters/matter-123",
                    headers=_admin_headers(),
                )

                assert response.status_code == 204
                mock_revoke.assert_called_once()

    def test_list_user_matters_returns_assignments(
        self, admin_app: TestClient
    ) -> None:
        """List user matters should return their matter assignments."""
        with patch("app.routers.admin.get_user_by_id") as mock_get_user:
            with patch("app.routers.admin.get_user_matters") as mock_get_matters:
                mock_get_user.return_value = MagicMock(
                    user_id="user-id",
                    tenant_id="test-tenant",
                )
                mock_get_matters.return_value = ["matter-1", "matter-2", "matter-3"]

                response = admin_app.get(
                    "/v1/admin/users/user-id/matters",
                    headers=_admin_headers(),
                )

                assert response.status_code == 200
                data = response.json()
                assert len(data["matters"]) == 3


class TestAdminPermissions:
    """Tests for admin endpoint permission enforcement."""

    def test_all_endpoints_require_admin(self, admin_app: TestClient) -> None:
        """All admin endpoints should require admin role."""
        non_admin = _non_admin_headers()

        # List users
        assert admin_app.get("/v1/admin/users", headers=non_admin).status_code == 403

        # Create user
        assert (
            admin_app.post(
                "/v1/admin/users", json={"email": "x"}, headers=non_admin
            ).status_code
            == 403
        )

        # Update user
        assert (
            admin_app.patch(
                "/v1/admin/users/x", json={"role": "viewer"}, headers=non_admin
            ).status_code
            == 403
        )

        # Delete user
        assert admin_app.delete("/v1/admin/users/x", headers=non_admin).status_code == 403

        # User matters
        assert (
            admin_app.get("/v1/admin/users/x/matters", headers=non_admin).status_code
            == 403
        )

        # Grant matter
        assert (
            admin_app.post("/v1/admin/users/x/matters/y", headers=non_admin).status_code
            == 403
        )

        # Revoke matter
        assert (
            admin_app.delete(
                "/v1/admin/users/x/matters/y", headers=non_admin
            ).status_code
            == 403
        )
