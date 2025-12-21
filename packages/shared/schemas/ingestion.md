# Ingestion and Parsing Schemas - DocQ&A v3.1 Demo

This document defines the ingestion flow and parsing outputs for Tier 0 and Tier 1.
Tier 2 is disabled in the demo and only documented as an interface.

## Ingestion Flow (logical steps)
1) Upload PDF (assign `doc_id`)
2) Store raw PDF immutably (`doc_sha256`, storage URI)
3) Enqueue parse job (async)
4) Parse to pages (Tier 0 default)
5) Chunk pages deterministically
6) Emit chunk records + embeddings
7) Index chunks for hybrid retrieval (BM25 + vector)

## Raw Document Metadata
- `doc_id`: string, required
- `doc_sha256`: string, required
- `source_name`: string, optional (original filename)
- `storage_uri`: string, required
- `ingested_at_utc`: string (ISO 8601), required

## Page Record (Tier 0)
- `doc_id`: string, required
- `page_num`: integer, required
- `page_text`: string, required
- `parse_mode`: string enum (`tier0`, `tier1`, `tier2`), required
- `parse_warnings`: array of string, optional

## Chunk Record (Tier 0/1)
- `chunk_id`: string, required
- `doc_id`: string, required
- `doc_sha256`: string, required
- `page_num`: integer, required
- `chunk_index`: integer, required
- `char_start`: integer, required
- `char_end`: integer, required
- `chunk_text`: string, required
- `parse_mode`: string enum (`tier0`, `tier1`, `tier2`), required
- `layout_hint`: string, optional (e.g., `table`, `header`, `footer`)

## Deterministic Chunking Rules (Tier 0)
- `CHUNK_SIZE = 900` characters
- `CHUNK_OVERLAP = 150` characters
- Fixed `chunk_size` and `chunk_overlap` across all documents.
- Chunk boundaries align to page text boundaries only (no cross-page spans).
- Header/footer stripping is disabled in v3.1 demo.

## Tier 1 Parsing (layout-aware)
Triggered when:
- Heuristic indicates table-like structure, or
- Query intent indicates table/row/column retrieval.

Outputs:
- `page_text` in a layout-preserving format (plain text or markdown).
- `layout_hint` populated per chunk where applicable.

## Tier 2 Parsing (disabled in demo)
- Interface only; no implementation in demo.
- If enabled later, must emit the same Page and Chunk records as Tier 0/1.

## Indexing Inputs (hybrid retrieval)
- `chunk_id`, `doc_id`, `page_num`, `chunk_text`
- `embedding_vector`
- `metadata` (doc_sha256, chunk_index, char_start, char_end, parse_mode)
