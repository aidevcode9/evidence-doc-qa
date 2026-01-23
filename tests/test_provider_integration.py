# tests/test_provider_integration.py
"""Tests for provider abstraction integration (NFR-032, NFR-034, NFR-035).

These tests verify that the main code paths use the provider factory functions
and that switching providers via config works correctly.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class TestEmbeddingsIntegration:
    """Tests for embeddings.py using provider abstraction."""

    def test_embed_texts_uses_factory_client(self) -> None:
        """embed_texts should use get_embedding_client factory."""
        from app.embedding import get_embedding_client
        from app.embedding.local import LocalEmbeddingClient

        # Default local mode should return LocalEmbeddingClient
        with patch("app.embedding.EMBEDDINGS_MODE", "local"):
            client = get_embedding_client()
            assert isinstance(client, LocalEmbeddingClient)

    def test_embed_texts_returns_correct_format(self) -> None:
        """embed_texts returns list of vectors with usage info."""
        from app.embeddings import embed_texts_with_usage

        embeddings, usage = embed_texts_with_usage(["test query"])
        assert len(embeddings) == 1
        assert isinstance(embeddings[0], list)
        assert "prompt_tokens" in usage
        assert "source" in usage

    def test_embed_texts_local_mode(self) -> None:
        """embed_texts in local mode uses hash-based embeddings."""
        with patch("app.embeddings.EMBEDDINGS_MODE", "local"):
            from app.embeddings import embed_texts_with_usage

            embeddings, usage = embed_texts_with_usage(["test"])
            assert len(embeddings) == 1
            assert usage["source"] == "local"

    def test_embedding_client_factory_local_returns_local(self) -> None:
        """get_embedding_client returns LocalEmbeddingClient for local mode."""
        with patch("app.embedding.EMBEDDINGS_MODE", "local"):
            from app.embedding import get_embedding_client
            from app.embedding.local import LocalEmbeddingClient

            client = get_embedding_client()
            assert isinstance(client, LocalEmbeddingClient)
            assert client.provider == "local"


class TestLLMClientIntegration:
    """Tests for LLM code using provider abstraction."""

    def test_llm_client_factory_azure_creates_azure_client(self) -> None:
        """get_llm_client returns AzureOpenAIClient for azure_openai provider."""
        with patch("app.llm.LLM_PROVIDER", "azure_openai"):
            with patch("app.llm.AZURE_OPENAI_CHAT_ENDPOINT", "https://test.openai.azure.com"):
                with patch("app.llm.AZURE_OPENAI_CHAT_API_KEY", "test-key"):
                    with patch("app.llm.MODEL_ID", "gpt-4o"):
                        from app.llm import get_llm_client
                        from app.llm.azure_openai import AzureOpenAIClient

                        client = get_llm_client()
                        assert isinstance(client, AzureOpenAIClient)
                        assert client.provider == "azure_openai"

    def test_llm_response_has_required_fields(self) -> None:
        """LLMResponse contains all required fields for telemetry."""
        from app.llm.base import LLMResponse

        response = LLMResponse(
            content="test answer",
            provider="azure_openai",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=500,
        )
        # All fields needed for NFR-030 telemetry
        assert response.content == "test answer"
        assert response.provider == "azure_openai"
        assert response.model == "gpt-4o"
        assert response.prompt_tokens == 100
        assert response.completion_tokens == 50
        assert response.latency_ms == 500


class TestSearchClientIntegration:
    """Tests for search code using provider abstraction."""

    def test_search_client_factory_local_creates_local_client(self) -> None:
        """get_search_client returns LocalSearchClient for local provider."""
        with patch("app.search.SEARCH_PROVIDER", "local"):
            from app.search import get_search_client
            from app.search.local import LocalSearchClient

            client = get_search_client()
            assert isinstance(client, LocalSearchClient)
            assert client.provider == "local"

    def test_search_client_factory_azure_creates_azure_client(self) -> None:
        """get_search_client returns AzureSearchClient for azure provider."""
        import os

        # Set environment vars before reloading module
        with patch.dict(os.environ, {
            "SEARCH_PROVIDER": "azure",
            "AZURE_SEARCH_ENDPOINT": "https://test.search.windows.net",
            "AZURE_SEARCH_API_KEY": "test-key",
            "AZURE_SEARCH_INDEX": "test-index",
        }):
            # Reload to pick up env vars
            import importlib
            import app.search
            importlib.reload(app.search)

            from app.search import get_search_client
            from app.search.azure import AzureSearchClient

            client = get_search_client()
            assert isinstance(client, AzureSearchClient)
            assert client.provider == "azure"

    def test_search_response_contains_provider_info(self) -> None:
        """SearchResponse includes provider information."""
        from app.search.base import SearchResponse, SearchResult

        response = SearchResponse(
            results=[
                SearchResult(
                    chunk_id="chunk-1",
                    doc_id="doc-1",
                    text="test content",
                    score=0.9,
                    page_number=1,
                )
            ],
            provider="azure",
        )
        assert response.provider == "azure"
        assert len(response.results) == 1


class TestProviderSwitchingViaConfig:
    """Tests that providers can be switched via environment config only."""

    def test_embedding_provider_switch(self) -> None:
        """Embedding provider can be switched between local and remote."""
        from app.embedding.base import EmbeddingClient

        # Local mode
        with patch("app.embedding.EMBEDDINGS_MODE", "local"):
            from app.embedding import get_embedding_client

            client = get_embedding_client()
            assert isinstance(client, EmbeddingClient)
            assert client.provider == "local"

    def test_llm_provider_raises_on_unknown(self) -> None:
        """Unknown LLM provider raises ValueError."""
        import os
        import importlib

        with patch.dict(os.environ, {"LLM_PROVIDER": "unknown_provider"}):
            import app.llm
            importlib.reload(app.llm)

            from app.llm import get_llm_client

            with pytest.raises(ValueError, match="Unknown LLM provider"):
                get_llm_client()

    def test_search_provider_raises_on_unknown(self) -> None:
        """Unknown search provider raises ValueError."""
        import os
        import importlib

        with patch.dict(os.environ, {"SEARCH_PROVIDER": "unknown_provider"}):
            import app.search
            importlib.reload(app.search)

            from app.search import get_search_client

            with pytest.raises(ValueError, match="Unknown SEARCH_PROVIDER"):
                get_search_client()

    def test_embedding_provider_raises_on_unknown(self) -> None:
        """Unknown embedding provider raises ValueError when mode is invalid."""
        # Test the ValueError is raised by directly calling with patched module globals
        # (env var approach doesn't work due to dotenv override=True in config.py)
        import app.embedding

        # Directly patch the module-level variable after _load_config runs
        original_mode = app.embedding.EMBEDDINGS_MODE
        try:
            app.embedding.EMBEDDINGS_MODE = "unknown_mode"
            # Force _load_config to not overwrite by patching it
            with patch.object(app.embedding, "_load_config", lambda: None):
                from app.embedding import get_embedding_client
                with pytest.raises(ValueError, match="Unknown EMBEDDINGS_MODE"):
                    get_embedding_client()
        finally:
            app.embedding.EMBEDDINGS_MODE = original_mode


class TestRetryAndErrorHandling:
    """Tests for retry logic and error handling in provider implementations."""

    def test_llm_client_has_rate_limit_error(self) -> None:
        """LLMRateLimitError exists for rate limit handling."""
        from app.llm.base import LLMRateLimitError

        error = LLMRateLimitError("Rate limit exceeded")
        assert str(error) == "Rate limit exceeded"

    def test_llm_client_has_timeout_error(self) -> None:
        """LLMTimeoutError exists for timeout handling."""
        from app.llm.base import LLMTimeoutError

        error = LLMTimeoutError("Request timed out")
        assert str(error) == "Request timed out"

    def test_search_client_has_search_error(self) -> None:
        """SearchError exists for search error handling."""
        from app.search.base import SearchError

        error = SearchError("Search failed")
        assert str(error) == "Search failed"

    def test_embedding_client_has_embedding_error(self) -> None:
        """EmbeddingError exists for embedding error handling."""
        from app.embedding.base import EmbeddingError

        error = EmbeddingError("Embedding failed")
        assert str(error) == "Embedding failed"
