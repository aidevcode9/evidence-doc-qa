from pydantic import BaseModel, EmailStr

from evidence_shared.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    EvidenceSupport,
    DebugCandidate,
    VersionSnapshot,
    RefusalCode
)


# Authentication schemas (FR-050)


class LoginRequest(BaseModel):
    """Request body for POST /v1/auth/login."""

    email: EmailStr
    password: str
    tenant_id: str


class LoginResponse(BaseModel):
    """Response body for POST /v1/auth/login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires


class RefreshRequest(BaseModel):
    """Request body for POST /v1/auth/refresh."""

    refresh_token: str


class RefreshResponse(BaseModel):
    """Response body for POST /v1/auth/refresh."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class LogoutRequest(BaseModel):
    """Request body for POST /v1/auth/logout."""

    refresh_token: str


class LogoutResponse(BaseModel):
    """Response body for POST /v1/auth/logout."""

    message: str


class UserInfo(BaseModel):
    """User information returned by GET /v1/auth/me."""

    user_id: str
    email: str
    role: str
    display_name: str | None
    tenant_id: str


__all__ = [
    "AskRequest",
    "AskResponse",
    "Citation",
    "EvidenceSupport",
    "DebugCandidate",
    "VersionSnapshot",
    "RefusalCode",
    # Auth schemas (FR-050)
    "LoginRequest",
    "LoginResponse",
    "RefreshRequest",
    "RefreshResponse",
    "LogoutRequest",
    "LogoutResponse",
    "UserInfo",
]
