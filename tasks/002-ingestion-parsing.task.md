# Task 002 - Ingestion, Parsing, and Indexing (Tier 0/1)

## Scope
- Define the ingestion flow for PDF upload, immutable raw storage, and async parsing.
- Specify Tier 0 parsing (per-page extraction, deterministic chunking, page fidelity).
- Specify Tier 1 parsing triggers and outputs (layout/table-aware text).
- Define chunk lineage fields: doc_id, doc_sha256, page_num, chunk_index, char_start/end.
- Persist chunk records and metadata for downstream indexing (no embeddings or index writes).

## Acceptance tests
- Ingestion flow document shows upload -> storage -> parse -> chunk -> persist metadata steps.
- Tier 0 parsing produces per-page chunks with deterministic sizing and lineage metadata.
- Tier 1 parsing trigger criteria are explicitly listed and Tier 2 remains disabled in demo.

## Files likely touched
- `apps/api/*`
- `apps/ingestion/*`
- `packages/shared/schemas/*`
- `docs/ARCHITECTURE.md`
