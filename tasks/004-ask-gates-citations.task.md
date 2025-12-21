# Task 004 - Ask Endpoint, Policy Gates, and Citation Enforcement

## Scope
- Define `/ask` request flow with pre-LLM policy gates (confidence, injection, parse integrity, PII-safe logging).
- Specify refusal code behavior and mapping to gate failures.
- Define citation validation rules (must resolve to retrieved evidence, include doc/page/snippet).
- Define response schema for answers and refusals, including `request_id`.

## Acceptance tests
- If retrieval confidence is below threshold, `/ask` returns refusal with `LOW_RETRIEVAL_CONFIDENCE`.
- If citations are missing or invalid, `/ask` returns refusal with `NO_SUPPORTING_EVIDENCE`.
- Valid evidence produces `answer_text` with `citations[]` and all required fields.
- Missing citations logs `failure_label=NO_CITATIONS` while returning `NO_SUPPORTING_EVIDENCE`.

## Files likely touched
- `apps/api/*`
- `packages/shared/schemas/*`
- `docs/ARCHITECTURE.md`
