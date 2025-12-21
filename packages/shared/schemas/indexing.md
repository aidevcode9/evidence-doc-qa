# Indexing Schemas - DocQ&A v3.1 Demo

This document defines embeddings, index schema, and indexing status fields.

## Embedding Input
- `chunk_id`: string, required
- `chunk_text`: string, required
- `doc_id`: string, required
- `doc_sha256`: string, required

## Index Record (hybrid search)
- `docs_snapshot_id`: string, required
- `doc_id`: string, required
- `doc_name`: string, optional
- `page_num`: integer, required
- `chunk_id`: string, required
- `chunk_index`: integer, required
- `chunk_text`: string, required
- `embedding_vector`: array of number, required
- `indexed_at_utc`: string (ISO 8601), required
- `index_version`: string, required
- `retrieval_version`: string, required
