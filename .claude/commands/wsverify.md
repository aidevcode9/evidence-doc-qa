---
description: Verify implementation (lint, types, tests)
---

Verify the current implementation works correctly.

Steps:
1. Run linter: `ruff check apps/`
2. Run type checker: `mypy apps/api/app --strict`
3. Run tests: `pytest tests/ -v --tb=short`
4. If there are failures:
   - Analyze the error
   - Suggest a fix
   - Ask if I want you to fix it
5. If all pass:
   - Report summary
   - Update project documenation as necessary
   - Confirm ready to commit

For UI changes, also describe how to manually verify in the browser.
