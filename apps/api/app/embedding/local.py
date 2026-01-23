"""Local (hash-based) embedding client implementation (NFR-035).

This module implements the EmbeddingClient interface using a deterministic
hash-based approach. Useful for testing and development without API calls.
"""

from __future__ import annotations

import hashlib

from app.embedding.base import EmbeddingClient, EmbeddingResult


class LocalEmbeddingClient(EmbeddingClient):
    """Local embedding client using hash-based vectors.

    Generates deterministic embeddings from text using SHA256 hashing.
    No API calls required - useful for testing and local development.
    """

    def __init__(self, dimensions: int = 16) -> None:
        """Initialize local embedding client.

        Args:
            dimensions: Dimensionality of output vectors.
        """
        self._dimensions = dimensions

    @property
    def provider(self) -> str:
        """Return 'local' as provider name."""
        return "local"

    @property
    def dimensions(self) -> int:
        """Return configured dimensions."""
        return self._dimensions

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate hash-based embeddings.

        Args:
            texts: List of text strings to embed.

        Returns:
            EmbeddingResult with deterministic vectors.
        """
        vectors = [self._hash_embed(text) for text in texts]
        return EmbeddingResult(
            vectors=vectors,
            model="local-hash",
            dimensions=self._dimensions,
            prompt_tokens=0,
            estimated=False,
        )

    def _hash_embed(self, text: str) -> list[float]:
        """Generate a deterministic embedding from text using SHA256.

        Args:
            text: Input text.

        Returns:
            Vector of floats derived from hash.
        """
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vec: list[float] = []
        for i in range(self._dimensions):
            vec.append(digest[i % len(digest)] / 255.0)
        return vec
