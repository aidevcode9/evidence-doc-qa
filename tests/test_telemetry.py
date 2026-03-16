# tests/test_telemetry.py
"""
Tests for LLM telemetry instrumentation (NFR-030, NFR-022).

Every LLM call must emit OpenTelemetry spans with required attributes.
Telemetry must be recorded to the database for audit.
"""

import ast
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


def _make_openai_response(
    content: str = '{"verdict":"YES","span":"test","start":0,"end":4,"reason":"FOUND"}',
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> dict:
    """Build a fake Azure OpenAI chat completion response."""
    return {
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


class TestLLMTelemetry:
    """Tests for LLM call instrumentation via safe_update_observation."""

    def test_llm_call_emits_span(self) -> None:
        """verify_relevance must call safe_update_observation with model + usage."""
        from app.verification import verify_relevance

        fake_resp = _make_openai_response()

        with (
            patch("app.verification._call_openai", return_value=fake_resp),
            patch("app.verification._llm_enabled", return_value=True),
            patch("app.verification.safe_update_observation") as mock_obs,
        ):
            status, span, reason, usage = verify_relevance(
                "What is test?", "test chunk text",
                request_id="r1", chunk_id="c1",
            )

            mock_obs.assert_called_once()
            call_kwargs = mock_obs.call_args.kwargs
            assert "model" in call_kwargs
            assert "usage" in call_kwargs

    def test_llm_span_has_required_attributes(self) -> None:
        """Usage dict passed to safe_update_observation must have input and output int keys."""
        from app.verification import verify_relevance

        fake_resp = _make_openai_response()

        with (
            patch("app.verification._call_openai", return_value=fake_resp),
            patch("app.verification._llm_enabled", return_value=True),
            patch("app.verification.safe_update_observation") as mock_obs,
        ):
            verify_relevance("What is test?", "test chunk text")

            call_kwargs = mock_obs.call_args.kwargs
            usage = call_kwargs["usage"]
            assert "input" in usage
            assert "output" in usage
            assert isinstance(usage["input"], int)
            assert isinstance(usage["output"], int)

    def test_llm_span_records_token_counts(self) -> None:
        """Exact token counts from LLM response must pass through to observation."""
        from app.verification import verify_relevance

        fake_resp = _make_openai_response(prompt_tokens=200, completion_tokens=75)

        with (
            patch("app.verification._call_openai", return_value=fake_resp),
            patch("app.verification._llm_enabled", return_value=True),
            patch("app.verification.safe_update_observation") as mock_obs,
        ):
            verify_relevance("What is test?", "test chunk text")

            usage = mock_obs.call_args.kwargs["usage"]
            assert usage["input"] == 200
            assert usage["output"] == 75

    def test_llm_span_records_latency(self) -> None:
        """Metadata must contain latency_ms as a non-negative int."""
        from app.verification import verify_relevance

        fake_resp = _make_openai_response()

        with (
            patch("app.verification._call_openai", return_value=fake_resp),
            patch("app.verification._llm_enabled", return_value=True),
            patch("app.verification.safe_update_observation") as mock_obs,
        ):
            verify_relevance("What is test?", "test chunk text")

            metadata = mock_obs.call_args.kwargs["metadata"]
            assert "latency_ms" in metadata
            assert isinstance(metadata["latency_ms"], int)
            assert metadata["latency_ms"] >= 0

    def test_llm_error_records_exception(self) -> None:
        """On LLM error, verify_relevance must return 'unverified' (fail-closed)."""
        from app.verification import verify_relevance

        with (
            patch("app.verification._call_openai", side_effect=Exception("API timeout")),
            patch("app.verification._llm_enabled", return_value=True),
        ):
            status, span, reason, usage = verify_relevance(
                "What is test?", "test chunk text",
            )

            assert status == "unverified"
            assert reason == "UNVERIFIED"


class TestEmbeddingTelemetry:
    """Tests for embedding call instrumentation via safe_update_observation."""

    def test_embedding_call_emits_observation(self) -> None:
        """embed_texts_with_usage must call safe_update_observation."""
        from app.embeddings import embed_texts_with_usage

        with patch("app.embeddings.safe_update_observation") as mock_obs:
            # Local mode doesn't need Azure credentials
            with patch("app.embeddings.EMBEDDINGS_MODE", "local"):
                embed_texts_with_usage(["test text"])

            mock_obs.assert_called_once()
            call_kwargs = mock_obs.call_args.kwargs
            assert "metadata" in call_kwargs
            assert call_kwargs["metadata"]["text_count"] == 1


class TestTelemetryTable:
    """Tests for telemetry database logging."""

    def test_request_logged_to_database(self) -> None:
        """record_telemetry must call insert_telemetry with a Telemetry object."""
        from app.telemetry import record_telemetry

        with patch("app.telemetry.insert_telemetry") as mock_insert:
            record_telemetry(
                request_id="test-req-123",
                tenant_id="t1",
                matter_id="m1",
                docs_snapshot_id="snap-1",
                prompt_version="v3.1.0",
                retrieval_version="v3.1.0",
                model_id="gpt-4o",
                parser_mode="marker",
                timestamp_utc="2026-03-01T00:00:00Z",
                latency_ms=500,
                tokens_in=100,
                tokens_out=50,
                cost_est=0.01,
                cache_hit=False,
            )

            mock_insert.assert_called_once()
            telemetry_obj = mock_insert.call_args.args[0]
            assert telemetry_obj.request_id == "test-req-123"
            assert telemetry_obj.tenant_id == "t1"
            assert telemetry_obj.model_id == "gpt-4o"
            assert telemetry_obj.tokens_in == 100
            assert telemetry_obj.tokens_out == 50
            assert telemetry_obj.latency_ms == 500
            assert telemetry_obj.cost_est == 0.01
            assert telemetry_obj.cache_hit is False

    def test_record_telemetry_estimates_tokens_when_missing(self) -> None:
        """When tokens_in/out are None, estimate from question/answer lengths."""
        from app.telemetry import record_telemetry

        with patch("app.telemetry.insert_telemetry") as mock_insert:
            record_telemetry(
                request_id="test-req-est",
                tenant_id="t1",
                matter_id="m1",
                docs_snapshot_id="snap-1",
                prompt_version="v1",
                retrieval_version="v1",
                model_id="gpt-4o",
                parser_mode="marker",
                timestamp_utc="2026-03-01T00:00:00Z",
                latency_ms=100,
                tokens_in=None,
                tokens_out=None,
                question_len=400,  # ~100 tokens
                answer_len=200,    # ~50 tokens
            )

            telemetry_obj = mock_insert.call_args.args[0]
            assert telemetry_obj.tokens_in == 100  # 400 // 4
            assert telemetry_obj.tokens_out == 50   # 200 // 4


class TestNoBypassingTelemetry:
    """AST checks: LLM-calling modules must import telemetry wrappers."""

    def test_ask_service_uses_telemetry(self) -> None:
        """ask_service.py must import record_telemetry from app.telemetry."""
        ask_service_path = Path(__file__).parent.parent / "apps" / "api" / "app" / "services" / "ask_service.py"
        if not ask_service_path.exists():
            pytest.skip("ask_service.py not found")

        source = ask_service_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "telemetry" in node.module:
                imported_names.extend(alias.name for alias in node.names)

        assert "record_telemetry" in imported_names, (
            "ask_service.py must import record_telemetry from app.telemetry"
        )

    def test_verification_uses_otel(self) -> None:
        """verification.py must import safe_update_observation from app.otel."""
        verification_path = Path(__file__).parent.parent / "apps" / "api" / "app" / "verification.py"
        if not verification_path.exists():
            pytest.skip("verification.py not found")

        source = verification_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "otel" in node.module:
                imported_names.extend(alias.name for alias in node.names)

        assert "safe_update_observation" in imported_names, (
            "verification.py must import safe_update_observation from app.otel"
        )

    def test_embeddings_uses_otel(self) -> None:
        """embeddings.py must import safe_update_observation from app.otel."""
        embeddings_path = Path(__file__).parent.parent / "apps" / "api" / "app" / "embeddings.py"
        if not embeddings_path.exists():
            pytest.skip("embeddings.py not found")

        source = embeddings_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        imported_names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "otel" in node.module:
                imported_names.extend(alias.name for alias in node.names)

        assert "safe_update_observation" in imported_names, (
            "embeddings.py must import safe_update_observation from app.otel"
        )


class TestGenAISpanAttributes:
    """Tests for OTEL GenAI semantic convention span attributes (NFR-022).

    These tests will be RED until set_genai_span_attributes is implemented in otel.py.
    """

    def test_set_genai_span_attributes_exists(self) -> None:
        """set_genai_span_attributes function must exist in otel module."""
        from app.otel import set_genai_span_attributes

        assert callable(set_genai_span_attributes)

    def test_set_genai_span_attributes_sets_all_required(self) -> None:
        """Must set gen_ai.system, gen_ai.request.model, token counts, latency."""
        from app.otel import set_genai_span_attributes

        mock_span = MagicMock()
        mock_span.is_recording.return_value = True

        with (
            patch("app.otel.OTEL_ENABLED", True),
            patch("app.otel.trace") as mock_trace,
        ):
            mock_trace.get_current_span.return_value = mock_span

            set_genai_span_attributes(
                system="azure_openai",
                model="gpt-4o",
                prompt_tokens=100,
                completion_tokens=50,
                latency_ms=250,
                request_id="req-123",
            )

            set_calls = {
                call.args[0]: call.args[1]
                for call in mock_span.set_attribute.call_args_list
            }
            assert set_calls.get("gen_ai.system") == "azure_openai"
            assert set_calls.get("gen_ai.request.model") == "gpt-4o"
            assert set_calls.get("gen_ai.usage.prompt_tokens") == 100
            assert set_calls.get("gen_ai.usage.completion_tokens") == 50
            assert set_calls.get("llm.latency_ms") == 250
            assert set_calls.get("llm.request_id") == "req-123"

    def test_set_genai_span_attributes_noop_when_otel_disabled(self) -> None:
        """When OTEL is disabled, must not raise."""
        from app.otel import set_genai_span_attributes

        with patch("app.otel.OTEL_ENABLED", False):
            # Should not raise
            set_genai_span_attributes(
                system="azure_openai",
                model="gpt-4o",
                prompt_tokens=0,
                completion_tokens=0,
                latency_ms=0,
            )


class TestRequestMetrics:
    """Tests for OTEL custom metrics recording (NFR-022).

    These tests will be RED until record_request_metrics is implemented in otel.py.
    """

    def test_record_request_metrics_exists(self) -> None:
        """record_request_metrics function must exist in otel module."""
        from app.otel import record_request_metrics

        assert callable(record_request_metrics)

    def test_record_request_metrics_accepts_required_params(self) -> None:
        """Must accept latency_ms, tokens_in, tokens_out, cost_est, cache_hit."""
        from app.otel import record_request_metrics

        # Should not raise
        record_request_metrics(
            latency_ms=250,
            tokens_in=100,
            tokens_out=50,
            cost_est=0.01,
            cache_hit=False,
            component="ask",
        )

    def test_record_request_metrics_handles_refusal(self) -> None:
        """Must accept refusal_code parameter."""
        from app.otel import record_request_metrics

        # Should not raise
        record_request_metrics(
            latency_ms=50,
            tokens_in=0,
            tokens_out=0,
            cost_est=0.0,
            cache_hit=False,
            component="ask",
            refusal_code="LOW_CONFIDENCE",
        )
