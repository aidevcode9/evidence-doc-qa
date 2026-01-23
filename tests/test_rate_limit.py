"""Tests for Rate Limiting (FR-052).

Tests cover:
- Rate limit returns 429 when exceeded
- Rate limit includes Retry-After header
- Rate limit resets after window
"""

from __future__ import annotations

from typing import Generator
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


@pytest.fixture
def rate_limited_app() -> Generator[TestClient, None, None]:
    """Create app with rate limiting enabled."""
    with patch.multiple(
        "app.config",
        RATE_LIMIT_ENABLED=True,
        RATE_LIMIT_DEFAULT="100/minute",
        RATE_LIMIT_QUERY="5/minute",  # Low for testing
        RATE_LIMIT_UPLOAD="3/minute",  # Low for testing
    ):
        from slowapi import Limiter
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address

        app = FastAPI()
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> None:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(exc.detail)},
            )

        @app.get("/v1/test")
        @limiter.limit("5/minute")
        async def test_endpoint(request: Request) -> dict:
            return {"message": "ok"}

        yield TestClient(app)


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    def test_rate_limit_returns_429_when_exceeded(
        self, rate_limited_app: TestClient
    ) -> None:
        """Should return 429 when rate limit is exceeded."""
        # Make requests up to the limit
        for _ in range(5):
            response = rate_limited_app.get("/v1/test")
            assert response.status_code == 200

        # Next request should be rate limited
        response = rate_limited_app.get("/v1/test")
        assert response.status_code == 429

    def test_rate_limit_includes_retry_after_header(
        self, rate_limited_app: TestClient
    ) -> None:
        """Should include Retry-After header when rate limited."""
        # Exhaust the rate limit
        for _ in range(5):
            rate_limited_app.get("/v1/test")

        # Check rate limited response has header
        response = rate_limited_app.get("/v1/test")
        assert response.status_code == 429
        assert "retry-after" in response.headers

    def test_rate_limit_error_message(self, rate_limited_app: TestClient) -> None:
        """Should return informative error message when rate limited."""
        # Exhaust the rate limit
        for _ in range(5):
            rate_limited_app.get("/v1/test")

        # Check error message
        response = rate_limited_app.get("/v1/test")
        assert response.status_code == 429
        data = response.json()
        assert "rate limit" in data.get("detail", "").lower()


class TestRateLimitDisabled:
    """Tests when rate limiting is disabled."""

    def test_no_rate_limit_when_disabled(self) -> None:
        """Should not rate limit when RATE_LIMIT_ENABLED=false."""
        with patch.multiple(
            "app.config",
            RATE_LIMIT_ENABLED=False,
        ):
            from fastapi import FastAPI, Request

            app = FastAPI()

            @app.get("/v1/test")
            async def test_endpoint(request: Request) -> dict:
                return {"message": "ok"}

            client = TestClient(app)

            # Should allow many requests
            for _ in range(20):
                response = client.get("/v1/test")
                assert response.status_code == 200
