"""Reranker interface (FR-022).

Defines the abstract reranker contract. Implementations re-score
hybrid search results for better top-k quality.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.search.base import SearchResult


class RerankerClient(ABC):
    """Abstract reranker interface."""

    provider: str

    @abstractmethod
    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        *,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Re-score and re-order candidates by relevance to query.

        Args:
            query: The user's search query.
            candidates: Search results to rerank.
            top_k: Maximum number of results to return.

        Returns:
            Reranked results sorted by relevance, truncated to top_k.
        """
        ...
