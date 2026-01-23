"""Search client factory and exports (NFR-034).

This module provides the factory function for creating search client instances
based on configuration. Swap Azure AI Search <-> pgvector via config only.

Usage:
    from app.search import get_search_client
    client = get_search_client()
    response = client.hybrid_search(query, embedding, tenant_id, matter_id)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.search.base import SearchClient, SearchError, SearchResponse, SearchResult

if TYPE_CHECKING:
    pass

__all__ = [
    "get_search_client",
    "SearchClient",
    "SearchError",
    "SearchResponse",
    "SearchResult",
]

# Import config values lazily to avoid circular imports
SEARCH_PROVIDER: str = ""
AZURE_SEARCH_ENDPOINT: str = ""
AZURE_SEARCH_API_KEY: str = ""
AZURE_SEARCH_INDEX: str = ""
AZURE_SEARCH_API_VERSION: str = ""
AZURE_SEMANTIC_ENABLED: bool = False
TOP_K_VECTOR: int = 5
RRF_K: int = 60
TOP_K_BM25: int = 5


def _load_config() -> None:
    """Load config values on first use."""
    global SEARCH_PROVIDER, AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_API_KEY
    global AZURE_SEARCH_INDEX, AZURE_SEARCH_API_VERSION, AZURE_SEMANTIC_ENABLED
    global TOP_K_VECTOR, RRF_K, TOP_K_BM25

    from app.config import (
        AZURE_SEARCH_API_KEY as _AZURE_SEARCH_API_KEY,
        AZURE_SEARCH_API_VERSION as _AZURE_SEARCH_API_VERSION,
        AZURE_SEARCH_ENDPOINT as _AZURE_SEARCH_ENDPOINT,
        AZURE_SEARCH_INDEX as _AZURE_SEARCH_INDEX,
        AZURE_SEMANTIC_ENABLED as _AZURE_SEMANTIC_ENABLED,
        RRF_K as _RRF_K,
        TOP_K_BM25 as _TOP_K_BM25,
        TOP_K_VECTOR as _TOP_K_VECTOR,
        _getenv,
    )

    SEARCH_PROVIDER = _getenv("SEARCH_PROVIDER", "local")  # Default to local/pgvector
    AZURE_SEARCH_ENDPOINT = _AZURE_SEARCH_ENDPOINT
    AZURE_SEARCH_API_KEY = _AZURE_SEARCH_API_KEY
    AZURE_SEARCH_INDEX = _AZURE_SEARCH_INDEX
    AZURE_SEARCH_API_VERSION = _AZURE_SEARCH_API_VERSION
    AZURE_SEMANTIC_ENABLED = _AZURE_SEMANTIC_ENABLED
    TOP_K_VECTOR = _TOP_K_VECTOR
    RRF_K = _RRF_K
    TOP_K_BM25 = _TOP_K_BM25


def get_search_client() -> SearchClient:
    """Get the configured search client.

    Returns search client based on SEARCH_PROVIDER environment variable:
    - "local": Local PostgreSQL BM25 + vector search (default)
    - "azure": Azure AI Search

    Returns:
        Configured SearchClient instance.

    Raises:
        ValueError: If SEARCH_PROVIDER is not recognized.
        RuntimeError: If required config is missing.
    """
    _load_config()

    if SEARCH_PROVIDER == "local":
        from app.search.local import LocalSearchClient

        return LocalSearchClient(
            top_k_bm25=TOP_K_BM25,
            top_k_vector=TOP_K_VECTOR,
            rrf_k=RRF_K,
        )

    elif SEARCH_PROVIDER == "azure":
        if not AZURE_SEARCH_ENDPOINT:
            raise RuntimeError("AZURE_SEARCH_ENDPOINT is required for azure provider")
        if not AZURE_SEARCH_API_KEY:
            raise RuntimeError("AZURE_SEARCH_API_KEY is required for azure provider")
        if not AZURE_SEARCH_INDEX:
            raise RuntimeError("AZURE_SEARCH_INDEX is required for azure provider")

        from app.search.azure import AzureSearchClient

        return AzureSearchClient(
            endpoint=AZURE_SEARCH_ENDPOINT,
            api_key=AZURE_SEARCH_API_KEY,
            index_name=AZURE_SEARCH_INDEX,
            api_version=AZURE_SEARCH_API_VERSION,
            semantic_enabled=AZURE_SEMANTIC_ENABLED,
            top_k_vector=TOP_K_VECTOR,
        )

    else:
        raise ValueError(
            f"Unknown SEARCH_PROVIDER: {SEARCH_PROVIDER}. Valid options: local, azure"
        )
