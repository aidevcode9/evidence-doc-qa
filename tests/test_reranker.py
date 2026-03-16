"""Tests for optional reranker (FR-022).

Reranker can be enabled/disabled via RERANKER_ENABLED config.
When enabled, re-scores hybrid search results for better top-k quality.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.search.base import SearchResult


def _make_result(chunk_id: str, text: str, score: float) -> SearchResult:
    """Helper to create a search result."""
    return SearchResult(
        chunk_id=chunk_id,
        doc_id="doc-1",
        text=text,
        score=score,
        page_number=1,
    )


class TestRerankerConfig:
    """Reranker config is toggleable."""

    def test_reranker_enabled_config_exists(self) -> None:
        """RERANKER_ENABLED should be available in config."""
        from app.config import RERANKER_ENABLED

        assert isinstance(RERANKER_ENABLED, bool)

    def test_reranker_top_k_config_exists(self) -> None:
        """RERANKER_TOP_K should be available in config."""
        from app.config import RERANKER_TOP_K

        assert isinstance(RERANKER_TOP_K, int)
        assert RERANKER_TOP_K > 0


class TestLocalReranker:
    """Local reranker re-scores candidates using query-document analysis."""

    def test_reranker_interface_exists(self) -> None:
        """RerankerClient interface exists with rerank method."""
        from app.reranker.base import RerankerClient

        assert hasattr(RerankerClient, "rerank")

    def test_local_reranker_exists(self) -> None:
        """LocalReranker implementation exists."""
        from app.reranker.local import LocalReranker

        reranker = LocalReranker()
        assert reranker.provider == "local"

    def test_rerank_returns_sorted_results(self) -> None:
        """Reranker should return results sorted by relevance."""
        from app.reranker.local import LocalReranker

        reranker = LocalReranker()
        query = "What is the indemnification clause?"
        candidates = [
            _make_result("c1", "The weather is nice today.", 0.9),
            _make_result("c2", "The indemnification clause states that parties must...", 0.5),
            _make_result("c3", "Contract terms include indemnification provisions.", 0.7),
        ]

        reranked = reranker.rerank(query, candidates, top_k=3)

        assert len(reranked) == 3
        # The most relevant result (c2) should be first or second
        chunk_ids = [r.chunk_id for r in reranked]
        assert chunk_ids[0] in ("c2", "c3")  # Both mention indemnification

    def test_rerank_respects_top_k(self) -> None:
        """Reranker should return at most top_k results."""
        from app.reranker.local import LocalReranker

        reranker = LocalReranker()
        candidates = [
            _make_result(f"c{i}", f"Text about clause {i} in the contract.", 0.5)
            for i in range(10)
        ]

        reranked = reranker.rerank("contract clause", candidates, top_k=3)
        assert len(reranked) == 3

    def test_rerank_empty_candidates(self) -> None:
        """Reranker should handle empty candidate list."""
        from app.reranker.local import LocalReranker

        reranker = LocalReranker()
        reranked = reranker.rerank("query", [], top_k=5)
        assert reranked == []

    def test_rerank_scores_phrase_matches_higher(self) -> None:
        """Exact phrase matches should score higher than scattered terms."""
        from app.reranker.local import LocalReranker

        reranker = LocalReranker()
        query = "force majeure clause"
        candidates = [
            _make_result("c1", "The clause covers force and majeure separately.", 0.8),
            _make_result("c2", "The force majeure clause excuses performance.", 0.6),
        ]

        reranked = reranker.rerank(query, candidates, top_k=2)
        # c2 has the exact phrase, should rank higher
        assert reranked[0].chunk_id == "c2"


class TestRerankerFactory:
    """Factory function creates correct reranker based on config."""

    def test_get_reranker_returns_local(self) -> None:
        """Default reranker should be local."""
        from app.reranker import get_reranker_client

        with patch("app.reranker.RERANKER_ENABLED", True):
            client = get_reranker_client()
            assert client is not None
            assert client.provider == "local"

    def test_get_reranker_returns_none_when_disabled(self) -> None:
        """When RERANKER_ENABLED=false, factory returns None."""
        from app.reranker import get_reranker_client

        with patch("app.reranker.RERANKER_ENABLED", False):
            client = get_reranker_client()
            assert client is None


class TestRerankerInSearchPipeline:
    """Reranker integrates with LocalSearchClient when enabled."""

    def test_confidence_score_key_uses_reranker_score(self) -> None:
        """When reranker_score is present, confidence should use it."""
        from app.services.rag import confidence_score_key

        chunks = [{"rrf_score": 0.8, "reranker_score": 0.95}]
        key = confidence_score_key(chunks)
        assert key == "reranker_score"

    def test_confidence_threshold_for_reranker(self) -> None:
        """Reranker score key should have a configurable threshold."""
        from app.services.rag import confidence_threshold

        threshold = confidence_threshold("reranker_score")
        assert isinstance(threshold, float)
        assert threshold > 0
