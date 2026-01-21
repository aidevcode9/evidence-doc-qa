import hashlib
from typing import Any

from app import evidence
from app.config import (
    CONFIDENCE_THRESHOLD,
    AZURE_RERANK_MIN,
    AZURE_SEARCH_SCORE_MIN,
)
from app.db import get_doc_name
from app.schemas import DebugCandidate

ChunkDict = dict[str, Any]


def retrieval_score_key(results: list[ChunkDict]) -> str:
    if not results:
        return "rrf_score"
    if "rrf_score" in results[0]:
        return "rrf_score"
    if "azure_search_score" in results[0]:
        return "azure_search_score"
    return "rrf_score"


def confidence_score_key(results: list[ChunkDict]) -> str:
    if not results:
        return "rrf_score"
    if "azure_search_score" in results[0]:
        if results[0].get("azure_reranker_score") is not None:
            return "azure_reranker_score"
        return "azure_search_score"
    return "rrf_score"


def confidence_threshold(score_key: str) -> float:
    if score_key == "azure_reranker_score":
        return AZURE_RERANK_MIN
    if score_key == "azure_search_score":
        return AZURE_SEARCH_SCORE_MIN
    return CONFIDENCE_THRESHOLD


def score_value(chunk: ChunkDict, key: str) -> float:
    value = chunk.get(key)
    if value is None:
        return 0.0
    return float(value)


def snippet_for(chunk_text: str, limit: int = 200) -> str:
    return chunk_text[:limit].strip()


def doc_name_for(doc_id: str) -> str:
    return get_doc_name(doc_id) or "unknown"


def build_debug_candidates(
    question: str,
    chunks: list[ChunkDict],
    *,
    verification_results: dict[str, tuple[str, str | None]] | None = None,
    verification_reasons: dict[str, str] | None = None,
    reason_override: str | None = None,
) -> list[DebugCandidate]:
    question_tokens = evidence.tokenize(question)
    debug_candidates: list[DebugCandidate] = []
    for chunk in chunks[:3]:
        span = evidence.best_supporting_span(question, chunk["chunk_text"])
        if not span:
            span = snippet_for(chunk["chunk_text"])
        status = "skipped"
        verified_span = None
        if verification_results:
            status, verified_span = verification_results.get(chunk["chunk_id"], ("skipped", None))
        if verified_span:
            span = verified_span
        overlap_score = evidence.overlap_score(question_tokens, span)
        if reason_override:
            reason = reason_override
        else:
            reason = {
                "verified": "LLM_VERIFIED",
                "rejected": "LLM_REJECTED",
                "unverified": "LLM_UNAVAILABLE",
                "skipped": "NOT_EVALUATED",
            }.get(status, "UNKNOWN")
            if verification_reasons and status in {"verified", "rejected"}:
                reason = verification_reasons.get(chunk["chunk_id"], reason)
        debug_candidates.append(
            DebugCandidate(
                doc_id=chunk["doc_id"],
                doc_name=chunk.get("doc_name") or doc_name_for(chunk["doc_id"]),
                page_num=chunk["page_num"],
                page_end=chunk.get("page_end", chunk["page_num"]),
                char_start=chunk.get("char_start", 0),
                char_end=chunk.get("char_end", 0),
                chunk_id=chunk["chunk_id"],
                rrf_score=round(chunk["rrf_score"], 4) if "rrf_score" in chunk else None,
                azure_search_score=(
                    round(chunk.get("azure_search_score", 0.0), 4)
                    if "azure_search_score" in chunk
                    else None
                ),
                azure_reranker_score=(
                    round(chunk.get("azure_reranker_score", 0.0), 4)
                    if "azure_reranker_score" in chunk
                    else None
                ),
                overlap_score=round(overlap_score, 4),
                verifier_verdict=status.upper(),
                reason=reason,
                snippet=span,
            )
        )
    return debug_candidates


def build_retrieval_trace(results: list[ChunkDict]) -> dict[str, Any] | None:
    if not results:
        return None
    trace: dict[str, float | str | bool | None] = {}
    if "azure_search_score" in results[0]:
        trace["lexical_mode"] = "azure_hybrid"
        trace["azure_search_score_top"] = round(
            results[0].get("azure_search_score", 0.0),
            4,
        )
        if results[0].get("azure_reranker_score") is not None:
            trace["semantic_reranker_enabled"] = True
            trace["azure_reranker_score_top"] = round(
                results[0].get("azure_reranker_score", 0.0),
                4,
            )
        else:
            trace["semantic_reranker_enabled"] = False
    else:
        top_rrf = results[0].get("rrf_score")
        second_rrf = results[1].get("rrf_score") if len(results) > 1 else 0.0
        trace = {
            "top_rrf_score": round(top_rrf, 4) if top_rrf is not None else None,
            "rrf_margin": round(top_rrf - second_rrf, 4) if top_rrf is not None else None,
            "semantic_reranker_enabled": False,
            "lexical_mode": "local_bm25",
        }
        if "bm25_score" in results[0]:
            trace["top_lexical_score"] = round(
                max(r.get("bm25_score", 0.0) for r in results),
                4,
            )
        if "vector_score" in results[0]:
            trace["top_vector_score"] = round(
                max(r.get("vector_score", 0.0) for r in results),
                4,
            )
    if "semantic_requested" in results[0]:
        trace["semantic_requested"] = bool(results[0].get("semantic_requested"))
    if "semantic_used" in results[0]:
        trace["semantic_used"] = bool(results[0].get("semantic_used"))
    if results[0].get("semantic_fallback_reason"):
        trace["semantic_fallback_reason"] = results[0].get("semantic_fallback_reason")
    return {k: v for k, v in trace.items() if v is not None}


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
