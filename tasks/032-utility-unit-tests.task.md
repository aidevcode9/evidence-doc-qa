# Task 032 - Utility Unit Tests

## Scope
- Create a `tests/unit` directory distinct from the existing `tests/debug` or `evals/`.
- Implement `pytest` based unit tests for deterministic utility functions:
    - Cost estimation logic (`_estimate_cost`).
    - Hashing and ID generation helpers.
    - Text chunking/splitting logic (if present locally in `ingestion.py`).
    - Metric window aggregation logic (`telemetry.py`).
- Ensure these tests run fast (no network calls, no LLM cost).

## Acceptance tests
- `pytest tests/unit` command runs successfully.
- Code coverage for `telemetry.py`, `ingestion.py` (partial), and other utility modules is > 80%.
- CI pipeline (if present) includes this unit test step.

## Files likely touched
- `tests/unit/*` (NEW)
- `apps/api/app/telemetry.py`
- `apps/api/app/ingestion.py`
