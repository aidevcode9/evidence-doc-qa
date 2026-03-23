"""Tests for JWT-based context extraction (FR-050).

TDD: Write tests first, then modify context.py to make them pass.
"""

from __future__ import annotations

import pytest


class TestJWTContextExtraction:
    """Tests for extracting context from JWT tokens (AUTH_MODE=jwt)."""

    def test_jwt_mode_extracts_from_bearer_token(self) -> None:
        """JWT mode should extract tenant_id, user_id, role from Bearer token."""
        from unittest.mock import MagicMock, patch

        from app.security import create_access_token

        # Create a valid access token
        access_token = create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            role="attorney",
            email="test@example.com",
        )

        # Mock user_has_matter_access to return True
        with (
            patch("app.context.AUTH_MODE", "jwt"),
            patch("app.context.user_has_matter_access", return_value=True),
        ):
            from app.context import get_request_context

            # Call with JWT Authorization header
            context = get_request_context(
                authorization=f"Bearer {access_token}",
                x_matter_id="matter-789",
                # These should be ignored in JWT mode
                x_tenant_id=None,
                x_user_id=None,
                x_user_role=None,
            )

            assert context.user_id == "user-123"
            assert context.tenant_id == "tenant-456"
            assert context.user_role.value == "attorney"
            assert context.matter_id == "matter-789"

    def test_jwt_mode_missing_auth_returns_401(self) -> None:
        """Missing Authorization header in JWT mode should return 401."""
        from unittest.mock import patch

        from fastapi import HTTPException

        with patch("app.context.AUTH_MODE", "jwt"):
            from app.context import get_request_context

            with pytest.raises(HTTPException) as exc_info:
                get_request_context(
                    authorization=None,
                    x_matter_id="matter-789",
                    x_tenant_id=None,
                    x_user_id=None,
                    x_user_role=None,
                )

            assert exc_info.value.status_code == 401
            assert "authorization" in exc_info.value.detail.lower()

    def test_jwt_mode_invalid_bearer_format_returns_401(self) -> None:
        """Authorization header without 'Bearer ' prefix should return 401."""
        from unittest.mock import patch

        from fastapi import HTTPException

        with patch("app.context.AUTH_MODE", "jwt"):
            from app.context import get_request_context

            with pytest.raises(HTTPException) as exc_info:
                get_request_context(
                    authorization="InvalidFormat token123",
                    x_matter_id="matter-789",
                    x_tenant_id=None,
                    x_user_id=None,
                    x_user_role=None,
                )

            assert exc_info.value.status_code == 401

    def test_jwt_mode_expired_token_returns_401(self) -> None:
        """Expired JWT should return 401."""
        from datetime import timedelta
        from unittest.mock import patch

        from fastapi import HTTPException

        from app.security import create_access_token

        # Create an expired token
        expired_token = create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            role="attorney",
            email="test@example.com",
            expires_delta=timedelta(seconds=-1),
        )

        with patch("app.context.AUTH_MODE", "jwt"):
            from app.context import get_request_context

            with pytest.raises(HTTPException) as exc_info:
                get_request_context(
                    authorization=f"Bearer {expired_token}",
                    x_matter_id="matter-789",
                    x_tenant_id=None,
                    x_user_id=None,
                    x_user_role=None,
                )

            assert exc_info.value.status_code == 401

    def test_jwt_mode_invalid_signature_returns_401(self) -> None:
        """JWT with invalid signature should return 401."""
        from unittest.mock import patch

        from fastapi import HTTPException

        # Tampered token
        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0YW1wZXJlZCJ9.invalid"

        with patch("app.context.AUTH_MODE", "jwt"):
            from app.context import get_request_context

            with pytest.raises(HTTPException) as exc_info:
                get_request_context(
                    authorization=f"Bearer {invalid_token}",
                    x_matter_id="matter-789",
                    x_tenant_id=None,
                    x_user_id=None,
                    x_user_role=None,
                )

            assert exc_info.value.status_code == 401

    def test_jwt_mode_validates_matter_access(self) -> None:
        """JWT mode should validate user has access to the matter."""
        from unittest.mock import patch

        from fastapi import HTTPException

        from app.security import create_access_token

        access_token = create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            role="attorney",
            email="test@example.com",
        )

        # User does NOT have access to this matter
        with (
            patch("app.context.AUTH_MODE", "jwt"),
            patch("app.context.user_has_matter_access", return_value=False),
        ):
            from app.context import get_request_context

            with pytest.raises(HTTPException) as exc_info:
                get_request_context(
                    authorization=f"Bearer {access_token}",
                    x_matter_id="matter-789",
                    x_tenant_id=None,
                    x_user_id=None,
                    x_user_role=None,
                )

            assert exc_info.value.status_code == 403
            assert "access denied" in exc_info.value.detail.lower()


