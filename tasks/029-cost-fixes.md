# Task 029 - Telemetry Cost Tracking

## Scope
- Add pricing configuration for LLM token cost (input/output) per model.
- Capture usage from verifier responses (prompt/completion tokens).
- Capture usage from embeddings responses (prompt tokens).
- Aggregate usage per request and compute `cost_est`.
- Store real `tokens_in`, `tokens_out`, and `cost_est` in telemetry.
- Add per-stage usage/cost breakdown in `trace_metadata`.
- Add fallback behavior when usage is missing (flag in `trace_metadata`).

## Acceptance tests
- Telemetry rows show non-zero `tokens_in`, `tokens_out`, and `cost_est` for LLM/embeddings-backed requests.
- `trace_metadata.cost_breakdown` includes verifier and embeddings usage with costs.
- If usage is missing from a provider response, telemetry still populates estimates and sets `trace_metadata.usage_fallback=true`.
- Metrics endpoint reflects average cost per query based on stored `cost_est`.

## Files likely touched
- `apps/api/app/verification.py`
- `apps/api/app/embeddings.py`
- `apps/api/app/main.py`
- `apps/api/app/telemetry.py`
- `apps/api/app/config.py`
- `docs/ENVIRONMENT_REFERENCE.md`
