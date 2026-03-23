# Performance & Scaling

> Latency tracking, concurrency model, and scaling strategy for Evidence-Bound.
> Covers NFR-011 (p95 < 8s) and NFR-012 (50 concurrent users).

---

## Latency Architecture

### End-to-End Timing

Every `/ask` request is timed with `time.perf_counter()` in `ask_service.py`:

```python
start_time = time.perf_counter()
# ... retrieval, verification, LLM, evidence grading ...
latency_ms = int((time.perf_counter() - start_time) * 1000)
```

The total `latency_ms` is recorded in both the `telemetry` table and OTEL metrics on every request, including refusals and cache hits.

### Sub-Component Breakdown

The request pipeline has distinct timed phases, each tracked via OTEL spans:

| Phase | Span Name | Typical Range | What It Measures |
|-------|-----------|---------------|------------------|
| **Retrieval** | `retrieval` | 200-1500ms | Embedding + Azure Search / pgvector query |
| **Verification** | `verification` | 500-3000ms | LLM relevance check (1-3 candidates) |
| **Evidence grading** | `evidence.grade` | <10ms | Score computation, overlap, grade assignment |
| **Overhead** | (computed) | 10-50ms | Serialization, cache checks, telemetry recording |

The verification step dominates latency because it involves 1-3 LLM calls to validate chunk relevance before answering.

### Latency Target

| Metric | Target | Config Variable |
|--------|--------|-----------------|
| p95 latency | < 8000ms | `DOCQA_LATENCY_TARGET_MS` |

Default is 8000ms. Override via environment variable for stricter targets.

### Storage

- **`telemetry` table:** `latency_ms` column stores end-to-end time per request
- **`trace_metadata`:** JSON blob with `latency_breakdown` per component (when cost tracking is active)
- **OTEL histogram:** `docqa.request.latency_ms` for percentile aggregation in Azure Monitor

---

## Latency in Langfuse

### @observe Decorator Waterfall

The `@observe` decorator from Langfuse creates a nested trace for each `/ask` request:

```
execute_ask              (trace root -- tenant/session context)
  |-- hybrid_search      (mode, result_count, latency)
  |   +-- embed_texts_with_usage  (model, tokens, embeddings_mode)
  +-- verify_relevance   (model, tokens, verdict)
      +-- call_openai    (generation span -- model, tokens)
```

Each observation captures start/end timestamps, creating a waterfall view of where time is spent.

### Metadata Enrichment

PII-safe metadata is attached via `redact_for_langfuse()`:

```python
safe_update_observation(metadata=redact_for_langfuse(
    question_len=question_len,
    answer_len=len(answer_text),
    citation_count=len(citations),
    evidence_grade=grade,
    evidence_label=label,
    verification_status=verification_status,
    doc_count=len(set(c.doc_id for c in citations)),
))
```

Only safe metrics are sent -- never raw question text, answer text, or document names (which may contain client names). This complies with NFR-004.

### Dashboard Usage

| Tab | What to Look For |
|-----|------------------|
| **Traces** | Filter by `user_id` (tenant), `session_id`, or tags (matter, model). Sort by latency to find slow requests. |
| **Generations** | View individual LLM calls (verification, embedding). Check token counts and model used. |
| **Metrics** | Aggregate latency distribution, token usage trends, cost over time. |

Filter by `tags` containing the `matter_id` or `model_id` to compare performance across configurations.

---

## Latency in OTEL / Azure Monitor

### Custom Metrics

Defined in `app/otel.py` using the OpenTelemetry metrics SDK:

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `docqa.request.count` | Counter | `component`, `refusal_code`, `cache_hit` | Total API requests |
| `docqa.request.latency_ms` | Histogram | `component` | Request latency distribution (p50/p95/p99) |
| `docqa.tokens.total` | Counter | `direction` (input/output), `component` | Total tokens consumed |
| `docqa.cache.hit` | Counter | `cache_type` (embedding/query) | Cache hit count |
| `docqa.cost.usd` | Counter | `component` | Estimated cost in USD |

