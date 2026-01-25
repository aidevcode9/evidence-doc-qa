---
description: Research before implementing - gather context before any code is written
---

# Research Before Implementing

> **Role:** Investigator that gathers context before any code is written. Prevents "code first, understand later" mistakes.

## Trigger

- Before `/wsstart`
- When `/wsorchestrate` routes here
- User says "research FR-XXX" or "what do I need to know for..."

---

## Protocol

### Step 1: Understand the FR/NFR

```bash
# Read the requirement
1. REQUIREMENTS.md → Find FR-NNN or NFR-NNN, read acceptance criteria
2. Note the phase (see § Phasing)
3. Check dependencies (does it need another FR first?)
4. Check implementation checklist (if exists in REQUIREMENTS.md)
```

---

### Step 2: Check Architecture Patterns

```bash
# What patterns apply?
1. ARCHITECTURE.md → Implementation status (is anything related ✅ already?)
2. docs/architecture/*.md → Detailed patterns:
   - data-model.md → Database schema, RLS, indexes
   - interfaces.md → LLM, Embedding, Search, Parser abstractions
   - observability.md → LLM tracking, Langfuse, telemetry
   - deployment.md → Tiers, Docker, env vars
```

**Output:** List of patterns to follow with file paths

---

### Step 3: Search Codebase for Similar Code

```bash
# Find examples
grep -r "relevant terms" apps/api/app/
ls apps/api/app/services/     # What services exist?
ls apps/api/app/routers/      # What routes exist?
ls apps/api/app/llm/          # LLM clients
ls apps/api/app/parser/       # Parser clients
ls apps/api/app/embedding/    # Embedding clients
```

**Look for:**
- Similar implementations to copy from
- Shared utilities to reuse
- Naming conventions to follow
- Test patterns to model

---

### Step 4: Check Database Schema

```bash
# If FR involves data
1. docs/architecture/data-model.md → Table schemas
2. apps/api/app/db.py → SQLAlchemy models
3. apps/api/migrations/versions/ → Alembic migrations
```

**Note:**
- Required columns (tenant_id, matter_id per FR-001/002)
- Indexes needed
- Foreign key relationships

---

### Step 5: Check Test Patterns

```bash
# Find test examples
1. tests/test_*.py → Existing tests to model after
2. evals/*.jsonl → Golden queries for retrieval/LLM
3. EVALS.md → Eval suite documentation
```

---

### Step 6: Check Config & Environment

```bash
# What config is needed?
1. apps/api/app/config.py → Existing env vars
2. .env.example → Template
3. .github/workflows/deploy-container.yml → Prod env vars
```

---

### Step 7: Identify Risks & Unknowns (Evidence-Bound Specific)

Consider these Evidence-Bound invariants (from CLAUDE.md):

- [ ] **Citation validation:** Does this touch `evidence.py`? Red flag - needs extra review
- [ ] **Confidence gating:** Does this affect `policy.py`? Red flag - needs extra review
- [ ] **Tenant isolation:** Does this query data? Must include tenant_id filter (FR-001)
- [ ] **Matter isolation:** Does this access artifacts? Must include matter_id (FR-002)
- [ ] **LLM telemetry:** Does this call LLM? Must use traced wrapper (NFR-030)
- [ ] **PII in logs:** Does this log queries/responses? Must redact (NFR-004)
- [ ] **Parser involved:** Touching ingestion? Check NFR-036 patterns

---

## Output Format

```markdown
## Research: FR-NNN - [Title]

### Requirement
[Copy acceptance criteria from REQUIREMENTS.md]

### Phase
[Phase N] - [Name] | Dependencies: [list or "None"]

### Patterns to Use
| Pattern | Location | Notes |
|---------|----------|-------|
| Service pattern | apps/api/app/services/ask_service.py | Copy structure |
| Router pattern | apps/api/app/routers/ask.py | Thin route + context |
| Config pattern | apps/api/app/config.py | Add env vars here |

### Existing Code to Reference
- `apps/api/app/services/document_service.py` - Similar service
- `apps/api/app/routers/docs.py` - Similar router
- `tests/test_api.py` - Test patterns

### Database (if applicable)
- **Table:** `table_name`
- **Required columns:** tenant_id, matter_id (FR-001/002)
- **Migration needed:** Yes/No

### Evidence-Bound Invariants
- [ ] Tenant isolation checked
- [ ] Matter isolation checked
- [ ] LLM telemetry verified (if applicable)
- [ ] PII redaction in place
- [ ] Citation validation unaffected

### Risks
1. **Risk:** [description]
   **Mitigation:** [approach]

### Implementation Approach
1. [Step 1 - with TDD: test first]
2. [Step 2]
3. [Step 3]

### Files to Create/Modify
| File | Action | Purpose |
|------|--------|---------|
| `apps/api/app/services/xxx.py` | Create | Business logic |
| `apps/api/app/routers/xxx.py` | Create/Modify | API endpoint |
| `tests/test_xxx.py` | Create | Tests (TDD - write first) |

### Tests Needed (TDD)
```python
def test_xxx_scenario_expected():
    """Description of what we're testing."""
    pass
```

### Environment Variables (if needed)
```bash
# Add to .env and deploy-container.yml
NEW_VAR=value
```

---

**Ready for /wsstart?** [Y/n]
```

---

## Quick Research by FR Category

### Retrieval FRs (FR-020s)
```bash
# Check
- apps/api/app/retrieval.py
- apps/api/app/embeddings.py
- docs/architecture/interfaces.md → SearchClient
- tests/test_retrieval.py
```

### Evidence/Citation FRs (FR-023–025)
```bash
# RED FLAG: Core invariants
- apps/api/app/evidence.py
- apps/api/app/policy.py
- apps/api/app/verification.py
- CLAUDE.md § Invariants
```

### Document FRs (FR-010s)
```bash
# Check
- apps/api/app/parser/
- apps/api/app/indexing.py
- apps/api/app/ingestion.py
- apps/api/app/services/document_service.py
```

### Export FRs (FR-030s)
```bash
# Check
- apps/api/app/routers/export.py
- apps/api/app/services/export.py (if exists)
- tests/test_export.py
```

### Auth FRs (FR-050s)
```bash
# Check
- apps/api/app/routers/auth.py
- apps/api/app/routers/sso.py
- apps/api/app/routers/admin.py
- docs/architecture/deployment.md
```

### Audit FRs (FR-040s)
```bash
# Check
- apps/api/app/routers/audit.py
- apps/api/app/db.py → AuditEvent model
- docs/architecture/data-model.md
```

### LLM/Provider NFRs (NFR-030s)
```bash
# Check
- apps/api/app/llm/
- apps/api/app/embedding/
- docs/architecture/interfaces.md
- docs/LLM_PROVIDERS.md
```

### Observability NFRs (NFR-045/046)
```bash
# Check
- apps/api/app/otel.py
- apps/api/app/telemetry.py
- docs/architecture/observability.md
```

---

## Invariants

1. **Research before code** — Never skip this step
2. **Document unknowns** — If something is unclear, flag it
3. **Check implementation status** — Don't reinvent what exists
4. **Identify dependencies** — Know what must come first
5. **Note TDD tests** — Outline failing tests before coding
6. **Output is approval gate** — Don't proceed to /wsstart without "Ready? Y"
7. **Red flags get extra scrutiny** — evidence.py, policy.py changes need justification
