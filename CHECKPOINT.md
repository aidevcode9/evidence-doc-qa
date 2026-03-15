# CHECKPOINT.md — Autonomous Work Log

> Auto-generated during autonomous work sessions. Review after each session.

---

## 2026-03-15 FR-056: User Menu with Sign Out

**Status:** ✅ Complete
**Files changed:**
- apps/web/components/UserMenu.tsx (new)
- apps/web/app/page.tsx (modified — added UserMenu to header)
- apps/web/app/login/page.tsx (modified — added signed-out banner)

**Verification:**
- [x] `npx tsc --noEmit` — passed
- [x] `npx next build` — passed
- [x] `pytest tests/ -v` — 357 passed (56 fail + 29 errors pre-existing SSO/rate-limit)
- [x] Skeptic review — APPROVED (0 critical, 0 high, 2 low)

**Notes:** Frontend-only change. Backend logout already existed. Uses /api/auth/me for user info (httpOnly cookie not readable client-side). Demo mode fallback when auth bypass enabled.

---

## 2026-03-02 NFR-045: Langfuse PII Redaction

**Status:** ✅ Complete
**Files changed:**
- apps/api/app/otel.py (modified — added `redact_for_langfuse()`)
- apps/api/app/services/ask_service.py (modified — reverted `capture_input=True` → `False`, added redacted enrichment)
- tests/test_langfuse.py (modified — added `TestLangfusePIIRedaction` class, 6 tests)
- REQUIREMENTS.md (modified — NFR-045 acceptance criteria updated with PII redaction)
- STATUS.md (modified — added PII redaction entry)

**Verification:**
- [x] `ruff check apps/` — passed
- [x] `mypy apps/api/app --strict` — pre-existing errors only (slowapi import)
- [x] `pytest tests/test_langfuse.py` — 33/33 passed (excluding pre-existing email_validator + credential-gated)
- [x] `/wsskeptic` — PASS (0 CRITICAL, 0 HIGH, 1 MEDIUM fixed)

**Skeptic MEDIUM fix:** Replaced `doc_names` with `doc_count` to prevent document filenames (which may contain client names in law firm context) from leaking to Langfuse Cloud.

**Notes:**
- `@observe` decorators still create trace spans with timing/hierarchy — `capture_input=False` only prevents raw function args from being sent
- `redact_for_langfuse()` sends: question_len, answer_len, citation_count, evidence_grade, evidence_label, verification_status, refusal_code, doc_count
- Both success and refusal paths enriched with redacted metadata
- Production deployment: no action needed (already deployed with `capture_input=False` default; this session reverted the temporary `True` change)

---

## 2026-03-01 NFR-045: Langfuse Pipeline Coverage + Doc Sync

**Status:** ✅ Complete
**Files changed:**
- apps/api/app/retrieval.py (modified — @observe + _enrich_hybrid_observation)
- apps/api/app/embeddings.py (modified — @observe + safe_update_observation)
- tests/test_langfuse.py (modified — 4 new tests in TestRetrievalAndEmbeddingObservability)
- tests/test_telemetry.py (modified — renamed TestLLMCallsTable → TestTelemetryTable)
- CLAUDE.md (modified — llm_calls → telemetry, 4 refs)
- REQUIREMENTS.md (modified — llm_calls → telemetry, 3 refs)
- ARCHITECTURE.md (modified — llm_calls → telemetry, 1 ref)
- docs/architecture/observability.md (rewritten — telemetry schema, Langfuse waterfall)
- docs/architecture/README.md (modified — llm_calls → telemetry, 1 ref)
- docs/architecture/deployment.md (rewritten — matches actual prod deployment)

**Verification:**
- [x] `ruff check apps/` — passed
- [x] `mypy apps/api/app --strict` — 16 pre-existing errors (slowapi/email_validator stubs), changed files clean
- [x] `pytest tests/ -v` — 351 passed, 56 failed (pre-existing), 29 errors (pre-existing)
- [x] `pytest tests/test_langfuse.py::TestRetrievalAndEmbeddingObservability` — 4/4 passed
- [x] `/wsskeptic` — 0 CRITICAL, 0 HIGH, 1 LOW (import order, fixed)
- [x] Zero `llm_calls` references remaining (grep verified)

**Langfuse waterfall after this:**
```
execute_ask → hybrid_search → embed_texts_with_usage → verify_relevance → call_openai
```