All metrics are recorded via `record_request_metrics()` in `otel.py`, called at the end of every request.

### GenAI Span Attributes

LLM and embedding calls set semantic convention attributes on the active OTEL span via `set_genai_span_attributes()`:

| Attribute | Example |
|-----------|---------|
| `gen_ai.system` | `azure_openai` |
| `gen_ai.request.model` | `gpt-5-mini` |
| `gen_ai.usage.prompt_tokens` | `800` |
| `gen_ai.usage.completion_tokens` | `50` |
| `llm.latency_ms` | `1200` |
| `llm.request_id` | `req-abc123` |

### Azure Monitor Alert Setup

To alert on NFR-011 violations:

1. Navigate to Azure Monitor > Alerts > New Alert Rule
2. **Resource:** Select the Application Insights instance (`OTEL_SERVICE_NAME=evidence-bound`)
3. **Condition:** Custom metric `docqa.request.latency_ms` > 8000ms at p95, evaluated over 15-minute window
4. **Action Group:** Email/Slack/PagerDuty notification
5. **Severity:** Sev 2 (Warning) for p95 > 8000ms, Sev 1 (Error) for p95 > 12000ms

Additional recommended alerts:

| Alert | Condition | Severity |
|-------|-----------|----------|
| High latency | `docqa.request.latency_ms` p95 > 8000ms | Sev 2 |
| Error spike | `docqa.request.count` with `refusal_code` > 20% of total | Sev 2 |
| Cost anomaly | `docqa.cost.usd` > 2x daily average | Sev 3 |
| Cache degradation | `docqa.cache.hit` rate drops below 10% (when enabled) | Sev 3 |

---

## Concurrency & Scaling

### FastAPI Async + Uvicorn

The API runs on FastAPI with uvicorn. All request handlers use synchronous code (database and external API calls are blocking), but FastAPI runs them in a thread pool automatically. For true async, external calls would need `async`/`await` with async HTTP clients.

### Rate Limiting

Rate limiting is applied via `slowapi` decorators when `RATE_LIMIT_ENABLED=1` (default: on).

| Endpoint Category | Default Limit | Config Variable |
|-------------------|---------------|-----------------|
| General | 100/minute | `RATE_LIMIT_DEFAULT` |
| Query (`/ask`) | 20/minute | `RATE_LIMIT_QUERY` |
| Upload | 10/minute | `RATE_LIMIT_UPLOAD` |

Rate limits use `get_remote_address` as the key function (per-IP). Exceeded limits return HTTP 429 with a `Retry-After` header.

Setup in `main.py`:

```python
if RATE_LIMIT_ENABLED:
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
```

### Thread-Safe Caches

Both in-memory caches use `threading.Lock` for thread safety under concurrent requests:

| Cache | Class | Max Size | TTL | Implementation |
|-------|-------|----------|-----|----------------|
| **Embedding cache** | `EmbeddingCache` | 5000 (configurable) | None (deterministic) | `app/cache.py` |
| **Query result cache** | `QueryResultCache` | 500 (configurable) | 3600s (configurable) | `app/cache.py` |

Both use `OrderedDict` for LRU eviction. The query cache keys include `tenant_id:matter_id:docs_snapshot_id:question_hash` for tenant isolation and automatic invalidation on re-indexing.

### Azure Container Apps Horizontal Scaling

For NFR-012 (50 concurrent users), the recommended deployment is Azure Container Apps with horizontal scaling:

| Setting | Value | Rationale |
|---------|-------|-----------|
| Min replicas | 1 | Always-on for low latency |
| Max replicas | 4 | Handles 50+ concurrent users |
| Scale trigger | HTTP concurrent requests > 15 | Scales before saturation |
| CPU per instance | 2 vCPU | Sufficient for sync processing |
| Memory per instance | 4 GiB | Accommodates embedding cache |

### Per-Instance Cache Tradeoffs

Since `EmbeddingCache` and `QueryResultCache` are in-memory per-process:

