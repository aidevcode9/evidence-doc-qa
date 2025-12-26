import json
import math
import re
import urllib.request
from typing import Dict, List, Optional

from .config import (
    AZURE_SEARCH_API_KEY,
    AZURE_SEARCH_API_VERSION,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    RRF_K,
    TOP_K,
    TOP_K_BM25,
    TOP_K_VECTOR,
)
from .db import load_chunks, load_index_records
from .embeddings import embed_texts


def hybrid_search(question: str, docs_snapshot_id: Optional[str]) -> List[Dict]:
    if _azure_enabled():
        return _azure_search(question, docs_snapshot_id)

    records = _load_index_records(docs_snapshot_id)
    if not records:
        return _fallback_overlap(question, docs_snapshot_id)


def _azure_enabled() -> bool:
    return bool(AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY and AZURE_SEARCH_INDEX)


def _azure_search(question: str, docs_snapshot_id: Optional[str]) -> List[Dict]:
    query_embedding = embed_texts([question])[0]
    payload = {
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
    if docs_snapshot_id and docs_snapshot_id != "none":
        payload["filter"] = f"docs_snapshot_id eq '{docs_snapshot_id}'"

    url = f"{AZURE_SEARCH_ENDPOINT.rstrip('/')}/indexes/{AZURE_SEARCH_INDEX}/docs/search?api-version={AZURE_SEARCH_API_VERSION}"
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
        data = json.load(resp)

    results = []
    for doc in data.get("value", []):
        results.append(
            {
                "chunk_id": doc["chunk_id"],
                "docs_snapshot_id": doc["docs_snapshot_id"],
                "doc_id": doc["doc_id"],
                "doc_name": doc.get("doc_name"),
                "page_num": doc["page_num"],
                "chunk_index": doc["chunk_index"],
                "chunk_text": doc["chunk_text"],
                "rrf_score": doc.get("@search.score", 0.0),
            }
        )
    return results


def _apply_rank_scores(
    combined: Dict[str, Dict], ranked: List[Dict], key: str
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


def _load_index_records(docs_snapshot_id: Optional[str]) -> List[Dict]:
    rows = load_index_records(docs_snapshot_id)
    records = []
    for row in rows:
        rec = {
            "chunk_id": row.chunk_id,
            "docs_snapshot_id": row.docs_snapshot_id,
            "doc_id": row.doc_id,
            "doc_name": row.doc_name,
            "page_num": row.page_num,
            "chunk_index": row.chunk_index,
            "chunk_text": row.chunk_text,
            "embedding_vector": json.loads(row.embedding_json),
        }
        records.append(rec)
    return records


def _fallback_overlap(
    question: str, docs_snapshot_id: Optional[str]
) -> List[Dict]:
    query_tokens = _tokenize(question)
    rows = load_chunks(docs_snapshot_id)
    scored = []
    for row in rows:
        score = _overlap_score(query_tokens, row.chunk_text)
        entry = {
            "chunk_id": row.chunk_id,
            "docs_snapshot_id": row.docs_snapshot_id,
            "doc_id": row.doc_id,
            "page_num": row.page_num,
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


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _overlap_score(query_tokens: List[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    text_tokens = set(_tokenize(text))
    overlap = sum(1 for t in query_tokens if t in text_tokens)
    return overlap / max(len(query_tokens), 1)


def _cosine(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
