"""Search client interface and data models (NFR-034).

This module defines the SearchClient abstract base class and data structures
used by all search provider implementations (Azure AI Search, pgvector/local).

Provider-agnostic interface. Swap Azure AI Search <-> pgvector via config only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """Result from a search operation.

    Attributes:
        chunk_id: Unique identifier for the chunk.
        doc_id: Document ID this chunk belongs to.
        text: The chunk text content.
        score: Relevance score (normalized or raw depending on provider).
        page_number: Page number in the source document.
        page_end: End page number (for multi-page chunks).
        char_start: Character offset start in document.
        char_end: Character offset end in document.
        doc_name: Document name/filename.
        metadata: Additional metadata (provider-specific scores, etc.).
    """

    chunk_id: str
    doc_id: str
    text: str
    score: float
    page_number: int
    page_end: int = 0
    char_start: int = 0
    char_end: int = 0
    doc_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    """Response from a search operation.

    Attributes:
        results: List of search results.
        provider: Provider name that executed the search.
        embedding_usage: Token usage for query embedding (if applicable).
    """

    results: list[SearchResult]
    provider: str
    embedding_usage: dict[str, Any] = field(default_factory=dict)


class SearchClient(ABC):
    """Abstract base class for search providers.

    Implementations must provide:
    - hybrid_search(): Method to execute hybrid (BM25 + vector) search.
    - provider: Property returning the provider name.

    All implementations MUST:
    - Filter by tenant_id and matter_id (isolation)
    - Return results sorted by fused score
    - Include chunk_id for citation mapping
    """

    @abstractmethod
    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        tenant_id: str,
        matter_id: str,
        *,
        docs_snapshot_id: str | None = None,
        top_k: int = 5,
    ) -> SearchResponse:
        """Execute hybrid search combining BM25 and vector search.

        Args:
            query: Search query text.
            query_embedding: Pre-computed query embedding vector.
            tenant_id: Tenant ID for isolation (REQUIRED - FR-001).
            matter_id: Matter ID for isolation (REQUIRED - FR-002).
            docs_snapshot_id: Optional document snapshot filter.
            top_k: Maximum number of results to return.

        Returns:
            SearchResponse with ranked results and provider info.

        Raises:
            SearchError: If the search fails.
        """
        pass

    @property
    @abstractmethod
    def provider(self) -> str:
        """Return the provider name (e.g., 'azure', 'local')."""
        pass


class SearchError(Exception):
    """Base exception for search errors."""

    pass
