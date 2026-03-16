# tests/test_cache.py
"""
Tests for embedding and query result caching (Cost Reduction).

EmbeddingCache: LRU cache for question embeddings (deterministic, no TTL).
QueryResultCache: LRU cache for Q&A responses (tenant-isolated, TTL-based).
"""

import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class TestEmbeddingCache:
    """EmbeddingCache: in-memory LRU for deterministic embeddings."""

    def test_cache_exists(self) -> None:
        """EmbeddingCache class must exist in app.cache."""
        from app.cache import EmbeddingCache

        assert EmbeddingCache is not None

    def test_cache_get_miss(self) -> None:
        """Cache miss returns None."""
        from app.cache import EmbeddingCache

        cache = EmbeddingCache(max_size=100)
        assert cache.get("nonexistent") is None

    def test_cache_put_and_get(self) -> None:
        """Can store and retrieve an embedding."""
        from app.cache import EmbeddingCache

        cache = EmbeddingCache(max_size=100)
        embedding = [0.1, 0.2, 0.3]
        cache.put("question_hash_1", embedding)
        assert cache.get("question_hash_1") == embedding

    def test_cache_evicts_lru(self) -> None:
        """When max_size exceeded, oldest entry is evicted."""
        from app.cache import EmbeddingCache

        cache = EmbeddingCache(max_size=2)
        cache.put("a", [1.0])
        cache.put("b", [2.0])
        cache.put("c", [3.0])  # Should evict "a"
        assert cache.get("a") is None
        assert cache.get("b") == [2.0]
        assert cache.get("c") == [3.0]

    def test_cache_stats(self) -> None:
        """Cache tracks hits and misses."""
        from app.cache import EmbeddingCache

        cache = EmbeddingCache(max_size=100)
        cache.put("x", [1.0])
        cache.get("x")       # hit
        cache.get("missing")  # miss

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_cache_thread_safe(self) -> None:
        """Cache operations should not raise under concurrent access."""
        import threading
        from app.cache import EmbeddingCache

        cache = EmbeddingCache(max_size=100)
        errors: list[Exception] = []

        def writer(start: int) -> None:
            try:
                for i in range(50):
                    cache.put(f"key_{start}_{i}", [float(i)])
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for i in range(50):
                    cache.get(f"key_0_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(0,)),
            threading.Thread(target=writer, args=(1,)),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestQueryResultCache:
    """QueryResultCache: tenant-isolated, TTL-based LRU cache."""

    def test_cache_exists(self) -> None:
        """QueryResultCache class must exist in app.cache."""
        from app.cache import QueryResultCache

        assert QueryResultCache is not None

    def test_cache_get_miss(self) -> None:
        """Cache miss returns None."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=100, ttl_seconds=3600)
        assert cache.get("t1", "m1", "snap1", "qhash") is None

    def test_cache_put_and_get(self) -> None:
        """Can store and retrieve a query result."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=100, ttl_seconds=3600)
        result = {"answer": "test answer", "citations": []}
        cache.put("t1", "m1", "snap1", "qhash", result)
        assert cache.get("t1", "m1", "snap1", "qhash") == result

    def test_cache_tenant_isolation(self) -> None:
        """Different tenants must not share cache entries."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=100, ttl_seconds=3600)
        cache.put("tenant_a", "m1", "snap1", "qhash", {"answer": "A"})
        cache.put("tenant_b", "m1", "snap1", "qhash", {"answer": "B"})

        assert cache.get("tenant_a", "m1", "snap1", "qhash")["answer"] == "A"
        assert cache.get("tenant_b", "m1", "snap1", "qhash")["answer"] == "B"

    def test_cache_matter_isolation(self) -> None:
        """Different matters within same tenant must not share entries."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=100, ttl_seconds=3600)
        cache.put("t1", "matter_a", "snap1", "qhash", {"answer": "A"})
        cache.put("t1", "matter_b", "snap1", "qhash", {"answer": "B"})

        assert cache.get("t1", "matter_a", "snap1", "qhash")["answer"] == "A"
        assert cache.get("t1", "matter_b", "snap1", "qhash")["answer"] == "B"

    def test_cache_snapshot_invalidation(self) -> None:
        """Different docs_snapshot_id must not return stale results."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=100, ttl_seconds=3600)
        cache.put("t1", "m1", "snap_old", "qhash", {"answer": "old"})

        # New snapshot should miss
        assert cache.get("t1", "m1", "snap_new", "qhash") is None
        # Old snapshot still cached
        assert cache.get("t1", "m1", "snap_old", "qhash")["answer"] == "old"

    def test_cache_ttl_expiry(self) -> None:
        """Expired entries must return None."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=100, ttl_seconds=0)  # 0 = immediate expiry
        cache.put("t1", "m1", "snap1", "qhash", {"answer": "test"})
        time.sleep(0.01)
        assert cache.get("t1", "m1", "snap1", "qhash") is None

    def test_cache_evicts_lru(self) -> None:
        """When max_size exceeded, oldest entry is evicted."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=2, ttl_seconds=3600)
        cache.put("t1", "m1", "s1", "q1", {"answer": "1"})
        cache.put("t1", "m1", "s1", "q2", {"answer": "2"})
        cache.put("t1", "m1", "s1", "q3", {"answer": "3"})  # Evicts q1

        assert cache.get("t1", "m1", "s1", "q1") is None
        assert cache.get("t1", "m1", "s1", "q2") is not None

    def test_cache_stats(self) -> None:
        """Cache tracks hits, misses, and size."""
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=100, ttl_seconds=3600)
        cache.put("t1", "m1", "s1", "q1", {"answer": "test"})
        cache.get("t1", "m1", "s1", "q1")  # hit
        cache.get("t1", "m1", "s1", "q2")  # miss

        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_cache_thread_safe(self) -> None:
        """Cache operations should not raise under concurrent access."""
        import threading
        from app.cache import QueryResultCache

        cache = QueryResultCache(max_size=100, ttl_seconds=3600)
        errors: list[Exception] = []

        def writer(tid: str) -> None:
            try:
                for i in range(50):
                    cache.put(tid, "m1", "s1", f"q{i}", {"answer": f"{tid}_{i}"})
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for i in range(50):
                    cache.get("t0", "m1", "s1", f"q{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=("t0",)),
            threading.Thread(target=writer, args=("t1",)),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestCacheConfig:
    """Cache configuration must be available in app.config."""

    def test_embedding_cache_enabled_config(self) -> None:
        """EMBEDDING_CACHE_ENABLED must exist in config."""
        from app.config import EMBEDDING_CACHE_ENABLED

        assert isinstance(EMBEDDING_CACHE_ENABLED, bool)

    def test_embedding_cache_max_size_config(self) -> None:
        """EMBEDDING_CACHE_MAX_SIZE must exist in config."""
        from app.config import EMBEDDING_CACHE_MAX_SIZE

        assert isinstance(EMBEDDING_CACHE_MAX_SIZE, int)
        assert EMBEDDING_CACHE_MAX_SIZE > 0

    def test_query_cache_enabled_config(self) -> None:
        """QUERY_CACHE_ENABLED must exist in config."""
        from app.config import QUERY_CACHE_ENABLED

        assert isinstance(QUERY_CACHE_ENABLED, bool)

    def test_query_cache_ttl_config(self) -> None:
        """QUERY_CACHE_TTL_SECONDS must exist in config."""
        from app.config import QUERY_CACHE_TTL_SECONDS

        assert isinstance(QUERY_CACHE_TTL_SECONDS, int)
        assert QUERY_CACHE_TTL_SECONDS > 0
