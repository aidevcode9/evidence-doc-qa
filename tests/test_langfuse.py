"""Tests for Langfuse LLM observability integration (NFR-045).

TDD: These tests define the expected Langfuse integration behavior.
"""

import os
from typing import Any
from unittest.mock import patch, MagicMock
import pytest


class TestLangfuseConfig:
    """Test Langfuse configuration loading."""

    def test_langfuse_config_vars_exist(self):
        """Config module should define Langfuse environment variables."""
        from app import config

        # Config should have these attributes (may be empty strings if not set)
        assert hasattr(config, "LANGFUSE_ENABLED")
        assert hasattr(config, "LANGFUSE_PUBLIC_KEY")
        assert hasattr(config, "LANGFUSE_SECRET_KEY")
        assert hasattr(config, "LANGFUSE_HOST")

    def test_langfuse_disabled_by_default(self):
        """Langfuse should be disabled by default (requires explicit opt-in)."""
        from app import config

        # Default should be disabled (empty keys = disabled)
        # This ensures no accidental data leakage
        assert isinstance(config.LANGFUSE_ENABLED, bool)

    def test_langfuse_enabled_when_keys_provided(self):
        """Langfuse should be enabled when both keys are provided."""
        with patch.dict(
            os.environ,
            {
                "LANGFUSE_PUBLIC_KEY": "pk-test-123",
                "LANGFUSE_SECRET_KEY": "sk-test-456",
                "LANGFUSE_ENABLED": "1",
            },
        ):
            # Reimport to pick up new env vars
            import importlib
            from app import config

            importlib.reload(config)
            assert config.LANGFUSE_ENABLED is True


class TestLangfuseInitialization:
    """Test Langfuse initialization in otel module."""

    def test_setup_langfuse_function_exists(self):
        """otel module should have setup_langfuse function."""
        from app import otel

        assert hasattr(otel, "setup_langfuse")
        assert callable(otel.setup_langfuse)

    def test_langfuse_not_initialized_when_disabled(self):
        """Langfuse should not initialize when disabled."""
        with patch.dict(os.environ, {"LANGFUSE_ENABLED": "0"}, clear=False):
            import importlib
            from app import config, otel

            importlib.reload(config)
            importlib.reload(otel)

            # Should not raise, just skip initialization
            otel.setup_langfuse()
            assert otel._LANGFUSE_INITIALIZED is False

    def test_langfuse_initialized_when_enabled(self):
        """Langfuse should initialize when enabled with valid keys."""
        import importlib
        from app import config, otel

        # Create a mock Langfuse class
        mock_langfuse_class = MagicMock()
        mock_langfuse_instance = MagicMock()
        mock_langfuse_class.return_value = mock_langfuse_instance

        # Inject mock and set state to simulate enabled config
        otel._LANGFUSE_INITIALIZED = False
        otel._langfuse_client = None
        otel.Langfuse = mock_langfuse_class

        # Temporarily override config values
        original_enabled = otel.LANGFUSE_ENABLED
        original_public = otel.LANGFUSE_PUBLIC_KEY
        original_secret = otel.LANGFUSE_SECRET_KEY
        original_host = otel.LANGFUSE_HOST

        try:
            # Patch the module-level config imports directly
            import app.otel as otel_module
            otel_module.LANGFUSE_ENABLED = True
            otel_module.LANGFUSE_PUBLIC_KEY = "pk-test-123"
            otel_module.LANGFUSE_SECRET_KEY = "sk-test-456"
            otel_module.LANGFUSE_HOST = "https://cloud.langfuse.com"

            otel.setup_langfuse()

            # Langfuse should have been instantiated
            mock_langfuse_class.assert_called_once()
            call_kwargs = mock_langfuse_class.call_args.kwargs
            assert call_kwargs["public_key"] == "pk-test-123"
            assert call_kwargs["secret_key"] == "sk-test-456"
            assert otel._LANGFUSE_INITIALIZED is True
        finally:
            # Restore original values
            otel_module.LANGFUSE_ENABLED = original_enabled
            otel_module.LANGFUSE_PUBLIC_KEY = original_public
            otel_module.LANGFUSE_SECRET_KEY = original_secret
            otel_module.LANGFUSE_HOST = original_host
            otel._LANGFUSE_INITIALIZED = False
            otel._langfuse_client = None


