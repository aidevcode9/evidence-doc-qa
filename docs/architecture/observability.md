# LLM Observability

> Every LLM call is tracked for audit, billing, and debugging.

## LLM Tracking Table (NFR-030)

```sql
llm_calls (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    session_id UUID REFERENCES qa_sessions(id),
    message_id UUID REFERENCES qa_messages(id),

    -- Provider info
    provider TEXT NOT NULL,           -- 'anthropic', 'openai', 'azure', 'ollama'
    model TEXT NOT NULL,              -- 'claude-3.5-sonnet', 'gpt-4o', 'llama-3.1-70b'

    -- Usage metrics
    prompt_tokens INT,
    completion_tokens INT,
    latency_ms INT,

    -- Status
    status TEXT NOT NULL,             -- 'success', 'error', 'timeout'
    error_message TEXT,

    -- Langfuse correlation (optional, for debugging UI)
    langfuse_trace_id TEXT,
    langfuse_generation_id TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_llm_calls_tenant_date ON llm_calls(tenant_id, created_at);
CREATE INDEX idx_llm_calls_langfuse ON llm_calls(langfuse_trace_id);
```

## Dual Logging Strategy

| Concern | Solution |
|---------|----------|
| **Billing accuracy** | `llm_calls` table — you own the data |
| **Legal audit trail** | `llm_calls` table — data stays in your DB |
| **Debugging UI** | Langfuse (optional) — trace viewer, prompt playground |
| **Offline access** | `llm_calls` table — no external dependency |

## Langfuse Integration (Optional)

> **Status:** PLANNED, not yet implemented. See REQUIREMENTS.md NFR-030.

Langfuse provides a debugging UI for LLM traces. When enabled:

1. Every LLM call logs to BOTH `llm_calls` table AND Langfuse
2. `langfuse_trace_id` stored in `llm_calls` for correlation
3. View traces at Langfuse dashboard

### Configuration

```bash
# Enable Langfuse (optional)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com  # or self-hosted URL
```

### Deployment Options

| Tier | Langfuse | Notes |
|------|----------|-------|
| Starter | Cloud (free: 50k traces/mo) | Quick start |
| Professional | Cloud (Pro: $59/mo) | More traces |
| Enterprise | Self-hosted | Data sovereignty |

### Self-Hosted Docker Compose

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

## TracedLLMClient Pattern

All LLM calls MUST go through a traced wrapper:

```python
class TracedLLMClient:
    """
    Wrapper that logs all LLM calls to:
    1. llm_calls table (for billing + audit)
    2. Langfuse (optional, for debugging UI)

    INVARIANT: Every LLM call MUST go through this wrapper.
    """

    async def complete(self, tenant_id, session_id, ...):
        # Start Langfuse trace (if enabled)
        # Make LLM call
        # Log to llm_calls table (ALWAYS)
        # End Langfuse trace (if enabled)
        pass
```

See [interfaces.md](interfaces.md) for full implementation pattern.