**Notes:** Deployment.md also rewritten this session (separate from NFR-045). LANGFUSE_ENABLED default changed to 1 in .env.example by user.

---

## [2026-03-01] NFR-045: Langfuse Cloud Production Integration (Enrichment)

**Status:** ✅ Complete
**Files changed:**
- apps/api/app/otel.py (modified — added safe_update_observation, safe_update_trace, safe_get_trace_id)
- apps/api/app/verification.py (modified — added Langfuse observation enrichment after LLM call)
- apps/api/app/services/ask_service.py (modified — added trace root context + trace ID capture)
- apps/api/app/db.py (modified — added langfuse_trace_id column to Telemetry)
- apps/api/app/telemetry.py (modified — added langfuse_trace_id param + exposed in load_window_telemetry)
- alembic/versions/0011_add_langfuse_trace_id.py (new — migration for langfuse_trace_id column)
- tests/test_langfuse.py (modified — added 13 new tests in 2 test classes)

**Verification:**
- [x] `ruff check apps/` — passed
- [x] `mypy apps/api/app --strict` — passed on changed files (8 pre-existing errors in security.py)
- [x] `pytest tests/test_langfuse.py -v` — 24 passed, 2 failed (pre-existing email-validator), 3 skipped
- [x] `/wsskeptic` adversarial review — 0 CRITICAL, 2 HIGH (fixed), 0 MEDIUM, 2 LOW (accepted)

**Skeptic fixes applied:**
- H1: Filter None values from Langfuse tags list (ask_service.py:95)
- H2: Add langfuse_trace_id to load_window_telemetry output (telemetry.py:88)

**Notes:** Previous NFR-045 work (01-24) added @observe decorator infrastructure but traces were empty in Langfuse Cloud — no model/token/cost data captured. This session adds the enrichment layer that makes traces actually useful in production. Deployment requires setting LANGFUSE_ENABLED=1 + Langfuse Cloud keys.

---

## Session: 2026-01-21

### Pre-Flight Check
- [x] Read STATUS.md — identified tasks
- [x] Read REQUIREMENTS.md — noted acceptance criteria
- [x] Read ARCHITECTURE.md — noted relevant interfaces
- [x] Identified test files to update

### Tasks Attempted

## Task 1: NFR-040 — Type annotations (mypy --strict)
- **FR/NFR:** NFR-040
- **Branch:** feat/ocr-image-support
- **Status:** ✅ Complete

### Changes Made
- Created `mypy.ini` with module ignore rules for third-party libraries without stubs
- Fixed 130+ type annotation issues across 15+ files:
  - `config.py`: Added return types to `_getenv` and `_is_truthy`
  - `cost.py`: Added type aliases `CostEntry`, `CostBreakdown`, `TraceMetadata`
  - `db.py`: Added `Engine` import and return type
  - `main.py`: Added return type to `startup_event`
  - `telemetry.py`: Modernized from `Dict`/`List` to `dict`/`list`
  - `retrieval.py`: Full rewrite with modern type annotations
  - `verification.py`: Added `UsageInfo` type alias, fixed all function signatures
  - `otel.py`: Removed unused type ignore comments
  - `embeddings.py`: Added `UsageInfo` type alias
  - `ingestion.py`: Fixed tuple return types
  - `indexing.py`: Added `ChunkRowTuple` type alias
  - `services/rag.py`: Added `ChunkDict` type alias
  - `services/document_service.py`: Added `ChunkRowTuple` type alias, TYPE_CHECKING import
  - `services/ask_service.py`: Added `ChunkDict`, `VersionSnapshot` aliases, fixed hybrid_search unpacking
  - `routers/`: Added generic type params to all dict returns

### Verification
- [x] `ruff check apps/` — passed
- [x] `mypy apps/api/app --strict` — passed (0 errors)
- [x] `pytest tests/ -v` — 51/57 passed (6 async test failures pre-existing)
- [ ] `pytest evals/ -v` — skipped (requires running backend)

### Notes
- Pre-existing issue: 6 telemetry tests fail due to missing pytest-asyncio configuration
- Pre-existing issue: evals fail because they require a running API server/database
- These are not regressions from the type annotation changes

---

## Task 2: pytest-asyncio configuration
- **FR/NFR:** —
- **Branch:** feat/ocr-image-support
- **Status:** ✅ Complete

### Changes Made
- Installed `pytest-asyncio` package
- Created `tests/conftest.py` with pytest-asyncio plugin configuration
- Created `pytest.ini` with `asyncio_mode = auto` setting

