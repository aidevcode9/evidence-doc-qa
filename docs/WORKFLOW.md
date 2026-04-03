# Evidence-Bound Development Workflow

> A structured approach to AI-assisted development with built-in quality gates, adversarial reviews, and autonomous work tracking.

---

## Overview

This project uses a **command-driven workflow system** that enforces:
- **TDD (Test-Driven Development)** — tests before code
- **Research before implementation** — understand patterns first
- **Adversarial reviews** — AI-specific failure mode checks
- **Phased delivery** — FRs/NFRs organized into ship milestones
- **Autonomous work logging** — session tracking in CHECKPOINT.md

---

## Workflow Commands

### Skills (user-invoked, require judgment)

| Command | Role | When to Use |
|---------|------|-------------|
| `/wsorchestrate` | Project Manager | Starting a session, picking work, batching FRs |
| `/wsresearch` | Investigator | Before coding, gather context and patterns |
| `/wsstart` | Developer | Plan + implement with TDD |
| `/wsverify` | QA | Run lint, types, tests (also enforced by pre-commit hook) |
| `/wsskeptic` | Security Auditor | Adversarial review for AI failure modes |
| `/wsedd` | Eval Engineer | Write failing eval before retrieval/LLM changes |
| `/wsredteam` | Red Team | Attack the system, find weaknesses across 6 vectors |
| `/wsdocs` | Technical Writer | Check which docs/diagrams need updating after changes |
| `/wsstatus` | Reporter | Update STATUS.md |
| `/wsmistake` | Historian | Document mistakes for future reference |

### Hooks (enforced automatically, can't be skipped)

Configured in `.claude/settings.json`. These fire on every matching tool call:

| Hook | Trigger | What it does |
|------|---------|-------------|
| **Pre-commit gates** | `git commit` | Runs `ruff + mypy --strict + pytest`. Blocks commit on failure. |
| **Pre-push reminder** | `git push` | Reminds to run `/wsskeptic` |
| **DB safety** | `DELETE`, `alembic` | Prompt hook blocks destructive DB commands without approval |
| **Post-edit lint** | Edit/Write `.py` | Auto-runs `ruff` after every Python file change |

### Published Documentation

When docs change, the GitHub Pages site auto-deploys. Run `/wsdocs` after code changes to check which docs need updating. The published site is the stakeholder-facing view of the same in-repo docs.

---

## Typical Development Session