class TestHeaderModeBackwardCompat:
    """Tests for header-based auth mode (AUTH_MODE=headers) - backward compatibility."""

    def test_header_mode_works_as_before(self) -> None:
        """Header mode should extract context from X-* headers as before."""
        from unittest.mock import patch

        with (
            patch("app.context.AUTH_MODE", "headers"),
            patch("app.context.user_has_matter_access", return_value=True),
        ):
            from app.context import get_request_context

            context = get_request_context(
                x_tenant_id="tenant-456",
                x_matter_id="matter-789",
                x_user_id="user-123",
                x_user_role="attorney",
                authorization=None,
            )

            assert context.tenant_id == "tenant-456"
            assert context.matter_id == "matter-789"
            assert context.user_id == "user-123"
            assert context.user_role.value == "attorney"

    def test_header_mode_missing_tenant_returns_400(self) -> None:
        """Missing X-Tenant-Id in header mode should return 400."""
        from unittest.mock import patch

        from fastapi import HTTPException

        with patch("app.context.AUTH_MODE", "headers"):
            from app.context import get_request_context

            with pytest.raises(HTTPException) as exc_info:
                get_request_context(
                    x_tenant_id="",
                    x_matter_id="matter-789",
                    x_user_id="user-123",
                    x_user_role="attorney",
                    authorization=None,
                )

            assert exc_info.value.status_code == 400
            assert "tenant" in exc_info.value.detail.lower()

    def test_header_mode_missing_user_returns_401(self) -> None:
        """Missing X-User-Id in header mode should return 401."""
        from unittest.mock import patch

        from fastapi import HTTPException

        with patch("app.context.AUTH_MODE", "headers"):
            from app.context import get_request_context

            with pytest.raises(HTTPException) as exc_info:
                get_request_context(
                    x_tenant_id="tenant-456",
                    x_matter_id="matter-789",
                    x_user_id="",
                    x_user_role="attorney",
                    authorization=None,
                )

            assert exc_info.value.status_code == 401
            assert "user" in exc_info.value.detail.lower()

    def test_header_mode_invalid_role_returns_400(self) -> None:
        """Invalid role in header mode should return 400."""
        from unittest.mock import patch

        from fastapi import HTTPException

        with patch("app.context.AUTH_MODE", "headers"):
            from app.context import get_request_context

            with pytest.raises(HTTPException) as exc_info:
                get_request_context(
                    x_tenant_id="tenant-456",
                    x_matter_id="matter-789",
                    x_user_id="user-123",
                    x_user_role="invalid_role",
                    authorization=None,
                )

            assert exc_info.value.status_code == 400
            assert "invalid role" in exc_info.value.detail.lower()


class TestJWTNameClaim:
    """JWT access tokens should include display_name as 'name' claim."""

    def test_create_access_token_includes_name_claim(self) -> None:
        """Token should contain 'name' claim from display_name parameter."""
        from app.security import create_access_token, decode_access_token

        token = create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            role="attorney",
            email="alice@firm.com",
            display_name="Alice Johnson",
        )

        claims = decode_access_token(token)
        assert claims is not None
        assert claims["name"] == "Alice Johnson"

    def test_create_access_token_name_defaults_to_empty(self) -> None:
        """Token should work without display_name (backward compat)."""
        from app.security import create_access_token, decode_access_token

        token = create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            role="attorney",
            email="bob@firm.com",
        )

        claims = decode_access_token(token)
        assert claims is not None
        assert claims.get("name", "") == ""

    def test_jwt_mode_extracts_name_from_token(self) -> None:
        """JWT mode context extraction should work with tokens containing 'name'."""
        from unittest.mock import patch

        from app.security import create_access_token

        token = create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            role="attorney",
            email="alice@firm.com",
            display_name="Alice Johnson",
        )

        with (
            patch("app.context.AUTH_MODE", "jwt"),
            patch("app.context.user_has_matter_access", return_value=True),
        ):
            from app.context import get_request_context

            context = get_request_context(
                authorization=f"Bearer {token}",
                x_matter_id="matter-789",
                x_tenant_id=None,
                x_user_id=None,
                x_user_role=None,
            )

            assert context.tenant_id == "tenant-456"
            assert context.user_id == "user-123"


class TestAuthModeDefault:
    """Tests for default AUTH_MODE behavior."""

    def test_default_mode_is_headers(self) -> None:
        """Default AUTH_MODE should be 'headers' for backward compatibility."""
        from app import config

        assert config.AUTH_MODE == "headers"
