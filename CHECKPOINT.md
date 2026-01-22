# CHECKPOINT.md — Autonomous Work Log

> Auto-generated during autonomous work sessions. Review after each session.

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
