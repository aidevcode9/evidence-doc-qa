"""Security utilities for authentication (FR-050).

This module provides password hashing, JWT token creation/validation,
and password policy enforcement.

Password hashing uses Argon2id (OWASP recommended).
JWT tokens use HS256 with configurable expiration.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import (
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_ALGORITHM,
    JWT_REFRESH_TOKEN_EXPIRE_DAYS,
    JWT_SECRET_KEY,
    MIN_PASSWORD_LENGTH,
)

# Password hashing context using Argon2id
_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Password policy regex patterns
_HAS_UPPERCASE = re.compile(r"[A-Z]")
_HAS_LOWERCASE = re.compile(r"[a-z]")
_HAS_DIGIT = re.compile(r"\d")
_HAS_SPECIAL = re.compile(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]\\;'/`~]")


def hash_password(password: str) -> str:
    """Hash a password using Argon2id.

    Args:
        password: The plaintext password to hash.

    Returns:
        The hashed password string.
    """
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: The plaintext password to verify.
        hashed_password: The stored hash to verify against.

    Returns:
        True if the password matches, False otherwise.
    """
    if not plain_password:
        return False
    return _pwd_context.verify(plain_password, hashed_password)


def validate_password_policy(password: str) -> tuple[bool, str]:
    """Validate a password against the policy requirements.

    Requirements:
    - Minimum length (default 8 characters)
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: The password to validate.

    Returns:
        Tuple of (is_valid, error_message). If valid, error_message is empty.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"

    if not _HAS_UPPERCASE.search(password):
        return False, "Password must contain at least one uppercase letter"

    if not _HAS_LOWERCASE.search(password):
        return False, "Password must contain at least one lowercase letter"

    if not _HAS_DIGIT.search(password):
        return False, "Password must contain at least one digit"

    if not _HAS_SPECIAL.search(password):
        return False, "Password must contain at least one special character"

    return True, ""


def create_access_token(
    user_id: str,
    tenant_id: str,
    role: str,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: The user's unique identifier.
        tenant_id: The tenant identifier.
        role: The user's role (admin, attorney, etc.).
        email: The user's email address.
        expires_delta: Optional custom expiration time.

    Returns:
        The encoded JWT token string.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "email": email,
        "exp": expire,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "type": "access",
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token.

    Args:
        token: The JWT token string to decode.

    Returns:
        The decoded claims dictionary, or None if invalid/expired.

    Security:
        Validates that token type is 'access' to prevent refresh tokens
        from being accepted as access tokens.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        # Security: Reject refresh tokens used as access tokens
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def create_refresh_token(
    user_id: str,
    tenant_id: str,
    expires_delta: timedelta | None = None,
) -> tuple[str, str]:
    """Create a JWT refresh token.

    Args:
        user_id: The user's unique identifier.
        tenant_id: The tenant identifier.
        expires_delta: Optional custom expiration time.

    Returns:
        Tuple of (token, token_id). The token_id should be stored in the database
        for revocation tracking.
    """
    if expires_delta is None:
        expires_delta = timedelta(days=JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    token_id = str(uuid.uuid4())

    payload: dict[str, Any] = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "exp": expire,
        "iat": now,
        "jti": token_id,
        "type": "refresh",
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, token_id


def decode_refresh_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT refresh token.

    Args:
        token: The JWT token string to decode.

    Returns:
        The decoded claims dictionary, or None if invalid/expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        # Verify it's a refresh token
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None
