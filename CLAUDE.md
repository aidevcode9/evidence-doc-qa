# CLAUDE.md — Evidence-Bound

> Evidence-bound document Q&A for law firms. Every answer requires retrieval-backed citations or the system refuses.

---

## ⚡ Auto-Trigger Rules (READ FIRST)

**These rules activate automatically. No command needed.**

### When I describe wanting to build something:
→ **STOP.** Do not write code immediately.
→ Activate brainstorming: Ask clarifying questions, explore alternatives, present design.
→ Wait for approval before implementation.

### When I say "implement", "build", or approve a plan:
→ Check if implementation plan exists with specific files and tests listed.
→ If no plan: Create one first, wait for approval.
→ If plan exists: Proceed with TDD (test first).

### When touching any LLM/AI code:
→ **MANDATORY:** Verify telemetry wrapper is used (see LLM Telemetry section below).
→ Check: Is `llm_calls` table being populated? Are OTEL spans emitting?
→ Add test for telemetry if missing.

### When implementing any feature:
→ **TDD ENFORCED:** Write failing test first → watch it fail → write minimal code → watch it pass → refactor.
→ If code is written before test: Delete the code, write the test first.
→ No exceptions.

### When task is complete:
→ Run full verification: `ruff check apps/ && mypy apps/api/app --strict && pytest tests/ -v && pytest evals/ -v`
→ Update STATUS.md: Move task to "Shipped" with date.
→ If more tasks in "Next": Ask if I should continue to next task.

### Before every PR/commit:
→ **MANDATORY:** Run `/wsskeptic` adversarial code review.
→ Fix all CRITICAL and HIGH severity issues before committing.
→ Document any accepted risks in commit message.

### When working autonomously (user said "work on this, I'll check back"):
→ Follow the Autonomous Work Protocol below.
→ Create checkpoint file after each task.
→ Stop and wait if: Red flag encountered, ambiguous requirement, or test failures you can't resolve in 2 attempts.

---

## 🤖 Autonomous Work Protocol

When user indicates they'll check back later (e.g., "work on the next 2 FRs", "I'll check in an hour"):

### 1. Before Starting
```
Read STATUS.md → identify tasks in "Now" and "Next"
For each task:
  - Read FR in REQUIREMENTS.md → note acceptance criteria
  - Check ARCHITECTURE.md → note relevant interfaces
  - Identify test files that need updating
```

### 2. Per-Task Loop
```
1. Create/switch to feature branch
2. Write failing test (TDD - RED)
3. Implement minimal code to pass (GREEN)
4. Run: ruff check && mypy --strict && pytest tests/ -v
5. If LLM code touched: Verify telemetry (see checklist)
6. Run: pytest evals/ -v
7. If all pass: 
   - Commit with (FR-NNN) reference
   - Update STATUS.md → move to "Shipped"
   - Log checkpoint
8. If failure:
   - Attempt fix (max 2 tries)
   - If still failing: Stop, document issue, wait for user
```

### 3. Checkpoint Log
After each completed task, append to `CHECKPOINT.md`:
```markdown
## [timestamp]
- **Task:** [description]
- **FR:** [FR-NNN]
- **Status:** ✅ Complete | ⚠️ Blocked | ❌ Failed
- **Tests:** [pass/fail count]
- **Notes:** [any issues or decisions made]
```

### 4. Stop Conditions (Wait for User)
- 🔴 Red flag from "Red Flags" section triggered
- 🔴 Test failures after 2 fix attempts
- 🔴 Ambiguous requirement (not in REQUIREMENTS.md)
- 🔴 Need to modify `policy.py` or `evidence.py`
- 🔴 Architecture decision needed (not in ARCHITECTURE.md)

---

## 🧪 TDD Enforcement

**This is mandatory. No exceptions.**

### The Cycle
```
RED    → Write test that fails (proves test works)
GREEN  → Write minimum code to pass
REFACTOR → Clean up, maintain passing tests
COMMIT → Only after green
```

### Rules
1. **No code before test.** If you catch yourself writing implementation first, delete it.
2. **One test at a time.** Don't batch.
3. **Watch it fail.** If test passes immediately, it's not testing the right thing.
4. **Minimal implementation.** Don't gold-plate. YAGNI.

### Test Naming
```python
def test_[unit]_[scenario]_[expected]():
    # e.g., test_retrieval_empty_query_returns_refusal()
    pass
```

### What to Test
| Component | Test Type | Location |
|-----------|-----------|----------|
| Retrieval logic | Unit | `tests/test_retrieval.py` |
| Citation validation | Unit | `tests/test_evidence.py` |
| Confidence gating | Unit | `tests/test_policy.py` |
| API endpoints | Integration | `tests/test_api.py` |
| Golden queries | Eval | `evals/test_*.py` |
| LLM telemetry | Unit | `tests/test_telemetry.py` |

