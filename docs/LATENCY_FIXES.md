# Latency Fixes: Implementation Guide

**Date:** 2026-03-31
**Target:** Reduce p95 query latency from ~8s to < 4s
**Priority:** Fix in order listed (each is independently deployable)

---

## Current Latency Profile

```
Total: 3-8 seconds typical, 14+ seconds worst case

Embedding (Azure OpenAI):     500-1500ms (cached: <5ms)
Azure AI Search:               300-1000ms (unbounded: no timeout)
Verification (1-3 LLM calls): 1000-6000ms (SEQUENTIAL)
Evidence/Citations:            50-100ms
DB writes (telemetry, QA):     50-200ms (NullPool overhead)
```

The three killers are: sequential verification, no Azure Search timeout, and synchronous I/O blocking threads.

---

## Fix 1: Add Timeout to Azure Search (5 minutes, zero risk)

### Problem
`retrieval.py:339` calls `urllib.request.urlopen(req)` with no timeout. If Azure Search is slow or unresponsive, the request hangs indefinitely.

The embedding call at `embeddings.py:121` has `timeout=30`. The verification call at `verification.py:211` has `timeout=30`. Azure Search is the only external call with no timeout.

### Current Code
```python
# retrieval.py:329-341
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
    with urllib.request.urlopen(req) as resp:  # <-- NO TIMEOUT
        result: dict[str, Any] = json.load(resp)
        return result
```

### Fix
```python
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
    with urllib.request.urlopen(req, timeout=15) as resp:  # 15s timeout
        result: dict[str, Any] = json.load(resp)
        return result
```

### Impact
- Prevents indefinite hangs
- Worst case bounded to 15 seconds instead of infinity
- No behavior change for normal requests (Azure Search typically responds in 300-1000ms)

### Test
```python
def test_azure_search_respects_timeout():
    """Verify Azure Search call has timeout set."""
    # Mock urlopen to verify timeout parameter is passed
    with patch("app.retrieval.urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = Mock(return_value=Mock(read=Mock(return_value=b'{"value":[]}')))
        mock_urlopen.return_value.__exit__ = Mock(return_value=False)
        _request_azure_search("http://test", {})
        call_args = mock_urlopen.call_args
        assert call_args.kwargs.get("timeout") == 15 or call_args[1].get("timeout") == 15
```

---

## Fix 2: Parallelize Verification Loop (2 hours, high impact)

### Problem
`ask_service.py:322-370` verifies top 3 candidates sequentially. Each verification is an Azure OpenAI API call taking 1-2 seconds. Worst case: 3 calls x 2s = 6 seconds just for verification.

### Current Code
```python
# ask_service.py:322-370
with otel.span("verification", candidate_count=len(candidates)) as verify_span:
    for chunk in candidates[:3]:  # SEQUENTIAL LOOP
        status, span, reason, usage = verification.verify_relevance(
            question,
            chunk["chunk_text"],
            request_id=request_id,
            chunk_id=chunk["chunk_id"],
        )
        # ... cost tracking ...
        if status == "verified":
            verified_chunk = chunk
            break
```

### Fix: Use `concurrent.futures.ThreadPoolExecutor`

This is the minimal-disruption fix. We fire all 3 verification calls in parallel and take the first verified result.

```python
import concurrent.futures

def _verify_candidates_parallel(
    question: str,
    candidates: list[ChunkDict],
    request_id: str,
    max_candidates: int = 3,
) -> list[tuple[ChunkDict, str, str | None, str, dict]]:
    """Verify up to max_candidates in parallel.

    Returns list of (chunk, status, span, reason, usage) tuples
    in the original candidate order.
    """
    to_verify = candidates[:max_candidates]

    def verify_one(chunk: ChunkDict) -> tuple[ChunkDict, str, str | None, str, dict]:
        status, span, reason, usage = verification.verify_relevance(
            question,
            chunk["chunk_text"],
            request_id=request_id,
            chunk_id=chunk["chunk_id"],
        )
        return (chunk, status, span, reason, usage or {})

    # Fire all verification calls in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_candidates) as executor:
        futures = {executor.submit(verify_one, chunk): idx
                   for idx, chunk in enumerate(to_verify)}

        results: list[tuple[int, tuple]] = []
        for future in concurrent.futures.as_completed(futures):
            idx = futures[future]
            try:
                result = future.result(timeout=30)
                results.append((idx, result))
            except Exception as e:
                chunk = to_verify[idx]
                results.append((idx, (chunk, "unverified", None, "ERROR", {})))

    # Sort back to original order (preserves priority ranking)
    results.sort(key=lambda x: x[0])
    return [r[1] for r in results]
```

