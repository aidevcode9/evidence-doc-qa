"""Performance validation tests for NFR-011 and NFR-012.

Tests cover:
- LATENCY_TARGET_MS config default (8000ms)
- compute_metrics returns p50, p95, p99, max, total_requests, latency_by_component
- /v1/metrics endpoint returns enhanced fields
- ask_service stores latency_breakdown in trace_metadata
- 50 concurrent requests via ThreadPoolExecutor (no crash)
- Rate-limited endpoint returns 429
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class TestLatencyTargetConfig:
    """Verify LATENCY_TARGET_MS config exists with correct default."""

    def test_latency_target_config_exists(self) -> None:
        """LATENCY_TARGET_MS must be 8000 by default (NFR-011)."""
        from app.config import LATENCY_TARGET_MS

        assert LATENCY_TARGET_MS == 8000


class TestComputeMetricsEnhanced:
    """Verify compute_metrics returns p50, p95, p99, max, total_requests."""

    def _make_rows(self, latencies: list[int]) -> list[dict[str, Any]]:
        """Build mock telemetry rows with given latencies."""
        rows = []
        for i, lat in enumerate(latencies):
            rows.append({
                "request_id": f"req-{i}",
                "docs_snapshot_id": "snap-1",
                "prompt_version": "v1",
                "retrieval_version": "v1",
                "model_id": "gpt-4o",
                "parser_mode": "pypdf",
                "timestamp_utc": f"2026-03-15T00:{i // 60:02d}:{i % 60:02d}Z",
                "latency_ms": lat,
                "tokens_in": 100,
                "tokens_out": 50,
                "cost_est": 0.01,
                "cache_hit": False,
                "refusal_code": None,
                "failure_label": None,
                "trace_metadata": {
                    "latency_breakdown": {
                        "retrieval_ms": lat // 3,
                        "verification_ms": lat // 3,
                        "llm_ms": lat // 3,
                        "overhead_ms": lat - 3 * (lat // 3),
                    }
                },
                "langfuse_trace_id": None,
            })
        return rows

    def test_compute_metrics_p50_p95_p99_calculation(self) -> None:
        """compute_metrics must return p50, p95, p99 percentiles."""
        from app.telemetry import compute_metrics

        # 100 rows with latencies from 100 to 10000
        latencies = [100 + i * 100 for i in range(100)]
        rows = self._make_rows(latencies)

        result = compute_metrics(rows)

        assert "p50_latency_ms" in result
        assert "p95_latency_ms" in result
        assert "p99_latency_ms" in result
        assert "max_latency_ms" in result
        assert "total_requests" in result
        assert "latency_by_component" in result

        # Verify total_requests
        assert result["total_requests"] == 100

        # Verify max is the highest latency
        assert result["max_latency_ms"] == 10000

        # p50 should be near middle (~5000)
        assert 4000 <= result["p50_latency_ms"] <= 6000

        # p95 should be near 95th percentile (~9500)
        assert 9000 <= result["p95_latency_ms"] <= 10000

        # p99 should be near the top
        assert result["p99_latency_ms"] >= 9500

    def test_compute_metrics_empty_rows(self) -> None:
        """compute_metrics must return zero defaults when no rows."""
        from app.telemetry import compute_metrics

        result = compute_metrics([])

        assert result["p50_latency_ms"] == 0
        assert result["p95_latency_ms"] == 0
        assert result["p99_latency_ms"] == 0
        assert result["max_latency_ms"] == 0
        assert result["total_requests"] == 0
        assert result["latency_by_component"] == {}

    def test_compute_metrics_latency_by_component(self) -> None:
        """compute_metrics must average latency_breakdown per component."""
        from app.telemetry import compute_metrics

        rows = self._make_rows([300, 600, 900])

        result = compute_metrics(rows)
        lbc = result["latency_by_component"]

        # Each row has retrieval_ms = lat // 3, so averages are 100, 200, 300 -> avg 200
        assert "retrieval_ms" in lbc
        assert "verification_ms" in lbc
        assert "llm_ms" in lbc
        assert isinstance(lbc["retrieval_ms"], float)


class TestMetricsEndpointEnhanced:
    """Verify /v1/metrics endpoint returns enhanced fields."""

    def test_metrics_endpoint_returns_enhanced_fields(self) -> None:
        """Metrics endpoint should return p99, max, total_requests."""
        mock_metrics = {
            "window_start_utc": "2026-03-15T00:00:00Z",
            "window_end_utc": "2026-03-15T01:00:00Z",
            "p50_latency_ms": 500,
            "p95_latency_ms": 2000,
            "p99_latency_ms": 3000,
            "max_latency_ms": 5000,
            "total_requests": 42,
            "avg_cost_per_query": 0.01,
            "refusals_by_code": {},
            "cache_hit_rate": 0.1,
            "latency_by_component": {"retrieval_ms": 200.0},
        }

        with (
            patch("app.routers.metrics.load_window_telemetry", return_value=[]),
            patch("app.routers.metrics.compute_metrics", return_value=mock_metrics),
            patch("app.routers.metrics.METRICS_ADMIN_TOKEN", ""),
        ):
            from app.routers.metrics import router as metrics_router

            app = FastAPI()
            app.include_router(metrics_router)
            client = TestClient(app)

            response = client.get("/v1/metrics")
            assert response.status_code == 200
            data = response.json()

            assert "p99_latency_ms" in data
            assert data["p99_latency_ms"] == 3000
            assert "max_latency_ms" in data
            assert data["max_latency_ms"] == 5000
            assert "total_requests" in data
            assert data["total_requests"] == 42


class TestLatencyBreakdownStored:
    """Verify ask_service stores latency_breakdown in trace_metadata."""

    def test_latency_breakdown_stored(self) -> None:
        """record_telemetry must receive trace_metadata with latency_breakdown."""
        from app.schemas import AskRequest

        # Build a minimal mock environment
        fake_chunk = {
            "chunk_id": "c1",
            "doc_id": "d1",
            "doc_name": "test.pdf",
            "page_num": 1,
            "chunk_text": "This is a test chunk about the key terms of the agreement.",
            "rrf_score": 0.9,
        }

        with (
            patch("app.services.ask_service.policy.is_injection_attempt", return_value=False),
            patch("app.services.ask_service.retrieval.hybrid_search", return_value=([fake_chunk], {})),
            patch("app.services.ask_service.verification.is_enabled", return_value=False),
            patch("app.services.ask_service.STRICT_EVIDENCE", False),
            patch("app.services.ask_service.ALLOW_UNVERIFIED", True),
            patch("app.services.ask_service.get_latest_snapshot_for_matter", return_value="snap-1"),
            patch("app.services.ask_service.record_telemetry") as mock_telemetry,
            patch("app.services.ask_service.record_request_metrics"),
            patch("app.services.ask_service.safe_update_trace"),
            patch("app.services.ask_service.safe_update_observation"),
            patch("app.services.ask_service.safe_get_trace_id", return_value=None),
            patch("app.services.ask_service.redact_for_langfuse", return_value={}),
        ):
            from app.services.ask_service import execute_ask

            payload = AskRequest(question="What are the key terms?")
            execute_ask(
                payload,
                session_id=None,
                tenant_id="t1",
                matter_id="m1",
            )

            mock_telemetry.assert_called_once()
            call_kwargs = mock_telemetry.call_args.kwargs
            trace_meta = call_kwargs.get("trace_metadata", {})
            assert "latency_breakdown" in trace_meta
            breakdown = trace_meta["latency_breakdown"]
            assert "retrieval_ms" in breakdown
            assert "verification_ms" in breakdown
            assert "overhead_ms" in breakdown
            # All values must be non-negative ints
            for key in ("retrieval_ms", "verification_ms", "overhead_ms"):
                assert isinstance(breakdown[key], int)
                assert breakdown[key] >= 0


class TestConcurrentRequests:
    """Verify 50 concurrent requests don't crash (NFR-012)."""

    def test_concurrent_requests_no_crash(self) -> None:
        """50 concurrent GET /healthz requests via ThreadPoolExecutor must all succeed."""
        from app.routers.health import router as health_router

        app = FastAPI()
        app.include_router(health_router)
        client = TestClient(app)

        def make_request() -> int:
            resp = client.get("/healthz")
            return resp.status_code

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 50
        assert all(code == 200 for code in results)


