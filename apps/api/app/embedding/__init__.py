"""Embedding client factory and exports (NFR-035).

This module provides the factory function for creating embedding client instances
based on configuration. Swap providers via config only, no code changes.

Usage:
    from app.embedding import get_embedding_client
    client = get_embedding_client()
    result = client.embed(["text to embed"])
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.embedding.base import EmbeddingClient, EmbeddingError, EmbeddingResult

if TYPE_CHECKING:
    pass

__all__ = [
    "get_embedding_client",
    "EmbeddingClient",
    "EmbeddingError",
    "EmbeddingResult",
]

# Import config values lazily to avoid circular imports
EMBEDDINGS_MODE: str = ""
AZURE_OPENAI_ENDPOINT: str = ""
AZURE_OPENAI_API_KEY: str = ""
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT: str = ""
AZURE_OPENAI_API_VERSION: str = ""
EMBEDDINGS_DIM: int = 16


def _load_config() -> None:
    """Load config values on first use."""
    global EMBEDDINGS_MODE, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY
    global AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT, AZURE_OPENAI_API_VERSION, EMBEDDINGS_DIM

    from app.config import (
        AZURE_OPENAI_API_KEY as _AZURE_OPENAI_API_KEY,
        AZURE_OPENAI_API_VERSION as _AZURE_OPENAI_API_VERSION,
        AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT as _AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
        AZURE_OPENAI_ENDPOINT as _AZURE_OPENAI_ENDPOINT,
        EMBEDDINGS_DIM as _EMBEDDINGS_DIM,
        EMBEDDINGS_MODE as _EMBEDDINGS_MODE,
    )

    EMBEDDINGS_MODE = _EMBEDDINGS_MODE
    AZURE_OPENAI_ENDPOINT = _AZURE_OPENAI_ENDPOINT
    AZURE_OPENAI_API_KEY = _AZURE_OPENAI_API_KEY
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT = _AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT
    AZURE_OPENAI_API_VERSION = _AZURE_OPENAI_API_VERSION
    EMBEDDINGS_DIM = _EMBEDDINGS_DIM


def get_embedding_client() -> EmbeddingClient:
    """Get the configured embedding client.

    Returns embedding client based on EMBEDDINGS_MODE environment variable:
    - "local": Hash-based local embeddings (default for testing)
    - "remote": Azure OpenAI embeddings

    Returns:
        Configured EmbeddingClient instance.

    Raises:
        ValueError: If EMBEDDINGS_MODE is not recognized.
        RuntimeError: If required config is missing.
    """
    _load_config()

    if EMBEDDINGS_MODE == "local":
        from app.embedding.local import LocalEmbeddingClient

        return LocalEmbeddingClient(dimensions=EMBEDDINGS_DIM)

    elif EMBEDDINGS_MODE == "remote":
        if not AZURE_OPENAI_ENDPOINT:
            raise RuntimeError(
                "AZURE_OPENAI_ENDPOINT is required for remote embeddings"
            )
        if not AZURE_OPENAI_API_KEY:
            raise RuntimeError("AZURE_OPENAI_API_KEY is required for remote embeddings")
        if not AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT:
            raise RuntimeError(
                "AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT is required for remote embeddings"
            )

        from app.embedding.azure_openai import AzureOpenAIEmbeddingClient

        return AzureOpenAIEmbeddingClient(
            endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=AZURE_OPENAI_API_KEY,
            deployment=AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
            api_version=AZURE_OPENAI_API_VERSION,
        )

    else:
        raise ValueError(
            f"Unknown EMBEDDINGS_MODE: {EMBEDDINGS_MODE}. Valid options: local, remote"
        )
