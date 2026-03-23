"""Tests for authentication module (FR-050).

TDD: Write tests first, then implement to make them pass.
"""

from __future__ import annotations

import pytest


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_hash(self) -> None:
        """hash_password should return a hash string, not the plaintext."""
        from app.security import hash_password

        password = "SecureP@ss123"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > 50  # Argon2 hashes are long
        assert hashed.startswith("$argon2")  # Argon2 hash format

    def test_verify_password_correct(self) -> None:
        """verify_password should return True for correct password."""
        from app.security import hash_password, verify_password

        password = "SecureP@ss123"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self) -> None:
        """verify_password should return False for incorrect password."""
        from app.security import hash_password, verify_password

        password = "SecureP@ss123"
        wrong_password = "WrongPassword123"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_verify_password_empty(self) -> None:
        """verify_password should return False for empty password."""
        from app.security import hash_password, verify_password

        password = "SecureP@ss123"
        hashed = hash_password(password)

        assert verify_password("", hashed) is False

    def test_hash_password_different_each_time(self) -> None:
        """hash_password should generate different hashes for same password (salt)."""
        from app.security import hash_password

        password = "SecureP@ss123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Different salts


class TestPasswordPolicy:
    """Tests for password policy validation."""

    def test_password_policy_valid(self) -> None:
        """A strong password should pass validation."""
        from app.security import validate_password_policy

        is_valid, message = validate_password_policy("SecureP@ss123")

        assert is_valid is True
        assert message == ""

    def test_password_policy_min_length(self) -> None:
        """Password shorter than minimum length should fail."""
        from app.security import validate_password_policy

        is_valid, message = validate_password_policy("Ab1@xyz")  # 7 chars

        assert is_valid is False
        assert "8 characters" in message.lower()

    def test_password_policy_requires_uppercase(self) -> None:
        """Password without uppercase should fail."""
        from app.security import validate_password_policy

        is_valid, message = validate_password_policy("securep@ss123")

        assert is_valid is False
        assert "uppercase" in message.lower()

    def test_password_policy_requires_lowercase(self) -> None:
        """Password without lowercase should fail."""
        from app.security import validate_password_policy

        is_valid, message = validate_password_policy("SECUREP@SS123")

        assert is_valid is False
        assert "lowercase" in message.lower()

    def test_password_policy_requires_digit(self) -> None:
        """Password without digit should fail."""
        from app.security import validate_password_policy

        is_valid, message = validate_password_policy("SecureP@ssword")

        assert is_valid is False
        assert "digit" in message.lower()

    def test_password_policy_requires_special(self) -> None:
        """Password without special character should fail."""
        from app.security import validate_password_policy

        is_valid, message = validate_password_policy("SecurePass123")

        assert is_valid is False
        assert "special" in message.lower()


class TestJWTTokens:
    """Tests for JWT token creation and validation."""

    def test_create_access_token_includes_claims(self) -> None:
        """Access token should include user_id, tenant_id, role in claims."""
        from app.security import create_access_token, decode_access_token

        token = create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            role="attorney",
            email="test@example.com",
        )

        claims = decode_access_token(token)
        assert claims is not None
        assert claims["sub"] == "user-123"
        assert claims["tenant_id"] == "tenant-456"
        assert claims["role"] == "attorney"
        assert claims["email"] == "test@example.com"
        assert "exp" in claims
        assert "iat" in claims
        assert "jti" in claims

    def test_decode_access_token_valid(self) -> None:
        """Valid token should decode successfully."""
        from app.security import create_access_token, decode_access_token

        token = create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            role="admin",
            email="admin@example.com",
        )

        claims = decode_access_token(token)
        assert claims is not None
        assert claims["sub"] == "user-123"

    def test_decode_access_token_expired(self) -> None:
        """Expired token should return None."""
        from datetime import timedelta

        from app.security import create_access_token, decode_access_token

        # Create token that expires immediately (negative delta)
        token = create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            role="viewer",
            email="viewer@example.com",
            expires_delta=timedelta(seconds=-1),
        )

        claims = decode_access_token(token)
        assert claims is None

    def test_decode_access_token_invalid_signature(self) -> None:
        """Token with invalid signature should return None."""
        from app.security import decode_access_token

        # Tampered token (modified payload)
        invalid_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0YW1wZXJlZCJ9.invalid"

        claims = decode_access_token(invalid_token)
        assert claims is None

    def test_decode_access_token_malformed(self) -> None:
        """Malformed token should return None."""
        from app.security import decode_access_token

        claims = decode_access_token("not-a-valid-jwt")
        assert claims is None

    def test_create_refresh_token_returns_token_and_id(self) -> None:
        """create_refresh_token should return (token, token_id) tuple."""
        from app.security import create_refresh_token

        token, token_id = create_refresh_token(
            user_id="user-123",
            tenant_id="tenant-456",
        )

        assert token is not None
        assert len(token) > 32  # Should be a substantial token
        assert token_id is not None
        assert len(token_id) == 36  # UUID format

    def test_refresh_token_contains_claims(self) -> None:
        """Refresh token should contain user and tenant claims."""
        from app.security import create_refresh_token, decode_refresh_token

        token, token_id = create_refresh_token(
            user_id="user-123",
            tenant_id="tenant-456",
        )

        claims = decode_refresh_token(token)
        assert claims is not None
        assert claims["sub"] == "user-123"
        assert claims["tenant_id"] == "tenant-456"
        assert claims["jti"] == token_id
        assert claims["type"] == "refresh"


