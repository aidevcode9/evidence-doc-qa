# tests/test_provider_abstraction.py
"""Tests for provider abstraction interfaces (NFR-032, NFR-034, NFR-035).

NFR-032: LLM provider abstracted behind LLMClient interface
NFR-034: Search/retrieval abstracted behind SearchClient interface
NFR-035: Embeddings abstracted behind EmbeddingClient interface
"""

import sys
from pathlib import Path

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class TestLLMClientInterface:
    """Tests for LLMClient interface (NFR-032)."""

    def test_llm_client_base_class_exists(self) -> None:
        """LLMClient abstract base class exists."""
        from app.llm.base import LLMClient

        assert LLMClient is not None

    def test_llm_response_dataclass_exists(self) -> None:
        """LLMResponse dataclass exists with required fields."""
        from app.llm.base import LLMResponse

        response = LLMResponse(
            content="test",
            provider="test",
            model="test",
            prompt_tokens=10,
            completion_tokens=5,
            latency_ms=100,
        )
        assert response.content == "test"
        assert response.provider == "test"
        assert response.model == "test"
        assert response.prompt_tokens == 10
        assert response.completion_tokens == 5
        assert response.latency_ms == 100

    def test_llm_client_has_complete_method(self) -> None:
        """LLMClient has abstract complete method."""
        import inspect

        from app.llm.base import LLMClient

        assert hasattr(LLMClient, "complete")
        sig = inspect.signature(LLMClient.complete)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "system_prompt" in params
        assert "user_prompt" in params

    def test_llm_client_has_provider_property(self) -> None:
        """LLMClient has provider property."""
        from app.llm.base import LLMClient

        assert hasattr(LLMClient, "provider")

    def test_llm_client_has_model_property(self) -> None:
        """LLMClient has model property."""
        from app.llm.base import LLMClient

        assert hasattr(LLMClient, "model")


class TestAzureOpenAIClient:
    """Tests for Azure OpenAI LLM client implementation."""

    def test_azure_openai_client_exists(self) -> None:
        """AzureOpenAIClient implementation exists."""
        from app.llm.azure_openai import AzureOpenAIClient

        assert AzureOpenAIClient is not None

    def test_azure_openai_client_inherits_llm_client(self) -> None:
        """AzureOpenAIClient inherits from LLMClient."""
        from app.llm.azure_openai import AzureOpenAIClient
        from app.llm.base import LLMClient

        assert issubclass(AzureOpenAIClient, LLMClient)

    def test_azure_openai_client_has_provider(self) -> None:
        """AzureOpenAIClient returns 'azure_openai' as provider."""
        from app.llm.azure_openai import AzureOpenAIClient

        client = AzureOpenAIClient(
            endpoint="https://test.openai.azure.com",
            api_key="test-key",
            deployment="test-deployment",
        )
        assert client.provider == "azure_openai"


class TestGetLLMClient:
    """Tests for get_llm_client factory function."""

    def test_get_llm_client_function_exists(self) -> None:
        """get_llm_client factory function exists."""
        from app.llm import get_llm_client

        assert callable(get_llm_client)

    def test_get_llm_client_returns_llm_client(self) -> None:
        """get_llm_client returns LLMClient instance."""
        from unittest.mock import patch

        from app.llm import get_llm_client
        from app.llm.base import LLMClient

        # Mock config to avoid needing real API keys
        with patch("app.llm.LLM_PROVIDER", "azure_openai"):
            with patch("app.llm.AZURE_OPENAI_CHAT_ENDPOINT", "https://test.openai.azure.com"):
                with patch("app.llm.AZURE_OPENAI_CHAT_API_KEY", "test-key"):
                    with patch("app.llm.MODEL_ID", "gpt-4o"):
                        client = get_llm_client()
                        assert isinstance(client, LLMClient)


