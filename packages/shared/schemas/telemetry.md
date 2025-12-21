# Telemetry and Metrics Schemas - DocQ&A v3.1 Demo

This document defines telemetry persistence and metrics aggregation outputs.

## Telemetry Record (per request)
- `request_id`: string (UUID), required
- `docs_snapshot_id`: string, required
- `prompt_version`: string, required
- `retrieval_version`: string, required
- `model_id`: string, required
- `parser_mode`: string enum (`tier0`, `tier1`, `tier2`), required
- `timestamp_utc`: string (ISO 8601), required
- `latency_ms`: integer, required
- `tokens_in`: integer, required
- `tokens_out`: integer, required
- `cost_est`: number, required
- `cache_hit`: boolean, required
- `refusal_code`: Refusal Code enum, optional
- `failure_label`: string, optional

## Metrics Endpoint Output
- `window_start_utc`: string (ISO 8601), required
- `window_end_utc`: string (ISO 8601), required
- `p50_latency_ms`: integer, required
- `p95_latency_ms`: integer, required
- `avg_cost_per_query`: number, required
- `refusals_by_code`: object, required (map of refusal_code -> count)
- `cache_hit_rate`: number (0..1), required

## Metrics Endpoint Semantics (demo)
- Route: `GET /v1/metrics`
- Auth: static admin token header
- Window: last 24h OR last 500 requests

## PII-Safe Logging
- Redact PII fields prior to persistence (emails, phone numbers, SSNs).
- Store only redacted request/response payloads in telemetry.
- Never log raw document text.
- Never log full user question (truncate to 200 chars or store a hash).