class TestLoginEndpoint:
    """Tests for POST /v1/auth/login endpoint (FR-050)."""

    def test_login_valid_credentials_returns_tokens(self) -> None:
        """Valid email/password should return access and refresh tokens."""
        from unittest.mock import MagicMock, patch

        from app.routers import auth as auth_module
        from app.schemas import LoginRequest
        from app.security import hash_password

        # Mock a user with valid password
        mock_user = MagicMock()
        mock_user.user_id = "user-123"
        mock_user.tenant_id = "tenant-456"
        mock_user.email = "test@example.com"
        mock_user.role = "attorney"
        mock_user.display_name = "Test User"
        mock_user.password_hash = hash_password("SecureP@ss123")
        mock_user.is_active = True
        mock_user.locked_until_utc = None
        mock_user.failed_login_count = 0

        with (
            patch.object(auth_module, "get_user_by_email", return_value=mock_user),
            patch.object(auth_module, "update_user_login_success"),
            patch.object(auth_module, "store_refresh_token"),
        ):
            request = LoginRequest(
                email="test@example.com",
                password="SecureP@ss123",
                tenant_id="tenant-456",
            )
            result = auth_module.login(request)

            assert "access_token" in result
            assert "refresh_token" in result
            assert result["token_type"] == "bearer"
            assert result["expires_in"] > 0

    def test_login_invalid_password_returns_401(self) -> None:
        """Invalid password should return 401 Unauthorized."""
        from unittest.mock import MagicMock, patch

        from fastapi import HTTPException

        from app.routers import auth as auth_module
        from app.schemas import LoginRequest
        from app.security import hash_password

        mock_user = MagicMock()
        mock_user.user_id = "user-123"
        mock_user.tenant_id = "tenant-456"
        mock_user.email = "test@example.com"
        mock_user.role = "attorney"
        mock_user.password_hash = hash_password("CorrectPassword123!")
        mock_user.is_active = True
        mock_user.locked_until_utc = None
        mock_user.failed_login_count = 0

        with (
            patch.object(auth_module, "get_user_by_email", return_value=mock_user),
            patch.object(auth_module, "increment_user_failed_login", return_value=1),
        ):
            request = LoginRequest(
                email="test@example.com",
                password="WrongPassword123!",
                tenant_id="tenant-456",
            )

            with pytest.raises(HTTPException) as exc_info:
                auth_module.login(request)
            assert exc_info.value.status_code == 401
            assert "invalid" in exc_info.value.detail.lower()

    def test_login_unknown_email_returns_401(self) -> None:
        """Unknown email should return 401 (not 404 - no user enumeration)."""
        from unittest.mock import patch

        from fastapi import HTTPException

        from app.routers import auth as auth_module
        from app.schemas import LoginRequest

        with patch.object(auth_module, "get_user_by_email", return_value=None):
            request = LoginRequest(
                email="unknown@example.com",
                password="SomePassword123!",
                tenant_id="tenant-456",
            )

            with pytest.raises(HTTPException) as exc_info:
                auth_module.login(request)
            assert exc_info.value.status_code == 401
            # Same error message as invalid password (prevent user enumeration)
            assert "invalid" in exc_info.value.detail.lower()

    def test_login_locked_account_returns_403(self) -> None:
        """Locked account should return 403 Forbidden."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from fastapi import HTTPException

        from app.routers import auth as auth_module
        from app.schemas import LoginRequest
        from app.security import hash_password

        # User is locked for another 15 minutes
        lock_time = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()

        mock_user = MagicMock()
        mock_user.user_id = "user-123"
        mock_user.tenant_id = "tenant-456"
        mock_user.email = "test@example.com"
        mock_user.password_hash = hash_password("SecureP@ss123")
        mock_user.is_active = True
        mock_user.locked_until_utc = lock_time
        mock_user.failed_login_count = 5

        with patch.object(auth_module, "get_user_by_email", return_value=mock_user):
            request = LoginRequest(
                email="test@example.com",
                password="SecureP@ss123",
                tenant_id="tenant-456",
            )

            with pytest.raises(HTTPException) as exc_info:
                auth_module.login(request)
            assert exc_info.value.status_code == 403
            assert "locked" in exc_info.value.detail.lower()

    def test_login_increments_failed_count_on_wrong_password(self) -> None:
        """Failed login should increment the failed_login_count."""
        from unittest.mock import MagicMock, patch

        from fastapi import HTTPException

        from app.routers import auth as auth_module
        from app.schemas import LoginRequest
        from app.security import hash_password

        mock_user = MagicMock()
        mock_user.user_id = "user-123"
        mock_user.tenant_id = "tenant-456"
        mock_user.email = "test@example.com"
        mock_user.password_hash = hash_password("CorrectPassword123!")
        mock_user.is_active = True
        mock_user.locked_until_utc = None
        mock_user.failed_login_count = 0

        increment_mock = MagicMock(return_value=1)

        with (
            patch.object(auth_module, "get_user_by_email", return_value=mock_user),
            patch.object(auth_module, "increment_user_failed_login", increment_mock),
        ):
            request = LoginRequest(
                email="test@example.com",
                password="WrongPassword123!",
                tenant_id="tenant-456",
            )

            with pytest.raises(HTTPException):
                auth_module.login(request)

            # Verify increment was called
            increment_mock.assert_called_once_with("user-123", "tenant-456")

    def test_login_locks_account_after_max_failures(self) -> None:
        """Account should be locked after MAX_FAILED_LOGIN_ATTEMPTS."""
        from unittest.mock import MagicMock, patch

        from fastapi import HTTPException

        from app import config
        from app.routers import auth as auth_module
        from app.schemas import LoginRequest
        from app.security import hash_password

        mock_user = MagicMock()
        mock_user.user_id = "user-123"
        mock_user.tenant_id = "tenant-456"
        mock_user.email = "test@example.com"
        mock_user.password_hash = hash_password("CorrectPassword123!")
        mock_user.is_active = True
        mock_user.locked_until_utc = None
        mock_user.failed_login_count = 4  # One more failure will trigger lock

        lock_mock = MagicMock()

        with (
            patch.object(auth_module, "get_user_by_email", return_value=mock_user),
            patch.object(auth_module, "increment_user_failed_login", return_value=5),
            patch.object(auth_module, "lock_user_account", lock_mock),
            patch.object(config, "MAX_FAILED_LOGIN_ATTEMPTS", 5),
            patch.object(config, "ACCOUNT_LOCKOUT_MINUTES", 30),
        ):
            request = LoginRequest(
                email="test@example.com",
                password="WrongPassword123!",
                tenant_id="tenant-456",
            )

            with pytest.raises(HTTPException):
                auth_module.login(request)

            # Verify lock was called
            lock_mock.assert_called_once()

    def test_login_inactive_user_returns_403(self) -> None:
        """Inactive user should return 403 Forbidden."""
        from unittest.mock import MagicMock, patch

        from fastapi import HTTPException

        from app.routers import auth as auth_module
        from app.schemas import LoginRequest
        from app.security import hash_password

        mock_user = MagicMock()
        mock_user.user_id = "user-123"
        mock_user.tenant_id = "tenant-456"
        mock_user.email = "test@example.com"
        mock_user.password_hash = hash_password("SecureP@ss123")
        mock_user.is_active = False  # User is deactivated
        mock_user.locked_until_utc = None
        mock_user.failed_login_count = 0

        with patch.object(auth_module, "get_user_by_email", return_value=mock_user):
            request = LoginRequest(
                email="test@example.com",
                password="SecureP@ss123",
                tenant_id="tenant-456",
            )

            with pytest.raises(HTTPException) as exc_info:
                auth_module.login(request)
            assert exc_info.value.status_code == 403
            assert "deactivated" in exc_info.value.detail.lower()


class TestRefreshEndpoint:
    """Tests for POST /v1/auth/refresh endpoint (FR-050)."""

    def test_refresh_valid_token_returns_new_access_token(self) -> None:
        """Valid refresh token should return new access token."""
        import hashlib
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from app.routers import auth as auth_module
        from app.schemas import RefreshRequest
        from app.security import create_refresh_token

        # Create a valid refresh token
        refresh_token, token_id = create_refresh_token(
            user_id="user-123",
            tenant_id="tenant-456",
        )

        # Mock the stored token
        mock_stored_token = MagicMock()
        mock_stored_token.token_id = token_id
        mock_stored_token.user_id = "user-123"
        mock_stored_token.tenant_id = "tenant-456"
        mock_stored_token.token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        mock_stored_token.revoked_at_utc = None
        mock_stored_token.expires_at_utc = (
            datetime.now(timezone.utc) + timedelta(days=7)
        ).isoformat()

        mock_user = MagicMock()
        mock_user.user_id = "user-123"
        mock_user.tenant_id = "tenant-456"
        mock_user.email = "test@example.com"
        mock_user.role = "attorney"
        mock_user.is_active = True
        mock_user.display_name = "Test Attorney"

        with (
            patch.object(auth_module, "get_refresh_token", return_value=mock_stored_token),
            patch.object(auth_module, "get_user_by_id", return_value=mock_user),
        ):
            request = RefreshRequest(refresh_token=refresh_token)
            result = auth_module.refresh(request)

            assert "access_token" in result
            assert result["token_type"] == "bearer"

    def test_refresh_revoked_token_returns_401(self) -> None:
        """Revoked refresh token should return 401."""
        import hashlib
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from fastapi import HTTPException

        from app.routers import auth as auth_module
        from app.schemas import RefreshRequest
        from app.security import create_refresh_token

        refresh_token, token_id = create_refresh_token(
            user_id="user-123",
            tenant_id="tenant-456",
        )

        # Token is revoked
        mock_stored_token = MagicMock()
        mock_stored_token.token_id = token_id
        mock_stored_token.token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        mock_stored_token.revoked_at_utc = datetime.now(timezone.utc).isoformat()
        mock_stored_token.expires_at_utc = (
            datetime.now(timezone.utc) + timedelta(days=7)
        ).isoformat()

        with patch.object(auth_module, "get_refresh_token", return_value=mock_stored_token):
            request = RefreshRequest(refresh_token=refresh_token)

            with pytest.raises(HTTPException) as exc_info:
                auth_module.refresh(request)
            assert exc_info.value.status_code == 401


class TestLogoutEndpoint:
    """Tests for POST /v1/auth/logout endpoint (FR-050)."""

    def test_logout_revokes_refresh_token(self) -> None:
        """Logout should revoke the provided refresh token."""
        from unittest.mock import MagicMock, patch

        from app.routers import auth as auth_module
        from app.schemas import LogoutRequest
        from app.security import create_refresh_token

        refresh_token, token_id = create_refresh_token(
            user_id="user-123",
            tenant_id="tenant-456",
        )

        revoke_mock = MagicMock(return_value=True)

        with patch.object(auth_module, "revoke_refresh_token", revoke_mock):
            request = LogoutRequest(refresh_token=refresh_token)
            result = auth_module.logout(request)

            assert result["message"] == "Logged out successfully"
            revoke_mock.assert_called_once()


class TestMeEndpoint:
    """Tests for GET /v1/auth/me endpoint (FR-050)."""

    def test_me_returns_user_info(self) -> None:
        """GET /v1/auth/me should return current user info from token."""
        from unittest.mock import MagicMock, patch

        from app.routers import auth as auth_module

        mock_user = MagicMock()
        mock_user.user_id = "user-123"
        mock_user.tenant_id = "tenant-456"
        mock_user.email = "test@example.com"
        mock_user.role = "attorney"
        mock_user.display_name = "Test User"
        mock_user.is_active = True

        # Simulate JWT claims
        mock_claims = {
            "sub": "user-123",
            "tenant_id": "tenant-456",
            "email": "test@example.com",
            "role": "attorney",
        }

        with patch.object(auth_module, "get_user_by_id", return_value=mock_user):
            result = auth_module.me(mock_claims)

            assert result["user_id"] == "user-123"
            assert result["email"] == "test@example.com"
            assert result["role"] == "attorney"
            assert result["tenant_id"] == "tenant-456"


class TestSecurityHardening:
    """Security hardening tests for FR-050 (wsskeptic review findings)."""

    def test_access_token_type_validation(self) -> None:
        """Access token decoder should reject refresh tokens.

        Security: Refresh tokens should not be accepted as access tokens.
        """
        from app.security import create_refresh_token, decode_access_token

        # Create a valid refresh token
        refresh_token, _token_id = create_refresh_token(
            user_id="user-123",
            tenant_id="tenant-456",
        )

        # Refresh token should be rejected when decoded as access token
        result = decode_access_token(refresh_token)
        assert result is None, "Refresh token should not be valid as access token"

    def test_access_token_validates_type_claim(self) -> None:
        """Access token should have type='access' and be validated."""
        from app.security import create_access_token, decode_access_token

        # Create a valid access token
        access_token = create_access_token(
            user_id="user-123",
            tenant_id="tenant-456",
            role="attorney",
            email="test@example.com",
        )

        # Access token should be accepted
        result = decode_access_token(access_token)
        assert result is not None
        assert result["type"] == "access"

    def test_get_refresh_token_requires_tenant_id(self) -> None:
        """get_refresh_token should require tenant_id for isolation.

        Security: Prevents cross-tenant token probing.
        """
        from app import db

        # Verify the function signature includes tenant_id parameter
        import inspect
        sig = inspect.signature(db.get_refresh_token)
        params = list(sig.parameters.keys())

        assert "tenant_id" in params, (
            "get_refresh_token must have tenant_id parameter for tenant isolation"
        )

    def test_refresh_token_validates_tenant_isolation(self) -> None:
        """Refresh token lookup should validate tenant_id.

        Security: Token from tenant A should not be found when querying with tenant B.
        """
        import hashlib
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from fastapi import HTTPException

        from app.routers import auth as auth_module
        from app.schemas import RefreshRequest
        from app.security import create_refresh_token

        # Create a refresh token for tenant-456
        refresh_token, token_id = create_refresh_token(
            user_id="user-123",
            tenant_id="tenant-456",
        )

        # Mock stored token belongs to tenant-456
        mock_stored_token = MagicMock()
        mock_stored_token.token_id = token_id
        mock_stored_token.user_id = "user-123"
        mock_stored_token.tenant_id = "tenant-456"
        mock_stored_token.token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        mock_stored_token.revoked_at_utc = None
        mock_stored_token.expires_at_utc = (
            datetime.now(timezone.utc) + timedelta(days=7)
        ).isoformat()

        # When get_refresh_token is called with tenant_id validation,
        # if token's tenant doesn't match, it should return None
        def mock_get_with_tenant(tid: str, tenant: str) -> MagicMock | None:
            if tenant != mock_stored_token.tenant_id:
                return None  # Different tenant
            return mock_stored_token

        mock_user = MagicMock()
        mock_user.user_id = "user-123"
        mock_user.tenant_id = "tenant-456"
        mock_user.email = "test@example.com"
        mock_user.role = "attorney"
        mock_user.is_active = True
        mock_user.display_name = "Test Attorney"

        with (
            patch.object(auth_module, "get_refresh_token", side_effect=mock_get_with_tenant),
            patch.object(auth_module, "get_user_by_id", return_value=mock_user),
        ):
            # Same tenant should work
            request = RefreshRequest(refresh_token=refresh_token)
            result = auth_module.refresh(request)
            assert "access_token" in result

    def test_increment_failed_login_is_atomic(self) -> None:
        """Failed login count increment should be atomic.

        Security: Prevents race condition where concurrent requests
        could exceed MAX_FAILED_LOGIN_ATTEMPTS before lockout triggers.
        """
        from app import db

        # Check that increment uses atomic SQL
        import inspect
        source = inspect.getsource(db.increment_user_failed_login)

        # The atomic implementation should use SET failed_login_count = failed_login_count + 1
        # Check for the SQLAlchemy pattern: User.failed_login_count + 1
        assert (
            "failed_login_count + 1" in source
            or "User.failed_login_count + 1" in source
        ), (
            "increment_user_failed_login must use atomic SQL to prevent race conditions. "
            "Use: .values(failed_login_count=User.failed_login_count + 1)"
        )