### Verification
- [x] `pytest tests/ -v` — 57/57 passed (all telemetry tests now work)

### Notes
- All async tests now run properly with the `@pytest.mark.asyncio` marker

---

## Task 3: NFR-041 — Dev dependencies separation
- **FR/NFR:** NFR-041
- **Branch:** feat/ocr-image-support
- **Status:** ✅ Complete

### Changes Made
- Created `apps/api/requirements-dev.txt` with dev-only dependencies:
  - ruff>=0.8.0 (linting/formatting)
  - mypy>=1.13.0 (type checking)
  - pytest>=8.0.0 (testing)
  - pytest-asyncio>=1.0.0 (async test support)
  - types-requests>=2.31.0 (type stubs)

### Verification
- [x] `ruff check apps/` — passed
- [x] `mypy apps/api/app --strict` — passed (0 errors)
- [x] `pytest tests/ -v` — 57/57 passed

### Notes
- Production dependencies remain in `requirements.txt`
- Dev dependencies now properly separated per NFR-041

---

## Task 4: FR-030 — UI displays citations (Phase 2)
- **FR/NFR:** FR-030
- **Branch:** feat/ocr-image-support
- **Status:** ✅ Complete (Already Implemented)

### Analysis
- FR-030 was already implemented in `EvidencePanel.tsx`
- Component displays: doc_name, page_num, snippet for each citation
- Citations shown in "Sources" section with proper formatting

### Notes
- No changes required — feature already existed

---

## Task 5: FR-031 — Click citation → document viewer (Phase 2)
- **FR/NFR:** FR-031
- **Branch:** feat/ocr-image-support
- **Status:** ✅ Complete

### Changes Made

**Backend:**
- `apps/api/app/db.py`: Added `get_document()` function
- `apps/api/app/routers/docs.py`: Added two new endpoints:
  - `GET /v1/docs/{doc_id}` — returns document metadata
  - `GET /v1/docs/{doc_id}/view` — serves document file (FileResponse)
- Proper media type detection for PDF/PNG/JPG/TIFF files

