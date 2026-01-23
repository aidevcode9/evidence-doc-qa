"""LLM client interface and data models (NFR-032).

This module defines the LLMClient abstract base class and data structures
used by all LLM provider implementations (Azure OpenAI, Anthropic, OpenAI, Ollama).

Provider-agnostic interface. Swap providers via config, not code changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Response from an LLM completion.

    Attributes:
        content: The generated text content.
        provider: Provider name (e.g., 'azure_openai', 'anthropic', 'openai', 'ollama').
        model: Model identifier (e.g., 'gpt-4o', 'claude-3.5-sonnet').
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        latency_ms: Request latency in milliseconds.
    """

    content: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int


class LLMClient(ABC):
    """Abstract base class for LLM providers.

    Implementations must provide:
    - complete(): Method to generate completions.
    - provider: Property returning the provider name.
    - model: Property returning the model identifier.

    All LLM calls should go through TracedLLMClient wrapper for telemetry (NFR-030).
    """

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate a completion from the LLM.

        Args:
            system_prompt: System message/instructions for the model.
            user_prompt: User message/query.
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens in the response.

        Returns:
            LLMResponse with content and usage metadata.

        Raises:
            LLMError: If the request fails.
        """
        pass

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return the provider name (e.g., 'azure_openai', 'anthropic')."""
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the model identifier (e.g., 'gpt-4o', 'claude-3.5-sonnet')."""
        pass


class LLMError(Exception):
    """Base exception for LLM errors."""

    pass


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    pass


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded."""

    pass
