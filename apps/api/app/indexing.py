import json
import urllib.request
import urllib.error
from typing import Any

from app.config import (
    AZURE_SEARCH_API_KEY,
    AZURE_SEARCH_API_VERSION,
    AZURE_SEARCH_CREATE_INDEX,
    AZURE_SEARCH_ENDPOINT,
    AZURE_SEARCH_INDEX,
    EMBEDDINGS_DIM,
    ENABLE_INDEXING,
    INDEX_VERSION,
    RETRIEVAL_VERSION,
)
from app.db import IndexRecord, insert_index_records
from app.embeddings import embed_texts
from app.ingestion import utc_now

# Type alias for chunk row tuple
ChunkRowTuple = tuple[str, str, str, str, int, int, int, int, int, str, str]


def index_chunk_rows(
    doc_id: str,
    doc_name: str,
    docs_snapshot_id: str,
    chunk_rows: list[ChunkRowTuple],
    tenant_id: str = "",
    matter_id: str = "",
) -> None:
    if not ENABLE_INDEXING:
        return

    # Tuple structure (FR-013): (chunk_id, snap_id, doc_id, sha256, page_num, page_end, chunk_idx, char_start, char_end, text, mode)
    texts = [row[9] for row in chunk_rows]
    embeddings = embed_texts(texts)
    indexed_at = utc_now()

    records = []
    for row, embedding in zip(chunk_rows, embeddings, strict=False):
        (
            chunk_id,
            docs_snapshot_id_row,
            doc_id_row,
            doc_sha256,
            page_num,
            page_end,
            chunk_index,
            char_start,
            char_end,
            chunk_text,
            parse_mode,
        ) = row
        records.append(
            {
                "chunk_id": chunk_id,
                "docs_snapshot_id": docs_snapshot_id_row,
                "doc_id": doc_id_row,
                "doc_name": doc_name,
                "page_num": page_num,
                "page_end": page_end,
                "char_start": char_start,
                "char_end": char_end,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "embedding_vector": embedding,
                "indexed_at_utc": indexed_at,
                "index_version": INDEX_VERSION,
                "retrieval_version": RETRIEVAL_VERSION,
                "tenant_id": tenant_id,
                "matter_id": matter_id,
            }
        )

    if _azure_enabled():
        ensure_index()
        _azure_upload(records)
    else:
        insert_index_records(
            IndexRecord(
                chunk_id=rec["chunk_id"],
                tenant_id=tenant_id,
                matter_id=matter_id,
                docs_snapshot_id=rec["docs_snapshot_id"],
                doc_id=rec["doc_id"],
                doc_name=rec["doc_name"],
                page_num=rec["page_num"],
                page_end=rec["page_end"],
                char_start=rec["char_start"],
                char_end=rec["char_end"],
                chunk_index=rec["chunk_index"],
                chunk_text=rec["chunk_text"],
                embedding_json=json.dumps(rec["embedding_vector"]),
                indexed_at_utc=rec["indexed_at_utc"],
                index_version=rec["index_version"],
                retrieval_version=rec["retrieval_version"],
            )
            for rec in records
        )


def _azure_enabled() -> bool:
    return bool(AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY and AZURE_SEARCH_INDEX)


def ensure_index(force: bool = False) -> None:
    if not AZURE_SEARCH_CREATE_INDEX and not force:
        return

    schema = {
        "name": AZURE_SEARCH_INDEX,
        "fields": [
            {"name": "chunk_id", "type": "Edm.String", "key": True, "filterable": True},
            {
                "name": "docs_snapshot_id",
                "type": "Edm.String",
                "filterable": True,
            },
            {"name": "doc_id", "type": "Edm.String", "filterable": True},
            {"name": "doc_name", "type": "Edm.String", "filterable": True},
            {"name": "page_num", "type": "Edm.Int32", "filterable": True},
            {"name": "page_end", "type": "Edm.Int32", "filterable": True, "retrievable": True},
            {"name": "char_start", "type": "Edm.Int32", "filterable": True, "retrievable": True},
            {"name": "char_end", "type": "Edm.Int32", "filterable": True, "retrievable": True},
            {"name": "chunk_index", "type": "Edm.Int32", "filterable": True},
            {"name": "chunk_text", "type": "Edm.String", "searchable": True, "retrievable": True},
            {
                "name": "embedding_vector",
                "type": "Collection(Edm.Single)",
                "searchable": True,
                "retrievable": True,
                "dimensions": EMBEDDINGS_DIM,
                "vectorSearchProfile": "vprofile",
            },
            {"name": "indexed_at_utc", "type": "Edm.String", "retrievable": True},
            {"name": "index_version", "type": "Edm.String", "retrievable": True},
            {"name": "retrieval_version", "type": "Edm.String", "retrievable": True},
        ],
        "vectorSearch": {
            "profiles": [{"name": "vprofile", "algorithm": "halgo"}],
            "algorithms": [{"name": "halgo", "kind": "hnsw"}],
        },
        "semantic": {
            "configurations": [
                {
                    "name": "default",
                    "prioritizedFields": {
                        "prioritizedContentFields": [{"fieldName": "chunk_text"}]
                    },
                }
            ]
        },
    }
    url = _azure_url(f"/indexes/{AZURE_SEARCH_INDEX}?api-version={AZURE_SEARCH_API_VERSION}")
    
    try:
        _azure_request("PUT", url, schema)
    except Exception as e:
        print(f"Warning: Index creation/update failed: {e}")


def _azure_upload(records: list[dict[str, Any]]) -> None:
    payload = {"value": [{"@search.action": "upload", **rec} for rec in records]}
    url = _azure_url(f"/indexes/{AZURE_SEARCH_INDEX}/docs/index?api-version={AZURE_SEARCH_API_VERSION}")
    _azure_request("POST", url, payload)


def _azure_url(path: str) -> str:
    return f"{AZURE_SEARCH_ENDPOINT.rstrip('/')}{path}"


def _azure_request(method: str, url: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Content-Type": "application/json",
            "api-key": AZURE_SEARCH_API_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            if resp.status >= 300:
                raise RuntimeError(f"Azure Search request failed: {resp.status}")
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"Azure Search request failed: {e.code} - {error_body}") from e
    except Exception:
        raise
