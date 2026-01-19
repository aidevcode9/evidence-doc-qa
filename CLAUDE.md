# CLAUDE.md — Evidence-Bound

> Evidence-bound document Q&A for law firms. Every answer requires retrieval-backed citations or the system refuses.

## Reference Docs (Read These)

| Doc | Purpose | When to Check |
|-----|---------|---------------|
| `REQUIREMENTS.md` | FRs/NFRs with acceptance criteria | Starting a new feature |
| `ARCHITECTURE.md` | Data model, interfaces, deployment tiers | Implementing schema, services, providers |
| `STATUS.md` | Current phase, active tasks, blockers | Daily; before picking work |
| `EVALS.md` | Golden queries and pass/fail criteria | Adding/changing retrieval or LLM logic |

**Workflow:**
1. Check `STATUS.md` → find task in "Next" or "Now"
2. Look up FR in `REQUIREMENTS.md` → read acceptance criteria
3. Check `ARCHITECTURE.md` → find relevant schema/interface
4. Implement → run tests + evals
5. Update `STATUS.md` → move task to "Shipped"
6. Commit with `(FR-NNN)` reference

## Stack (Current)

- **Backend:** FastAPI + Python 3.11
- **Database:** PostgreSQL (Azure Flexible Server)
- **Search:** Azure AI Search (hybrid BM25 + vector + semantic reranker)
- **Embeddings:** Azure OpenAI (text-embedding-3-large)
- **LLM:** Azure OpenAI (GPT-4o)
- **Frontend:** Next.js 14
- **Deployment:** Azure App Service + Vercel

> **Planned:** Config-driven provider abstraction (NFR-032, 034, 035). See ARCHITECTURE.md for target interfaces.

## File Layout

```
apps/api/app/
├── main.py              # FastAPI app entry
├── config.py            # Environment config + provider selection
├── db.py                # Database models + session
├── schemas.py           # Pydantic models
│
├── routers/             # API endpoints
│   ├── ask.py
│   ├── docs.py
│   ├── metrics.py
│   └── health.py
│
├── services/            # Business logic
│   ├── ask_service.py   # Orchestrates retrieval → LLM → validation
│   ├── document_service.py
│   ├── cost.py          # Cost tracking
│   └── rag.py           # RAG pipeline
│
├── retrieval.py         # Hybrid search (currently Azure AI Search)
├── embeddings.py        # Embedding generation + cache
├── evidence.py          # Citation extraction + validation
├── policy.py            # Pre/post-LLM gates, confidence check
├── verification.py      # LLM verification
├── indexing.py          # Document indexing
├── ingestion.py         # Document ingestion pipeline
├── otel.py              # OpenTelemetry setup
└── telemetry.py         # Metrics + PII-safe logging

packages/shared/         # Shared schemas (SSOT)
evals/                   # Golden queries + runner
tests/                   # Unit + integration tests

REQUIREMENTS.md          # What to build (FRs/NFRs)
ARCHITECTURE.md          # How to build (schemas, interfaces, tiers)
STATUS.md                # Current work (updated daily)
EVALS.md                 # Golden queries + criteria
```

> **Note:** Provider abstraction (`SearchClient`, `LLMClient`, `EmbeddingClient` interfaces) is planned but not yet implemented. See ARCHITECTURE.md for target structure.

## Commands

```bash
# Dev server
cd apps/api && uvicorn app.main:app --reload

# Tests
pytest tests/ -v

# Evals (golden queries)
pytest evals/ -v

# Lint + format
ruff check apps/ --fix
ruff format apps/

# Type check
mypy apps/api/app --strict
```

## Invariants — Current (Enforced Now)

| Rule | Enforcement | Status |
|------|-------------|--------|
| Every answer requires citation | `evidence.py` validates post-LLM; no citation → refuse | ✅ Implemented |
| Confidence < 0.70 → refuse | `policy.py` gates response; returns refusal message | ✅ Implemented |
| No PII in logs | `telemetry.py` redacts; log audit checks in CI | ✅ Implemented |

## Invariants — Planned (Phase 3: Multi-tenancy)

| Rule | Enforcement | FR |
|------|-------------|-----|
| Tenant isolation on all queries | Every DB query includes `tenant_id` | FR-001 |
| Matter isolation | All artifacts scoped by `matter_id` | FR-002 |
| RBAC enforcement | Role checked on every API call | FR-003 |

> ⚠️ **Current state:** Single-tenant demo. Multi-tenancy comes in Phase 3.

## Quality Gates

| Check | Command | Enforced |
|-------|---------|----------|
| Lint | `ruff check apps/` | CI blocks PR |
| Types | `mypy apps/api/app --strict` | CI blocks PR |
| Unit tests | `pytest tests/ -v` | CI blocks PR |
| Evals | `pytest evals/ -v` | CI blocks PR if <95% pass |

**No exceptions.** If a gate fails, fix it before merging.

## Commit Convention

```
type(scope): description (FR-NNN)

# Examples:
feat(retrieval): add BM25 + vector hybrid search (FR-021)
fix(evidence): handle empty citation spans (FR-025)
test(evals): add adversarial prompt injection cases
```

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`

## Mistakes (Learn from These)

| Date | Mistake | Rule Added |
|------|---------|------------|
| 01-14 | LLM cited non-existent page | Post-LLM validation required; verify chunk exists |
| 01-15 | PII in debug logs during demo | Redact by default; use `telemetry.py` |
| 01-16 | Confidence 0.68 returned answer | Gate MUST be < not <= ; 0.70 is refuse |
| 01-17 | Azure AI Search latency too high | Pivot to pgvector for hybrid search |

## Red Flags — Stop and Ask

- Removing or weakening citation validation
- Logging raw document content or user queries
- Disabling confidence threshold for "testing"
- Any change to `policy.py` or `evidence.py` without review
- Skipping evals "just this once"

## Key Files (Read These First)

| File | Purpose |
|------|---------|
| `REQUIREMENTS.md` | FRs/NFRs with acceptance criteria |
| `ARCHITECTURE.md` | Data model, interfaces (planned), deployment tiers |
| `STATUS.md` | What to work on now |
| `app/retrieval.py` | Hybrid search (Azure AI Search currently) |
| `app/embeddings.py` | Embedding generation + cache |
| `app/evidence.py` | Citation extraction + validation |
| `app/policy.py` | Pre/post-LLM gates, confidence check |
| `app/services/ask_service.py` | Orchestrates retrieval → LLM → validation |
| `app/services/rag.py` | RAG pipeline |
| `app/db.py` | Database models |
| `app/config.py` | Environment config |
| `app/otel.py` | OpenTelemetry setup |
| `evals/golden.jsonl` | Golden queries for regression |

## Dependencies (Current)

- PostgreSQL: `asyncpg` + `sqlalchemy[asyncio]`
- Azure AI Search: `azure-search-documents`
- Azure OpenAI: `openai` (with Azure endpoint)
- Observability: `opentelemetry-*`
- FastAPI + Pydantic

## Environment Variables (Current)

```bash
# Database
DATABASE_URL=postgresql://...

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=xxx
AZURE_SEARCH_INDEX=evidence-chunks

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com
AZURE_OPENAI_API_KEY=xxx
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_LLM_DEPLOYMENT=gpt-4o

# App
CONFIDENCE_THRESHOLD=0.70
```

> **Planned:** Config-driven provider selection (SEARCH_PROVIDER, LLM_PROVIDER, EMBEDDING_PROVIDER). See ARCHITECTURE.md.
