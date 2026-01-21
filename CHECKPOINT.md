# CHECKPOINT.md — Autonomous Work Log

> Auto-generated during autonomous work sessions. Review after each session.

---

## Session: 2026-01-21

### Pre-Flight Check
- [ ] Read STATUS.md — identified tasks
- [ ] Read REQUIREMENTS.md — noted acceptance criteria
- [ ] Read ARCHITECTURE.md — noted relevant interfaces
- [ ] Identified test files to update

### Tasks Attempted

<!-- Entries added automatically during autonomous work -->

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
