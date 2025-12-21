# Policy and Citation Gates - DocQ&A v3.1 Demo

This document defines pre-LLM policy gates and post-LLM citation enforcement.

## Pre-LLM Gates
All gates must pass before generation:
- `retrieval_confidence`: refuse if below threshold
- `injection_heuristics`: refuse if prompt injection is detected
- `parse_integrity`: refuse if parsing failed or chunks are invalid
- `pii_safe_logging`: redact sensitive fields before persistence

## Injection Heuristics (v0)
Block (case-insensitive substring match) if question contains any of:
- ignore previous instructions
- system prompt
- developer message
- reveal your prompt
- jailbreak
- bypass
- print the hidden rules
- exfiltrate

## Post-LLM Citation Gate
Rules for a valid answer:
- Every answer must include `citations[]`.
- Each citation must resolve to a retrieved chunk by `chunk_id`.
- Each citation must include `doc_id`, `page_num`, and a `snippet`.

If any rule fails, refuse with `NO_SUPPORTING_EVIDENCE`.

## Refusal Mapping
- `LOW_RETRIEVAL_CONFIDENCE`: confidence below threshold
- `INJECTION_DETECTED`: injection heuristics triggered
- `PARSE_FAILED`: parsing integrity failure
- `NO_SUPPORTING_EVIDENCE`: missing or invalid citations
- `POLICY_REFUSAL`: catch-all for other policy blocks
