# Task 025 - Verifier prompt v2 (structured outputs + injection hardening)

## Summary
The current verifier prompt is a minimal YES/NO pattern and is not injection-hardened. It also relies on free-form parsing. We need a versioned prompt with structured outputs, span offsets, and strict substring validation to make verification reliable and auditable.

## Goals
- Use a schema-enforced response (structured output) instead of free-form text.
- Treat chunk text as untrusted and ignore any instructions inside it.
- Require exact, contiguous spans with offsets that can be validated against the raw chunk.
- Record prompt version, schema version, and verification reason in telemetry.

## Scope
1. Prompt registry
   - Add `prompts/evidence_verifier/2.0.0.txt` with the new system prompt.
   - Define `PROMPT_ID`, `PROMPT_VERSION`, `PROMPT_HASH`, and `SCHEMA_VERSION`.
2. Structured output
   - Use `response_format` with a JSON schema (or tool/function schema if required by the model).
   - Required fields: `verdict`, `span`, `start`, `end`, `reason`.
   - `start`/`end` are 0-based offsets into the raw chunk string.
3. Injection hardening
   - Add explicit "untrusted chunk" rule to system prompt.
   - Wrap chunk in clear delimiters (`<chunk>...</chunk>`).
4. Validation logic
   - If `verdict=YES`, verify:
     - `start >= 0`, `end > start`
     - `span == chunk_text[start:end]`
   - If validation fails, treat as `NO` with `reason=SPAN_MISMATCH`.
   - If schema parse fails, treat as `NO` with `reason=INVALID_OUTPUT`.
5. Telemetry
   - Store `verifier.prompt_id`, `verifier.prompt_version`, `verifier.prompt_hash`, `verifier.schema_version`.
   - Store `verifier.model`, `verifier.temperature`, `verifier.max_output_tokens`.
   - Store `verifier.reason` and `verifier.verdict`.
6. Configuration defaults
   - Use `temperature=0` and `max_output_tokens<=150` unless proven insufficient.

## Files to change
- `apps/api/app/verification.py` (prompt load, schema, validation, parsing)
- `apps/api/app/config.py` (verifier prompt/version settings if needed)
- `apps/api/app/telemetry.py` (structured verifier metadata)
- `docs/ENVIRONMENT_REFERENCE.md` (if new env vars are added)
- `prompts/evidence_verifier/2.0.0.txt` (new prompt)

## Acceptance criteria
- Verifier output is schema-validated and parsed without brittle string logic.
- YES results only pass when the span is an exact substring of the raw chunk.
- Chunk instructions do not override the verifier task.
- Telemetry includes verifier prompt/version/hash and reason codes.

## Tests
- Unit tests for parsing and validation:
  - Direct span present -> YES with matching offsets.
  - Paraphrase only -> NO, reason=REQUIRES_INFERENCE.
  - Ambiguous answer -> NO, reason=AMBIGUOUS.
  - Non-contiguous answer -> NO, reason=NON_CONTIGUOUS.
  - Injection chunk -> NO unless answer span exists.
  - Output with mismatched offsets -> NO, reason=SPAN_MISMATCH.
