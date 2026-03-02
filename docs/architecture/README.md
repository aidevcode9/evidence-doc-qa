# Architecture Overview

> Evidence-bound document Q&A. Implementation details split into focused modules.

## Design Principles

1. **Open Source First** — PostgreSQL + pgvector, MinIO, OpenTelemetry
2. **LLM Abstraction** — Swap providers via config, not code changes
3. **Deployment Portability** — Same images; Docker Compose or Kubernetes
4. **Single Database** — PostgreSQL for metadata + vectors + FTS

## Module Index

| Module | Purpose | When to Read |
|--------|---------|--------------|
| [data-model.md](data-model.md) | DB schemas (tenants, docs, chunks, Q&A) | Adding tables, understanding isolation |
| [interfaces.md](interfaces.md) | LLM, Embedding, Search, Parser abstractions | Implementing new providers |
| [observability.md](observability.md) | LLM tracking, Langfuse, telemetry table | Adding telemetry, debugging LLM calls |
| [deployment.md](deployment.md) | Tiers, Docker, Kubernetes, env vars | Deploying, switching providers |
| [migrations.md](migrations.md) | Alembic commands and patterns | Schema changes |

## Quick Reference

### Key Constraints

| Constraint | Rationale |
|------------|-----------|
| All providers config-driven | Swap via env vars, no code changes |
| All queries filter by `tenant_id` | Tenant isolation (FR-001) |
| All artifacts scoped by `matter_id` | Matter isolation (FR-002) |
| All LLM calls via TracedLLMClient | Ensures telemetry (NFR-030) |
| pgvector over dedicated vector DB | Single database, less ops complexity |

### Provider Defaults by Tier

| Tier | LLM | Search | Parser |
|------|-----|--------|--------|
| Starter | Gemini Flash | pgvector | pypdf |
| Professional | Azure OpenAI | pgvector | LlamaParse |
| Enterprise | Azure OpenAI | Azure AI Search | LlamaParse |
| On-Prem | Ollama (Llama 3.2) | pgvector | Marker |

See [deployment.md](deployment.md) for full provider matrix and config.
