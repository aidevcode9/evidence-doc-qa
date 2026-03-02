# LLM Observability

> Every LLM call is tracked for audit, billing, and debugging.

## Telemetry Table (NFR-030)

The `telemetry` table records every request for audit, billing, and debugging:

```sql
telemetry (
    request_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    matter_id TEXT NOT NULL,
    docs_snapshot_id TEXT NOT NULL,

    -- Version tracking
    prompt_version TEXT NOT NULL,
    retrieval_version TEXT NOT NULL,
    model_id TEXT NOT NULL,
    parser_mode TEXT NOT NULL,

    -- Timing & usage
    timestamp_utc TEXT NOT NULL,
    latency_ms INT NOT NULL,
    tokens_in INT NOT NULL,
    tokens_out INT NOT NULL,
    cost_est FLOAT NOT NULL,
    cache_hit BOOLEAN NOT NULL,

    -- Outcome
    refusal_code TEXT,
    failure_label TEXT,

    -- Debugging
    trace_metadata TEXT,           -- JSON blob with retrieval scores, debug info
    langfuse_trace_id TEXT         -- Langfuse correlation (NFR-045)
);

CREATE INDEX idx_telemetry_tenant_ts ON telemetry(tenant_id, timestamp_utc);
CREATE INDEX idx_telemetry_langfuse ON telemetry(langfuse_trace_id);
```

## Dual Logging Strategy

| Concern | Solution |
|---------|----------|
| **Billing accuracy** | `telemetry` table — you own the data |
| **Legal audit trail** | `telemetry` table — data stays in your DB |
| **Debugging UI** | Langfuse (optional) — trace viewer, prompt playground |
| **Offline access** | `telemetry` table — no external dependency |

## Langfuse Integration (NFR-045)

> **Status:** IMPLEMENTED. Infrastructure + trace enrichment shipped.

Langfuse provides a debugging UI for LLM traces. When enabled:

1. Every LLM call logs to BOTH `telemetry` table AND Langfuse
2. `langfuse_trace_id` stored in `telemetry` for correlation
3. View traces at Langfuse dashboard

### Langfuse Waterfall

The `@observe` decorators create a nested trace:

```
execute_ask              (trace root — tenant/session context)
  ├── hybrid_search      (mode, result_count, latency)
  │   └── embed_texts_with_usage  (model, tokens, embeddings_mode)
  └── verify_relevance   (model, tokens, verdict)
      └── call_openai    (generation span — model, tokens)
```

### Configuration

```bash
# Enable Langfuse (optional)
LANGFUSE_ENABLED=1
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com  # or self-hosted URL
```

### Safe Helpers (never break request pipeline)

All Langfuse enrichment uses error-safe wrappers from `app/otel.py`:

| Helper | Purpose |
|--------|---------|
| `safe_update_observation()` | Attach model/token/cost to current `@observe` span |
| `safe_update_trace()` | Attach tenant/session context to trace root |
| `safe_get_trace_id()` | Get current trace ID for DB correlation |

All wrapped in `try/except` — Langfuse errors never break the request pipeline.

### Deployment Options

| Tier | Langfuse | Notes |
|------|----------|-------|
| Starter | Cloud (free: 50k traces/mo) | Quick start |
| Professional | Cloud (Pro: $59/mo) | More traces |
| Enterprise | Self-hosted (NFR-046) | Data sovereignty |

### Self-Hosted Docker Compose (NFR-046 — Planned)

```yaml
services:
  langfuse:
    image: langfuse/langfuse:latest
    ports:
      - "3001:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:password@postgres-langfuse:5432/langfuse
      NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET}
      SALT: ${LANGFUSE_SALT}
    depends_on:
      - postgres-langfuse

  postgres-langfuse:
    image: postgres:16
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: ${LANGFUSE_DB_PASSWORD}
      POSTGRES_DB: langfuse
    volumes:
      - langfuse_pgdata:/var/lib/postgresql/data

volumes:
  langfuse_pgdata:
```

## Telemetry Wrapper Pattern

All LLM calls use `@observe` decorators + `record_telemetry()`:

```python
from app.otel import get_observe_decorator, safe_update_observation
from app.telemetry import record_telemetry

_observe = get_observe_decorator()

@_observe(name="my_llm_function", capture_input=False, capture_output=False)
def my_llm_function(...):
    # Make LLM call
    response = _call_openai(...)

    # Enrich Langfuse span (optional, for debugging UI)
    safe_update_observation(
        model=MODEL_ID,
        usage={"input": prompt_tokens, "output": completion_tokens},
        metadata={"latency_ms": latency_ms},
    )

    # Log to telemetry table (ALWAYS)
    record_telemetry(
        request_id=..., tenant_id=..., matter_id=...,
        model_id=MODEL_ID, tokens_in=..., tokens_out=...,
        latency_ms=..., langfuse_trace_id=safe_get_trace_id(),
    )
```

**INVARIANT:** Every LLM call MUST go through this pattern.

See [interfaces.md](interfaces.md) for full implementation pattern.
