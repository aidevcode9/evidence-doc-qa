"""Tests for SSO (Single Sign-On) integration (FR-051).

Tests cover:
- Microsoft Entra ID login redirect
- Google Workspace login redirect
- SSO callback with JIT user provisioning
- Token issuance after successful SSO
- ID token validation with JWKS
- Database-backed state storage
"""

from __future__ import annotations

from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def sso_enabled_app() -> Generator[TestClient, None, None]:
    """Create app with SSO enabled."""
    with patch.multiple(
        "app.config",
        MICROSOFT_SSO_ENABLED=True,
        MICROSOFT_CLIENT_ID="test-microsoft-client-id",
        MICROSOFT_CLIENT_SECRET="test-microsoft-secret",
        MICROSOFT_TENANT_ID="test-tenant-id",
        GOOGLE_SSO_ENABLED=True,
        GOOGLE_CLIENT_ID="test-google-client-id",
        GOOGLE_CLIENT_SECRET="test-google-secret",
        SSO_REDIRECT_URI="https://app.example.com/v1/auth/sso/callback",
        SSO_DEFAULT_ROLE="viewer",
        JWT_SECRET_KEY="test-secret-key-for-jwt-tokens",
        JWT_ALGORITHM="HS256",
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30,
        JWT_REFRESH_TOKEN_EXPIRE_DAYS=7,
    ):
        # Mock DB operations
        with patch("app.routers.sso.store_sso_state"):
            from app.routers.sso import router

            app = FastAPI()
            app.include_router(router)
            yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def microsoft_disabled_app() -> Generator[TestClient, None, None]:
    """Create app with Microsoft SSO disabled."""
    with patch.multiple(
        "app.config",
        MICROSOFT_SSO_ENABLED=False,
        GOOGLE_SSO_ENABLED=True,
        GOOGLE_CLIENT_ID="test-google-client-id",
        GOOGLE_CLIENT_SECRET="test-google-secret",
        SSO_REDIRECT_URI="https://app.example.com/v1/auth/sso/callback",
    ):
        from importlib import reload

        import app.routers.sso as sso_module

        reload(sso_module)

        app = FastAPI()
        app.include_router(sso_module.router)
        yield TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def google_disabled_app() -> Generator[TestClient, None, None]:
    """Create app with Google SSO disabled."""
    with patch.multiple(
        "app.config",
        MICROSOFT_SSO_ENABLED=True,
        MICROSOFT_CLIENT_ID="test-microsoft-client-id",
        MICROSOFT_CLIENT_SECRET="test-microsoft-secret",
        MICROSOFT_TENANT_ID="test-tenant-id",
        GOOGLE_SSO_ENABLED=False,
        SSO_REDIRECT_URI="https://app.example.com/v1/auth/sso/callback",
    ):
        from importlib import reload

        import app.routers.sso as sso_module

        reload(sso_module)

        app = FastAPI()
        app.include_router(sso_module.router)
        yield TestClient(app, raise_server_exceptions=False)


class TestMicrosoftSSO:
    """Tests for Microsoft Entra ID SSO login."""

    def test_microsoft_login_redirects_to_microsoft(
        self, sso_enabled_app: TestClient
    ) -> None:
        """Microsoft login should redirect to Microsoft authorization endpoint."""
        response = sso_enabled_app.get(
            "/v1/auth/sso/microsoft",
            params={"tenant_id": "test-tenant"},
            follow_redirects=False,
        )

        assert response.status_code == 307  # Redirect
        location = response.headers.get("location", "")
        assert "login.microsoftonline.com" in location
        assert "client_id=test-microsoft-client-id" in location

    def test_microsoft_login_includes_state_param(
        self, sso_enabled_app: TestClient
    ) -> None:
        """Microsoft login should include state parameter for CSRF protection."""
        response = sso_enabled_app.get(
            "/v1/auth/sso/microsoft",
            params={"tenant_id": "test-tenant"},
            follow_redirects=False,
        )

        location = response.headers.get("location", "")
        assert "state=" in location

    def test_microsoft_login_includes_pkce_challenge(
        self, sso_enabled_app: TestClient
    ) -> None:
        """Microsoft login should include PKCE code_challenge."""
        response = sso_enabled_app.get(
            "/v1/auth/sso/microsoft",
            params={"tenant_id": "test-tenant"},
            follow_redirects=False,
        )

        location = response.headers.get("location", "")
        assert "code_challenge=" in location
        assert "code_challenge_method=S256" in location

    def test_microsoft_login_includes_nonce(
        self, sso_enabled_app: TestClient
    ) -> None:
        """Microsoft login should include nonce for replay protection."""
        response = sso_enabled_app.get(
            "/v1/auth/sso/microsoft",
            params={"tenant_id": "test-tenant"},
            follow_redirects=False,
        )

        location = response.headers.get("location", "")
        assert "nonce=" in location

    def test_microsoft_login_disabled_returns_404(
        self, microsoft_disabled_app: TestClient
    ) -> None:
        """Microsoft login should return 404 when disabled."""
        response = microsoft_disabled_app.get(
            "/v1/auth/sso/microsoft",
            params={"tenant_id": "test-tenant"},
        )

        assert response.status_code == 404