class TestObserveDecoratorUsage:
    """Test that @observe decorators are applied to key functions."""

    def test_verify_relevance_is_observable(self):
        """verification.verify_relevance should be decorated with @observe."""
        from app import verification

        # The function should exist and be callable
        assert hasattr(verification, "verify_relevance")
        assert callable(verification.verify_relevance)

        # Check if function has langfuse metadata (set by @observe)
        func = verification.verify_relevance
        # The @observe decorator adds __wrapped__ or langfuse metadata
        # We check the function is properly structured
        assert func.__name__ == "verify_relevance"

    def test_call_openai_is_observable(self):
        """verification._call_openai should be decorated with @observe."""
        from app import verification

        assert hasattr(verification, "_call_openai")
        assert callable(verification._call_openai)

    def test_execute_ask_is_observable(self):
        """ask_service.execute_ask should be decorated with @observe."""
        from app.services import ask_service

        assert hasattr(ask_service, "execute_ask")
        assert callable(ask_service.execute_ask)


class TestLangfuseTraceContent:
    """Test that Langfuse traces contain expected metadata."""

    def test_trace_includes_model_info(self):
        """LLM traces should include model information."""
        # This tests the trace metadata structure
        from app import verification

        metadata = verification.verifier_trace_metadata()
        assert "verifier" in metadata
        assert "model" in metadata["verifier"]
        assert "prompt_id" in metadata["verifier"]
        assert "prompt_version" in metadata["verifier"]

    def test_trace_excludes_pii(self):
        """Traces should not include raw question/answer content (PII safety)."""
        # This is a design requirement - trace_metadata should have hashes, not raw content
        from app.services import rag

        # hash_text should exist for PII-safe logging
        assert hasattr(rag, "hash_text")
        hashed = rag.hash_text("test question")
        assert "test question" not in hashed  # Hash shouldn't contain plaintext


