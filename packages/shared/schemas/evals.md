# Evals Schemas - DocQ&A v3.1 Demo

This document defines eval dataset format, output artifacts, and gate inputs.

## Golden Set Format (evals/golden.jsonl)
Required fields:
- `id`: string, required
- `category`: string enum (`answerable`, `refusal`, `adversarial`, `table_layout`)
- `question`: string, required
- `docs_snapshot_id`: string, required
- `expected_behavior`: string enum (`answer`, `refuse`)
- `expected_doc_id`: string, optional
- `expected_page_num`: integer, optional
- `expected_keywords`: array of string, optional

## Eval Output Summary (evals/out/summary.json)
- `run_id`: string, required
- `prompt_version`: string, required
- `retrieval_version`: string, required
- `model_id`: string, required
- `parser_mode`: string, required
- `docs_snapshot_id`: string, required
- `metrics`: object, required

## Eval Output Details (evals/out/details.jsonl)
Per record fields:
- `id`, `category`, `question`
- `expected_behavior`
- `refusal_code` (if refused)
- `citations` (if answered)
- `latency_ms`, `tokens_in`, `tokens_out`, `cost_est`
- `failure_label` (if failed)
