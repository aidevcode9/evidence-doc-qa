# ARCHITECTURE.md — Evidence-Bound

> Implementation details: data model, interfaces, deployment tiers.
> **Full documentation split into focused modules in `docs/architecture/`.**

## Design Principles

1. **Open Source First** — PostgreSQL + pgvector, MinIO, OpenTelemetry
2. **LLM Abstraction** — Swap providers via config, not code changes
3. **Deployment Portability** — Same images; Docker Compose or Kubernetes
4. **Single Database** — PostgreSQL for metadata + vectors + FTS

---

## Documentation Index

| Module | Purpose | When to Read |
|--------|---------|--------------|
| [docs/architecture/data-model.md](docs/architecture/data-model.md) | DB schemas (tenants, docs, chunks, Q&A, audit) | Adding tables, understanding isolation |
| [docs/architecture/interfaces.md](docs/architecture/interfaces.md) | LLM, Embedding, Search, Parser abstractions | Implementing NFR-032/034/035/036 |
| [docs/architecture/observability.md](docs/architecture/observability.md) | LLM tracking, telemetry table, Langfuse | NFR-030, debugging LLM calls |
| [docs/architecture/deployment.md](docs/architecture/deployment.md) | Tiers, Docker, Kubernetes, env vars | Deploying, switching providers |
| [docs/architecture/migrations.md](docs/architecture/migrations.md) | Alembic commands and patterns | Schema changes |
| [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | Latency tracking, concurrency, scaling | NFR-011/012, load testing, metrics |

---

## Quick Reference

### Key Constraints

| Constraint | Rationale |
|------------|-----------|
| All providers config-driven | Swap via env vars, no code changes (NFR-032/034/035/036) |
| All queries filter by `tenant_id` | Tenant isolation (FR-001) |
| All artifacts scoped by `matter_id` | Matter isolation (FR-002) |
| All LLM calls via TracedLLMClient | Ensures telemetry (NFR-030) |
| `embedding_model` stored with vectors | Mixed-model deployments; future migrations |
| pgvector over dedicated vector DB | Single database, less ops complexity |

### Performance & Rate Limiting

- **Enhanced metrics endpoint** (`/v1/metrics`): Returns p50/p95 latency, cache stats (embedding + query), and per-component cost breakdown over a 24-hour window.
- **Rate limiting** via `slowapi` decorators: Per-IP limits configurable via `RATE_LIMIT_QUERY` (20/min), `RATE_LIMIT_UPLOAD` (10/min), `RATE_LIMIT_DEFAULT` (100/min). Returns HTTP 429 with `Retry-After` header.
- **OTEL custom metrics**: `docqa.request.latency_ms` histogram, `docqa.request.count`, `docqa.tokens.total`, `docqa.cache.hit`, `docqa.cost.usd` -- all emitted to Azure Monitor.
- **Latency target**: p95 < 8000ms (`DOCQA_LATENCY_TARGET_MS`), tracked per-request in the `telemetry` table.

See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for full latency architecture, scaling strategy, and load testing guidance.

### Provider Defaults by Tier

| Tier | LLM | Search | Parser | Embeddings |
|------|-----|--------|--------|------------|
| **Starter** | Gemini Flash | pgvector | pypdf | local (nomic) |
| **Professional** | Azure GPT-5-mini | pgvector | LlamaParse | Azure OpenAI |
| **Enterprise** | Azure GPT-5-mini | Azure AI Search | LlamaParse | Azure OpenAI |
| **On-Prem** | Ollama Llama 3.2 | pgvector | Marker | local (nomic) |

### Core Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/evidence

# LLM Provider
LLM_PROVIDER=azure_openai  # azure_openai | anthropic | gemini | ollama

# Search Provider
SEARCH_PROVIDER=pgvector   # pgvector | azure

# Embeddings
EMBEDDINGS_MODE=local      # local | remote

# Parser
PARSER_PROVIDER=marker     # pypdf | marker | llamaparse
```

See [docs/architecture/deployment.md](docs/architecture/deployment.md) for full env var reference.

---

## Current Implementation Status

| Interface | Status | Location |
|-----------|--------|----------|
| LLMClient (NFR-032) | ✅ Implemented | `apps/api/app/llm/` |
| ParserClient (NFR-036) | ✅ Implemented | `apps/api/app/parsers/` |
| SearchClient (NFR-034) | ⏳ Planned | Uses Azure AI Search directly |
| EmbeddingClient (NFR-035) | ⏳ Planned | `apps/api/app/embeddings.py` |

---

## Switching Providers

```bash
# 1. Change config
export LLM_PROVIDER=ollama
export SEARCH_PROVIDER=pgvector

# 2. Run migrations (if schema changed)
alembic upgrade head

# 3. Re-embed documents (if embedding model changed)
python -m app.tasks.reindex --all

# 4. Verify with evals
pytest evals/ -v
```

No code changes required — just config + new adapter.

---

## Migration Notes

When adding new deployment tier or swapping providers:

1. Implement new `LLMClient` or `EmbeddingClient` subclass
2. Add config option in `config.py`
3. Update `get_llm_client()` / `get_embedding_client()`
4. Test with evals (`pytest evals/ -v`)
5. Document quality trade-offs if on-prem
