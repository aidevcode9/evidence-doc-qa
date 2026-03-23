"""SSO (Single Sign-On) router for FR-051.

Provides endpoints for:
- GET /v1/auth/sso/microsoft - Redirect to Microsoft Entra ID login
- GET /v1/auth/sso/google - Redirect to Google Workspace login
- GET /v1/auth/sso/callback - Handle callback from either provider

Supports:
- Microsoft Entra ID (formerly Azure AD) for Microsoft 365 firms
- Google Workspace for Gmail-based firms
- PKCE flow for enhanced security
- JIT (Just-In-Time) user provisioning

Security:
- ID token signature validated via JWKS
- SSO state stored in database (not memory)
- Nonce validation prevents token replay
- Opaque state tokens (no sensitive data in URL)
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app import config
from app.db import (
    SSOState,
    create_user,
    get_and_delete_sso_state,
    get_user_by_email,
    store_refresh_token,
    store_sso_state,
    update_user_login_success,
)
from app.security import create_access_token, create_refresh_token
from app.telemetry import logger

router = APIRouter(prefix="/v1/auth/sso", tags=["sso"])

# HTTP client timeout (seconds)
_HTTP_TIMEOUT = 10.0

# JWKS cache: provider -> (keys, fetched_at)
_jwks_cache: dict[str, tuple[dict[str, Any], datetime]] = {}
_JWKS_CACHE_TTL = timedelta(hours=1)


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge.

    Returns:
        Tuple of (code_verifier, code_challenge)
    """
    # Generate 32 random bytes, base64url encode
    code_verifier = secrets.token_urlsafe(32)

    # S256: SHA256 hash of verifier, then base64url encode
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    return code_verifier, code_challenge


def _create_state_token(
    provider: str, tenant_id: str, code_verifier: str, nonce: str
) -> str:
    """Create an opaque state token and store data in database.

    Args:
        provider: SSO provider (microsoft, google)
        tenant_id: Application tenant ID
        code_verifier: PKCE code verifier
        nonce: Nonce for ID token validation

    Returns:
        Opaque random state token
    """
    # Generate opaque random token (no sensitive data in URL)
    state_token = secrets.token_urlsafe(32)

    # Store state data in database
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    store_sso_state(
        state_token=state_token,
        provider=provider,
        tenant_id=tenant_id,
        code_verifier=code_verifier,
        nonce=nonce,
        expires_at_utc=expires_at.isoformat(),
    )

    return state_token


def _validate_and_consume_state(state_token: str) -> SSOState:
    """Validate state token and remove from database (consume once).

    Args:
        state_token: The state token from callback

    Returns:
        SSOState data if valid

    Raises:
        HTTPException: If state is invalid or expired
    """
    state = get_and_delete_sso_state(state_token)
    if state is None:
        raise HTTPException(status_code=400, detail="Invalid or expired SSO state")

    return state


async def _get_jwks(provider: str) -> dict[str, Any]:
    """Fetch JWKS (JSON Web Key Set) from provider with caching.

    Args:
        provider: SSO provider (microsoft, google)

    Returns:
        JWKS dict with 'keys' array
    """
    # Check cache
    if provider in _jwks_cache:
        keys, fetched_at = _jwks_cache[provider]
        if datetime.now(timezone.utc) - fetched_at < _JWKS_CACHE_TTL:
            return keys

    # Determine JWKS URL
    if provider == "microsoft":
        jwks_url = f"https://login.microsoftonline.com/{config.MICROSOFT_TENANT_ID}/discovery/v2.0/keys"
    elif provider == "google":
        jwks_url = "https://www.googleapis.com/oauth2/v3/certs"
    else:
        raise HTTPException(status_code=400, detail="Unknown SSO provider")

    # Fetch JWKS
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        try:
            response = await client.get(jwks_url)
            response.raise_for_status()
            jwks: dict[str, Any] = response.json()
        except httpx.TimeoutException:
            logger.error(f"JWKS fetch timeout for {provider}")
            raise HTTPException(status_code=503, detail="SSO service temporarily unavailable")
        except httpx.HTTPError as e:
            logger.error(f"JWKS fetch failed for {provider}: {e}")
            raise HTTPException(status_code=503, detail="SSO service temporarily unavailable")

    # Cache
    _jwks_cache[provider] = (jwks, datetime.now(timezone.utc))
    return jwks


