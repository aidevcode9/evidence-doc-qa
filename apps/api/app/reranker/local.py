"""Local reranker using query-document term analysis (FR-022).

Lightweight reranker that scores candidates using:
1. Exact phrase matching (highest boost)
2. Term overlap ratio
3. Original retrieval score (weighted blend)

No external API calls — runs entirely in-process.
"""

from __future__ import annotations

from app.reranker.base import RerankerClient
from app.search.base import SearchResult
from app.text_utils import STOP_WORDS, tokenize


class LocalReranker(RerankerClient):
    """Term-analysis reranker with phrase matching."""

    provider: str = "local"

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        *,
        top_k: int = 5,
    ) -> list[SearchResult]:
        if not candidates:
            return []

        # Pre-compute query analysis (once, not per-candidate)
        content_tokens = [t for t in tokenize(query) if t not in STOP_WORDS]
        content_token_set = set(content_tokens)
        content_phrase = " ".join(content_tokens)
        has_phrase = len(content_tokens) > 1

        scored: list[tuple[float, int, SearchResult]] = []
        for idx, result in enumerate(candidates):
            text_lower = result.text.lower()

            # Phrase match bonus (0.0 or 0.5)
            phrase_bonus = 0.5 if has_phrase and content_phrase in text_lower else 0.0

            # Term overlap ratio (0.0 - 0.4)
            doc_tokens = set(tokenize(result.text))
            if content_token_set:
                content_overlap = len(content_token_set & doc_tokens) / len(content_token_set)
            else:
                content_overlap = 0.0
            term_score = content_overlap * 0.4

            # Original score weight (0.0 - 0.1)
            original_weight = result.score * 0.1

            combined = phrase_bonus + term_score + original_weight
            # Use -idx as tiebreaker to maintain stable order
            scored.append((combined, -idx, result))

        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

        reranked: list[SearchResult] = []
        for combined_score, _, result in scored[:top_k]:
            reranked.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    doc_id=result.doc_id,
                    text=result.text,
                    score=round(combined_score, 4),
                    page_number=result.page_number,
                    page_end=result.page_end,
                    char_start=result.char_start,
                    char_end=result.char_end,
                    doc_name=result.doc_name,
                    metadata=result.metadata,
                )
            )
        return reranked
