"""Authentication router for FR-050.

Provides endpoints for:
- POST /v1/auth/login - Email/password login
- POST /v1/auth/refresh - Refresh access token
- POST /v1/auth/logout - Revoke refresh token
- GET /v1/auth/me - Get current user info
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app import config
from app.db import (
    get_refresh_token,
    get_user_by_email,
    get_user_by_id,
    increment_user_failed_login,
    lock_user_account,
    revoke_refresh_token,
    store_refresh_token,
    update_user_login_success,
)
from app.schemas import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    RefreshResponse,
    UserInfo,
)
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    verify_password,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _is_account_locked(locked_until_utc: str | None) -> bool:
    """Check if account is currently locked."""
    if not locked_until_utc:
        return False
    locked_until = datetime.fromisoformat(locked_until_utc)
    return datetime.now(timezone.utc) < locked_until


@router.post("/login", response_model=LoginResponse)
def login(request: LoginRequest) -> dict[str, Any]:
    """Authenticate user with email/password.

    Returns access and refresh tokens on success.
    Returns 401 for invalid credentials (no user enumeration).
    Returns 403 for locked or deactivated accounts.
    """
    # Find user by email and tenant
    user = get_user_by_email(request.email, request.tenant_id)

    if user is None:
        # Return same error as invalid password to prevent user enumeration
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Check if account is deactivated
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account has been deactivated")

    # Check if account is locked
    if _is_account_locked(user.locked_until_utc):
        raise HTTPException(
            status_code=403, detail="Account is locked due to too many failed attempts"
        )

    # Verify password
    if not verify_password(request.password, user.password_hash or ""):
        # Increment failed login count
        new_count = increment_user_failed_login(user.user_id, user.tenant_id)

        # Lock account if max failures exceeded
        if new_count >= config.MAX_FAILED_LOGIN_ATTEMPTS:
            lock_user_account(
                user.user_id, user.tenant_id, config.ACCOUNT_LOCKOUT_MINUTES
            )

        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Success - reset failed count and update last login
    update_user_login_success(user.user_id, user.tenant_id)

    # Create tokens
    access_token = create_access_token(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        role=user.role,
        email=user.email,
        display_name=user.display_name or "",
    )

    refresh_token, token_id = create_refresh_token(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
    )

    # Store refresh token hash
    from datetime import timedelta

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=config.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    store_refresh_token(
        token_id=token_id,
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        token_hash=token_hash,
        expires_at_utc=expires_at.isoformat(),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/refresh", response_model=RefreshResponse)
def refresh(request: RefreshRequest) -> dict[str, Any]:
    """Refresh access token using a valid refresh token.

    Returns 401 for invalid, expired, or revoked tokens.
    """
    # Decode the refresh token to get claims
    claims = decode_refresh_token(request.refresh_token)
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    token_id = claims.get("jti")
    tenant_id = claims.get("tenant_id")
    if not token_id or not tenant_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token format")

    # Look up stored token with tenant isolation
    stored_token = get_refresh_token(token_id, tenant_id)
    if stored_token is None:
        raise HTTPException(status_code=401, detail="Refresh token not found")

    # Check if revoked
    if stored_token.revoked_at_utc is not None:
        raise HTTPException(status_code=401, detail="Refresh token has been revoked")

    # Check if expired
    expires_at = datetime.fromisoformat(stored_token.expires_at_utc)
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=401, detail="Refresh token has expired")

    # Verify token hash
    provided_hash = hashlib.sha256(request.refresh_token.encode()).hexdigest()
    if provided_hash != stored_token.token_hash:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Get user to verify still active
    user = get_user_by_id(stored_token.user_id, stored_token.tenant_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User account not found or inactive")

    # Create new access token
    access_token = create_access_token(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        role=user.role,
        email=user.email,
        display_name=user.display_name or "",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


@router.post("/logout", response_model=LogoutResponse)
def logout(request: LogoutRequest) -> dict[str, str]:
    """Revoke a refresh token (logout).

    Always returns success even if token is invalid (security best practice).
    """
    # Decode to get token ID
    claims = decode_refresh_token(request.refresh_token)
    if claims is not None:
        token_id = claims.get("jti")
        if token_id:
            revoke_refresh_token(token_id)

    return {"message": "Logged out successfully"}


def get_current_user_claims(authorization: str | None = None) -> dict[str, Any]:
    """Dependency to extract and validate JWT claims from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization[7:]  # Remove "Bearer " prefix
    claims = decode_access_token(token)
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")

    return claims


@router.get("/me", response_model=UserInfo)
def me(claims: dict[str, Any] = Depends(get_current_user_claims)) -> dict[str, Any]:
    """Get current user information from JWT token.

    Requires valid access token in Authorization header.
    """
    user = get_user_by_id(claims["sub"], claims["tenant_id"])
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user_id": user.user_id,
        "email": user.email,
        "role": user.role,
        "display_name": user.display_name,
        "tenant_id": user.tenant_id,
    }