Then in `execute_ask()`, replace the sequential loop:

```python
with otel.span("verification", candidate_count=len(candidates)) as verify_span:
    parallel_results = _verify_candidates_parallel(question, candidates, request_id)

    for chunk, status, span, reason, usage in parallel_results:
        # ... existing cost tracking logic ...
        verification_results[chunk["chunk_id"]] = (status, span)
        verification_reasons[chunk["chunk_id"]] = reason

        if status == "verified":
            verified_chunk = chunk
            verification_status = "VERIFIED"
            verification_rejected = False
            break
        if status == "unverified":
            verification_status = "UNVERIFIED"
            verification_rejected = False
            break

    if verified_chunk is None:
        verification_rejected = True
```

### Impact
- **Before:** 1-3 sequential calls = 1-6 seconds
- **After:** 1-3 parallel calls = time of slowest single call = 1-2 seconds
- **Savings:** 2-4 seconds on worst case (when first candidate is rejected)
- **Cost:** Same number of LLM calls, same cost. Only latency changes.

### Why ThreadPoolExecutor and not asyncio?
Because `execute_ask()` and all its callees are synchronous. Converting to async is a larger refactor (Fix 6). `ThreadPoolExecutor` works within the existing sync architecture and gives 80% of the benefit.

### Test
```python
def test_parallel_verification_faster_than_sequential():
    """Parallel verification should complete in ~1 call time, not 3."""
    import time

    # Mock verify_relevance to take 1 second each
    with patch("app.verification.verify_relevance") as mock_verify:
        mock_verify.side_effect = lambda *a, **kw: (
            time.sleep(1),
            ("rejected", None, "NOT_FOUND", {"prompt_tokens": 100, "completion_tokens": 50})
        )[-1]

        start = time.perf_counter()
        results = _verify_candidates_parallel("test?", [
            {"chunk_id": "1", "chunk_text": "a"},
            {"chunk_id": "2", "chunk_text": "b"},
            {"chunk_id": "3", "chunk_text": "c"},
        ], request_id="test")
        elapsed = time.perf_counter() - start

        assert len(results) == 3
        assert elapsed < 2.0  # Should be ~1s, not ~3s
```

---

## Fix 3: Enable Database Connection Pooling (10 minutes, low risk)

### Problem
`db.py` uses `NullPool`, which creates a new TCP connection for every database operation. Each connection setup costs 10-50ms (TCP handshake + TLS + Postgres auth). With 5-10 DB operations per request, that's 50-500ms of pure connection overhead.

### Current Code
```python
# db.py (engine creation)
from sqlalchemy.pool import NullPool

_engine: Engine | None = None

def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL, poolclass=NullPool)
    return _engine
```

### Fix
```python
from sqlalchemy.pool import QueuePool

_engine: Engine | None = None

def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=10,          # Persistent connections
            max_overflow=20,       # Burst capacity
            pool_timeout=30,       # Wait for connection before error
            pool_recycle=1800,     # Recycle connections every 30 min
            pool_pre_ping=True,    # Verify connection is alive before use
        )
    return _engine
```

### Why these values?
- `pool_size=10`: Steady-state connections. Matches expected concurrent query volume for a small pilot.
- `max_overflow=20`: Allows bursts up to 30 total connections. Azure Flexible Server default max is 100.
- `pool_recycle=1800`: Azure Postgres may close idle connections after 30 minutes. Recycling prevents stale connection errors.
- `pool_pre_ping=True`: Prevents "connection already closed" errors after idle periods. Small overhead (~1ms ping) but eliminates a class of production errors.

### Impact
- Saves 50-500ms per request from connection reuse
- Reduces database server connection churn
- Enables connection count monitoring via `_engine.pool.status()`

### Test
```python
def test_db_engine_uses_connection_pooling():
    """Verify engine uses QueuePool, not NullPool."""
    from app.db import _get_engine
    from sqlalchemy.pool import QueuePool
    engine = _get_engine()
    assert isinstance(engine.pool, QueuePool)

def test_db_pool_size_is_reasonable():
    """Pool should handle concurrent requests without exhaustion."""
    engine = _get_engine()
    assert engine.pool.size() >= 5
    assert engine.pool.size() <= 50
```

---

## Fix 4: Enable Query Cache (2 minutes, zero risk)

### Problem
Query caching is fully implemented but disabled by default (`QUERY_CACHE_ENABLED=0` in `config.py:62`).

For repeated questions within a matter (extremely common in legal review -- attorneys ask the same question across depositions), the full pipeline runs every time: embedding + search + verification + citation = 3-8 seconds.