class TestGoogleSSO:
    """Tests for Google Workspace SSO login."""

    def test_google_login_redirects_to_google(
        self, sso_enabled_app: TestClient
    ) -> None:
        """Google login should redirect to Google authorization endpoint."""
        response = sso_enabled_app.get(
            "/v1/auth/sso/google",
            params={"tenant_id": "test-tenant"},
            follow_redirects=False,
        )

        assert response.status_code == 307  # Redirect
        location = response.headers.get("location", "")
        assert "accounts.google.com" in location
        assert "client_id=test-google-client-id" in location

    def test_google_login_includes_state_param(
        self, sso_enabled_app: TestClient
    ) -> None:
        """Google login should include state parameter for CSRF protection."""
        response = sso_enabled_app.get(
            "/v1/auth/sso/google",
            params={"tenant_id": "test-tenant"},
            follow_redirects=False,
        )

        location = response.headers.get("location", "")
        assert "state=" in location

    def test_google_login_disabled_returns_404(
        self, google_disabled_app: TestClient
    ) -> None:
        """Google login should return 404 when disabled."""
        response = google_disabled_app.get(
            "/v1/auth/sso/google",
            params={"tenant_id": "test-tenant"},
        )

        assert response.status_code == 404


class TestSSOCallback:
    """Tests for SSO callback handling."""

    def test_callback_validates_state(self, sso_enabled_app: TestClient) -> None:
        """Callback should reject invalid state parameter."""
        with patch("app.routers.sso.get_and_delete_sso_state") as mock_get_state:
            mock_get_state.return_value = None  # Invalid state

            response = sso_enabled_app.get(
                "/v1/auth/sso/callback",
                params={"code": "auth-code", "state": "invalid-state"},
            )

            assert response.status_code == 400
            assert "invalid" in response.json().get("detail", "").lower()

    def test_callback_creates_new_user_as_viewer(
        self, sso_enabled_app: TestClient
    ) -> None:
        """Callback should create new user with Viewer role on first SSO login."""
        # Mock state from database
        mock_state = MagicMock()
        mock_state.provider = "microsoft"
        mock_state.tenant_id = "test-tenant"
        mock_state.code_verifier = "test-verifier"
        mock_state.nonce = "test-nonce"

        with patch("app.routers.sso.get_and_delete_sso_state") as mock_get_state:
            with patch("app.routers.sso._exchange_code_for_tokens") as mock_exchange:
                with patch("app.routers.sso._get_jwks") as mock_jwks:
                    with patch("app.routers.sso._validate_id_token") as mock_validate:
                        with patch("app.routers.sso.get_user_by_email") as mock_get_user:
                            with patch("app.routers.sso.create_user") as mock_create_user:
                                with patch("app.routers.sso.store_refresh_token"):
                                    mock_get_state.return_value = mock_state
                                    mock_exchange.return_value = {"id_token": "test-id-token"}
                                    mock_jwks.return_value = {"keys": []}
                                    mock_validate.return_value = {
                                        "email": "attorney@firm.com",
                                        "name": "John Attorney",
                                    }
                                    mock_get_user.return_value = None  # New user
                                    mock_create_user.return_value = MagicMock(
                                        user_id="new-user-id",
                                        email="attorney@firm.com",
                                        role="viewer",
                                        tenant_id="test-tenant",
                                    )

                                    response = sso_enabled_app.get(
                                        "/v1/auth/sso/callback",
                                        params={"code": "auth-code", "state": "valid-state"},
                                    )

                                    # Should return tokens
                                    assert response.status_code == 200
                                    data = response.json()
                                    assert "access_token" in data
                                    assert "refresh_token" in data

                                    # Should create user as Viewer
                                    mock_create_user.assert_called_once()
                                    call_kwargs = mock_create_user.call_args.kwargs
                                    assert call_kwargs["role"] == "viewer"
                                    assert call_kwargs["auth_provider"] == "microsoft"

    def test_callback_logs_in_existing_user(
        self, sso_enabled_app: TestClient
    ) -> None:
        """Callback should log in existing user without changing role."""
        # Mock state from database
        mock_state = MagicMock()
        mock_state.provider = "microsoft"
        mock_state.tenant_id = "test-tenant"
        mock_state.code_verifier = "test-verifier"
        mock_state.nonce = "test-nonce"

        # Mock existing user
        existing_user = MagicMock(
            user_id="existing-user-id",
            email="attorney@firm.com",
            role="attorney",  # Already promoted
            tenant_id="test-tenant",
            auth_provider="microsoft",
        )

        with patch("app.routers.sso.get_and_delete_sso_state") as mock_get_state:
            with patch("app.routers.sso._exchange_code_for_tokens") as mock_exchange:
                with patch("app.routers.sso._get_jwks") as mock_jwks:
                    with patch("app.routers.sso._validate_id_token") as mock_validate:
                        with patch("app.routers.sso.get_user_by_email") as mock_get_user:
                            with patch(
                                "app.routers.sso.update_user_login_success"
                            ) as mock_update:
                                with patch("app.routers.sso.store_refresh_token"):
                                    mock_get_state.return_value = mock_state
                                    mock_exchange.return_value = {"id_token": "test-id-token"}
                                    mock_jwks.return_value = {"keys": []}
                                    mock_validate.return_value = {
                                        "email": "attorney@firm.com",
                                        "name": "John Attorney",
                                    }
                                    mock_get_user.return_value = existing_user

                                    response = sso_enabled_app.get(
                                        "/v1/auth/sso/callback",
                                        params={"code": "auth-code", "state": "valid-state"},
                                    )

                                    assert response.status_code == 200
                                    mock_update.assert_called_once()

    def test_callback_rejects_mismatched_auth_provider(
        self, sso_enabled_app: TestClient
    ) -> None:
        """Callback should reject if user exists with different auth provider."""
        # Mock state from database for Microsoft login
        mock_state = MagicMock()
        mock_state.provider = "microsoft"
        mock_state.tenant_id = "test-tenant"
        mock_state.code_verifier = "test-verifier"
        mock_state.nonce = "test-nonce"

        # Mock existing user registered via Google
        existing_user = MagicMock(
            user_id="existing-user-id",
            email="attorney@firm.com",
            role="attorney",
            tenant_id="test-tenant",
            auth_provider="google",  # Different provider!
        )

        with patch("app.routers.sso.get_and_delete_sso_state") as mock_get_state:
            with patch("app.routers.sso._exchange_code_for_tokens") as mock_exchange:
                with patch("app.routers.sso._get_jwks") as mock_jwks:
                    with patch("app.routers.sso._validate_id_token") as mock_validate:
                        with patch("app.routers.sso.get_user_by_email") as mock_get_user:
                            mock_get_state.return_value = mock_state
                            mock_exchange.return_value = {"id_token": "test-id-token"}
                            mock_jwks.return_value = {"keys": []}
                            mock_validate.return_value = {
                                "email": "attorney@firm.com",
                                "name": "John Attorney",
                            }
                            mock_get_user.return_value = existing_user

                            response = sso_enabled_app.get(
                                "/v1/auth/sso/callback",
                                params={"code": "auth-code", "state": "valid-state"},
                            )

                            assert response.status_code == 409
                            # Error message should NOT reveal the other provider (sanitized)
                            detail = response.json().get("detail", "")
                            assert "another account" in detail.lower()
                            assert "google" not in detail.lower()

    def test_callback_issues_jwt_tokens(self, sso_enabled_app: TestClient) -> None:
        """Callback should issue valid JWT access and refresh tokens."""
        # Mock state from database
        mock_state = MagicMock()
        mock_state.provider = "microsoft"
        mock_state.tenant_id = "test-tenant"
        mock_state.code_verifier = "test-verifier"
        mock_state.nonce = "test-nonce"

        existing_user = MagicMock(
            user_id="existing-user-id",
            email="attorney@firm.com",
            role="attorney",
            tenant_id="test-tenant",
            auth_provider="microsoft",
        )

        with patch("app.routers.sso.get_and_delete_sso_state") as mock_get_state:
            with patch("app.routers.sso._exchange_code_for_tokens") as mock_exchange:
                with patch("app.routers.sso._get_jwks") as mock_jwks:
                    with patch("app.routers.sso._validate_id_token") as mock_validate:
                        with patch("app.routers.sso.get_user_by_email") as mock_get_user:
                            with patch("app.routers.sso.update_user_login_success"):
                                with patch("app.routers.sso.store_refresh_token"):
                                    mock_get_state.return_value = mock_state
                                    mock_exchange.return_value = {"id_token": "test-id-token"}
                                    mock_jwks.return_value = {"keys": []}
                                    mock_validate.return_value = {
                                        "email": "attorney@firm.com",
                                        "name": "John Attorney",
                                    }
                                    mock_get_user.return_value = existing_user

                                    response = sso_enabled_app.get(
                                        "/v1/auth/sso/callback",
                                        params={"code": "auth-code", "state": "valid-state"},
                                    )

                                    assert response.status_code == 200
                                    data = response.json()

                                    # Verify token structure
                                    assert "access_token" in data
                                    assert "refresh_token" in data
                                    assert data.get("token_type") == "bearer"
                                    assert "expires_in" in data

                                    # Verify access token is decodable
                                    from app.security import decode_access_token

                                    claims = decode_access_token(data["access_token"])
                                    assert claims is not None
                                    assert claims["sub"] == "existing-user-id"
                                    assert claims["tenant_id"] == "test-tenant"
                                    assert claims["role"] == "attorney"
