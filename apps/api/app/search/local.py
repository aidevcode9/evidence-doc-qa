"""Local (PostgreSQL/BM25) search client implementation (NFR-034).

This module implements the SearchClient interface using local database
queries with BM25 scoring and vector similarity. Uses the existing
retrieval logic from app.retrieval.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any

from app.db import load_chunks, load_index_records
from app.search.base import SearchClient, SearchResponse, SearchResult


class LocalSearchClient(SearchClient):
    """Local search client using PostgreSQL BM25 + vector search.

    Uses in-memory BM25 scoring and cosine similarity for hybrid search.
    Results are fused using Reciprocal Rank Fusion (RRF).
    """

    def __init__(
        self,
        *,
        top_k_bm25: int = 5,
        top_k_vector: int = 5,
        rrf_k: int = 60,
    ) -> None:
        """Initialize local search client.

        Args:
            top_k_bm25: Number of BM25 results to consider.
            top_k_vector: Number of vector results to consider.
            rrf_k: RRF smoothing constant.
        """
        self._top_k_bm25 = top_k_bm25
        self._top_k_vector = top_k_vector
        self._rrf_k = rrf_k
        self._bm25_cache: dict[str, dict[str, Any]] = {}

    @property
    def provider(self) -> str:
        """Return 'local' as provider name."""
        return "local"

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
        """Execute hybrid BM25 + vector search with RRF fusion.

        Args:
            query: Search query text.
            query_embedding: Pre-computed query embedding vector.
            tenant_id: Tenant ID for isolation (REQUIRED - FR-001).
            matter_id: Matter ID for isolation (REQUIRED - FR-002).
            docs_snapshot_id: Optional document snapshot filter.
            top_k: Maximum number of results to return.

        Returns:
            SearchResponse with ranked results.
        """
        # Load records with tenant/matter isolation
        records = self._load_index_records(docs_snapshot_id, tenant_id, matter_id)

        if not records:
            # Try fallback overlap search
            fallback = self._fallback_overlap(
                query, docs_snapshot_id, tenant_id, matter_id, top_k
            )
            return SearchResponse(
                results=fallback,
                provider=self.provider,
                embedding_usage={},
            )

        # Build BM25 stats
        query_tokens = self._tokenize(query)
        snapshot_key = docs_snapshot_id or "none"
        bm25_stats = self._get_bm25_stats(records, snapshot_key)

        # Score all records
        for rec in records:
            doc_stats = bm25_stats["doc_stats"].get(rec["chunk_id"])
            if not doc_stats:
                doc_stats = self._build_doc_stats(rec["chunk_text"])
            rec["bm25_score"] = self._bm25_score(
                query_tokens,
                doc_stats["tf"],
                bm25_stats["df"],
                bm25_stats["num_docs"],
                doc_stats["dl"],
                bm25_stats["avgdl"],
            )
            rec["vector_score"] = self._cosine(query_embedding, rec["embedding_vector"])

        # Get top-K from each method
        bm25_ranked = sorted(records, key=lambda r: r["bm25_score"], reverse=True)[
            : self._top_k_bm25
        ]
        vec_ranked = sorted(records, key=lambda r: r["vector_score"], reverse=True)[
            : self._top_k_vector
        ]

        # RRF fusion
        combined: dict[str, dict[str, Any]] = {}
        self._apply_rank_scores(combined, bm25_ranked, "bm25")
        self._apply_rank_scores(combined, vec_ranked, "vector")

        # Normalize RRF scores
        max_rrf = 2 / (self._rrf_k + 1)
        for rec in combined.values():
            rec["rrf_score"] = rec["rrf_score_raw"] / max_rrf if max_rrf else 0.0

        # Sort and limit
        fused = sorted(combined.values(), key=lambda r: r["rrf_score"], reverse=True)[
            :top_k
        ]

        # Convert to SearchResult objects
        results = [
            SearchResult(
                chunk_id=rec["chunk_id"],
                doc_id=rec["doc_id"],
                text=rec["chunk_text"],
                score=rec["rrf_score"],
                page_number=rec["page_num"],
                page_end=rec.get("page_end", rec["page_num"]),
                char_start=rec.get("char_start", 0),
                char_end=rec.get("char_end", 0),
                doc_name=rec.get("doc_name"),
                metadata={
                    "bm25_score": rec.get("bm25_score", 0.0),
                    "vector_score": rec.get("vector_score", 0.0),
                    "rrf_score": rec["rrf_score"],
                },
            )
            for rec in fused
        ]

        # FR-022: Apply optional reranker post-RRF
        results = self._apply_reranker(query, results, top_k)

        return SearchResponse(
            results=results,
            provider=self.provider,
            embedding_usage={},
        )

    def _apply_reranker(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Apply optional reranker to results (FR-022).

        When RERANKER_ENABLED=true, re-scores results using the configured
        reranker client. Stores reranker_score in result metadata.
        When disabled, returns results unchanged.
        """
        from app.reranker import get_reranker_client

        reranker = get_reranker_client()
        if reranker is None:
            return results

        from app.config import RERANKER_TOP_K

        reranked = reranker.rerank(query, results, top_k=min(top_k, RERANKER_TOP_K))

        # Inject reranker_score into metadata for confidence gating
        for result in reranked:
            result.metadata["reranker_score"] = result.score

        return reranked

    def _load_index_records(
        self,
        docs_snapshot_id: str | None,
        tenant_id: str,
        matter_id: str,
    ) -> list[dict[str, Any]]:
        """Load index records with tenant/matter isolation."""
        rows = load_index_records(docs_snapshot_id, tenant_id, matter_id)
        records: list[dict[str, Any]] = []
        for row in rows:
            rec: dict[str, Any] = {
                "chunk_id": row.chunk_id,
                "docs_snapshot_id": row.docs_snapshot_id,
                "doc_id": row.doc_id,
                "doc_name": row.doc_name,
                "page_num": row.page_num,
                "page_end": getattr(row, "page_end", row.page_num),
                "char_start": getattr(row, "char_start", 0),
                "char_end": getattr(row, "char_end", 0),
                "chunk_index": row.chunk_index,
                "chunk_text": row.chunk_text,
                "embedding_vector": json.loads(row.embedding_json),
            }
            records.append(rec)
        return records

    def _fallback_overlap(
        self,
        query: str,
        docs_snapshot_id: str | None,
        tenant_id: str,
        matter_id: str,
        top_k: int,
    ) -> list[SearchResult]:
        """Fallback overlap search when no indexed records exist."""
        query_tokens = self._tokenize(query)
        rows = load_chunks(docs_snapshot_id, tenant_id, matter_id)
        scored: list[dict[str, Any]] = []

        for row in rows:
            score = self._overlap_score(query_tokens, row.chunk_text)
            scored.append(
                {
                    "chunk_id": row.chunk_id,
                    "doc_id": row.doc_id,
                    "chunk_text": row.chunk_text,
                    "page_num": row.page_num,
                    "page_end": getattr(row, "page_end", row.page_num),
                    "char_start": getattr(row, "char_start", 0),
                    "char_end": getattr(row, "char_end", 0),
                    "score": score,
                }
            )

        scored.sort(key=lambda x: x["score"], reverse=True)

        return [
            SearchResult(
                chunk_id=rec["chunk_id"],
                doc_id=rec["doc_id"],
                text=rec["chunk_text"],
                score=rec["score"],
                page_number=rec["page_num"],
                page_end=rec.get("page_end", rec["page_num"]),
                char_start=rec.get("char_start", 0),
                char_end=rec.get("char_end", 0),
                metadata={"fallback": True},
            )
            for rec in scored[:top_k]
        ]

    def _apply_rank_scores(
        self,
        combined: dict[str, dict[str, Any]],
        ranked: list[dict[str, Any]],
        key: str,
    ) -> None:
        """Apply RRF rank scores to combined results."""
        for idx, rec in enumerate(ranked, start=1):
            chunk_id = rec["chunk_id"]
            entry = combined.get(chunk_id)
            if not entry:
                entry = dict(rec)
                entry["rrf_score_raw"] = 0.0
                combined[chunk_id] = entry
            entry["rrf_score_raw"] += 1 / (self._rrf_k + idx)
            entry[f"{key}_rank"] = idx

    def _get_bm25_stats(
        self, records: list[dict[str, Any]], snapshot_key: str
    ) -> dict[str, Any]:
        """Get or compute BM25 statistics."""
        cached = self._bm25_cache.get(snapshot_key)
        if cached and cached.get("num_docs") == len(records):
            return cached
        stats = self._build_bm25_stats(records)
        self._bm25_cache[snapshot_key] = stats
        return stats

    def _build_bm25_stats(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Build BM25 statistics from records."""
        df: Counter[str] = Counter()
        doc_stats: dict[str, dict[str, Any]] = {}
        total_len = 0

        for rec in records:
            stats = self._build_doc_stats(rec["chunk_text"])
            doc_stats[rec["chunk_id"]] = stats
            total_len += stats["dl"]
            df.update(set(stats["tf"].keys()))

        num_docs = len(records)
        avgdl = (total_len / num_docs) if num_docs else 0.0

        return {
            "df": df,
            "avgdl": avgdl,
            "doc_stats": doc_stats,
            "num_docs": num_docs,
        }

    def _build_doc_stats(self, text: str) -> dict[str, Any]:
        """Build document statistics for BM25."""
        tokens = self._tokenize(text)
        return {"tf": Counter(tokens), "dl": len(tokens)}

    def _bm25_score(
        self,
        query_tokens: list[str],
        tf: Counter[str],
        df: Counter[str],
        num_docs: int,
        dl: int,
        avgdl: float,
        k1: float = 1.2,
        b: float = 0.75,
    ) -> float:
        """Calculate BM25 score."""
        if not query_tokens or num_docs == 0 or dl == 0:
            return 0.0

        score = 0.0
        for term in set(query_tokens):
            df_t = df.get(term, 0)
            idf = math.log((num_docs - df_t + 0.5) / (df_t + 0.5) + 1)
            tf_t = tf.get(term, 0)
            if tf_t == 0:
                continue
            denom = tf_t + k1 * (1 - b + b * (dl / avgdl)) if avgdl else 1.0
            score += idf * ((tf_t * (k1 + 1)) / denom)

        return score

    # Stop words for tokenization
    _STOP_WORDS = {
        "a", "an", "the", "and", "or", "but", "if", "then", "else", "when",
        "at", "from", "by", "for", "with", "about", "against", "between",
        "into", "through", "during", "before", "after", "above", "below",
        "to", "up", "down", "in", "out", "on", "off", "over", "under",
        "again", "further", "once", "here", "there", "where", "why", "how",
        "all", "any", "both", "each", "few", "more", "most", "other", "some",
        "such", "no", "nor", "not", "only", "own", "same", "so", "than",
        "too", "very", "can", "will", "just", "should", "now", "of", "is",
        "am", "are", "was", "were", "be", "been", "being", "have", "has",
        "had", "do", "does", "did",
    }

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text, removing stop words."""
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return [t for t in tokens if t not in self._STOP_WORDS]

    def _overlap_score(self, query_tokens: list[str], text: str) -> float:
        """Calculate token overlap score."""
        if not query_tokens:
            return 0.0
        text_tokens = set(self._tokenize(text))
        overlap = sum(1 for t in query_tokens if t in text_tokens)
        return overlap / max(len(query_tokens), 1)

    def _cosine(self, vec_a: list[float], vec_b: list[float]) -> float:
        """Calculate cosine similarity."""
        if not vec_a or not vec_b:
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