def _validate_id_token(id_token: str, provider: str, nonce: str, jwks: dict[str, Any]) -> dict[str, Any]:
    """Validate ID token signature and claims.

    Args:
        id_token: JWT ID token from provider
        provider: SSO provider for validation context
        nonce: Expected nonce value
        jwks: JWKS from provider

    Returns:
        Validated token claims

    Raises:
        HTTPException: If token is invalid
    """
    from jose import JWTError, jwt
    from jose.constants import ALGORITHMS

    # Determine expected audience and issuer
    if provider == "microsoft":
        audience = config.MICROSOFT_CLIENT_ID
        issuer = f"https://login.microsoftonline.com/{config.MICROSOFT_TENANT_ID}/v2.0"
    elif provider == "google":
        audience = config.GOOGLE_CLIENT_ID
        issuer = "https://accounts.google.com"
    else:
        raise HTTPException(status_code=400, detail="Unknown SSO provider")

    try:
        # Decode and validate with JWKS
        claims = jwt.decode(
            id_token,
            jwks,
            algorithms=[ALGORITHMS.RS256],
            audience=audience,
            issuer=issuer,
            options={"verify_at_hash": False},  # Not all providers include at_hash
        )
    except JWTError as e:
        logger.warning(f"ID token validation failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid ID token")

    # Validate nonce to prevent replay attacks
    token_nonce = claims.get("nonce")
    if token_nonce != nonce:
        logger.warning(f"Nonce mismatch: expected {nonce}, got {token_nonce}")
        raise HTTPException(status_code=400, detail="Invalid ID token")

    return claims


async def _exchange_code_for_tokens(
    provider: str, code: str, code_verifier: str
) -> dict[str, Any]:
    """Exchange authorization code for tokens.

    Args:
        provider: SSO provider (microsoft, google)
        code: Authorization code from callback
        code_verifier: PKCE code verifier

    Returns:
        Token response containing id_token
    """
    if provider == "microsoft":
        token_url = f"https://login.microsoftonline.com/{config.MICROSOFT_TENANT_ID}/oauth2/v2.0/token"
        data = {
            "client_id": config.MICROSOFT_CLIENT_ID,
            "client_secret": config.MICROSOFT_CLIENT_SECRET,
            "code": code,
            "redirect_uri": config.SSO_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        }
    elif provider == "google":
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "code": code,
            "redirect_uri": config.SSO_REDIRECT_URI,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        }
    else:
        raise HTTPException(status_code=400, detail="Unknown SSO provider")

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        try:
            response = await client.post(token_url, data=data)
        except httpx.TimeoutException:
            logger.error(f"Token exchange timeout for {provider}")
            raise HTTPException(status_code=503, detail="SSO service temporarily unavailable")
        except httpx.HTTPError as e:
            logger.error(f"Token exchange failed for {provider}: {e}")
            raise HTTPException(status_code=503, detail="SSO service temporarily unavailable")

        if response.status_code != 200:
            # Log full error server-side, return sanitized message to client
            logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=400,
                detail="SSO authentication failed. Please try again.",
            )
        result: dict[str, Any] = response.json()
        return result


def _extract_user_info(claims: dict[str, Any]) -> dict[str, Any]:
    """Extract user info from validated token claims.

    Args:
        claims: Validated ID token claims

    Returns:
        Dict with email, name from token claims
    """
    email = claims.get("email") or claims.get("preferred_username")
    name = claims.get("name") or claims.get("given_name", "")

    if not email:
        raise HTTPException(status_code=400, detail="Email not found in SSO response")

    return {"email": email.lower(), "name": name}


