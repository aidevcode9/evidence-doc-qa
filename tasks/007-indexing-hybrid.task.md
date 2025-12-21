# Task 007 - Indexing to Hybrid Search

## Scope
- Define search backend abstraction for lexical, vector, and hybrid queries.
- Specify embeddings generation and caching rules per chunk.
- Define AI Search schema/index creation and write path for chunks + vectors.
- Track indexing status fields (`indexed_at`, `index_version` / `retrieval_version`).
- Publish indexing schema contract in `packages/shared/schemas/indexing.md`.

## Acceptance tests
- After ingest, lexical search returns the correct chunk for a unique phrase.
- Hybrid query returns results even if vector or BM25 is weak.
- Index records include required metadata fields (`docs_snapshot_id`, `doc_id`, `page_num`, `chunk_id`, `chunk_index`).

## Files likely touched
- `apps/api/indexing/*`
- `apps/api/retrieval/*`
- `packages/shared/schemas/*`
- `docs/ARCHITECTURE.md`
