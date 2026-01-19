---
description: Commit, push, and create PR
---

Commit the current changes, push, and create a PR.

Steps:
1. Run `git status` and `git diff --stat` to understand what changed
2. Run tests first: `pytest tests/ -v --tb=short`
3. If tests fail, fix them before committing
4. If tests pass, write a commit message:
   - Format: `type(scope): description`
   - Types: feat, fix, test, docs, refactor, chore
   - Example: `feat(retrieval): implement RRF fusion for hybrid search`
5. Commit: `git add -A && git commit -m "message"`
6. Push: `git push -u origin HEAD`
7. Create PR with summary of what changed and why

If this is a work-in-progress, ask me if I want to commit anyway or keep working.