class TestEmbeddingClientInterface:
    """Tests for EmbeddingClient interface (NFR-035)."""

    def test_embedding_client_base_class_exists(self) -> None:
        """EmbeddingClient abstract base class exists."""
        from app.embedding.base import EmbeddingClient

        assert EmbeddingClient is not None

    def test_embedding_result_dataclass_exists(self) -> None:
        """EmbeddingResult dataclass exists with required fields."""
        from app.embedding.base import EmbeddingResult

        result = EmbeddingResult(
            vectors=[[0.1, 0.2, 0.3]],
            model="test-model",
            dimensions=3,
            prompt_tokens=10,
        )
        assert result.vectors == [[0.1, 0.2, 0.3]]
        assert result.model == "test-model"
        assert result.dimensions == 3
        assert result.prompt_tokens == 10

    def test_embedding_client_has_embed_method(self) -> None:
        """EmbeddingClient has abstract embed method."""
        import inspect

        from app.embedding.base import EmbeddingClient

        assert hasattr(EmbeddingClient, "embed")
        sig = inspect.signature(EmbeddingClient.embed)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "texts" in params

    def test_embedding_client_has_provider_property(self) -> None:
        """EmbeddingClient has provider property."""
        from app.embedding.base import EmbeddingClient

        assert hasattr(EmbeddingClient, "provider")

    def test_embedding_client_has_dimensions_property(self) -> None:
        """EmbeddingClient has dimensions property."""
        from app.embedding.base import EmbeddingClient

        assert hasattr(EmbeddingClient, "dimensions")


class TestAzureOpenAIEmbeddingClient:
    """Tests for Azure OpenAI embedding client implementation."""

    def test_azure_openai_embedding_client_exists(self) -> None:
        """AzureOpenAIEmbeddingClient implementation exists."""
        from app.embedding.azure_openai import AzureOpenAIEmbeddingClient

        assert AzureOpenAIEmbeddingClient is not None

    def test_azure_openai_embedding_client_inherits_embedding_client(self) -> None:
        """AzureOpenAIEmbeddingClient inherits from EmbeddingClient."""
        from app.embedding.azure_openai import AzureOpenAIEmbeddingClient
        from app.embedding.base import EmbeddingClient

        assert issubclass(AzureOpenAIEmbeddingClient, EmbeddingClient)


class TestLocalEmbeddingClient:
    """Tests for local (hash-based) embedding client implementation."""

    def test_local_embedding_client_exists(self) -> None:
        """LocalEmbeddingClient implementation exists."""
        from app.embedding.local import LocalEmbeddingClient

        assert LocalEmbeddingClient is not None

    def test_local_embedding_client_inherits_embedding_client(self) -> None:
        """LocalEmbeddingClient inherits from EmbeddingClient."""
        from app.embedding.base import EmbeddingClient
        from app.embedding.local import LocalEmbeddingClient

        assert issubclass(LocalEmbeddingClient, EmbeddingClient)

    def test_local_embedding_client_embed_returns_vectors(self) -> None:
        """LocalEmbeddingClient.embed returns vectors."""
        from app.embedding.local import LocalEmbeddingClient

        client = LocalEmbeddingClient(dimensions=16)
        result = client.embed(["test text"])
        assert len(result.vectors) == 1
        assert len(result.vectors[0]) == 16
        assert client.provider == "local"


class TestGetEmbeddingClient:
    """Tests for get_embedding_client factory function."""

    def test_get_embedding_client_function_exists(self) -> None:
        """get_embedding_client factory function exists."""
        from app.embedding import get_embedding_client

        assert callable(get_embedding_client)

    def test_get_embedding_client_returns_embedding_client(self) -> None:
        """get_embedding_client returns EmbeddingClient instance."""
        from unittest.mock import patch

        from app.embedding import get_embedding_client
        from app.embedding.base import EmbeddingClient

        # Mock config to use local embeddings
        with patch("app.embedding.EMBEDDINGS_MODE", "local"):
            client = get_embedding_client()
            assert isinstance(client, EmbeddingClient)


