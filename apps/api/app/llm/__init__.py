"""LLM client factory and exports (NFR-032).

This module provides the factory function for creating LLM client instances
based on configuration. Swap providers via config only, no code changes.

Usage:
    from app.llm import get_llm_client
    client = get_llm_client()
    response = client.complete(system_prompt, user_prompt)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.llm.base import LLMClient, LLMError, LLMRateLimitError, LLMResponse, LLMTimeoutError

if TYPE_CHECKING:
    pass

__all__ = [
    "get_llm_client",
    "LLMClient",
    "LLMError",
    "LLMRateLimitError",
    "LLMResponse",
    "LLMTimeoutError",
]

# Import config values lazily to avoid circular imports
LLM_PROVIDER: str = ""
AZURE_OPENAI_CHAT_ENDPOINT: str = ""
AZURE_OPENAI_CHAT_API_KEY: str = ""
AZURE_OPENAI_CHAT_API_VERSION: str = ""
MODEL_ID: str = ""

# Ollama config
OLLAMA_BASE_URL: str = ""
OLLAMA_MODEL: str = ""

# Gemini config
GEMINI_API_KEY: str = ""
GEMINI_MODEL: str = ""

# Anthropic config
ANTHROPIC_API_KEY: str = ""
ANTHROPIC_MODEL: str = ""


def _load_config() -> None:
    """Load config values on first use."""
    global LLM_PROVIDER, AZURE_OPENAI_CHAT_ENDPOINT, AZURE_OPENAI_CHAT_API_KEY
    global AZURE_OPENAI_CHAT_API_VERSION, MODEL_ID
    global OLLAMA_BASE_URL, OLLAMA_MODEL
    global GEMINI_API_KEY, GEMINI_MODEL
    global ANTHROPIC_API_KEY, ANTHROPIC_MODEL

    from app.config import (
        AZURE_OPENAI_CHAT_API_KEY as _AZURE_OPENAI_CHAT_API_KEY,
        AZURE_OPENAI_CHAT_API_VERSION as _AZURE_OPENAI_CHAT_API_VERSION,
        AZURE_OPENAI_CHAT_ENDPOINT as _AZURE_OPENAI_CHAT_ENDPOINT,
        MODEL_ID as _MODEL_ID,
        _getenv,
    )

    LLM_PROVIDER = _getenv("LLM_PROVIDER", "azure_openai")
    AZURE_OPENAI_CHAT_ENDPOINT = _AZURE_OPENAI_CHAT_ENDPOINT
    AZURE_OPENAI_CHAT_API_KEY = _AZURE_OPENAI_CHAT_API_KEY
    AZURE_OPENAI_CHAT_API_VERSION = _AZURE_OPENAI_CHAT_API_VERSION
    MODEL_ID = _MODEL_ID

    # Ollama config
    OLLAMA_BASE_URL = _getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = _getenv("OLLAMA_MODEL", "llama3.2:8b")

    # Gemini config
    GEMINI_API_KEY = _getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = _getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # Anthropic config
    ANTHROPIC_API_KEY = _getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = _getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def get_llm_client() -> LLMClient:
    """Get the configured LLM client.

    Returns LLM client based on LLM_PROVIDER environment variable:
    - "azure_openai": Azure OpenAI (default)
    - "ollama": Ollama local (open-source models)
    - "gemini": Google Gemini
    - "anthropic": Anthropic Claude

    Returns:
        Configured LLMClient instance.

    Raises:
        ValueError: If LLM_PROVIDER is not recognized.
        RuntimeError: If required config is missing.
    """
    _load_config()

    if LLM_PROVIDER == "azure_openai":
        if not AZURE_OPENAI_CHAT_ENDPOINT:
            raise RuntimeError("AZURE_OPENAI_CHAT_ENDPOINT is required for azure_openai provider")
        if not AZURE_OPENAI_CHAT_API_KEY:
            raise RuntimeError("AZURE_OPENAI_CHAT_API_KEY is required for azure_openai provider")
        if not MODEL_ID:
            raise RuntimeError("MODEL_ID (deployment name) is required for azure_openai provider")

        from app.llm.azure_openai import AzureOpenAIClient

        return AzureOpenAIClient(
            endpoint=AZURE_OPENAI_CHAT_ENDPOINT,
            api_key=AZURE_OPENAI_CHAT_API_KEY,
            deployment=MODEL_ID,
            api_version=AZURE_OPENAI_CHAT_API_VERSION,
        )

    elif LLM_PROVIDER == "ollama":
        from app.llm.ollama import OllamaClient

        return OllamaClient(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
        )

    elif LLM_PROVIDER == "gemini":
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is required for gemini provider")

        from app.llm.gemini import GeminiClient

        return GeminiClient(
            api_key=GEMINI_API_KEY,
            model=GEMINI_MODEL,
        )

    elif LLM_PROVIDER == "anthropic":
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is required for anthropic provider")

        from app.llm.anthropic import AnthropicClient

        return AnthropicClient(
            api_key=ANTHROPIC_API_KEY,
            model=ANTHROPIC_MODEL,
        )

    else:
        raise ValueError(
            f"Unknown LLM provider: {LLM_PROVIDER}. "
            f"Valid options: azure_openai, ollama, gemini, anthropic"
        )