| Concern | Impact | Mitigation |
|---------|--------|------------|
| Cache not shared across instances | Lower hit rate with multiple replicas | Each instance warms independently; repeated queries converge |
| Memory usage | Each instance holds its own cache | Limit `EMBEDDING_CACHE_MAX_SIZE` and `QUERY_CACHE_MAX_SIZE` |
| Cold start | New instances start with empty cache | First few requests have higher latency; acceptable for scale-out events |

For shared caching across instances, a future enhancement could add Redis as an external cache layer. This is not currently implemented.

---

## Metrics Reference

| Metric | Source | Where Visible | Granularity |
|--------|--------|---------------|-------------|
| `latency_ms` | `telemetry` table | `/v1/metrics` endpoint, SQL queries | Per-request |
| `p50_latency_ms` | `compute_metrics()` | `/v1/metrics` endpoint | 24-hour window |
| `p95_latency_ms` | `compute_metrics()` | `/v1/metrics` endpoint | 24-hour window |
| `docqa.request.latency_ms` | OTEL histogram | Azure Monitor, Grafana | Per-request (aggregated) |
| `docqa.request.count` | OTEL counter | Azure Monitor, Grafana | Per-request |
| `docqa.tokens.total` | OTEL counter | Azure Monitor, Grafana | Per-request |
| `docqa.cache.hit` | OTEL counter | Azure Monitor, Grafana | Per-event |
| `docqa.cost.usd` | OTEL counter | Azure Monitor, Grafana | Per-request |
| `cost_breakdown` | `trace_metadata` JSON | `/v1/metrics` (cost_by_component), Langfuse | Per-request |
| `cache_hit_rate` | `compute_metrics()` | `/v1/metrics` endpoint | 24-hour window |
| `embedding_cache` stats | `EmbeddingCache.stats()` | `/v1/metrics` endpoint | Cumulative |
| `query_cache` stats | `QueryResultCache.stats()` | `/v1/metrics` endpoint | Cumulative |
| Langfuse trace waterfall | `@observe` decorators | Langfuse dashboard | Per-request |

---

## Load Testing

### Locust Script

A load test script should be placed at `tests/loadtest/locustfile.py`. Example structure:

```python
from locust import HttpUser, task, between

class DocQAUser(HttpUser):
    wait_time = between(1, 5)

    @task(3)
    def ask_question(self):
        self.client.post("/v1/ask", json={
            "question": "What are the indemnification provisions?"
        }, headers={
            "X-Tenant-Id": "test-tenant",
            "X-Matter-Id": "test-matter",
        })

    @task(1)
    def health_check(self):
        self.client.get("/health")
```

### Running Load Tests

```bash
# Install locust
pip install locust

# Run against local dev server
locust -f tests/loadtest/locustfile.py --host http://localhost:8000

# Headless mode (CI)
locust -f tests/loadtest/locustfile.py \
    --host http://localhost:8000 \
    --users 50 \
    --spawn-rate 5 \
    --run-time 5m \
    --headless \
    --csv results/loadtest
```

### Interpreting Results

| Metric | NFR-011 Target | NFR-012 Target |
|--------|----------------|----------------|
| p95 response time | < 8000ms | -- |
| Concurrent users sustained | -- | 50 |
| Error rate | < 1% | < 1% |
| Requests/sec (sustained) | -- | > 5 rps |

### Baseline Targets

| Scenario | Users | Expected p95 | Notes |
|----------|-------|-------------|-------|
| Light (single user) | 1 | < 4000ms | Baseline without contention |
| Normal (10 users) | 10 | < 6000ms | Typical usage |
| Peak (50 users) | 50 | < 8000ms | NFR-012 target |
| Stress (100 users) | 100 | < 12000ms | Graceful degradation expected |

---

## Related Documentation

- [Cost Monitoring](COST_MONITORING.md) -- Cost tracking, caching, and cost reduction strategies
- [Observability](architecture/observability.md) -- Langfuse integration, telemetry table schema
- [Deployment](DEPLOYMENT.md) -- Azure Container Apps setup, scaling configuration