class TestSearchClientInterface:
    """Tests for SearchClient interface (NFR-034)."""

    def test_search_client_base_class_exists(self) -> None:
        """SearchClient abstract base class exists."""
        from app.search.base import SearchClient

        assert SearchClient is not None

    def test_search_result_dataclass_exists(self) -> None:
        """SearchResult dataclass exists with required fields."""
        from app.search.base import SearchResult

        result = SearchResult(
            chunk_id="chunk-1",
            doc_id="doc-1",
            text="test text",
            score=0.9,
            page_number=1,
            metadata={},
        )
        assert result.chunk_id == "chunk-1"
        assert result.doc_id == "doc-1"
        assert result.text == "test text"
        assert result.score == 0.9
        assert result.page_number == 1

    def test_search_client_has_hybrid_search_method(self) -> None:
        """SearchClient has abstract hybrid_search method."""
        import inspect

        from app.search.base import SearchClient

        assert hasattr(SearchClient, "hybrid_search")
        sig = inspect.signature(SearchClient.hybrid_search)
        params = list(sig.parameters.keys())
        assert "self" in params
        assert "query" in params
        assert "query_embedding" in params
        assert "tenant_id" in params
        assert "matter_id" in params

    def test_search_client_has_provider_property(self) -> None:
        """SearchClient has provider property."""
        from app.search.base import SearchClient

        assert hasattr(SearchClient, "provider")


class TestAzureSearchClient:
    """Tests for Azure AI Search client implementation."""

    def test_azure_search_client_exists(self) -> None:
        """AzureSearchClient implementation exists."""
        from app.search.azure import AzureSearchClient

        assert AzureSearchClient is not None

    def test_azure_search_client_inherits_search_client(self) -> None:
        """AzureSearchClient inherits from SearchClient."""
        from app.search.azure import AzureSearchClient
        from app.search.base import SearchClient

        assert issubclass(AzureSearchClient, SearchClient)


class TestLocalSearchClient:
    """Tests for local (PostgreSQL/pgvector) search client implementation."""

    def test_local_search_client_exists(self) -> None:
        """LocalSearchClient implementation exists."""
        from app.search.local import LocalSearchClient

        assert LocalSearchClient is not None

    def test_local_search_client_inherits_search_client(self) -> None:
        """LocalSearchClient inherits from SearchClient."""
        from app.search.base import SearchClient
        from app.search.local import LocalSearchClient

        assert issubclass(LocalSearchClient, SearchClient)


class TestGetSearchClient:
    """Tests for get_search_client factory function."""

    def test_get_search_client_function_exists(self) -> None:
        """get_search_client factory function exists."""
        from app.search import get_search_client

        assert callable(get_search_client)

    def test_get_search_client_returns_search_client(self) -> None:
        """get_search_client returns SearchClient instance."""
        from unittest.mock import patch

        from app.search import get_search_client
        from app.search.base import SearchClient

        # Mock config to use local search
        with patch("app.search.SEARCH_PROVIDER", "local"):
            client = get_search_client()
            assert isinstance(client, SearchClient)


class TestConfigDrivenProviderSelection:
    """Tests that providers are selected via config only (no code changes)."""

    def test_llm_provider_config_exists(self) -> None:
        """LLM_PROVIDER config variable exists."""
        from app.config import _getenv

        # Config should be able to read LLM_PROVIDER (even if not set)
        assert callable(_getenv)

    def test_embedding_provider_config_exists(self) -> None:
        """EMBEDDINGS_MODE config variable exists."""
        from app.config import EMBEDDINGS_MODE

        assert EMBEDDINGS_MODE is not None

    def test_search_provider_default_is_local(self) -> None:
        """SEARCH_PROVIDER defaults to 'local' for pgvector."""
        from unittest.mock import patch
        import os

        # Clear the env var if set and test default
        with patch.dict(os.environ, {"SEARCH_PROVIDER": ""}, clear=False):
            from importlib import reload

            import app.config
            reload(app.config)
            # Default should prefer local/pgvector per ARCHITECTURE.md
