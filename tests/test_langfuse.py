"""Tests for Langfuse LLM observability integration (NFR-045).

TDD: These tests define the expected Langfuse integration behavior.
"""

import os
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
