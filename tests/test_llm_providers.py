# tests/test_llm_providers.py
"""Tests for LLM provider implementations (NFR-032).

Tests cover:
- Ollama client for local open-source models
- Gemini client for Google AI
- Anthropic client for Claude models
- Factory function with all providers
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class TestOllamaClient:
    """Tests for Ollama LLM client."""

    def test_ollama_client_exists(self) -> None:
        """OllamaClient implementation exists."""
        from app.llm.ollama import OllamaClient

        assert OllamaClient is not None

    def test_ollama_client_inherits_llm_client(self) -> None:
        """OllamaClient inherits from LLMClient."""
        from app.llm.base import LLMClient
        from app.llm.ollama import OllamaClient

        assert issubclass(OllamaClient, LLMClient)

    def test_ollama_client_has_provider(self) -> None:
        """OllamaClient returns 'ollama' as provider."""
        from app.llm.ollama import OllamaClient

        client = OllamaClient(model="llama3.2:8b")
        assert client.provider == "ollama"

    def test_ollama_client_has_model(self) -> None:
        """OllamaClient returns configured model."""
        from app.llm.ollama import OllamaClient

        client = OllamaClient(model="mistral:7b")
        assert client.model == "mistral:7b"

    def test_ollama_client_default_model(self) -> None:
        """OllamaClient has sensible default model."""
        from app.llm.ollama import OllamaClient

        client = OllamaClient()
        assert client.model == "llama3.2:8b"

    def test_ollama_client_custom_base_url(self) -> None:
        """OllamaClient accepts custom base URL."""
        from app.llm.ollama import OllamaClient

        client = OllamaClient(base_url="http://remote-ollama:11434")
        assert "remote-ollama" in client._base_url


class TestGeminiClient:
    """Tests for Google Gemini LLM client."""

    def test_gemini_client_exists(self) -> None:
        """GeminiClient implementation exists."""
        from app.llm.gemini import GeminiClient

        assert GeminiClient is not None

    def test_gemini_client_inherits_llm_client(self) -> None:
        """GeminiClient inherits from LLMClient."""
        from app.llm.base import LLMClient
        from app.llm.gemini import GeminiClient

        assert issubclass(GeminiClient, LLMClient)

    def test_gemini_client_has_provider(self) -> None:
        """GeminiClient returns 'gemini' as provider."""
        from app.llm.gemini import GeminiClient

        client = GeminiClient(api_key="test-key")
        assert client.provider == "gemini"

    def test_gemini_client_has_model(self) -> None:
        """GeminiClient returns configured model."""
        from app.llm.gemini import GeminiClient

        client = GeminiClient(api_key="test-key", model="gemini-1.5-pro")
        assert client.model == "gemini-1.5-pro"

    def test_gemini_client_default_model(self) -> None:
        """GeminiClient has sensible default model."""
        from app.llm.gemini import GeminiClient

        client = GeminiClient(api_key="test-key")
        assert client.model == "gemini-2.0-flash"


class TestAnthropicClient:
    """Tests for Anthropic Claude LLM client."""

    def test_anthropic_client_exists(self) -> None:
        """AnthropicClient implementation exists."""
        from app.llm.anthropic import AnthropicClient

        assert AnthropicClient is not None

    def test_anthropic_client_inherits_llm_client(self) -> None:
        """AnthropicClient inherits from LLMClient."""
        from app.llm.anthropic import AnthropicClient
        from app.llm.base import LLMClient

        assert issubclass(AnthropicClient, LLMClient)

    def test_anthropic_client_has_provider(self) -> None:
        """AnthropicClient returns 'anthropic' as provider."""
        from app.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="test-key")
        assert client.provider == "anthropic"

    def test_anthropic_client_has_model(self) -> None:
        """AnthropicClient returns configured model."""
        from app.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="test-key", model="claude-3-5-haiku-20241022")
        assert client.model == "claude-3-5-haiku-20241022"

    def test_anthropic_client_default_model(self) -> None:
        """AnthropicClient has sensible default model."""
        from app.llm.anthropic import AnthropicClient

        client = AnthropicClient(api_key="test-key")
        assert client.model == "claude-sonnet-4-20250514"


class TestLLMFactoryNewProviders:
    """Tests for get_llm_client factory with new providers."""

    def test_factory_creates_ollama_client(self) -> None:
        """Factory creates OllamaClient for ollama provider."""
        import app.llm

        original_provider = app.llm.LLM_PROVIDER
        try:
            app.llm.LLM_PROVIDER = "ollama"
            app.llm.OLLAMA_MODEL = "llama3.2:8b"
            app.llm.OLLAMA_BASE_URL = "http://localhost:11434"

            with patch.object(app.llm, "_load_config", lambda: None):
                from app.llm import get_llm_client
                from app.llm.ollama import OllamaClient

                client = get_llm_client()
                assert isinstance(client, OllamaClient)
        finally:
            app.llm.LLM_PROVIDER = original_provider

    def test_factory_creates_gemini_client(self) -> None:
        """Factory creates GeminiClient for gemini provider."""
        import app.llm

        original_provider = app.llm.LLM_PROVIDER
        try:
            app.llm.LLM_PROVIDER = "gemini"
            app.llm.GEMINI_API_KEY = "test-key"
            app.llm.GEMINI_MODEL = "gemini-2.0-flash"

            with patch.object(app.llm, "_load_config", lambda: None):
                from app.llm import get_llm_client
                from app.llm.gemini import GeminiClient

                client = get_llm_client()
                assert isinstance(client, GeminiClient)
        finally:
            app.llm.LLM_PROVIDER = original_provider

    def test_factory_creates_anthropic_client(self) -> None:
        """Factory creates AnthropicClient for anthropic provider."""
        import app.llm

        original_provider = app.llm.LLM_PROVIDER
        try:
            app.llm.LLM_PROVIDER = "anthropic"
            app.llm.ANTHROPIC_API_KEY = "test-key"
            app.llm.ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

            with patch.object(app.llm, "_load_config", lambda: None):
                from app.llm import get_llm_client
                from app.llm.anthropic import AnthropicClient

                client = get_llm_client()
                assert isinstance(client, AnthropicClient)
        finally:
            app.llm.LLM_PROVIDER = original_provider

    def test_factory_gemini_requires_api_key(self) -> None:
        """Factory raises RuntimeError when GEMINI_API_KEY is missing."""
        import app.llm

        original_provider = app.llm.LLM_PROVIDER
        original_key = app.llm.GEMINI_API_KEY
        try:
            app.llm.LLM_PROVIDER = "gemini"
            app.llm.GEMINI_API_KEY = ""

            with patch.object(app.llm, "_load_config", lambda: None):
                from app.llm import get_llm_client

                with pytest.raises(RuntimeError, match="GEMINI_API_KEY is required"):
                    get_llm_client()
        finally:
            app.llm.LLM_PROVIDER = original_provider
            app.llm.GEMINI_API_KEY = original_key

    def test_factory_anthropic_requires_api_key(self) -> None:
        """Factory raises RuntimeError when ANTHROPIC_API_KEY is missing."""
        import app.llm

        original_provider = app.llm.LLM_PROVIDER
        original_key = app.llm.ANTHROPIC_API_KEY
        try:
            app.llm.LLM_PROVIDER = "anthropic"
            app.llm.ANTHROPIC_API_KEY = ""

            with patch.object(app.llm, "_load_config", lambda: None):
                from app.llm import get_llm_client

                with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is required"):
                    get_llm_client()
        finally:
            app.llm.LLM_PROVIDER = original_provider
            app.llm.ANTHROPIC_API_KEY = original_key


class TestLLMResponseDataclass:
    """Tests for LLMResponse dataclass with new providers."""

    def test_llm_response_works_with_ollama(self) -> None:
        """LLMResponse works with Ollama provider info."""
        from app.llm.base import LLMResponse

        response = LLMResponse(
            content="Test response",
            provider="ollama",
            model="llama3.2:8b",
            prompt_tokens=50,
            completion_tokens=25,
            latency_ms=2000,
        )
        assert response.provider == "ollama"
        assert response.model == "llama3.2:8b"

    def test_llm_response_works_with_gemini(self) -> None:
        """LLMResponse works with Gemini provider info."""
        from app.llm.base import LLMResponse

        response = LLMResponse(
            content="Test response",
            provider="gemini",
            model="gemini-2.0-flash",
            prompt_tokens=50,
            completion_tokens=25,
            latency_ms=500,
        )
        assert response.provider == "gemini"
        assert response.model == "gemini-2.0-flash"

    def test_llm_response_works_with_anthropic(self) -> None:
        """LLMResponse works with Anthropic provider info."""
        from app.llm.base import LLMResponse

        response = LLMResponse(
            content="Test response",
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            prompt_tokens=50,
            completion_tokens=25,
            latency_ms=600,
        )
        assert response.provider == "anthropic"
        assert response.model == "claude-sonnet-4-20250514"
