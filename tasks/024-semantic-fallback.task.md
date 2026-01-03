# Task 024 — Add semantic ranker fallback when tier/feature not supported

## Summary
Azure queries currently set semantic options unconditionally:
- `queryType="semantic"`
- `semanticConfiguration="default"`
- `captions="extractive"` / highlights

If the service tier/index configuration does not support semantic search, Azure can return 4xx errors and the whole request fails (user-visible outage).

**Current code**
- `apps/api/app/retrieval.py`: semantic fields set in `_azure_search()` payload (approx line ~84)

## Goals
- Never hard-fail solely because semantic features are unavailable.
- If semantic query fails, automatically retry as non-semantic hybrid:
  - keep `"search"` + `"vectorQueries"`
  - remove semantic fields (`queryType`, `semanticConfiguration`, `captions`, `answers`)

## Scope
1. Wrap `_call_azure_search(payload)` with:
   - try semantic payload first
   - on HTTP 400/403 and JSON body `error.code` or `details[].code` that indicates semantic not supported (ex: `SemanticQueriesNotAvailable`, `FeatureNotSupportedInService`):
     - log a warning (no PII)
     - retry once with semantic fields removed
   - ensure there is at most one fallback retry per request
2. Add config flag:
   - `DOCQA_AZURE_SEMANTIC_ENABLED` default true
   - If false, never request semantic features
3. Ensure results parsing handles missing `@search.rerankerScore` and captions.

## Files to change
- `apps/api/app/retrieval.py`
- `apps/api/app/config.py` (new flag)

## Acceptance criteria
- When semantic ranker is unsupported, ask requests still succeed using non-semantic hybrid.
- Telemetry records `semantic_requested`, `semantic_used`, and `semantic_fallback_reason`.
- UI handles absent highlights/reranker scores gracefully.

## Tests
- Unit test: simulate HTTPError with JSON `error.code` or `details[].code` indicating semantic unsupported → triggers retry.
- Integration (manual): toggle `DOCQA_AZURE_SEMANTIC_ENABLED=0` and ensure normal responses.

## Telemetry additions
- `trace_metadata.semantic_requested`
- `trace_metadata.semantic_used`
- `trace_metadata.semantic_fallback_reason`
