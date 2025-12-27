# Shared Schemas - DocQ&A v3.1 Demo

This document defines the contract-first schemas used by API, evals, and telemetry.
All fields are ASCII and stable unless a new `*_version` is promoted via evals.

## Version Snapshot (required on every request/response/telemetry)
- `request_id`: string (UUID), required
- `docs_snapshot_id`: string, required
- `prompt_version`: string, required
- `retrieval_version`: string, required
- `model_id`: string, required
- `parser_mode`: string enum (`tier0`, `tier1`, `tier2`), required

## Ask Request
- `question`: string, required
- `top_k`: integer, optional (default 8)
- `include_debug`: boolean, optional (default false)
- `version_snapshot`: object, required (see Version Snapshot)

## Citation
- `doc_id`: string, required
- `doc_name`: string, required
- `page_num`: integer, required
- `chunk_id`: string, required
- `snippet`: string, required
- `score`: number, required

## Refusal Codes (v3)
- `NO_SUPPORTING_EVIDENCE`
- `LOW_RETRIEVAL_CONFIDENCE`
- `INJECTION_DETECTED`
- `PARSE_FAILED`
- `POLICY_REFUSAL`

## Ask Response
- `request_id`: string (UUID), required
- `answer_text`: string, optional (required if `refusal_code` is null)
- `citations`: array of Citation, optional (required if `refusal_code` is null)
- `refusal_code`: Refusal Code enum, optional (required if `answer_text` is null)
- `reason`: string, optional (human-readable refusal message)
- `version_snapshot`: object, required (see Version Snapshot)

## Telemetry Record
- `request_id`: string (UUID), required
- `docs_snapshot_id`: string, required
- `prompt_version`: string, required
- `retrieval_version`: string, required
- `model_id`: string, required
- `parser_mode`: string enum (`tier0`, `tier1`, `tier2`), required
- `timestamp_utc`: string (ISO 8601), required
- `latency_ms`: integer, required
- `tokens_in`: integer, required
- `tokens_out`: integer, required
- `cost_est`: number, required
- `cache_hit`: boolean, required
- `refusal_code`: Refusal Code enum, optional
- `failure_label`: string, optional

## Sample Ask Request (minimal)
```json
{
  "question": "What is the refusal behavior when retrieval confidence is low?",
  "version_snapshot": {
    "request_id": "1b3c1c31-02e6-4b98-8d5b-0a91a08d9fb4",
    "docs_snapshot_id": "snap_2025_12_21_0001",
    "prompt_version": "v3.1.0",
    "retrieval_version": "v3.1.0",
    "model_id": "gpt5-mini",
    "parser_mode": "tier0"
  }
}
```

## Sample Ask Response (answer)
```json
{
  "request_id": "1b3c1c31-02e6-4b98-8d5b-0a91a08d9fb4",
  "answer_text": "The system refuses when retrieval confidence is below threshold.",
  "citations": [
    {
      "doc_id": "PRD",
      "doc_name": "PRD.md",
      "page_num": 1,
      "chunk_id": "PRD-1-3",
      "snippet": "If retrieval confidence is below threshold, the system refuses.",
      "score": 0.73
    }
  ],
  "refusal_code": null,
  "version_snapshot": {
    "request_id": "1b3c1c31-02e6-4b98-8d5b-0a91a08d9fb4",
    "docs_snapshot_id": "snap_2025_12_21_0001",
    "prompt_version": "v3.1.0",
    "retrieval_version": "v3.1.0",
    "model_id": "gpt5-mini",
    "parser_mode": "tier0"
  }
}
```

## Sample Ask Response (refusal)
```json
{
  "request_id": "1b3c1c31-02e6-4b98-8d5b-0a91a08d9fb4",
  "answer_text": null,
  "citations": null,
  "refusal_code": "LOW_RETRIEVAL_CONFIDENCE",
  "reason": "Insufficient evidence to answer.",
  "version_snapshot": {
    "request_id": "1b3c1c31-02e6-4b98-8d5b-0a91a08d9fb4",
    "docs_snapshot_id": "snap_2025_12_21_0001",
    "prompt_version": "v3.1.0",
    "retrieval_version": "v3.1.0",
    "model_id": "gpt5-mini",
    "parser_mode": "tier0"
  }
}
```