### Fix
Set environment variable:
```bash
QUERY_CACHE_ENABLED=1
```

The cache is already scoped by `tenant_id + matter_id + docs_snapshot_id + question_hash + doc_id`, so there's no cross-tenant leakage. TTL is 1 hour by default (`QUERY_CACHE_TTL_SECONDS=3600`).

### Impact
- Cache hit: <10ms response (vs 3-8 seconds)
- Cache miss: No change
- Memory: LRU cache, max 500 entries by default, auto-evicts oldest
- Legal safety: Cache invalidates when `docs_snapshot_id` changes (new document uploaded)

### Considerations
- The cache is in-memory, so it doesn't survive container restarts
- Each container has its own cache (no sharing across horizontal scale)
- For beta: this is fine. For production: move to Redis (see Fix 7)

---

## Fix 5: Skip Verification for High-Confidence Results (1-2 hours, medium risk)

### Problem
The LLM verification step (`verification.verify_relevance()`) re-asks "does this chunk answer the question?" after Azure's semantic reranker already answered the same question. When the reranker score is high (>2.5 on a 0-4 scale), the LLM verification almost never disagrees. You're paying 1-2 seconds of latency for a rubber stamp.

### Current Flow
```
Azure Search (BM25 + vector + semantic reranker)
  --> Confidence filter (score >= threshold)
    --> LLM Verification (1-3 calls, 1-6 seconds)  <-- redundant for high scores
      --> Evidence grading
```

### Proposed Flow
```
Azure Search (BM25 + vector + semantic reranker)
  --> Confidence filter (score >= threshold)
    --> IF reranker_score >= 2.5 AND overlap >= 0.3:
          SKIP verification, mark as "auto_verified"
        ELSE:
          LLM Verification (1-3 calls)
    --> Evidence grading
```

### Implementation
Add to `ask_service.py` before the verification block:

```python
# Fast-path: Skip LLM verification for high-confidence Azure reranker results
AUTO_VERIFY_RERANKER_MIN = 2.5
AUTO_VERIFY_OVERLAP_MIN = 0.3

def _can_auto_verify(chunk: ChunkDict, question: str) -> bool:
    """Check if chunk's reranker score is high enough to skip LLM verification."""
    reranker = chunk.get("azure_reranker_score")
    if reranker is None or reranker < AUTO_VERIFY_RERANKER_MIN:
        return False
    q_tokens = evidence.tokenize(question)
    overlap = evidence.overlap_score(q_tokens, chunk["chunk_text"])
    return overlap >= AUTO_VERIFY_OVERLAP_MIN
```

Then in the verification section:
```python
if verification.is_enabled():
    # Fast-path: auto-verify high-confidence results
    if _can_auto_verify(candidates[0], question):
        verified_chunk = candidates[0]
        verification_status = "AUTO_VERIFIED"
        verification_rejected = False
        logger.info(f"Auto-verified [{request_id}]: reranker={candidates[0].get('azure_reranker_score')}")
    else:
        # Existing verification loop (now with parallel execution per Fix 2)
        ...
```

### Risk
- **False positives:** A high reranker score doesn't guarantee the chunk answers the question. It means the chunk is semantically similar.
- **Mitigation:** The `overlap >= 0.3` check adds a second signal. Combined reranker + overlap false positive rate should be <5% based on the evidence grading logic already in `evidence.py:58-80` (Grade A requires similar thresholds).
- **Validation required:** Run the eval suite (`pytest evals/ -v`) with auto-verify enabled. If golden query pass rate drops below 95%, tighten thresholds or revert.

### Impact
- Typical query with high reranker score: 2-6 seconds saved (entire verification step skipped)
- Low reranker score: No change (falls through to existing verification)
- Estimated hit rate: 60-70% of queries (based on Azure semantic reranker quality for legal documents)

---

## Fix 6: Replace urllib with httpx (4-8 hours, foundation for async)

### Problem
The codebase makes HTTP calls to three external services:
1. Azure OpenAI (embeddings) -- `embeddings.py`
2. Azure AI Search -- `retrieval.py`
3. Azure OpenAI (verification/chat) -- `verification.py`

All use `urllib.request`, which:
- Creates a new TCP connection per call (no keep-alive)
- Has no connection pooling
- Has no async support
- Requires manual JSON serialization
- Has no middleware for retries, logging, or metrics

### Fix: Replace with `httpx`

`httpx` is the modern Python HTTP client (essentially `requests` but with async support). It provides connection pooling, automatic keep-alive, and an identical sync/async API.

**Phase 1: Sync httpx (drop-in replacement)**

