# Task 009: CI/CD Integration (Evaluation Gate)

## Description
Integrate the evaluation suite (`evals/run.py`) into the GitHub Actions workflow to ensure that any changes to the RAG engine, prompts, or retrieval logic pass the "Golden Set" before being merged.

## CI Flow
1.  **Dependency Setup:** Install all Python requirements using `pip`.
2.  **Mock Environment:** Configure the API to use a local SQLite database (`ci_test.db`) and local hash-based embeddings.
3.  **Data Seeding:** Run `evals/seed.py` to ingest `ARCHITECTURE.md` into the mock database as a standard snapshot.
4.  **API Startup:** Spin up the FastAPI server in the background.
5.  **Execution:** Run `evals/run.py` against the mock API using the "Golden Set" of questions.
6.  **Gate Check:** The workflow fails if:
    - Citation Coverage is < 90%
    - Refusal Correctness is < 90%

## Objectives
- [x] Create `evals/seed.py` for automated test data ingestion.
- [x] Update `evals/run.py` to support thresholds and exit codes.
- [x] Configure `.github/workflows/ci.yml` with the full automation flow.
- [ ] Verify local execution against real Azure resources.

## Acceptance Criteria
- [x] PRs cannot be merged if the `evals/run.py --suite golden` command fails.
- [x] CI logs clearly show evaluation metrics (citation coverage, refusal correctness, etc.).
