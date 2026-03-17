"""In-memory LRU caches for embedding and query result reuse (Cost Reduction).

EmbeddingCache: Deterministic embeddings keyed by question text hash. No TTL needed.
QueryResultCache: Q&A responses keyed by (tenant, matter, snapshot, question_hash).
  Tenant-isolated, auto-invalidated on re-indexing via docs_snapshot_id, TTL-based.

Both caches are thread-safe via threading.Lock.
"""

import threading
import time
from collections import OrderedDict
from typing import Any


class EmbeddingCache:
    """LRU cache for question embeddings. Thread-safe."""

    def __init__(self, max_size: int = 5000) -> None:
        self._max_size = max_size
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> list[float] | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def put(self, key: str, embedding: list[float]) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = embedding
                return
            self._cache[key] = embedding
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "max_size": self._max_size,
            }


class QueryResultCache:
    """LRU cache for Q&A responses with tenant isolation and TTL. Thread-safe."""

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(
        self, tenant_id: str, matter_id: str, docs_snapshot_id: str, question_hash: str,
        doc_id: str | None = None,
    ) -> str:
        return f"{tenant_id}:{matter_id}:{docs_snapshot_id}:{question_hash}:{doc_id or ''}"

    def get(
        self,
        tenant_id: str,
        matter_id: str,
        docs_snapshot_id: str,
        question_hash: str,
        doc_id: str | None = None,
    ) -> dict[str, Any] | None:
        key = self._make_key(tenant_id, matter_id, docs_snapshot_id, question_hash, doc_id)
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
            ts, value = self._cache[key]
            if time.monotonic() - ts > self._ttl_seconds:
                del self._cache[key]
                self._misses += 1
                return None
            self._cache.move_to_end(key)
            self._hits += 1
            return value

    def put(
        self,
        tenant_id: str,
        matter_id: str,
        docs_snapshot_id: str,
        question_hash: str,
        result: dict[str, Any],
        doc_id: str | None = None,
    ) -> None:
        key = self._make_key(tenant_id, matter_id, docs_snapshot_id, question_hash, doc_id)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = (time.monotonic(), result)
                return
            self._cache[key] = (time.monotonic(), result)
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "max_size": self._max_size,
            }
