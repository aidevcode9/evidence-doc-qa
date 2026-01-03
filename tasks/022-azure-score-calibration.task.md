# Task 022 — Calibrate Azure score handling (stop treating @search.score as RRF)

## Summary
In Azure mode, `@search.score` is currently normalized using a local RRF scaling constant (`max_rrf = 2/(RRF_K+1)`), and stored as `rrf_score`. This is conceptually incorrect and can distort confidence gating.

**Current code**
- `apps/api/app/retrieval.py`: 
  - `max_rrf = 2/(RRF_K+1)` then `normalized_score = raw_score / max_rrf`
  - `reranker_score = doc.get("@search.rerankerScore", 0.0)` (good)

## Goals
- Preserve raw Azure scores:
  - `azure_search_score` = `@search.score`
  - `azure_reranker_score` = `@search.rerankerScore`
- Make gating operate on the correct signals:
  - confidence gate should use a calibrated confidence function per mode
- Avoid naming Azure merged score as `rrf_score`

## Scope
1. Change result schema (backend internal) to store:
   - `retrieval_score` (generic)
   - `azure_search_score` (raw)
   - `azure_reranker_score` (raw)
   - `rrf_score` only for local fused mode
2. Update confidence gate in `main.py`:
   - If Azure mode:
     - gate on `azure_search_score` and/or `azure_reranker_score` using calibrated thresholds
   - If local mode:
     - gate on `rrf_score` as today
3. Update UI/debug:
   - Display both scores distinctly in Evidence panel if present.
4. Add calibration notes:
   - store `confidence_version` and threshold values in config

## Files to change
- `apps/api/app/retrieval.py`
- `apps/api/app/main.py`
- `apps/api/app/schemas.py` (if API response includes these fields)
- UI: `EvidencePanel.tsx` (labeling)

## Acceptance criteria
- Azure mode does not compute “RRF-normalized score” from `@search.score`.
- Telemetry can distinguish local vs Azure score distributions.
- Confidence gate behaves consistently across modes for a small eval set.

## Tests
- Unit test: ensure Azure results include raw scores and local results include rrf_score.
- Smoke test: Azure search returns non-zero `azure_search_score`, and gating doesn’t crash.

## Telemetry additions
- `trace_metadata.mode: "azure" | "local"`
- `trace_metadata.azure_search_score_top`
- `trace_metadata.azure_reranker_score_top`
- `trace_metadata.confidence_version`
