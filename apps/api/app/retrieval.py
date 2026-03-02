import json
import math
import re
import time as _time
import urllib.request
import urllib.error
from collections import Counter
from typing import Any

from app.config import (
    AZURE_SEARCH_API_KEY,
    AZURE_SEARCH_API_VERSION,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    AZURE_SEMANTIC_ENABLED,
    RRF_K,
    TOP_K,
    TOP_K_BM25,
    TOP_K_VECTOR,
)

from app.db import load_chunks, load_index_records
from app.embeddings import embed_texts_with_usage
from app.otel import get_observe_decorator, safe_update_observation
from app.telemetry import logger

_observe = get_observe_decorator()

# Type aliases for clarity
ChunkRecord = dict[str, Any]
BM25Stats = dict[str, Any]
UsageInfo = dict[str, Any]

_BM25_CACHE: dict[str, BM25Stats] = {}


def _enrich_hybrid_observation(mode: str, result_count: int, start: float) -> None:
    """Enrich Langfuse observation with search metadata (NFR-045). No PII."""
    latency_ms = int((_time.perf_counter() - start) * 1000)
    safe_update_observation(
        metadata={
            "mode": mode,
            "result_count": result_count,
            "latency_ms": latency_ms,
        },
    )


@_observe(name="hybrid_search", capture_input=False, capture_output=False)
def hybrid_search(
    question: str,
    docs_snapshot_id: str | None,
    tenant_id: str,
    matter_id: str,
    *,
    return_usage: bool = False,
) -> list[ChunkRecord] | tuple[list[ChunkRecord], UsageInfo]:
    """Hybrid search with REQUIRED tenant/matter isolation (FR-001, FR-002).

    Args:
        question: Search query
        docs_snapshot_id: Optional document snapshot filter
        tenant_id: Tenant ID (REQUIRED for FR-001 isolation)
        matter_id: Matter ID (REQUIRED for FR-002 isolation)
        return_usage: Whether to return embedding usage info

    Returns:
        List of matching chunks, optionally with usage info
    """
    _start = _time.perf_counter()
    embeddings, embedding_usage = embed_texts_with_usage([question])
    query_embedding = embeddings[0]
    if _azure_enabled():
        logger.info(f"Retrieval: Routing to Azure AI Search (Snapshot: {docs_snapshot_id}, Tenant: {tenant_id})")
        results = _azure_search(question, docs_snapshot_id, query_embedding, tenant_id, matter_id)
        if results:
            _enrich_hybrid_observation("azure", len(results), _start)
            return (results, embedding_usage) if return_usage else results
        logger.info("Retrieval: Azure returned zero hits. Falling back to local index.")

    logger.info(f"Retrieval: Using Local Hybrid Logic (Snapshot: {docs_snapshot_id}, Tenant: {tenant_id})")
    records = _load_index_records(docs_snapshot_id, tenant_id, matter_id)
    if not records:
        fallback = _fallback_overlap(question, docs_snapshot_id, tenant_id, matter_id)
        _enrich_hybrid_observation("local_fallback", len(fallback), _start)
        return (fallback, embedding_usage) if return_usage else fallback

    query_tokens = _tokenize(question)
    snapshot_key = docs_snapshot_id or "none"
    bm25_stats = _get_bm25_stats(records, snapshot_key)

    for rec in records:
        doc_stats = bm25_stats["doc_stats"].get(rec["chunk_id"])
        if not doc_stats:
            doc_stats = _build_doc_stats(rec["chunk_text"])
        rec["bm25_score"] = _bm25_score(
            query_tokens,
            doc_stats["tf"],
            bm25_stats["df"],
            bm25_stats["num_docs"],
            doc_stats["dl"],
            bm25_stats["avgdl"],
        )
        rec["vector_score"] = _cosine(query_embedding, rec["embedding_vector"])

    bm25_ranked = sorted(records, key=lambda r: r["bm25_score"], reverse=True)[
        :TOP_K_BM25
    ]
    vec_ranked = sorted(records, key=lambda r: r["vector_score"], reverse=True)[
        :TOP_K_VECTOR
    ]

    combined: dict[str, ChunkRecord] = {}
    _apply_rank_scores(combined, bm25_ranked, key="bm25")
    _apply_rank_scores(combined, vec_ranked, key="vector")

    max_rrf = 2 / (RRF_K + 1)
    for rec in combined.values():
        rec["rrf_score"] = rec["rrf_score_raw"] / max_rrf if max_rrf else 0.0

    fused = sorted(combined.values(), key=lambda r: r["rrf_score"], reverse=True)[:TOP_K]
    for idx, rec in enumerate(fused, start=1):
        rec["rrf_rank"] = idx

    logger.info(f"Local Hybrid Search: Found {len(fused)} fused results")
    _enrich_hybrid_observation("local", len(fused), _start)
    return (fused, embedding_usage) if return_usage else fused