---

## 📊 LLM Telemetry Requirements (NFR-030)

**Every LLM call MUST be instrumented. This applies to all projects with AI features.**

### Required Attributes (OTEL GenAI Semantic Conventions)

| Attribute | OTEL Key | Required |
|-----------|----------|----------|
| Provider | `gen_ai.system` | ✅ |
| Model | `gen_ai.request.model` | ✅ |
| Prompt tokens | `gen_ai.usage.prompt_tokens` | ✅ |
| Completion tokens | `gen_ai.usage.completion_tokens` | ✅ |
| Latency | `llm.latency_ms` | ✅ |
| Status | span status | ✅ |
| Request ID | `llm.request_id` | ✅ |

### Implementation Pattern

```python
# app/telemetry.py - Use this wrapper for ALL LLM calls
from opentelemetry import trace
import time

tracer = trace.get_tracer("app.llm")

async def traced_llm_call(
    client,
    prompt: str,
    model: str,
    **kwargs
) -> LLMResponse:
    with tracer.start_as_current_span("llm.completion") as span:
        span.set_attribute("gen_ai.system", "azure_openai")  # or anthropic, openai
        span.set_attribute("gen_ai.request.model", model)
        
        start = time.perf_counter()
        try:
            response = await client.complete(prompt, model=model, **kwargs)
            
            span.set_attribute("gen_ai.usage.prompt_tokens", response.prompt_tokens)
            span.set_attribute("gen_ai.usage.completion_tokens", response.completion_tokens)
            span.set_attribute("llm.latency_ms", int((time.perf_counter() - start) * 1000))
            span.set_status(Status(StatusCode.OK))
            
            return response
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
```

### Database Logging (Required for Audit)

```python
# Log to llm_calls table per ARCHITECTURE.md
await session.execute(
    text("""
        INSERT INTO llm_calls (id, session_id, provider, model, 
                               prompt_tokens, completion_tokens, latency_ms, status)
        VALUES (:id, :sid, :provider, :model, :pt, :ct, :latency, :status)
    """),
    {...}
)
```

### Verification Checklist (Run When Touching LLM Code)

- [ ] All LLM calls use `traced_llm_call()` or equivalent wrapper
- [ ] OTEL exporter configured (console for dev, OTLP for prod)
- [ ] `llm_calls` table populated on each call
- [ ] Test exists: `tests/test_telemetry.py::test_llm_call_emits_span`
- [ ] No raw client calls bypassing wrapper

---

## Reference Docs (Read These)

| Doc | Purpose | When to Check |
|-----|---------|---------------|
| `REQUIREMENTS.md` | FRs/NFRs with acceptance criteria | Starting a new feature |
| `ARCHITECTURE.md` | Overview + pointers to detailed docs | Quick reference |
| `docs/architecture/*.md` | Detailed: data-model, interfaces, deployment, observability | Deep implementation work |
| `STATUS.md` | Current phase, active tasks, blockers | Daily; before picking work |
| `EVALS.md` | Golden queries and pass/fail criteria | Adding/changing retrieval or LLM logic |

**Workflow:**
1. Check `STATUS.md` → find task in "Next" or "Now"
2. Look up FR in `REQUIREMENTS.md` → read acceptance criteria
3. Check `ARCHITECTURE.md` → find relevant schema/interface
4. **Write test first (TDD)**
5. Implement → run tests + evals
6. **Verify LLM telemetry if applicable**
7. Update `STATUS.md` → move task to "Shipped"
8. Commit with `(FR-NNN)` reference

---

## Stack (Current)

- **Backend:** FastAPI + Python 3.11
- **Database:** PostgreSQL (Azure Flexible Server)
- **Search:** Azure AI Search (hybrid BM25 + vector + semantic reranker)
- **Embeddings:** Azure OpenAI (text-embedding-3-large)
- **LLM:** Azure OpenAI (GPT-4o)
- **Frontend:** Next.js 14
- **Deployment:** Azure App Service + Vercel
- **Parser:** Marker (default), LlamaParse (cloud option)

> **Planned:** Config-driven provider abstraction (NFR-032, 034, 035). See ARCHITECTURE.md for target interfaces.

---

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
├── parser/              # Document parsing (NFR-036)
│   ├── client.py        # ParserClient interface
│   ├── marker.py        # Marker implementation
│   ├── llamaparse.py    # LlamaParse implementation
│   └── pypdf.py         # PyPDF fallback
├── otel.py              # OpenTelemetry setup
└── telemetry.py         # Metrics + PII-safe logging + LLM tracing

packages/shared/         # Shared schemas (SSOT)
evals/                   # Golden queries + runner
tests/                   # Unit + integration tests