class TestRateLimitReturns429:
    """Verify rate-limited endpoint returns 429 when exceeded."""

    def test_rate_limit_returns_429(self) -> None:
        """A rate-limited endpoint must return 429 after exceeding the limit."""
        from slowapi import Limiter
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address
        from fastapi.responses import JSONResponse

        app = FastAPI()
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_handler(
            request: Request,
            exc: RateLimitExceeded,
        ) -> JSONResponse:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."},
                headers={"Retry-After": "60"},
            )

        @app.get("/v1/test-rate")
        @limiter.limit("3/minute")
        async def test_endpoint(request: Request) -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        # First 3 requests should succeed
        for _ in range(3):
            response = client.get("/v1/test-rate")
            assert response.status_code == 200

        # 4th request should be rate limited
        response = client.get("/v1/test-rate")
        assert response.status_code == 429
        assert "rate limit" in response.json()["detail"].lower()


class TestAzureSearchTimeout:
    """[PERF-1] Verify Azure Search HTTP call has timeout."""

    def test_urlopen_called_with_timeout(self) -> None:
        """_request_azure_search must pass timeout=15 to urlopen."""
        import io
        import json
        from unittest.mock import patch, MagicMock

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"value": []}).encode()
        mock_response.__enter__ = MagicMock(return_value=io.BytesIO(json.dumps({"value": []}).encode()))
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("app.retrieval.urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            from app.retrieval import _request_azure_search

            _request_azure_search("https://example.com/search", {"search": "test"})

            mock_urlopen.assert_called_once()
            call_args = mock_urlopen.call_args
            # timeout should be passed as keyword arg
            assert call_args.kwargs.get("timeout") == 15 or (
                len(call_args.args) >= 2 and call_args.args[1] == 15
            ), f"Expected timeout=15, got args={call_args.args}, kwargs={call_args.kwargs}"


class TestDatabasePoolConfig:
    """[PERF-2] Verify database engine does NOT use NullPool."""

    def test_engine_does_not_use_nullpool(self) -> None:
        """_engine() must not use NullPool — should use QueuePool with connection pooling."""
        from unittest.mock import patch
        from sqlalchemy.pool import NullPool

        with patch("app.db.DATABASE_URL", "sqlite:///test.db"):
            from app.db import _engine

            engine = _engine()
            assert not isinstance(engine.pool, NullPool), \
                f"Expected QueuePool, got {type(engine.pool).__name__}"
            engine.dispose()


class TestQueryCacheDefault:
    """[PERF-4] Verify QUERY_CACHE_ENABLED defaults to True."""

    def test_query_cache_enabled_by_default(self) -> None:
        """QUERY_CACHE_ENABLED must default to True (enabled)."""
        from app.config import QUERY_CACHE_ENABLED

        assert QUERY_CACHE_ENABLED is True, \
            f"Expected QUERY_CACHE_ENABLED=True, got {QUERY_CACHE_ENABLED}"


class TestParallelVerification:
    """Verify parallel verification reduces latency and preserves correctness (NFR-011)."""

    def test_parallel_verification_faster_than_sequential(self) -> None:
        """3 verification calls sleeping 1s each should complete in <2s when parallelized."""
        import time

        def mock_verify(
            question: str,
            chunk_text: str,
            *,
            request_id: str | None = None,
            chunk_id: str | None = None,
        ) -> tuple[str, str | None, str, dict[str, Any]]:
            time.sleep(1.0)
            return ("rejected", None, "NOT_FOUND", {"prompt_tokens": 10, "completion_tokens": 5})

        candidates = [
            {"chunk_id": f"c{i}", "chunk_text": f"text {i}", "doc_id": "d1", "page_num": 1}
            for i in range(3)
        ]

        with patch("app.services.ask_service.verification.verify_relevance", side_effect=mock_verify):
            from app.services.ask_service import _verify_candidates_parallel

            start = time.perf_counter()
            results = _verify_candidates_parallel("What is X?", candidates, request_id="req-1")
            elapsed = time.perf_counter() - start

        assert elapsed < 2.0, f"Parallel verification took {elapsed:.2f}s, expected <2s"
        assert len(results) == 3

    def test_parallel_verification_preserves_order(self) -> None:
        """Results must come back in original candidate order regardless of completion order."""
        import time

        def mock_verify(
            question: str,
            chunk_text: str,
            *,
            request_id: str | None = None,
            chunk_id: str | None = None,
        ) -> tuple[str, str | None, str, dict[str, Any]]:
            # Stagger sleep so they complete in reverse order
            delay = {"c0": 0.3, "c1": 0.2, "c2": 0.1}.get(chunk_id or "", 0.1)
            time.sleep(delay)
            status = {"c0": "verified", "c1": "rejected", "c2": "rejected"}.get(chunk_id or "", "rejected")
            return (status, f"span-{chunk_id}" if status == "verified" else None, "FOUND" if status == "verified" else "NOT_FOUND", {})

        candidates = [
            {"chunk_id": "c0", "chunk_text": "text 0", "doc_id": "d1", "page_num": 1},
            {"chunk_id": "c1", "chunk_text": "text 1", "doc_id": "d1", "page_num": 2},
            {"chunk_id": "c2", "chunk_text": "text 2", "doc_id": "d1", "page_num": 3},
        ]

        with patch("app.services.ask_service.verification.verify_relevance", side_effect=mock_verify):
            from app.services.ask_service import _verify_candidates_parallel

            results = _verify_candidates_parallel("What is X?", candidates, request_id="req-2")

        # Results must be in candidate order: c0, c1, c2
        assert results[0][0]["chunk_id"] == "c0"
        assert results[1][0]["chunk_id"] == "c1"
        assert results[2][0]["chunk_id"] == "c2"

        # c0 should be verified
        assert results[0][1] == "verified"
        assert results[0][2] == "span-c0"

    def test_parallel_verification_accumulates_costs(self) -> None:
        """Token counts from all parallel verification calls must be returned."""

        def mock_verify(
            question: str,
            chunk_text: str,
            *,
            request_id: str | None = None,
            chunk_id: str | None = None,
        ) -> tuple[str, str | None, str, dict[str, Any]]:
            tokens = {"c0": 100, "c1": 200, "c2": 300}.get(chunk_id or "", 0)
            return ("rejected", None, "NOT_FOUND", {"prompt_tokens": tokens, "completion_tokens": tokens // 2})

        candidates = [
            {"chunk_id": "c0", "chunk_text": "text 0", "doc_id": "d1", "page_num": 1},
            {"chunk_id": "c1", "chunk_text": "text 1", "doc_id": "d1", "page_num": 2},
            {"chunk_id": "c2", "chunk_text": "text 2", "doc_id": "d1", "page_num": 3},
        ]

        with patch("app.services.ask_service.verification.verify_relevance", side_effect=mock_verify):
            from app.services.ask_service import _verify_candidates_parallel

            results = _verify_candidates_parallel("What is X?", candidates, request_id="req-3")

        # All 3 results should have their respective token counts
        total_prompt = sum(r[4].get("prompt_tokens", 0) for r in results)
        total_completion = sum(r[4].get("completion_tokens", 0) for r in results)
        assert total_prompt == 600  # 100 + 200 + 300
        assert total_completion == 300  # 50 + 100 + 150
