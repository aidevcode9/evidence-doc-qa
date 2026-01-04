# Task 026 - OpenTelemetry tracing for FastAPI (Application Insights)

## Summary
Add OpenTelemetry tracing to the FastAPI backend so we get request/response spans, dependency calls, and richer diagnostics in Azure Application Insights (or any OTLP-compatible backend).

## Goals
- Capture HTTP server spans for `/v1/ask`, `/v1/docs/upload`, `/v1/metrics`.
- Add custom spans for retrieval, verification, and evidence gating.
- Export traces to Azure Application Insights using the connection string.

## Scope
1. Dependencies
   - Add `opentelemetry-api`, `opentelemetry-sdk`
   - Add `opentelemetry-instrumentation-fastapi`
   - Add `opentelemetry-instrumentation-urllib`
   - Add `opentelemetry-exporter-azuremonitor`
2. Configuration
   - New env var `APPLICATIONINSIGHTS_CONNECTION_STRING` (already set by Azure when Insights enabled).
   - Optional `DOCQA_OTEL_ENABLED=1` to toggle instrumentation.
3. App wiring
   - Initialize tracer provider on startup.
   - Instrument FastAPI and urllib.
4. Span coverage
   - Create spans for: retrieval, verification call, evidence grading, refusal path.
   - Attach key attributes (request_id, docs_snapshot_id, retrieval_mode, evidence_grade).

## Files to change
- `apps/api/app/main.py` (init + spans)
- `apps/api/app/retrieval.py` (span around Azure/local retrieval)
- `apps/api/app/verification.py` (span around verifier call)
- `apps/api/app/config.py` (otel flag)
- `requirements.txt`
- `docs/ENVIRONMENT_REFERENCE.md`

## Acceptance criteria
- Traces appear in Application Insights within 5 minutes.
- `/v1/ask` shows nested spans for retrieval and verification.
- Disabling `DOCQA_OTEL_ENABLED` bypasses instrumentation without errors.

## Tests
- Manual: enable Insights, hit `/v1/ask`, confirm traces and child spans in the portal.