REQUIREMENTS.md          # What to build (FRs/NFRs)
ARCHITECTURE.md          # How to build (schemas, interfaces, tiers)
STATUS.md                # Current work (updated daily)
EVALS.md                 # Golden queries + criteria
CHECKPOINT.md            # Autonomous work log (auto-generated)
```

---

## Commands

```bash
# Dev server
cd apps/api && uvicorn app.main:app --reload

# Tests (run in this order)
ruff check apps/ --fix          # Lint
ruff format apps/               # Format
mypy apps/api/app --strict      # Types
pytest tests/ -v                # Unit + integration
pytest evals/ -v                # Golden queries

# Quick verification (all gates)
ruff check apps/ && mypy apps/api/app --strict && pytest tests/ -v && pytest evals/ -v

# Evals only (specific suite)
pytest evals/test_citations.py -v
python -m evals.run --suite adversarial
```

---

## Invariants — Current (Enforced Now)

| Rule | Enforcement | Status |
|------|-------------|--------|
| Every answer requires citation | `evidence.py` validates post-LLM; no citation → refuse | ✅ Implemented |
| Confidence < 0.70 → refuse | `policy.py` gates response; returns refusal message | ✅ Implemented |
| No PII in logs | `telemetry.py` redacts; log audit checks in CI | ✅ Implemented |
| **TDD for all features** | CLAUDE.md enforces; tests must exist before merge | ✅ Enforced |
| **LLM calls instrumented** | `telemetry.py` wrapper; NFR-030 | ✅ Enforced |

## Invariants — Planned (Phase 3: Multi-tenancy)

| Rule | Enforcement | FR |
|------|-------------|-----|
| Tenant isolation on all queries | Every DB query includes `tenant_id` | FR-001 |
| Matter isolation | All artifacts scoped by `matter_id` | FR-002 |
| RBAC enforcement | Role checked on every API call | FR-003 |

> ⚠️ **Current state:** Single-tenant demo. Multi-tenancy comes in Phase 3.

---

## Quality Gates

| Check | Command | Enforced |
|-------|---------|----------|
| Lint | `ruff check apps/` | CI blocks PR |
| Types | `mypy apps/api/app --strict` | CI blocks PR |
| Unit tests | `pytest tests/ -v` | CI blocks PR |
| Evals | `pytest evals/ -v` | CI blocks PR if <95% pass |
| **LLM Telemetry** | `pytest tests/test_telemetry.py -v` | CI blocks PR |

**No exceptions.** If a gate fails, fix it before merging.

---

## Commit Convention

```
type(scope): description (FR-NNN)

# Examples:
feat(retrieval): add BM25 + vector hybrid search (FR-021)
fix(evidence): handle empty citation spans (FR-025)
test(evals): add adversarial prompt injection cases
test(telemetry): add LLM span emission test
```

Types: `feat`, `fix`, `test`, `docs`, `refactor`, `chore`

---

## Mistakes (Learn from These)

| Date | Mistake | Rule Added |
|------|---------|------------|
| 01-14 | LLM cited non-existent page | Post-LLM validation required; verify chunk exists |
| 01-15 | PII in debug logs during demo | Redact by default; use `telemetry.py` |
| 01-16 | Confidence 0.68 returned answer | Gate MUST be < not <= ; 0.70 is refuse |
| 01-17 | Azure AI Search latency too high | Pivot to pgvector for hybrid search |
| 01-20 | Code written before tests | TDD enforced; delete code if no test exists |
| 01-20 | LLM call without telemetry | All LLM calls must use `traced_llm_call()` wrapper |

---

## Red Flags — Stop and Ask

- Removing or weakening citation validation
- Logging raw document content or user queries
- Disabling confidence threshold for "testing"
- Any change to `policy.py` or `evidence.py` without review
- Skipping evals "just this once"
- **Writing code before tests**
- **LLM calls bypassing telemetry wrapper**
- **Skipping LLM telemetry "for speed"**

---

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
| `app/telemetry.py` | **LLM telemetry wrapper + PII redaction** |
| `app/otel.py` | OpenTelemetry setup |
| `evals/golden.jsonl` | Golden queries for regression |

---

## Dependencies (Current)

- PostgreSQL: `asyncpg` + `sqlalchemy[asyncio]`
- Azure AI Search: `azure-search-documents`
- Azure OpenAI: `openai` (with Azure endpoint)
- Observability: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`
- FastAPI + Pydantic
- Parser: `marker-pdf` (default), `llama-parse` (optional)

---

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

# Parser
PARSER_PROVIDER=marker  # or pypdf, llamaparse

# App
CONFIDENCE_THRESHOLD=0.70

# Telemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=evidence-bound
```

> **Planned:** Config-driven provider selection (SEARCH_PROVIDER, LLM_PROVIDER, EMBEDDING_PROVIDER). See ARCHITECTURE.md.
