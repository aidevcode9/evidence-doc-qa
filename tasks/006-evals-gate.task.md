# Task 006 - Evals Harness and Release Gate

## Scope
- Define golden eval suite structure, data format, and storage location.
- Specify eval runner CLI usage and JSON artifact format.
- Define CI gate thresholds and promotion rules for prompt/retrieval/model changes.
- Define test cases for refusal correctness and citation validation.
- Publish eval schema contract in `packages/shared/schemas/evals.md`.

## Acceptance tests
- `python -m evals.run --suite golden` produces a JSON artifact with pass/fail and metrics.
- CI fails when eval thresholds are not met and blocks version promotion.
- Golden set includes lexical-heavy questions and injection attempts.

## Files likely touched
- `docs/EVALS_V1_REQUIREMENTS.md`
- `docs/PROJECT_PLAN_CODEX.md`
- `.github/workflows/*`
