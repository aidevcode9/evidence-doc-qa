# Task 027 - Hard Citation Gate (NO_CITATIONS Refusal)

## Scope
- Enforce a hard citation validation step before returning an answer.
- Define explicit citation validity rules (doc/page/snippet present, snippet length, doc/page match retrieved evidence).
- If invalid/missing citations, refuse with `NO_SUPPORTING_EVIDENCE` and `failure_label=NO_CITATIONS`.
- Add telemetry fields for citation validation failures.
- Add an eval case that forces a missing/invalid citation to ensure the gate trips.

## Acceptance tests
- When citations are missing or invalid, `/v1/ask` returns `refusal_code=NO_SUPPORTING_EVIDENCE` and logs `failure_label=NO_CITATIONS`.
- When citations are valid, answers return with `citations[]` and no refusal.
- Eval suite includes a citation validation failure case and fails if the gate does not trigger.

## Files likely touched
- `apps/api/app/main.py`
- `apps/api/app/evidence.py`
- `apps/api/app/telemetry.py`
- `evals/golden.jsonl`
- `evals/run.py`
- `docs/ARCHITECTURE.md`
- `docs/PRD.md`
