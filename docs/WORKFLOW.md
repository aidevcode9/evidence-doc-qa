# Evidence-Bound Development Workflow

> Agent-driven development with enforced quality gates, adversarial reviews, and telemetry as a first-class concern.

---

## How to Start Working

Say **"next task"** — Claude handles the rest:

```
You:    "next task"
Claude: "Next task: [ARCH-2] Decompose execute_ask(). Confirm, or pick another?"
You:    "confirm"
Claude: → pulls main → creates branch → spawns researcher → presents brief
You:    "looks good"
Claude: → spawns coder → TDD implementation → verifier → skeptic → PR
```

That's it. One prompt to start, one confirmation to approve the approach. Claude orchestrates all 6 subagents automatically.

---

## Architecture: Agents + Hooks + Commands

### Subagents (`.claude/agents/`) — Isolated, Model-Appropriate

```
Main Conversation (opus) — talks to you, picks tasks, spawns agents
  │
  ├── researcher (sonnet) ← "what should we build?"
  ├── coder (opus)        ← "build it with TDD"
  ├── eval-writer (sonnet) ← "write the eval first" (LLM/retrieval only)
  ├── verifier (haiku)    ← "did it pass?"
  ├── skeptic (sonnet)    ← "is it safe?"
  └── doc-sync (haiku)    ← "are docs current?"
```

| Agent | Model | What it does | When |
|-------|-------|-------------|------|
| **researcher** | sonnet | Gathers context, patterns, risks. Returns structured brief. | Before any FR/NFR (NON-NEGOTIABLE) |
| **coder** | opus | Implements with TDD. Follows project invariants. Returns files + tests. | After research brief approved |
| **eval-writer** | sonnet | Writes failing eval before AI behavior changes. | When touching retrieval/evidence/policy/verification |
| **verifier** | haiku | Runs lint + types + tests + telemetry grep. Returns pass/fail table. | After implementation |
| **skeptic** | sonnet | Adversarial review: AI failures, data leakage, security, telemetry audit. | Before PR merge (NON-NEGOTIABLE) |
| **doc-sync** | haiku | Checks if docs are stale after code changes. | Before PR, parallel with skeptic |

### Hooks (`.claude/settings.json`) — Automatic, Can't Skip

| Hook | Trigger | Blocks? |
|------|---------|---------|
| **Branch protection** | `git push` to main | Yes — use feature branches |
| **Pre-commit gates** | `git commit` | Yes — ruff + mypy + pytest must pass |
| **Pre-push adversarial scan** | `git push` | Yes — agent scans diff for security issues |
| **DB safety** | `DELETE`, `alembic` | Yes — requires explicit approval |
| **Post-edit lint** | Edit/Write `.py` | No — informational |

### Commands (`.claude/commands/`) — Lightweight Utilities

| Command | What it does |
|---------|-------------|
| `/wsstatus` | Quick STATUS.md update |
| `/wsmistake` | Log a mistake to CLAUDE.md |

---

## The Flow

```
HOW A FEATURE GETS BUILT
─────────────────────────
1. git checkout -b feat/TASK-ID-description

   ┌─────────────────────────────────┐
   │ researcher (sonnet)             │ ← returns structured brief
   │  • reads REQUIREMENTS.md        │
   │  • finds patterns in codebase   │
   │  • identifies risks + invariants│
   └─────────────────────────────────┘
                 │
   You approve the approach
                 │
   ┌──────────────────────────────────────────┐
   │ coder (opus)                             │
   │  • receives research brief               │
   │  • writes test first (RED)               │
   │  • implements (GREEN)                    │
   │  • spawns eval-writer if LLM code        │
   │  • returns files changed + test results  │
   └──────────────────────────────────────────┘
                 │
   ┌─────────────────────────────────┐
   │ verifier (haiku)                │ ← lint + types + tests + telemetry check
   └─────────────────────────────────┘
                 │
   ┌──────────────────────────────────────────┐
   │ skeptic (sonnet)  ← adversarial review   │
   │ doc-sync (haiku)  ← doc drift check      │  IN PARALLEL
   └──────────────────────────────────────────┘
                 │
   git commit    ← [hook: ruff + mypy + pytest BLOCK on fail]
   git push      ← [hook: blocks main + adversarial scan]
   gh pr create  ← PR to main
   merge         ← auto-deploys API + Web + Docs
```

---

## Git Flow

**`main` is protected. All changes go through feature branches + PRs.**

```
main (production — no direct push)
  ↑
  PR required, skeptic review must pass
  │
feat/TASK-ID-description (where work happens)
  ↑
  git checkout -b feat/ARCH-2-decompose-ask
```

**Branch naming:** `feat/TASK-ID-desc`, `fix/TASK-ID-desc`, `chore/desc`

**Auto-deploy on merge to main:**
- API → Azure Container Apps (via GitHub Actions)
- Frontend → Vercel
- Docs → knowledge.bound.legal (Nextra on Vercel)

---

## Telemetry Invariant

Telemetry is a first-class concern, enforced at 3 levels:

| Level | Agent/Hook | What it checks |
|-------|-----------|----------------|
| **Implementation** | `coder` | Every LLM call uses `traced_llm_call()`. Every request calls `record_telemetry()`. All `@_observe` have `capture_input=False`. |
| **Verification** | `verifier` | Greps for raw `httpx.post`/`httpx.get` calls that bypass telemetry wrapper. |
| **Review** | `skeptic` | Reviews for missing `@_observe` decorators, missing `record_telemetry()`, PII in logs. |

```
Every LLM call    → traced_llm_call() wrapper
Every request     → record_telemetry() (including refusals)
Every @observe    → capture_input=False, capture_output=False (PII safety)
```

---

## Published Documentation — knowledge.bound.legal

Source of truth: `docs/*.md` in the repo. Published via Nextra on Vercel.

```
docs/*.md (edit these)
    ↓ sync-docs.sh (copies on build)
apps/docs/content/*.mdx (gitignored, generated)
    ↓ Nextra v4
knowledge.bound.legal (static site)
```

**To update:** Edit `docs/`, commit, push. Auto-deploys.
**Local preview:** `cd apps/docs && npm run dev`

---

## Key Files

| File | Purpose |
|------|---------|
| `STATUS.md` | Current phase, Now/Next/Done |
| `REQUIREMENTS.md` | FRs/NFRs with acceptance criteria |
| `CLAUDE.md` | AI assistant rules + auto-trigger protocol |
| `CHECKPOINT.md` | Autonomous work log |
| `.claude/agents/` | 6 subagent definitions |
| `.claude/commands/` | 2 utility commands |
| `.claude/settings.json` | 5 enforced hooks |

---

## Autonomous Work Mode

When user says "work on this, I'll check back":

1. Read STATUS.md → identify tasks
2. For each task: researcher → coder → verifier → skeptic → doc-sync
3. Log to CHECKPOINT.md after each task
4. **Stop conditions:**
   - Test failures after 2 fix attempts
   - Need to modify `policy.py` or `evidence.py`
   - Architecture decision needed
   - Ambiguous requirement

---

## NON-NEGOTIABLE Rules

| Rule | Enforcement |
|------|-------------|
| `researcher` before implementation | CLAUDE.md auto-trigger |
| `skeptic` before PR merge | CLAUDE.md auto-trigger |
| Tests pass before commit | Pre-commit hook (blocks) |
| No direct push to main | Branch protection hook (blocks) |
| Telemetry on all LLM calls | verifier grep + skeptic audit |
| No PII in logs | skeptic audit |