def _azure_enabled() -> bool:
    return bool(AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY and AZURE_SEARCH_INDEX)


def _azure_search(
    question: str,
    docs_snapshot_id: str | None,
    query_embedding: list[float],
    tenant_id: str,
    matter_id: str,
) -> list[ChunkRecord]:
    """Azure AI Search with REQUIRED tenant/matter filters (FR-001, FR-002).

    Args:
        question: Search query
        docs_snapshot_id: Optional document snapshot filter
        query_embedding: Query embedding vector
        tenant_id: Tenant ID (REQUIRED for FR-001 isolation)
        matter_id: Matter ID (REQUIRED for FR-002 isolation)

    Returns:
        List of matching chunks from Azure Search
    """
    vector_len = len(query_embedding)
    base_payload: dict[str, Any] = {
        "search": question,
        "vectorQueries": [
            {
                "kind": "vector",
                "vector": query_embedding,
                "fields": "embedding_vector",
                "k": TOP_K_VECTOR,
            }
        ],
        "top": TOP_K,
    }
    semantic_payload: dict[str, Any] = {
        **base_payload,
        "queryType": "semantic",
        "semanticConfiguration": "default",
        "captions": "extractive|highlight-true",
        "answers": "extractive|count-3",
    }

    # Build filter with REQUIRED tenant/matter isolation (FR-001, FR-002)
    filters: list[str] = []
    filters.append(f"tenant_id eq '{tenant_id}'")
    filters.append(f"matter_id eq '{matter_id}'")
    if docs_snapshot_id and docs_snapshot_id != "none":
        filters.append(f"docs_snapshot_id eq '{docs_snapshot_id}'")

    filter_string = " and ".join(filters)
    base_payload["filter"] = filter_string
    semantic_payload["filter"] = filter_string
    filter_state = f"tenant={tenant_id},matter={matter_id},snapshot={docs_snapshot_id or 'none'}"

    url = f"{AZURE_SEARCH_ENDPOINT.rstrip('/')}/indexes/{AZURE_SEARCH_INDEX}/docs/search?api-version={AZURE_SEARCH_API_VERSION}"
    semantic_requested = bool(AZURE_SEMANTIC_ENABLED)
    semantic_used = False
    fallback_reason: str | None = None
    data: dict[str, Any] = {}

    if semantic_requested:
        _log_azure_search_request(semantic_payload, vector_len, filter_state)
        try:
            data = _request_azure_search(url, semantic_payload)
            semantic_used = True
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            reason = _semantic_fallback_reason(body)
            if exc.code in (400, 403) and reason:
                fallback_reason = reason
                logger.warning(
                    "Azure Search semantic unavailable (%s). Retrying without semantic features.",
                    reason,
                )
                _log_azure_search_request(base_payload, vector_len, filter_state)
                try:
                    data = _request_azure_search(url, base_payload)
                except urllib.error.HTTPError as fallback_exc:
                    fallback_body = fallback_exc.read().decode("utf-8", errors="replace")
                    _log_azure_error(
                        fallback_exc,
                        fallback_body,
                        url,
                        vector_len,
                        filter_state,
                    )
                    raise
            else:
                _log_azure_error(exc, body, url, vector_len, filter_state)
                raise
    else:
        _log_azure_search_request(base_payload, vector_len, filter_state)
        try:
            data = _request_azure_search(url, base_payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            _log_azure_error(exc, body, url, vector_len, filter_state)
            raise

    hits = data.get("value", [])
    logger.info(f"Azure Search: Found {len(hits)} hits for snapshot {docs_snapshot_id}")
    for idx, doc in enumerate(hits[:3]):
        logger.info(
            f"  Hit {idx+1}: AzureScore={doc.get('@search.score')} Reranker={doc.get('@search.rerankerScore')} ID={doc['chunk_id']}"
        )

    results: list[ChunkRecord] = []
    for doc in hits:
        azure_search_score = doc.get("@search.score", 0.0)
        azure_reranker_score = doc.get("@search.rerankerScore")

        # Extract captions if available (semantic highlight)
        captions = doc.get("@search.captions", [])
        highlighted_text = captions[0].get("highlights") if captions else None

        # If no highlight, fallback to chunk_text or text from caption
        if not highlighted_text and captions:
            highlighted_text = captions[0].get("text")

        results.append(
            {
                "chunk_id": doc["chunk_id"],
                "docs_snapshot_id": doc["docs_snapshot_id"],
                "doc_id": doc["doc_id"],
                "doc_name": doc.get("doc_name"),
                "page_num": doc["page_num"],
                "page_end": doc.get("page_end", doc["page_num"]),
                "char_start": doc.get("char_start", 0),
                "char_end": doc.get("char_end", 0),
                "chunk_index": doc["chunk_index"],
                "chunk_text": doc["chunk_text"],
                "highlighted_text": highlighted_text,
                "azure_search_score": azure_search_score,
                "azure_reranker_score": azure_reranker_score,
                "reranker_score": azure_reranker_score or 0.0,
                "semantic_requested": semantic_requested,
                "semantic_used": semantic_used,
                "semantic_fallback_reason": fallback_reason,
            }
        )
    return results


def _request_azure_search(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_SEARCH_API_KEY,
        },
    )
    with urllib.request.urlopen(req) as resp:
        result: dict[str, Any] = json.load(resp)
        return result


