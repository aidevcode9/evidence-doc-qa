# Task 003 - Hybrid Retrieval, RRF, and Confidence Scoring

## Scope
- Define hybrid retrieval flow (vector + BM25) and RRF fusion behavior.
- Specify optional reranker contract and how it integrates with fused results.
- Define retrieval confidence scoring and thresholds for refusal.
- Define retrieval debug fields required for evals (vector score, bm25 score, fused rank, rerank score).

## Acceptance tests
- Retrieval spec shows vector K + bm25 K + RRF fusion + optional rerank.
- Confidence scoring definition is explicit and maps to refusal behavior.
- Debug fields are emitted for each retrieved chunk to support evals.

## Files likely touched
- `apps/api/*`
- `packages/shared/schemas/*`
- `docs/ARCHITECTURE.md`