Create `apps/api/app/http_client.py`:
```python
import httpx

# Shared client with connection pooling for Azure services
_azure_client: httpx.Client | None = None

def get_azure_client() -> httpx.Client:
    global _azure_client
    if _azure_client is None:
        _azure_client = httpx.Client(
            timeout=httpx.Timeout(
                connect=5.0,    # Connection timeout
                read=30.0,      # Read timeout (LLM calls can be slow)
                write=10.0,     # Write timeout
                pool=10.0,      # Wait for available connection
            ),
            limits=httpx.Limits(
                max_connections=20,        # Total connection pool
                max_keepalive_connections=10,  # Keep-alive connections
                keepalive_expiry=30.0,     # Keep-alive duration
            ),
            http2=True,  # HTTP/2 multiplexing (reduces connection overhead)
        )
    return _azure_client
```

Then replace `urllib.request` calls:

```python
# Before (retrieval.py):
req = urllib.request.Request(url, data=json.dumps(payload).encode(), ...)
with urllib.request.urlopen(req) as resp:
    result = json.load(resp)

# After:
client = get_azure_client()
resp = client.post(url, json=payload, headers={"api-key": API_KEY})
resp.raise_for_status()
result = resp.json()
```

**Phase 2: Async httpx (after execute_ask becomes async)**

```python
_azure_async_client: httpx.AsyncClient | None = None

async def get_azure_async_client() -> httpx.AsyncClient:
    global _azure_async_client
    if _azure_async_client is None:
        _azure_async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=10.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            http2=True,
        )
    return _azure_async_client
```

### Impact
- Connection reuse saves 50-200ms per external call (TCP+TLS handshake avoided)
- HTTP/2 multiplexing allows multiple requests over a single connection
- Built-in timeout configuration (no more missing timeouts)
- Foundation for async migration

### Dependency
```bash
pip install httpx[http2]
```

---

## Fix 7: External Cache with Redis (Future -- for horizontal scaling)

### Problem
Current in-memory caches (`EmbeddingCache`, `QueryResultCache`, `_BM25_CACHE`) don't work across multiple API containers. When you scale to 2+ containers for NFR-012, each container builds its own cache from scratch, and cache hit rates drop proportionally.

### When to implement
After Fixes 1-6 are deployed and you're preparing for horizontal scaling (2+ API containers).

### Approach
Replace in-memory LRU caches with Redis:

```python
# cache.py -- Redis-backed cache
import redis
import json
import hashlib

class RedisCache:
    def __init__(self, redis_url: str, prefix: str, ttl_seconds: int = 3600):
        self.client = redis.from_url(redis_url)
        self.prefix = prefix
        self.ttl = ttl_seconds

    def _key(self, *parts: str) -> str:
        raw = ":".join(parts)
        return f"{self.prefix}:{hashlib.sha256(raw.encode()).hexdigest()}"

    def get(self, *key_parts: str) -> Any | None:
        data = self.client.get(self._key(*key_parts))
        return json.loads(data) if data else None

    def put(self, *key_parts: str, value: Any) -> None:
        self.client.setex(
            self._key(*key_parts),
            self.ttl,
            json.dumps(value),
        )
```

### Azure option
Use Azure Cache for Redis (Basic tier: ~$16/month). No infrastructure to manage.

---

## Fix Priority and Timeline

| Fix | Effort | Latency Impact | Risk | When |
|-----|--------|---------------|------|------|
| 1. Azure Search timeout | 5 min | Prevents hangs | Zero | Now |
| 2. Parallel verification | 2 hours | -2-4s worst case | Low | This week |
| 3. Connection pooling | 10 min | -50-500ms/req | Low | Now |
| 4. Enable query cache | 2 min | -100% on cache hit | Zero | Now |
| 5. Auto-verify high confidence | 1-2 hours | -2-6s typical | Medium | After eval validation |
| 6. httpx migration | 4-8 hours | -100-400ms/req | Low | This sprint |
| 7. Redis cache | 4-8 hours | Cross-container sharing | Low | Before horizontal scale |

### Expected p95 After Fixes 1-5

```
Before:  ~8000ms (current)
Fix 1:   ~8000ms (only prevents worst case)
Fix 2:   ~5000ms (parallel verification)
Fix 3:   ~4500ms (connection reuse)
Fix 4:   ~4500ms (no change on miss, <10ms on hit)
Fix 5:   ~2500ms (skip verification for 60-70% of queries)
Fix 6:   ~2000ms (connection reuse + HTTP/2)

Target:  <4000ms (NFR-011)
```

Fixes 1-5 alone should get you under the 4-second target for most queries.
