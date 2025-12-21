# Task 001 - Versioning, IDs, and Shared Schemas

## Scope
- Define core IDs and version snapshot fields: `request_id`, `docs_snapshot_id`, `prompt_version`, `retrieval_version`, `model_id`, `parser_mode`.
- Specify request/response schemas for `/ask`, including `answer_text`, `citations[]`, `refusal_code`, and version snapshot fields.
- Define telemetry record shape (latency, tokens, cost_est, cache_hit, refusal_code, failure_label).
- Document how version snapshots are created and persisted per request.

## Acceptance tests
- A schema document exists that enumerates all required request/response fields and refusal codes, aligned with PRD/ARCH.
- A sample request/response pair includes `request_id` and full version snapshot fields.
- Telemetry schema includes every required field listed in PRD/ARCH with types and required/optional status.

## Files likely touched
- `packages/shared/schemas/*`
- `docs/ARCHITECTURE.md`
- `docs/PRD.md`
- `docs/PROJECT_PLAN_CODEX.md`
