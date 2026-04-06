---
name: doc-sync
description: Check if documentation is stale after code changes. Reads git diff and compares against docs. Returns list of stale docs with specific sections to update.
model: haiku
tools: Read, Glob, Grep, Bash
---

# Doc Sync Agent

Check if documentation matches current code after changes.

## Protocol

1. Run `git diff HEAD~1 --stat` to see what files changed
2. For each changed file, check if related docs are stale:

| Changed File Pattern | Check These Docs |
|---------------------|------------------|
| `routers/*.py` | `docs/ARCHITECTURE_DIAGRAM.md` (system overview mermaid) |
| `db.py` or `migrations/` | `docs/architecture/data-model.md` |
| `config.py` | `.env.example`, `docs/GETTING_STARTED.md` |
| `retrieval.py`, `evidence.py`, `policy.py` | `docs/TECHNICAL_DEEP_DIVE.md` |
| `llm/`, `parsers/`, `search/`, `embedding/` | `docs/LLM_PROVIDERS.md`, `docs/architecture/interfaces.md` |
| `otel.py`, `telemetry.py` | `docs/TECHNICAL_DEEP_DIVE.md` (observability section) |
| `Dockerfile`, deploy workflows | `docs/OPERATIONS.md` |
| Any new test files | `README.md` (test count) |

3. Read the relevant doc sections and compare against actual code

## Output Format

```
## Doc Sync Check

**Files changed:** [count]

| Doc | Status | Section | Issue |
|-----|--------|---------|-------|
| path | CURRENT / STALE / DEAD LINK | section name | what's wrong |

**Action needed:** [count] docs to update, or "All docs current"
```
