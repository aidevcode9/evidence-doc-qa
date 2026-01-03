# Task 022 - Calibrate Azure score handling (stop treating @search.score as RRF)

## Summary
In Azure mode, `@search.score` is currently normalized with a local RRF scaling constant. This is conceptually wrong because Azure scores are not guaranteed to be RRF-equivalent. We need to preserve raw Azure scores and gate on calibrated thresholds per mode.

## Goals
- Preserve raw Azure scores:
  - `azure_search_score` = `@search.score`
  - `azure_reranker_score` = `@search.rerankerScore`
- Use mode-specific confidence gating:
  - Azure mode gates on calibrated Azure thresholds.
  - Local mode continues to gate on local `rrf_score`.
- Stop labeling Azure merged scores as `rrf_score`.

## Scope
1. Retrieval results (backend internal)
   - Azure mode includes:
     - `azure_search_score` (raw)
     - `azure_reranker_score` (raw, if available)
   - Local mode includes:
     - `rrf_score` only for local fused results.
   - Optional: keep a generic `retrieval_score` for UI display, but it must reflect the active mode.
2. Confidence gate
   - If Azure mode and `azure_reranker_score` is present, gate on `azure_reranker_score` first.
   - If reranker score is missing, gate on `azure_search_score`.
   - Add explicit env-configured thresholds:
     - `DOCQA_AZURE_SEARCH_SCORE_MIN`
     - `DOCQA_AZURE_RERANK_MIN`
   - Store a `confidence_version` string with threshold values (for telemetry and audit).
3. UI/debug display
   - Label Azure scores clearly (e.g., "Azure Hybrid Score" and "Semantic Reranker").
   - Keep these in the debug section only if we do not want them in the default UI.
4. Telemetry
   - Add `trace_metadata.lexical_mode: "azure_hybrid" | "local_bm25"` (or equivalent).
   - Add `trace_metadata.azure_search_score_top` and `trace_metadata.azure_reranker_score_top`.
   - Log `trace_metadata.confidence_version`.

## Files to change
- `apps/api/app/retrieval.py`
- `apps/api/app/main.py`
- `apps/api/app/schemas.py` (only if API response shape changes)
- UI: `apps/web/components/EvidencePanel.tsx` (score labels)

## Acceptance criteria
- Azure mode does not compute any RRF-normalized score from `@search.score`.
- Azure gating uses the calibrated thresholds in env vars.
- Local gating still uses `rrf_score` and behaves unchanged.
- API responses remain backward-compatible unless explicitly updated in docs.
- Telemetry can distinguish local vs Azure score distributions.

## Tests
- Unit: Azure results expose raw scores; local results include `rrf_score`.
- Smoke: Azure search returns non-zero `azure_search_score` and gating does not crash.
