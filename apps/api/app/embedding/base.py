"""Embedding client interface and data models (NFR-035).

This module defines the EmbeddingClient abstract base class and data structures
used by all embedding provider implementations (Azure OpenAI, OpenAI, local).

Provider-agnostic interface. Swap providers via config, not code changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmbeddingResult:
    """Result from an embedding operation.

    Attributes:
        vectors: List of embedding vectors (one per input text).
        model: Model identifier used for embeddings.
        dimensions: Dimensionality of the embedding vectors.
        prompt_tokens: Number of tokens processed.
        estimated: Whether token count was estimated (vs from API).
    """

    vectors: list[list[float]]
    model: str
    dimensions: int
    prompt_tokens: int
    estimated: bool = False


class EmbeddingClient(ABC):
    """Abstract base class for embedding providers.

    Implementations must provide:
    - embed(): Method to generate embeddings for a list of texts.
    - provider: Property returning the provider name.
    - dimensions: Property returning the embedding dimensions.
    """

    @abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            EmbeddingResult with vectors and usage metadata.

        Raises:
            EmbeddingError: If the request fails.
        """
        pass

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return the provider name (e.g., 'azure_openai', 'local')."""
        pass

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding vector dimensions."""
        pass


class EmbeddingError(Exception):
    """Base exception for embedding errors."""

    pass
