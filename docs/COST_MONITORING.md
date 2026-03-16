# Cost Monitoring & Savings

How Evidence-Bound tracks, reduces, and reports on per-request costs.

---

## Cost Components

Every `/ask` request incurs up to three billable costs:

| Component | Service | Rate | Configurable Via |
|-----------|---------|------|------------------|
| **LLM Verification** | Azure OpenAI GPT-4o | ~$0.0025/1K input, ~$0.01/1K output | `DOCQA_MODEL_COST_INPUT_PER_1K`, `DOCQA_MODEL_COST_OUTPUT_PER_1K` |
| **Embeddings** | Azure OpenAI text-embedding-3-large | ~$0.00013/1K tokens | `DOCQA_EMBEDDINGS_COST_PER_1K` |
| **Azure Search** | Azure AI Search queries | ~$0.001/query | `AZURE_SEARCH_COST_PER_QUERY` |

**Free components** (no external API cost):
- Local reranker (CPU-based term+phrase analysis)
- pgvector search (when `SEARCH_PROVIDER=pgvector`)
- Local embeddings (when `EMBEDDINGS_MODE=local`)
- Ollama LLM (when `LLM_PROVIDER=ollama`)

---

## How Costs Are Tracked

### Per-Request Accumulation

Each `/ask` request accumulates a `cost_breakdown` dict with per-component entries:

```
cost_breakdown = {
    "azure_search": {"prompt_tokens": 0, "completion_tokens": 0, "cost_est": 0.001},
    "embeddings":   {"prompt_tokens": 45, "completion_tokens": 0, "cost_est": 0.000006},
    "verifier":     {"prompt_tokens": 800, "completion_tokens": 50, "cost_est": 0.0025},
}
```

**Code path:** `services/cost.py` → `estimate_cost()` and `merge_cost_breakdown()`

### Storage

- **`telemetry` table**: Every request stores `cost_est` (total) + `trace_metadata.cost_breakdown` (per-component JSON)
- **Langfuse traces**: Token counts and model info per observation (when `LANGFUSE_ENABLED=1`)
- **OTEL metrics**: `docqa.cost.usd` counter by component (when `OTEL_ENABLED=1`)

### Token Estimation Fallback

When actual token counts aren't available (e.g., cache hits, errors), the system estimates:
- `tokens_in ≈ question_length / 4`
- `tokens_out ≈ answer_length / 4`
- Flagged with `usage_fallback: true` in trace metadata

---

## Cost Reduction — Caching

### Embedding Cache

Eliminates redundant Azure OpenAI embedding calls for repeated questions.

| Setting | Default | Description |
|---------|---------|-------------|
| `EMBEDDING_CACHE_ENABLED` | `1` (on) | Enable/disable |
| `EMBEDDING_CACHE_MAX_SIZE` | `5000` | Max cached embeddings (LRU eviction) |

- **Key:** SHA256 hash of question text
- **No TTL:** Embeddings are deterministic — same input always produces the same output
- **Thread-safe:** `threading.Lock` on all operations
- **Implementation:** `app/cache.py:EmbeddingCache`

### Query Result Cache

Caches entire Q&A responses. Tenant-isolated with TTL.

| Setting | Default | Description |
|---------|---------|-------------|
| `QUERY_CACHE_ENABLED` | `0` (off) | Enable/disable (opt-in) |
| `QUERY_CACHE_MAX_SIZE` | `500` | Max cached responses (LRU eviction) |
| `QUERY_CACHE_TTL_SECONDS` | `3600` | Time-to-live (1 hour) |

- **Key:** `tenant_id:matter_id:docs_snapshot_id:question_hash`
- **Tenant isolation:** Different tenants never share cache entries
- **Auto-invalidation:** When documents are re-indexed, `docs_snapshot_id` changes → old cache entries miss
- **Thread-safe:** `threading.Lock` on all operations
- **Implementation:** `app/cache.py:QueryResultCache`

**Why off by default?** Query caching trades freshness for cost savings. Enable when:
- Questions are frequently repeated (e.g., standard due diligence checklists)
- Document corpus changes infrequently
- Cost reduction is prioritized over real-time accuracy

---

## Cost Flow