```
┌─────────────────────────────────────────────────────────────────┐
│                        SESSION START                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  /wsorchestrate                                                  │
│  ─────────────────                                               │
│  • Reads STATUS.md, REQUIREMENTS.md, CHECKPOINT.md               │
│  • Identifies current phase and available work                   │
│  • Creates session plan with batched FRs                         │
│  • Waits for approval before proceeding                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  FOR EACH FR/NFR IN BATCH:                                       │
│  ═══════════════════════════                                     │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ /wsresearch  │ →  │  /wsstart    │ →  │  /wsverify   │       │
│  │              │    │              │    │              │       │
│  │ • Patterns   │    │ • TDD cycle  │    │ • ruff       │       │
│  │ • Similar    │    │ • RED→GREEN  │    │ • mypy       │       │
│  │   code       │    │ • Implement  │    │ • pytest     │       │
│  │ • Risks      │    │              │    │              │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│                                                 │                │
│                                                 ▼                │
│                                          ┌──────────────┐       │
│                                          │  /wsskeptic  │       │
│                                          │              │       │
│                                          │ • Failure    │       │
│                                          │   modes      │       │
│                                          │ • Data leak  │       │
│                                          │ • Citations  │       │
│                                          └──────────────┘       │
│                                                 │                │
│                                                 ▼                │
│                                          Log to CHECKPOINT.md   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  SESSION END                                                     │
│  ───────────                                                     │
│  • /wsstatus → Update STATUS.md                                  │
│  • /wscommit → Commit with (FR-XXX) reference, push, PR          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Command Details

### `/wsorchestrate` — Project Manager

**Purpose:** Route work to the right workflows, manage phases, batch related FRs.

**Input triggers:**
- "Let's work on Phase 7"
- "Implement FR-011, FR-014"
- "What should I work on?"
- "Continue where we left off"

**Protocol:**
1. **Assess state** — Read STATUS.md, REQUIREMENTS.md, CHECKPOINT.md
2. **Determine scope** — Validate phase, check dependencies, batch FRs
3. **Create plan** — Present numbered plan with batches
4. **Wait for approval** — Don't proceed without "Y"
5. **Execute** — Route through research → start → verify → skeptic
6. **Log** — Update CHECKPOINT.md after each FR

**Phase Rules:**
| Phase | Contents | Prerequisite |
|-------|----------|--------------|
| 1. Core RAG | FR-010–025 | None |
| 2. Citations UI | FR-030–032 | Phase 1 |
| 3. Multi-tenancy | FR-001–004 | Phase 2 |
| 4. Provider Abstraction | NFR-032–036 | Phase 3 |
| 5. Auth | FR-050–053 | Phase 4 |
| 6. Audit | FR-040–043 | Phase 5 |
| 7. Polish | FR-011, FR-014, FR-015 | Phase 6 |
| 8. NFRs | NFR-001–046 | Phase 7 |

---

### `/wsresearch` — Investigator

**Purpose:** Gather context before coding. Prevent "code first, understand later."

**Output includes:**
- Acceptance criteria from REQUIREMENTS.md
- Architecture patterns to follow
- Similar existing code to reference
- Database schema considerations
- Evidence-Bound invariants checklist:
  - [ ] Tenant isolation (FR-001)
  - [ ] Matter isolation (FR-002)
  - [ ] LLM telemetry (NFR-030)
  - [ ] PII redaction (NFR-004)
  - [ ] Citation validation unchanged
- TDD test outline
- Risk assessment

**Ends with:** "Ready for /wsstart? [Y/n]"

---

### `/wsstart` — Developer

**Purpose:** Plan and implement with TDD enforcement.

**Protocol:**
1. Read STATUS.md → identify task
2. Create feature branch
3. Move task from "Next" to "Now"
4. **Enter Plan mode:**
   - What files need to change?
   - What tests are needed? (write FIRST)
   - What telemetry is needed?
   - Any env vars to add?
5. Wait for approval
6. Implement following TDD: RED → GREEN → REFACTOR

---

### `/wsverify` — QA

**Purpose:** Run all quality gates.

**Commands executed:**
```bash
ruff check apps/                    # Lint
mypy apps/api/app --strict          # Type check
pytest tests/ -v --tb=short         # Unit + integration tests
pytest evals/ -v                    # Golden query evals
```

**On failure:** Analyze error, suggest fix, ask before applying.

---

### `/wsskeptic` — Security Auditor

**Purpose:** Adversarial review for AI-specific failure modes.

**Checklist:**
1. **Failure Modes**
   - Empty retrieval handling
   - Low confidence gating (threshold 0.70)
   - LLM timeout behavior
   - Malformed input handling
   - Token limit exceeded

2. **Data Leakage**
   - Tenant isolation on every query
   - Prompt injection risks
   - PII in logs
   - Error message safety

3. **Citation Integrity**
   - Every claim validated against chunks
   - Fabrication risk assessment
   - Validation failure = refusal

4. **Refusal Behavior**
   - Explicit refusal triggers
   - No silent failures
   - Confidence bypass check

**Output format:**
```
CRITICAL: [description]
   Location: [file:line]
   Risk: [what could go wrong]
   Fix: [how to fix]

HIGH: [description]
   ...

Summary: X critical, Y high, Z low
Recommendation: BLOCK / APPROVE WITH FIXES / APPROVE
```

**Rule:** If CRITICAL issues exist → BLOCK. No exceptions.

---

### `/wsstatus` — Reporter

**Purpose:** Update STATUS.md with current progress.

**Updates:**
- Move completed items to "Done (This Week)"
- Update phase progress tables
- Add decisions made
- Note any blockers

---

### `/wscommit` — Release Manager

**Purpose:** Commit, push, create PR.

**Commit format:**
```
type(scope): description (FR-NNN)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:** `feat`, `fix`, `test`, `docs`, `refactor`, `chore`

---

## Key Files