**Frontend:**
- `apps/web/components/DocumentViewer.tsx`: New modal component
  - Displays document in iframe with page targeting (#page=N)
  - Shows loading/error states
  - "Open in New Tab" fallback for browser compatibility
  - Displays citation details (doc name, page, snippet preview)
- `apps/web/components/EvidencePanel.tsx`: Made citations clickable
  - Added `onCitationClick` callback prop
  - Citations now render as buttons with hover effects
  - Shows "View Source" on hover
- `apps/web/app/page.tsx`: Integrated DocumentViewer
  - Added `selectedCitation` state
  - Wired up `handleCitationClick` handler
  - Renders DocumentViewer modal when citation selected

**Tests:**
- `tests/test_docs_api.py`: 6 new tests for document API endpoints
  - Test metadata retrieval
  - Test 404 handling
  - Test file serving
  - Test media type detection

### Verification
- [x] `ruff check apps/` — passed
- [x] `mypy apps/api/app --strict` — passed (0 errors)
- [x] `pytest tests/ -v` — 63/63 passed (6 new tests)

### Notes
- Used iframe with PDF page targeting (#page=N) for simplicity
- Decision logged in STATUS.md: Iframe PDF viewer over complex PDF.js integration

---

## Task 6: FR-001 & FR-002 — Tenant + Matter Isolation (Phase 3)
- **FR/NFR:** FR-001, FR-002
- **Branch:** feat/citation-export
- **Status:** ✅ Complete

### TDD Cycle
- [x] RED: 19 tests written for tenant_id and matter_id columns + query filters
- [x] GREEN: Added tenant_id/matter_id to all 6 models; updated load_chunks/load_index_records
- [x] REFACTOR: Cleaned up, added indexes

### Changes Made

**Database Models (`apps/api/app/db.py`):**
- Added `tenant_id: Mapped[str]` and `matter_id: Mapped[str]` to all 6 models:
  - Document
  - Chunk
  - IndexRecord
  - Telemetry
  - QASession
  - QAMessage
- All columns are NOT NULL with indexes for query performance
- Updated `load_chunks()` to accept optional `tenant_id` and `matter_id` filters
- Updated `load_index_records()` to accept optional `tenant_id` and `matter_id` filters

**Tests (`tests/test_multitenancy.py`):**
- 19 new tests covering:
  - Presence of tenant_id/matter_id on all models (12 tests)
  - Function signatures accept tenant_id/matter_id parameters (4 tests)
  - Query functions apply filters correctly (3 tests)

**Migration (`alembic/versions/0004_add_tenant_matter_isolation.py`):**
- Adds tenant_id and matter_id columns to all 6 tables
- Sets default values for existing data during migration
- Creates indexes for efficient filtering

### Verification
- [x] `ruff check apps/api/app/db.py tests/test_multitenancy.py` — passed
- [x] `mypy apps/api/app --strict` — passed
- [x] `pytest tests/ -v` — 107/107 passed

### Notes
- FR-001/FR-002 add the schema foundation for multi-tenancy
- FR-003/FR-004 (RBAC + matter permissions) are next
- Default tenant/matter IDs used for migration of existing data

---

## Session: 2026-01-22

### Pre-Flight Check
- [x] Read STATUS.md — Phase 4 Provider Abstraction is next
- [x] Read REQUIREMENTS.md — NFR-032, NFR-034, NFR-035
- [x] Read ARCHITECTURE.md — Provider interface patterns
- [x] Identified test files to update

---

## Task 1: NFR-032, NFR-034, NFR-035 — Provider Abstraction Interfaces
- **FR/NFR:** NFR-032 (LLM), NFR-034 (Search), NFR-035 (Embedding)
- **Branch:** feat/rbac-roles
- **Status:** ✅ Complete

### Changes Made

**LLM Provider (`apps/api/app/llm/`):**
- `base.py`: LLMClient abstract interface + LLMResponse dataclass
- `azure_openai.py`: AzureOpenAIClient implementation
- `__init__.py`: Factory function `get_llm_client()`

**Embedding Provider (`apps/api/app/embedding/`):**
- `base.py`: EmbeddingClient abstract interface + EmbeddingResult dataclass
- `local.py`: LocalEmbeddingClient (hash-based for testing)
- `azure_openai.py`: AzureOpenAIEmbeddingClient implementation
- `__init__.py`: Factory function `get_embedding_client()`

**Search Provider (`apps/api/app/search/`):**
- `base.py`: SearchClient abstract interface + SearchResult/SearchResponse dataclasses
- `local.py`: LocalSearchClient (BM25 + vector with RRF fusion)
- `azure.py`: AzureSearchClient (Azure AI Search with semantic reranking)
- `__init__.py`: Factory function `get_search_client()`

**Tests (`tests/test_provider_abstraction.py`):**
- 35 tests covering all interfaces and implementations

### Verification
- [x] `ruff check apps/` — passed
- [x] `mypy apps/api/app --strict` — passed (0 errors)
- [x] `pytest tests/ -v` — 218/218 passed (35 new tests)

### Commits
- `42b07fa` feat(security): add provider abstraction and security hardening (NFR-032, NFR-034, NFR-035)

---

## Task 2: Security Hardening (wsskeptic review)
- **FR/NFR:** Security
- **Branch:** feat/rbac-roles
- **Status:** ✅ Complete

### Changes Made

**CRITICAL Fix - Filter Injection Prevention:**
- `context.py`: Added `_is_valid_identifier()` function
- Validates tenant_id/matter_id/user_id are alphanumeric with hyphens only
- Rejects injection attempts like `"foo' or 1 eq 1 or '"`

**HIGH Fix - Token Overflow Prevention:**
- `config.py`: Added `MAX_QUERY_LENGTH = 4000`
- `ask_service.py`: Added query length validation

**HIGH Fix - Rate Limit Handling:**
- `verification.py`: Added retry with exponential backoff (1s, 2s, 4s) for 429/5xx errors

**HIGH Fix - Unsafe Config Warnings:**
- `main.py`: Added startup warnings for ALLOW_UNVERIFIED and !STRICT_EVIDENCE

**Tests (`tests/test_tenant_isolation.py`):**
- 11 new security tests

### Verification
- [x] `ruff check apps/` — passed
- [x] `mypy apps/api/app --strict` — passed (0 errors)
- [x] `pytest tests/ -v` — 218/218 passed (11 new security tests)

### Notes
- wsskeptic review identified 1 CRITICAL, 4 HIGH issues — all fixed
- Recommendation: APPROVE WITH FIXES → now APPROVED

---

## Task 3: Provider Abstraction Integration
- **FR/NFR:** NFR-032, NFR-034, NFR-035
- **Branch:** feat/rbac-roles
- **Status:** ✅ Complete

### Changes Made

**Integration Tests (`tests/test_provider_integration.py`):**
- 17 new tests for provider factory functions
- Tests for embedding, LLM, and search client creation
- Tests for config-driven provider switching
- Tests for unknown provider error handling

**Configuration (`.env.example`):**
- Added `LLM_PROVIDER=azure_openai` (future: ollama, openai, anthropic)
- Added `SEARCH_PROVIDER=azure` (or `local` for pgvector)
- Added `DOCQA_MAX_QUERY_LENGTH=4000` (security)

### Provider Abstraction Summary

| Provider Type | Azure Implementation | Open Source Alternative |
|--------------|---------------------|------------------------|
| LLM | AzureOpenAIClient | (Ollama planned) |
| Embeddings | AzureOpenAIEmbeddingClient | LocalEmbeddingClient |
| Search | AzureSearchClient | LocalSearchClient (pgvector) |

### Verification
- [x] `ruff check apps/` — passed
- [x] `mypy apps/api/app --strict` — passed (0 errors)
- [x] `pytest tests/ -v` — 235/235 passed (17 new integration tests)

### Notes
- Phase 4 complete: All provider abstractions implemented
- Providers can be swapped via environment variables only
- No code changes needed to switch between Azure and open-source alternatives

---

## Session: 2026-01-24

### Pre-Flight Check
- [x] Read STATUS.md — NFR-045 Phase 2 in Next
- [x] Read REQUIREMENTS.md — NFR-045 acceptance criteria
- [x] Read ARCHITECTURE.md — Langfuse integration pattern
- [x] Identified files to update: verification.py, ask_service.py, otel.py

---

## Task 1: NFR-045 Phase 2 — @observe Decorators
- **FR/NFR:** NFR-045
- **Branch:** feat/fr050-frontend-auth
- **Status:** ✅ Complete

### Changes Made

**otel.py:**
- Added `observe` import from `langfuse.decorators` (with fallback)
- Added `_noop_observe()` for graceful degradation when Langfuse unavailable
- Added `get_observe_decorator()` factory function
- Proper TypeVar typing for mypy --strict

**verification.py:**
- Added `@_observe(name="verify_relevance", capture_input=False, capture_output=False)`
- Added `@_observe(name="call_openai", as_type="generation", capture_input=False, capture_output=False)`

**ask_service.py:**
- Added `@_observe(name="execute_ask", capture_input=False, capture_output=False)`

### Verification
- [x] `ruff check apps/` — passed
- [x] `mypy apps/api/app --strict` — passed (0 errors)
- [x] `pytest tests/ -v` — 405/405 passed
- [x] LLM telemetry verified — decorators applied, PII-safe (capture_input/output=False)

### wsskeptic Review
- 0 CRITICAL, 0 HIGH, 0 MEDIUM, 2 LOW (accepted)
- Recommendation: APPROVE

### Notes
- Phase 2 completes NFR-045 decorator integration
- All decorators use PII-safe settings (no input/output capture)
- Graceful degradation: app works without Langfuse installed

---

## Template (Copy for each task)

```markdown
## [HH:MM] Task: [description]
- **FR/NFR:** [FR-NNN or NFR-NNN]
- **Branch:** [branch name]
- **Status:** ✅ Complete | ⚠️ Blocked | ❌ Failed

### TDD Cycle
- [ ] RED: Test written and fails
- [ ] GREEN: Minimal code passes
- [ ] REFACTOR: Cleaned up

### Verification
- [ ] `ruff check apps/` — passed
- [ ] `mypy apps/api/app --strict` — passed
- [ ] `pytest tests/ -v` — [X/Y passed]
- [ ] `pytest evals/ -v` — [X/Y passed]
- [ ] LLM telemetry verified (if applicable)

### Commits
- `[hash]` [commit message]

### Notes
[Any decisions, issues, or blockers encountered]
```

---

## Quick Reference

### Stop Conditions (Wait for User)
- 🔴 Red flag triggered (see CLAUDE.md)
- 🔴 Test failures after 2 fix attempts  
- 🔴 Ambiguous requirement
- 🔴 Need to modify `policy.py` or `evidence.py`
- 🔴 Architecture decision needed

### Verification Command (All Gates)
```bash
ruff check apps/ && mypy apps/api/app --strict && pytest tests/ -v && pytest evals/ -v
```
