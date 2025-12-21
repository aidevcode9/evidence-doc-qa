# Task 005 - Telemetry, Metrics, and PII-Safe Logging

## Scope
- Define telemetry persistence for every request (answer or refusal).
- Specify latency, token, and cost tracking fields and calculation rules.
- Define metrics endpoint output (p50/p95, cost/query, refusal rates).
- Define PII redaction rules for logs and stored artifacts.

## Acceptance tests
- Every request yields a telemetry record with required fields and version snapshot.
- Metrics endpoint returns latency and cost aggregates for a defined time window.
- Log redaction rules are documented and applied to all request/response logs.

## Files likely touched
- `apps/api/*`
- `packages/shared/schemas/*`
- `docs/ARCHITECTURE.md`
