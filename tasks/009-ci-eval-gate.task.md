# Task 009: CI/CD Integration (Evaluation Gate)

## Description
Integrate the evaluation suite (`evals/run.py`) into the GitHub Actions workflow to ensure that any changes to the RAG engine, prompts, or retrieval logic pass the "Golden Set" before being merged.

## Objectives
- [ ] Update `.github/workflows/ci.yml` to include an evaluation step.
- [ ] Ensure the evaluation step runs after successful API build and unit tests.
- [ ] Configure environment variables needed for evals in CI (mocking or using a dedicated test resource).
- [ ] Set failure threshold for the CI gate based on `evals/run.py` results.

## Acceptance Criteria
- [ ] PRs cannot be merged if the `evals/run.py --suite golden` command fails.
- [ ] CI logs clearly show evaluation metrics (citation coverage, refusal correctness, etc.).