```
Question
  │
  ├─ Query Cache check ──→ HIT → Return cached response ($0)
  │                             └─ Record cache_hit=True
  │
  ├─ Embedding Cache check ──→ HIT → Skip embedding API ($0)
  │                                └─ source="cache"
  │
  ├─ Embedding API call ──→ $0.00001–0.0001
  │   └─ Store in Embedding Cache
  │
  ├─ Azure Search query ──→ $0.001
  │
  ├─ LLM Verification (1-3 calls) ──→ $0.001–0.005
  │
  ├─ Record telemetry (cost_est + breakdown)
  │
  └─ Store in Query Cache (if enabled)
```

---

## Monitoring

### `/v1/metrics` Endpoint

Requires `X-Admin-Token` header. Returns:

```json
{
  "total_requests": 1500,
  "avg_latency_ms": 2300,
  "avg_cost_per_query": 0.0035,
  "cache_hit_rate": 0.12,
  "embedding_cache": {
    "hits": 420, "misses": 1080, "size": 1080, "max_size": 5000, "enabled": true
  },
  "query_cache": {
    "hits": 0, "misses": 0, "size": 0, "max_size": 0, "enabled": false
  },
  "cost_by_component": {
    "azure_search": 1.5,
    "embeddings": 0.15,
    "verifier": 3.75
  }
}
```

### OTEL Metrics (when `OTEL_ENABLED=1`)

| Metric | Type | Labels |
|--------|------|--------|
| `docqa.request.count` | Counter | `component` |
| `docqa.request.latency_ms` | Histogram | `component` |
| `docqa.tokens.total` | Counter | `direction` (input/output) |
| `docqa.cache.hit` | Counter | `cache_type` (embedding/query) |
| `docqa.cost.usd` | Counter | `component` |

### OTEL GenAI Span Attributes

Every LLM/embedding call sets semantic convention attributes on the active span:

| Attribute | Example |
|-----------|---------|
| `gen_ai.system` | `azure_openai` |
| `gen_ai.request.model` | `gpt-4o` |
| `gen_ai.usage.prompt_tokens` | `800` |
| `gen_ai.usage.completion_tokens` | `50` |
| `llm.latency_ms` | `1200` |
| `llm.request_id` | `req-abc123` |

### Langfuse Traces

When `LANGFUSE_ENABLED=1`, each request creates a trace with:
- Model, tokens, latency per observation (verification, embedding)
- Redacted metadata only (no PII): `question_len`, `citation_count`, `evidence_grade`
- `langfuse_trace_id` stored in telemetry table for correlation

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCQA_MODEL_COST_INPUT_PER_1K` | `0.0025` | LLM input cost per 1K tokens |
| `DOCQA_MODEL_COST_OUTPUT_PER_1K` | `0.01` | LLM output cost per 1K tokens |
| `DOCQA_EMBEDDINGS_COST_PER_1K` | `0.00013` | Embedding cost per 1K tokens |
| `AZURE_SEARCH_COST_PER_QUERY` | `0.001` | Azure Search cost per query |
| `EMBEDDING_CACHE_ENABLED` | `1` | Enable embedding LRU cache |
| `EMBEDDING_CACHE_MAX_SIZE` | `5000` | Max cached embeddings |
| `QUERY_CACHE_ENABLED` | `0` | Enable query result cache |
| `QUERY_CACHE_MAX_SIZE` | `500` | Max cached responses |
| `QUERY_CACHE_TTL_SECONDS` | `3600` | Query cache TTL |
| `METRICS_ADMIN_TOKEN` | (none) | Token for `/v1/metrics` access |
| `OTEL_ENABLED` | `0` | Enable OTEL metrics/traces |
| `LANGFUSE_ENABLED` | `0` | Enable Langfuse LLM tracing |

---

## Known Gaps

| Gap | Severity | Notes |
|-----|----------|-------|
| **LlamaParse API cost** | Medium | When `PARSER_PROVIDER=llamaparse`, parsing calls the LlamaParse API but cost isn't tracked in `cost_breakdown`. Rarely used (pypdf/marker are defaults). |
| **Ingestion-time embedding cost** | Medium | Document indexing calls `embed_texts` for chunk embeddings, but this cost isn't accumulated in any per-request breakdown. It's a batch operation during upload, not during `/ask`. |
| **Per-provider LLM cost rates** | Low | Single cost rate for all LLM providers. When using Ollama (free/local), cost is overestimated. When using Anthropic/Gemini, rates may differ from Azure OpenAI defaults. |
| **Reranker compute cost** | None | Local CPU reranker has no API cost. If a cloud reranker is added later, it would need tracking. |