| File | Purpose | Updated By | Sync Requirement |
|------|---------|------------|------------------|
| `STATUS.md` | Current phase, Now/Next/Blocked | `/wsstatus` | After every FR |
| `REQUIREMENTS.md` | FRs/NFRs with acceptance criteria | Manual | When scope changes |
| `ARCHITECTURE.md` | Patterns, schemas, interfaces | Manual | When adding patterns |
| `CHECKPOINT.md` | Autonomous work log | `/wsorchestrate` | After each task |
| `CLAUDE.md` | AI assistant instructions | Manual | When rules change |
| `docs/WORKFLOW.md` | Development workflow | Manual | When process changes |

---

## Documentation Sync Protocol

**These docs are the source of truth. They must stay in sync with code.**

### When to Update Each Doc

| Document | Update When |
|----------|-------------|
| `REQUIREMENTS.md` | FR/NFR scope changes, acceptance criteria updated |
| `ARCHITECTURE.md` | New pattern added, interface changed, schema modified |
| `STATUS.md` | Task started, completed, or blocked |
| `CHECKPOINT.md` | After each FR in autonomous mode |

### Manual Review Checklist (Before PR)

- [ ] Added new pattern? → Update `ARCHITECTURE.md`
- [ ] Added env vars? → Update `.env.example` + deployment docs
- [ ] Changed interface? → Update `docs/architecture/interfaces.md`
- [ ] Changed schema? → Update `docs/architecture/data-model.md`
- [ ] Shipped FR? → Update `STATUS.md` (move to Done)

### Automated Checks (Future CI)

```yaml
# Proposed CI checks for documentation drift
- name: Check STATUS.md freshness
  run: |
    # Warn if items in "Now" older than 3 days without update

- name: Check file references
  run: |
    # Verify ARCHITECTURE.md file paths exist

- name: Check env var documentation
  run: |
    # Verify all env vars in config.py are in .env.example
```

---

## Invariants (Always Enforced)

### ⛔ NON-NEGOTIABLE (Cannot Skip Under Any Circumstances)

| Rule | Why |
|------|-----|
| `/wsresearch` before implementation | Prevents "code first, understand later" failures |
| `/wsskeptic` before commit | Catches AI-specific failure modes before they ship |

These two steps are the minimum viable process. Everything else can be adapted, but these two cannot be skipped even under deadline pressure.

### Required (Should Not Skip)

| Rule | Enforcement |
|------|-------------|
| TDD required | CLAUDE.md: "Write failing test first" |
| Tenant isolation | Every DB query includes `tenant_id` |
| Citation validation | Every answer has verified citations |
| Confidence gating | < 0.70 = refuse |
| LLM telemetry | All calls through traced wrapper |
| No PII in logs | Redaction in `telemetry.py` |
| Documentation sync | Update docs when code patterns change |

---

## Autonomous Work Mode

When user says "work on this, I'll check back":

1. Follow `/wsorchestrate` protocol
2. Log every FR to CHECKPOINT.md
3. **Stop conditions:**
   - Red flag triggered (see CLAUDE.md)
   - Test failures after 2 fix attempts
   - Ambiguous requirement
   - Need to modify `policy.py` or `evidence.py`
   - Architecture decision needed

---

## Quick Reference

**Start a session:**
```
User: "Let's work on NFR-045"
→ /wsorchestrate activates
→ Creates plan, waits for approval
→ Routes through: research → start → verify → skeptic
→ Logs to CHECKPOINT.md
→ Updates STATUS.md
→ Commits with (NFR-045) reference
```

**Single FR mode:**
```
/wsresearch FR-011
/wsstart
/wsverify
/wsskeptic
/wscommit
```

**Check what's next:**
```
/wsorchestrate
→ "What should I work on?"
```

---

## Benefits

1. **Consistency** — Same process every time
2. **Quality gates** — Lint, types, tests, adversarial review
3. **Traceability** — Every change linked to FR/NFR
4. **Knowledge capture** — Decisions logged in STATUS.md
5. **Safe autonomy** — Clear stop conditions prevent runaway changes
6. **AI-specific safety** — /wsskeptic catches hallucination, leakage, citation issues