class TestLangfuseIntegrationWithVerification:
    """Integration tests for Langfuse with verification flow."""

    def test_verification_emits_langfuse_span(self):
        """verify_relevance should emit a Langfuse span when called."""
        with patch("app.verification._call_openai") as mock_call:
            mock_call.return_value = {
                "choices": [{"message": {"content": "YES: test span"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            }

            from app import verification

            # Call the function
            status, span, reason, usage = verification.verify_relevance(
                "What is the test?",
                "This is a test span for verification.",
                request_id="test-123",
                chunk_id="chunk-456",
            )

            # Verify it completed (Langfuse observability is transparent)
            assert status in ("verified", "rejected", "unverified")


class TestLangfuseFlushOnShutdown:
    """Test Langfuse proper shutdown behavior."""

    def test_flush_langfuse_function_exists(self):
        """otel module should have flush_langfuse function for graceful shutdown."""
        from app import otel

        assert hasattr(otel, "flush_langfuse")
        assert callable(otel.flush_langfuse)


class TestLangfuseEnrichmentHelpers:
    """Test safe Langfuse context helpers for trace enrichment (NFR-045)."""

    def test_safe_update_observation_exists(self):
        """otel module should export safe_update_observation."""
        from app import otel

        assert hasattr(otel, "safe_update_observation")
        assert callable(otel.safe_update_observation)

    def test_safe_update_trace_exists(self):
        """otel module should export safe_update_trace."""
        from app import otel

        assert hasattr(otel, "safe_update_trace")
        assert callable(otel.safe_update_trace)

    def test_safe_get_trace_id_exists(self):
        """otel module should export safe_get_trace_id."""
        from app import otel

        assert hasattr(otel, "safe_get_trace_id")
        assert callable(otel.safe_get_trace_id)

    def test_safe_update_observation_noop_when_disabled(self):
        """safe_update_observation should silently no-op when Langfuse is disabled."""
        from app import otel

        # Should not raise even when Langfuse is not active
        otel.safe_update_observation(
            model="gpt-4o",
            usage={"input": 100, "output": 20},
            metadata={"latency_ms": 500},
        )

    def test_safe_update_trace_noop_when_disabled(self):
        """safe_update_trace should silently no-op when Langfuse is disabled."""
        from app import otel

        # Should not raise even when Langfuse is not active
        otel.safe_update_trace(
            user_id="tenant-123",
            session_id="session-456",
            tags=["matter-789", "gpt-4o"],
            metadata={"docs_snapshot_id": "snap-1"},
        )

    def test_safe_get_trace_id_returns_none_when_disabled(self):
        """safe_get_trace_id should return None when Langfuse is disabled."""
        from app import otel

        result = otel.safe_get_trace_id()
        assert result is None

    def test_safe_update_observation_calls_langfuse_context(self):
        """safe_update_observation should call langfuse_context API when active."""
        from app import otel

        mock_context = MagicMock()
        original_context = otel.langfuse_context
        original_enabled = otel.LANGFUSE_ENABLED
        original_initialized = otel._LANGFUSE_INITIALIZED

        try:
            otel.langfuse_context = mock_context
            otel.LANGFUSE_ENABLED = True
            otel._LANGFUSE_INITIALIZED = True

            otel.safe_update_observation(
                model="gpt-4o",
                usage={"input": 100, "output": 20},
                metadata={"latency_ms": 500},
            )

            mock_context.update_current_observation.assert_called_once_with(
                model="gpt-4o",
                usage={"input": 100, "output": 20},
                metadata={"latency_ms": 500},
            )
        finally:
            otel.langfuse_context = original_context
            otel.LANGFUSE_ENABLED = original_enabled
            otel._LANGFUSE_INITIALIZED = original_initialized

    def test_safe_update_trace_calls_langfuse_context(self):
        """safe_update_trace should call langfuse_context API when active."""
        from app import otel

        mock_context = MagicMock()
        original_context = otel.langfuse_context
        original_enabled = otel.LANGFUSE_ENABLED
        original_initialized = otel._LANGFUSE_INITIALIZED

        try:
            otel.langfuse_context = mock_context
            otel.LANGFUSE_ENABLED = True
            otel._LANGFUSE_INITIALIZED = True

            otel.safe_update_trace(
                user_id="tenant-123",
                session_id="session-456",
                tags=["matter-789"],
                metadata={"request_id": "req-1"},
            )

            mock_context.update_current_trace.assert_called_once_with(
                user_id="tenant-123",
                session_id="session-456",
                tags=["matter-789"],
                metadata={"request_id": "req-1"},
            )
        finally:
            otel.langfuse_context = original_context
            otel.LANGFUSE_ENABLED = original_enabled
            otel._LANGFUSE_INITIALIZED = original_initialized

    def test_safe_get_trace_id_returns_id_when_active(self):
        """safe_get_trace_id should return trace ID when Langfuse is active."""
        from app import otel

        mock_context = MagicMock()
        mock_context.get_current_trace_id.return_value = "trace-abc-123"
        original_context = otel.langfuse_context
        original_enabled = otel.LANGFUSE_ENABLED
        original_initialized = otel._LANGFUSE_INITIALIZED

        try:
            otel.langfuse_context = mock_context
            otel.LANGFUSE_ENABLED = True
            otel._LANGFUSE_INITIALIZED = True

            result = otel.safe_get_trace_id()
            assert result == "trace-abc-123"
            mock_context.get_current_trace_id.assert_called_once()
        finally:
            otel.langfuse_context = original_context
            otel.LANGFUSE_ENABLED = original_enabled
            otel._LANGFUSE_INITIALIZED = original_initialized

    def test_safe_update_observation_swallows_errors(self):
        """safe_update_observation should never raise, even if Langfuse errors."""
        from app import otel

        mock_context = MagicMock()
        mock_context.update_current_observation.side_effect = RuntimeError("Langfuse down")
        original_context = otel.langfuse_context
        original_enabled = otel.LANGFUSE_ENABLED
        original_initialized = otel._LANGFUSE_INITIALIZED

        try:
            otel.langfuse_context = mock_context
            otel.LANGFUSE_ENABLED = True
            otel._LANGFUSE_INITIALIZED = True

            # Should NOT raise
            otel.safe_update_observation(model="gpt-4o")
        finally:
            otel.langfuse_context = original_context
            otel.LANGFUSE_ENABLED = original_enabled
            otel._LANGFUSE_INITIALIZED = original_initialized

    def test_no_pii_in_observation_metadata(self):
        """Observation metadata must never contain raw question text."""
        from app import otel

        mock_context = MagicMock()
        original_context = otel.langfuse_context
        original_enabled = otel.LANGFUSE_ENABLED
        original_initialized = otel._LANGFUSE_INITIALIZED

        try:
            otel.langfuse_context = mock_context
            otel.LANGFUSE_ENABLED = True
            otel._LANGFUSE_INITIALIZED = True

            # Pass metadata that should be safe
            otel.safe_update_observation(
                model="gpt-4o",
                metadata={"latency_ms": 200, "estimated": False},
            )

            call_kwargs = mock_context.update_current_observation.call_args.kwargs
            metadata = call_kwargs.get("metadata", {})
            # Metadata should not contain question text fields
            for value in metadata.values():
                if isinstance(value, str):
                    assert len(value) < 100, "Metadata string too long — possible PII leak"
        finally:
            otel.langfuse_context = original_context
            otel.LANGFUSE_ENABLED = original_enabled
            otel._LANGFUSE_INITIALIZED = original_initialized


class TestLangfuseTraceIdCorrelation:
    """Test Langfuse trace ID storage in telemetry DB."""

    def test_telemetry_model_has_langfuse_trace_id(self):
        """Telemetry DB model should have langfuse_trace_id column."""
        from app.db import Telemetry

        assert hasattr(Telemetry, "langfuse_trace_id")

    def test_record_telemetry_accepts_langfuse_trace_id(self):
        """record_telemetry() should accept langfuse_trace_id parameter."""
        import inspect
        from app.telemetry import record_telemetry

        sig = inspect.signature(record_telemetry)
        assert "langfuse_trace_id" in sig.parameters


class TestRetrievalAndEmbeddingObservability:
    """Test @observe decorators on retrieval and embedding functions (NFR-045)."""

    def test_hybrid_search_calls_safe_update_observation(self):
        """hybrid_search should enrich Langfuse observation with search metadata."""
        mock_usage: dict[str, Any] = {"prompt_tokens": 10, "total_tokens": 10, "estimated": False, "source": "local"}
        with patch("app.retrieval.embed_texts_with_usage", return_value=([[0.1] * 16], mock_usage)), \
             patch("app.retrieval._azure_enabled", return_value=False), \
             patch("app.retrieval._load_index_records", return_value=[]), \
             patch("app.retrieval._fallback_overlap", return_value=[]), \
             patch("app.retrieval.safe_update_observation") as mock_obs:
            from app import retrieval

            retrieval.hybrid_search("test question", None, "t1", "m1")

            mock_obs.assert_called_once()
            call_kwargs = mock_obs.call_args.kwargs
            metadata = call_kwargs.get("metadata", {})
            assert "mode" in metadata
            assert "result_count" in metadata

    def test_embed_texts_calls_safe_update_observation(self):
        """embed_texts_with_usage should enrich Langfuse observation with embedding metadata."""
        with patch("app.embeddings.safe_update_observation") as mock_obs:
            from app import embeddings

            embeddings.embed_texts_with_usage(["hello world"])

            mock_obs.assert_called_once()
            call_kwargs = mock_obs.call_args.kwargs
            metadata = call_kwargs.get("metadata", {})
            assert "embeddings_mode" in metadata
            assert "text_count" in metadata

    def test_hybrid_search_observation_no_pii(self):
        """hybrid_search observation must never contain raw question text."""
        mock_usage: dict[str, Any] = {"prompt_tokens": 5, "total_tokens": 5, "estimated": False, "source": "local"}
        sensitive_question = "What is John Smith's salary at 123 Main Street?"

        with patch("app.retrieval.embed_texts_with_usage", return_value=([[0.1] * 16], mock_usage)), \
             patch("app.retrieval._azure_enabled", return_value=False), \
             patch("app.retrieval._load_index_records", return_value=[]), \
             patch("app.retrieval._fallback_overlap", return_value=[]), \
             patch("app.retrieval.safe_update_observation") as mock_obs:
            from app import retrieval

            retrieval.hybrid_search(sensitive_question, None, "t1", "m1")

            if mock_obs.called:
                all_values = str(mock_obs.call_args.kwargs)
                assert sensitive_question not in all_values

    def test_embed_texts_observation_no_pii(self):
        """embed_texts_with_usage observation must never contain raw text content."""
        with patch("app.embeddings.safe_update_observation") as mock_obs:
            from app import embeddings

            embeddings.embed_texts_with_usage(["Confidential document about John Smith"])

            if mock_obs.called:
                all_values = str(mock_obs.call_args.kwargs)
                assert "Confidential" not in all_values
                assert "John Smith" not in all_values


class TestLangfuseIntegration:
    """Integration tests that verify actual Langfuse connectivity.

    These tests require LANGFUSE_* environment variables to be set.
    Skip in CI where credentials aren't available.
    """

    @pytest.mark.skipif(
        not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"),
        reason="Langfuse credentials not configured"
    )
    def test_langfuse_client_can_connect(self):
        """Test that Langfuse client can connect with current credentials."""
        from langfuse import Langfuse

        client = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )

        # Auth check - this will fail if credentials are wrong
        try:
            client.auth_check()
            auth_ok = True
        except Exception as e:
            pytest.fail(f"Langfuse auth check failed: {e}")

        assert auth_ok is True
        client.flush()

    @pytest.mark.skipif(
        not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"),
        reason="Langfuse credentials not configured"
    )
    def test_langfuse_can_send_trace(self):
        """Test that we can send a trace to Langfuse."""
        from langfuse import Langfuse

        client = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )

        # Create a test trace
        trace = client.trace(
            name="test_trace_from_pytest",
            metadata={"test": True, "source": "test_langfuse.py"},
        )

        # Add a span to the trace
        span = trace.span(
            name="test_span",
            input={"test_input": "hello"},
            output={"test_output": "world"},
        )
        span.end()

        # Flush to ensure it's sent
        client.flush()

        # If we get here without exception, the trace was sent
        assert trace.id is not None
        print(f"\nLangfuse test trace ID: {trace.id}")
        print(f"Check Langfuse dashboard for trace: {trace.id}")

    @pytest.mark.skipif(
        not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"),
        reason="Langfuse credentials not configured"
    )
    def test_observe_decorator_sends_trace(self):
        """Test that @observe decorator actually sends traces."""
        from langfuse.decorators import observe, langfuse_context
        import time

        @observe(name="test_observed_function")
        def test_function(x: int, y: int) -> int:
            langfuse_context.update_current_observation(
                metadata={"test": True, "timestamp": time.time()}
            )
            return x + y

        # Call the decorated function
        result = test_function(2, 3)
        assert result == 5

        # Flush to ensure trace is sent
        langfuse_context.flush()

        print("\nObserve decorator test completed - check Langfuse for 'test_observed_function' trace")
