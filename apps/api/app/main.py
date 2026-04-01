import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import otel
from app.config import (
    AUTH_BYPASS_ENABLED,
    AUTH_MODE,
    DATA_DIR,
    RAW_DIR,
    ALLOWED_ORIGINS,
    ALLOW_UNVERIFIED,
    JWT_SECRET_KEY,
    RATE_LIMIT_ENABLED,
    STRICT_EVIDENCE,
)
from app.db import init_db
from app.indexing import ensure_index
from app.rate_limit import limiter as _shared_limiter
from app.telemetry import logger
from app.routers import health, ask, docs, metrics, export, auth, sso, admin, audit, matters

app = FastAPI(title="DocQ&A API", version="0.0.0")

# Setup Tracing
otel.setup_otel(app)

# Rate Limiting (NFR-012)
if RATE_LIMIT_ENABLED and _shared_limiter is not None:
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from slowapi.errors import RateLimitExceeded

    app.state.limiter = _shared_limiter

    async def _rate_limit_handler(
        request: Request,  # noqa: ARG001
        exc: RateLimitExceeded,
    ) -> JSONResponse:
        """Handle rate limit exceeded errors."""
        retry_after = str(exc.detail) if exc.detail else "60"
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please try again later."},
            headers={"Retry-After": retry_after},
        )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)  # type: ignore[arg-type]

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(sso.router)  # FR-051: SSO login
app.include_router(admin.router)  # FR-052: Admin dashboard
app.include_router(audit.router)  # FR-040: Audit logging
app.include_router(ask.router)
app.include_router(docs.router)
app.include_router(metrics.router)
app.include_router(export.router)
app.include_router(matters.router)


@app.on_event("startup")
def startup_event() -> None:
    # JWT secret validation (FR-050)
    if AUTH_MODE == "jwt" and JWT_SECRET_KEY == "dev-secret-key-change-in-production":
        raise RuntimeError(
            "SECURITY: JWT_SECRET_KEY is still the default value. "
            "Set a secure JWT_SECRET_KEY before starting in JWT mode "
            "(generate with: openssl rand -hex 32)"
        )

    # Security warnings for production (HIGH severity)
    if AUTH_BYPASS_ENABLED:
        logger.warning(
            "SECURITY WARNING: AUTH_BYPASS_ENABLED=True - ALL authentication is disabled! "
            "This is for LOCAL DEMOS ONLY. Never enable in production."
        )
    if ALLOW_UNVERIFIED:
        logger.warning(
            "SECURITY WARNING: ALLOW_UNVERIFIED=True - unverified chunks may be returned. "
            "This should be disabled in production environments."
        )
    if not STRICT_EVIDENCE:
        logger.warning(
            "SECURITY WARNING: STRICT_EVIDENCE=False - weak evidence may be returned. "
            "This should be enabled in production environments."
        )

    # Initialize Langfuse LLM observability (NFR-045)
    otel.setup_langfuse()

    # Initialize DB
    try:
        init_db()
    except Exception as e:
        logger.error(f"DB initialization failed: {e}")

    # Ensure Search Index exists
    try:
        ensure_index()
    except Exception as e:
        logger.error(f"Search index initialization failed: {e}")

    # Bootstrap data directories
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)


@app.on_event("shutdown")
def shutdown_event() -> None:
    # Flush Langfuse traces on shutdown (NFR-045)
    otel.flush_langfuse()