@router.get("/microsoft")
async def microsoft_login(tenant_id: str = Query(...)) -> RedirectResponse:
    """Redirect to Microsoft Entra ID login page.

    Args:
        tenant_id: Application tenant ID for the user

    Returns:
        Redirect to Microsoft authorization endpoint
    """
    if not config.MICROSOFT_SSO_ENABLED:
        raise HTTPException(status_code=404, detail="Microsoft SSO is not enabled")

    # Generate PKCE pair and nonce
    code_verifier, code_challenge = _generate_pkce_pair()
    nonce = secrets.token_urlsafe(16)

    # Create opaque state token (data stored in DB)
    state = _create_state_token("microsoft", tenant_id, code_verifier, nonce)

    # Build authorization URL
    auth_url = f"https://login.microsoftonline.com/{config.MICROSOFT_TENANT_ID}/oauth2/v2.0/authorize"
    params = {
        "client_id": config.MICROSOFT_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": config.SSO_REDIRECT_URI,
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    return RedirectResponse(url=f"{auth_url}?{urlencode(params)}")


@router.get("/google")
async def google_login(tenant_id: str = Query(...)) -> RedirectResponse:
    """Redirect to Google Workspace login page.

    Args:
        tenant_id: Application tenant ID for the user

    Returns:
        Redirect to Google authorization endpoint
    """
    if not config.GOOGLE_SSO_ENABLED:
        raise HTTPException(status_code=404, detail="Google SSO is not enabled")

    # Generate PKCE pair and nonce
    code_verifier, code_challenge = _generate_pkce_pair()
    nonce = secrets.token_urlsafe(16)

    # Create opaque state token (data stored in DB)
    state = _create_state_token("google", tenant_id, code_verifier, nonce)

    # Build authorization URL
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": config.SSO_REDIRECT_URI,
        "scope": "openid profile email",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    return RedirectResponse(url=f"{auth_url}?{urlencode(params)}")


@router.get("/callback")
async def sso_callback(
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """Handle SSO callback from Microsoft or Google (FR-053).

    Args:
        code: Authorization code from provider
        state: State token for CSRF protection

    Returns:
        Redirect to frontend /auth/callback with tokens in query params.
        Frontend stores tokens in httpOnly cookies for XSS protection.
    """
    # Validate state and get provider/tenant info from DB
    state_data = _validate_and_consume_state(state)
    provider = state_data.provider
    tenant_id = state_data.tenant_id
    code_verifier = state_data.code_verifier
    nonce = state_data.nonce

    # Exchange code for tokens
    token_response = await _exchange_code_for_tokens(provider, code, code_verifier)
    id_token = token_response.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="SSO authentication failed")

    # Fetch JWKS and validate ID token signature
    jwks = await _get_jwks(provider)
    claims = _validate_id_token(id_token, provider, nonce, jwks)

    # Extract user info from validated claims
    user_info = _extract_user_info(claims)
    email = user_info["email"]
    display_name = user_info["name"]

    # Find or create user
    user = get_user_by_email(email, tenant_id)

    if user is not None:
        # Existing user - verify auth provider matches
        if user.auth_provider != provider:
            # Don't reveal which provider - generic message
            raise HTTPException(
                status_code=409,
                detail="This email is already associated with another account. "
                "Contact your administrator for assistance.",
            )
        # Update last login
        update_user_login_success(user.user_id, tenant_id)
    else:
        # New user - create with Viewer role (JIT provisioning)
        import uuid

        user = create_user(
            user_id=str(uuid.uuid4()),
            email=email,
            tenant_id=tenant_id,
            display_name=display_name,
            role=config.SSO_DEFAULT_ROLE,
            auth_provider=provider,
            password_hash=None,  # No password for SSO users
        )

    # Create our JWT tokens
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

    # Redirect to frontend with tokens (FR-053)
    # Frontend will store tokens in httpOnly cookies
    params = urlencode({
        "access_token": access_token,
        "refresh_token": refresh_token,
    })
    frontend_callback = f"{config.FRONTEND_URL}/auth/callback?{params}"
    return RedirectResponse(url=frontend_callback, status_code=302)
