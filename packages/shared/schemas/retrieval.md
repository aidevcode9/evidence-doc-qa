# Retrieval Schemas - DocQ&A v3.1 Demo

This document defines hybrid retrieval, RRF fusion, confidence scoring, and debug fields.

## Retrieval Inputs
- `query_text`: string, required
- `top_k_vector`: integer, required
- `top_k_bm25`: integer, required
- `use_reranker`: boolean, optional (default false)

## Retrieval Result (per chunk)
- `chunk_id`: string, required
- `doc_id`: string, required
- `page_num`: integer, required
- `chunk_text`: string, required
- `vector_score`: number, required
- `bm25_score`: number, required
- `rrf_rank`: integer, required
- `rrf_score`: number, required
- `rerank_score`: number, optional

## RRF Fusion
- `rrf_k`: integer, required
- `rrf_score`: number, required (derived from ranks)

## Retrieval Confidence
- `confidence_score`: number (0..1), required
- `confidence_threshold`: number (0..1), required
- `confidence_method`: string, required (e.g., `rrf_calibrated`, `rerank_calibrated`)

If `confidence_score` < `confidence_threshold`, the request is refused with
`LOW_RETRIEVAL_CONFIDENCE`.

## Demo Default (v3.1)
- `confidence_score = top_evidence.rrf_score`
- `confidence_threshold = 0.35`
- `confidence_method = rrf_top_score`
