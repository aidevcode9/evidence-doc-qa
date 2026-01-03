# Task 020 — Local lexical scoring: implement BM25 (or explicitly label overlap fallback)

## Summary
Local retrieval currently sets `bm25_score` using a token-overlap ratio, not BM25. This is fine for a demo, but misleading in logs/metrics/UI and makes hybrid/RRF behavior diverge from Azure mode.

**Current code**
- `apps/api/app/retrieval.py`: `rec["bm25_score"] = _overlap_score(...)` (approx line ~40)

## Decision
Implement **true BM25** for local mode **OR** relabel local lexical as `overlap_score` everywhere (UI/metrics/debug).

**Recommendation (production-ready):** implement BM25 in local mode and keep overlap as a fallback for very small corpora or as a feature for fast triage.

## Scope
### A) Implement BM25 in local mode
1. Add BM25 scoring functions:
   - `bm25_score(query_tokens, doc_tokens, df, N, dl, avgdl, k1=1.2, b=0.75)`
   - `idf(term) = log((N - df + 0.5) / (df + 0.5) + 1)`
2. Build per-snapshot corpus stats cache:
   - `N` = #chunks
   - `avgdl` = average chunk length in tokens
   - `df[term]` = document frequency across chunks
3. Compute per-chunk BM25 score at query-time:
   - Tokenize chunk text once for scoring (consider caching tokenized chunks in memory for small snapshots).
4. Keep `overlap_score` available but do not call it “BM25”.

### B) Rename/label if you choose not to implement BM25
1. Rename `bm25_score` → `overlap_score` in:
   - `retrieval.py` result objects
   - any downstream code/telemetry/UI that refers to BM25
2. Ensure UI labels reflect “Lexical overlap” not “BM25”.

## Files to change
- `apps/api/app/retrieval.py`
- (optional) `apps/api/app/config.py` (BM25 params, cache limits)
- UI: `EvidencePanel.tsx` / `ChatInterface.tsx` (labels) if exposed

## Acceptance criteria
- Local mode lexical score is **true BM25** OR clearly labeled as overlap (no “BM25” mislabel).
- Hybrid local retrieval still returns `rrf_score` and ranks improve on exact identifiers vs overlap baseline.
- Telemetry/debug includes lexical score name and top values for operators.

## Tests
- Unit tests:
  - BM25 IDF monotonicity: rare terms score higher than common terms
  - Query with exact ID/token ranks correct chunk above semantically similar chunks
- Regression:
  - Compare overlap vs BM25 on a mini golden set (IDs, dates, negation tokens)

## Telemetry additions
- Add to `trace_metadata`:
  - `lexical_mode: "bm25" | "overlap"`
  - `top_lexical_score`, `top_vector_score`, `rrf_margin`
  - corpus stats snapshot: `bm25_N`, `bm25_avgdl` (optional, not per-request if large)
