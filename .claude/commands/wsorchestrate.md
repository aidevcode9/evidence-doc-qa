---
description: Orchestrate work session - routes to right workflows, manages phases
---

# Orchestrate Work Session

> **Role:** Senior Technical Project manager that follows the phased dev plan, batches work, and routes to the right workflows.

## Trigger

User says something like:
- "Let's work on Phase 7"
- "Implement FR-011, FR-014, FR-015"
- "What should I work on?"
- "Continue where we left off"
- Any ambiguous development request

---

## Protocol

### Step 1: Assess Current State

```bash
# Read project state
1. STATUS.md → Current phase, Now, Next, Blocked
2. REQUIREMENTS.md → Phase plan, FR/NFR priorities
3. ARCHITECTURE.md → Implementation status (✅ vs 📋)
4. CHECKPOINT.md → Last session progress (if exists)
```

**Output:** Brief status summary (3-5 lines max)

---

### Step 2: Determine Work Scope

**If user specified FRs/NFRs:**
- Validate they're in current or next phase (or get explicit approval)
- Group by dependency (e.g., FR-001 before FR-020 if tenant isolation needed)
- Flag any blocked items

**If user said "continue" or "what's next":**
- Pick next items from "Next" in STATUS.md
- Batch related FRs (max 3-5 per session)
- Respect dependencies

**Phase Rules (from REQUIREMENTS.md § Phasing):**
| Phase | FRs/NFRs | Can Start When |
|-------|----------|----------------|
| 1. Core RAG | FR-010–025 | Always |
| 2. Citations UI | FR-030–032 | Phase 1 P0s complete |
| 3. Multi-tenancy | FR-001–004, FR-020 | Phase 2 complete |
| 4. Provider Abstraction | NFR-032–036 | Phase 3 complete |
| 5. Auth | FR-050–053 | Phase 4 complete |
| 6. Audit | FR-040–043 | Phase 5 complete |
| 7. Polish | FR-011, FR-014, FR-015, FR-022, FR-033 | Phase 6 complete |
| 8. NFRs | NFR-001–022, NFR-040–046 | Phase 7 complete |

**Priority Rules:**
- P0/P1 items first (see REQUIREMENTS.md acceptance criteria)
- Items with "⬜ TODO" status before "📋 Planned"
- Dependencies must be resolved first

---

### Step 3: Create Session Plan

Present a numbered plan:

```markdown
## Session Plan

**Current Phase:** [N] - [Name] (from STATUS.md)
**FRs/NFRs:** [list]
**Estimated Tasks:** [N batches]

### Batch 1: [Title] (FR-XXX)
1. /wsresearch FR-XXX → Understand patterns
2. /wsstart → Plan + implement (TDD)
3. /wsverify → lint + types + tests
4. /wsskeptic → Adversarial review

### Batch 2: [Title] (FR-YYY)
... same pattern ...

**After all batches:**
- /wsstatus → Update STATUS.md
- /wscommit → Commit with (FR-XXX, FR-YYY) references

Approve this plan? [Y/n]
```

---

### Step 4: Execute (After Approval)

For each FR/NFR in the batch:

```
1. /wsresearch [FR-NNN]  → Understand before coding     ⛔ NON-NEGOTIABLE
2. /wsstart [FR-NNN]     → Plan + implement (TDD enforced per CLAUDE.md)
3. /wsverify             → Quality gates (ruff, mypy, pytest)
4. /wsskeptic            → Adversarial review           ⛔ NON-NEGOTIABLE
5. Log to CHECKPOINT.md  → Track progress
```

**⛔ NON-NEGOTIABLE STEPS:**
- `/wsresearch` — MUST run before any implementation. No "I already know the patterns."
- `/wsskeptic` — MUST run before any commit. No "it's a small change."

These steps cannot be skipped even under time pressure. They are in CLAUDE.md "Red Flags".

**Between FRs:**
- Commit working code (don't wait for all)
- Update CHECKPOINT.md
- Check if blocked → stop and report

**After all FRs:**
- /wsstatus → Update STATUS.md
- /wscommit → Push all changes
- Summary of what shipped

---

### Step 5: Handle Edge Cases

**If FR is blocked:**
```
⚠️ FR-XXX blocked: [reason]
Options:
1. Skip and continue with FR-YYY
2. Try to unblock (describe approach)
3. Stop session and report
```

**If out-of-phase FR requested:**
```
⚠️ FR-XXX is in Phase N, but we're in Phase M.
Current phase incomplete items: [list from STATUS.md]

Options:
1. Complete current phase first (recommended)
2. Override and work on FR-XXX anyway
3. Add to "Next" in STATUS.md for later
```

**If dependency missing:**
```
⚠️ FR-XXX depends on FR-YYY which isn't done.
Adding FR-YYY to batch first.

Updated plan: FR-YYY → FR-XXX
Approve? [Y/n]
```

---

## CHECKPOINT.md Format

After each FR, log:

```markdown
## [YYYY-MM-DD HH:MM] FR-NNN: [Title]

**Status:** ✅ Complete | ⚠️ Partial | ❌ Blocked
**Files changed:**
- apps/api/app/services/xxx.py (new)
- apps/api/app/routers/xxx.py (modified)
- tests/test_xxx.py (new)

**Verification:**
- [ ] `ruff check apps/` — passed
- [ ] `mypy apps/api/app --strict` — passed
- [ ] `pytest tests/ -v` — [X/Y passed]
- [ ] `pytest evals/ -v` — [X/Y passed]
- [ ] LLM telemetry verified (if applicable)

**Commits:**
- `[hash]` [commit message]

**Notes:** [Any decisions, issues, or context for next session]

---
```

---

## Quick Commands

| User Says | Orchestrator Does |
|-----------|-------------------|
| "Work on Phase 7" | Batch all items from FR-011, FR-014, FR-015, FR-022, FR-033 |
| "FR-011 and FR-014" | Batch those two, validate same phase |
| "Continue" | Check CHECKPOINT.md, resume from last point |
| "What's blocking?" | Show Blocked items from STATUS.md |
| "Skip to Phase 8" | Warn about incomplete items, require confirmation |
| "Just NFR-045" | Single item mode, full workflow |
| "What's next?" | Read STATUS.md "Next" section, suggest batch |

---

## Invariants (from CLAUDE.md)

### ⛔ NON-NEGOTIABLE (Cannot Skip)
1. **`/wsresearch` before implementation** — Gather context first. Always.
2. **`/wsskeptic` before commit** — Adversarial review. Always.

### Required (Should Not Skip)
3. **TDD enforced** — Tests before code per CLAUDE.md
4. **Verify after each FR** — Don't batch verifications
5. **Log to CHECKPOINT.md** — Every FR gets an entry
6. **LLM telemetry** — If touching LLM code, verify NFR-030 per CLAUDE.md
7. **Update STATUS.md** — Session ends with accurate state
8. **Commit with FR reference** — `feat(scope): description (FR-NNN)`
9. **Documentation sync** — Update ARCHITECTURE.md, REQUIREMENTS.md if patterns/scope change