def _log_azure_search_request(payload: dict[str, Any], vector_len: int, filter_state: str) -> None:
    logger.info(
        "Azure Search request: index=%s api=%s top=%s vector_k=%s vector_len=%s queryType=%s semanticConfig=%s filter=%s",
        AZURE_SEARCH_INDEX,
        AZURE_SEARCH_API_VERSION,
        TOP_K,
        TOP_K_VECTOR,
        vector_len,
        payload.get("queryType"),
        payload.get("semanticConfiguration"),
        filter_state,
    )


def _log_azure_error(
    exc: urllib.error.HTTPError,
    body: str,
    url: str,
    vector_len: int,
    filter_state: str,
) -> None:
    logger.error(
        "Azure Search HTTP %s: %s | url=%s index=%s api=%s vector_len=%s filter=%s",
        exc.code,
        body,
        url,
        AZURE_SEARCH_INDEX,
        AZURE_SEARCH_API_VERSION,
        vector_len,
        filter_state,
    )


_SEMANTIC_UNSUPPORTED_CODES = {
    "SemanticQueriesNotAvailable",
    "FeatureNotSupportedInService",
}


def _semantic_fallback_reason(body: str) -> str | None:
    if not body:
        return None
    try:
        data = json.loads(body)
        error = data.get("error", {}) if isinstance(data, dict) else {}
        codes: list[str] = []
        code = error.get("code")
        if code:
            codes.append(code)
        for detail in error.get("details") or []:
            detail_code = detail.get("code")
            if detail_code:
                codes.append(detail_code)
        for candidate in codes:
            if candidate in _SEMANTIC_UNSUPPORTED_CODES:
                return candidate
        message = (error.get("message") or "").lower()
        if "semantic" in message and ("not enabled" in message or "not supported" in message):
            return "semantic_not_supported"
    except json.JSONDecodeError:
        pass
    lower = body.lower()
    if "semantic" in lower and ("not enabled" in lower or "not supported" in lower):
        return "semantic_not_supported"
    return None


