# Task 021 — Enforce PII-safe logging in telemetry and verification

## Summary
PII and sensitive content may leak via:
- `verification.py` logging full question text, chunk prefix, and full raw model response JSON
- `telemetry.record_telemetry()` taking raw `question_text`/`answer_text` to estimate tokens (even if not stored, it increases accidental leakage risk via trace_metadata/loggers)

**Current code**
- `apps/api/app/verification.py`: logs `Q='{question}'`, `Chunk='{chunk_text[:50]}'`, and `LLM Raw Response: {json.dumps(response)}`
- `apps/api/app/telemetry.py`: token estimation from `len(question_text)//4` and `len(answer_text)//4` (approx line ~18+)

## Goals
- No raw question, answer, or chunk content in logs by default.
- Store only:
  - hashes, lengths, coarse classifications
  - structured metrics and scores
- Provide an explicit debug flag for short-lived, local-only troubleshooting.

## Scope
1. **Verification logging**
   - Remove raw question/chunk text from logs.
   - Log:
     - `request_id` (pass into verifier)
     - `question_hash`, `question_len`
     - `chunk_id` (pass in), `chunk_len`
     - `verdict` (verified/rejected/unverified) and `verifier_latency_ms`
   - Remove full raw response logging.
   - If needed, log a truncated, redacted response behind `DOCQA_DEBUG_VERIFIER=1`.

2. **Telemetry token estimation**
   - Change `record_telemetry()` signature to accept:
     - `question_len`, `answer_len` (ints) OR `question_hash` + lengths
   - Do not pass raw texts into telemetry layer.
   - Prefer provider usage tokens when available (wire through from Azure OpenAI response).

3. **Trace metadata hygiene**
   - Ensure `trace_metadata` never includes raw question/chunk/answer.
   - Add a lightweight redaction helper for any operator-supplied debug fields.

## Files to change
- `apps/api/app/verification.py`
- `apps/api/app/main.py` (pass request_id/chunk_id into verifier and adjust calls)
- `apps/api/app/telemetry.py`
- (optional) `apps/api/app/policy.py` (shared redaction/hash helpers)

## Acceptance criteria
- Default logs contain no raw question/answer/chunk content.
- Telemetry DB rows contain no raw question/answer content.
- Verifier still functions; refusal paths unchanged.
- Debug mode can be enabled explicitly and clearly warns “do not use in prod”.

## Tests
- Unit tests:
  - Verify log messages do not contain input substrings
  - Verify telemetry insert excludes raw texts (and schema unchanged except new fields)
- Manual:
  - Run a query containing an email/phone and confirm logs show redacted/hashes only

## Telemetry additions
- `trace_metadata.verifier_enabled`
- `trace_metadata.verdict`
- `trace_metadata.verifier_latency_ms`
- `trace_metadata.question_hash`, `question_len`, `answer_len`