def _apply_rank_scores(
    combined: dict[str, ChunkRecord], ranked: list[ChunkRecord], key: str
) -> None:
    for idx, rec in enumerate(ranked, start=1):
        chunk_id = rec["chunk_id"]
        entry = combined.get(chunk_id)
        if not entry:
            entry = dict(rec)
            entry["rrf_score_raw"] = 0.0
            combined[chunk_id] = entry
        entry["rrf_score_raw"] += 1 / (RRF_K + idx)
        entry[f"{key}_rank"] = idx


def _load_index_records(
    docs_snapshot_id: str | None,
    tenant_id: str,
    matter_id: str,
) -> list[ChunkRecord]:
    """Load index records with REQUIRED tenant/matter isolation (FR-001, FR-002)."""
    rows = load_index_records(docs_snapshot_id, tenant_id, matter_id)
    records: list[ChunkRecord] = []
    for row in rows:
        rec: ChunkRecord = {
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
    question: str,
    docs_snapshot_id: str | None,
    tenant_id: str,
    matter_id: str,
) -> list[ChunkRecord]:
    """Fallback overlap search with REQUIRED tenant/matter isolation (FR-001, FR-002)."""
    query_tokens = _tokenize(question)
    rows = load_chunks(docs_snapshot_id, tenant_id, matter_id)
    scored: list[ChunkRecord] = []
    for row in rows:
        score = _overlap_score(query_tokens, row.chunk_text)
        entry: ChunkRecord = {
            "chunk_id": row.chunk_id,
            "docs_snapshot_id": row.docs_snapshot_id,
            "doc_id": row.doc_id,
            "page_num": row.page_num,
            "page_end": getattr(row, "page_end", row.page_num),
            "char_start": getattr(row, "char_start", 0),
            "char_end": getattr(row, "char_end", 0),
            "chunk_index": row.chunk_index,
            "chunk_text": row.chunk_text,
        }
        entry["bm25_score"] = score
        entry["vector_score"] = 0.0
        entry["rrf_score"] = score
        entry["rrf_rank"] = 0
        scored.append(entry)
    scored.sort(key=lambda x: x["rrf_score"], reverse=True)
    return scored[:TOP_K]


def _build_doc_stats(text: str) -> dict[str, Any]:
    tokens = _tokenize(text)
    return {"tf": Counter(tokens), "dl": len(tokens)}


def _build_bm25_stats(records: list[ChunkRecord]) -> BM25Stats:
    df: Counter[str] = Counter()
    doc_stats: dict[str, dict[str, Any]] = {}
    total_len = 0
    for rec in records:
        stats = _build_doc_stats(rec["chunk_text"])
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


def _get_bm25_stats(records: list[ChunkRecord], snapshot_key: str) -> BM25Stats:
    cached = _BM25_CACHE.get(snapshot_key)
    if cached and cached.get("num_docs") == len(records):
        return cached
    stats = _build_bm25_stats(records)
    _BM25_CACHE[snapshot_key] = stats
    return stats


def _bm25_score(
    query_tokens: list[str],
    tf: Counter[str],
    df: Counter[str],
    num_docs: int,
    dl: int,
    avgdl: float,
    k1: float = 1.2,
    b: float = 0.75,
) -> float:
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


STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", "at", "from",
    "by", "for", "with", "about", "against", "between", "into", "through", "during",
    "before", "after", "above", "below", "to", "up", "down", "in", "out", "on", "off",
    "over", "under", "again", "further", "then", "once", "here", "there", "where",
    "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "can", "will", "just", "should", "now", "of", "is", "am", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did"
}


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def _overlap_score(query_tokens: list[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    text_tokens = set(_tokenize(text))
    overlap = sum(1 for t in query_tokens if t in text_tokens)
    return overlap / max(len(query_tokens), 1)


def _cosine(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
