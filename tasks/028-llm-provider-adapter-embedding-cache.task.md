# Task 028 - LLM Provider Adapter + Embedding Cache

## Scope
- Add a provider adapter layer for chat + embeddings with a single interface.
- Support `LLM_PROVIDER` selection in `apps/api/app/config.py` (default to Azure).
- Implement an embedding cache in `apps/api/app/embeddings.py` (memory or SQLite), keyed by model+input hash.
- Add telemetry for provider ID and embedding cache hit/miss.
- Update docs to mark the Open Questions as implemented.

## Acceptance tests
- Switching `LLM_PROVIDER` selects the correct adapter with no code changes.
- Embedding cache reduces duplicate requests (cache hit rate visible in telemetry).
- Config and docs reflect the provider adapter and cache behavior.

## Files likely touched
- `apps/api/app/config.py`
- `apps/api/app/embeddings.py`
- `apps/api/app/telemetry.py`
- `apps/api/app/*` (provider adapters)
- `docs/OPEN_QUESTIONS.md`
- `docs/ENVIRONMENT_REFERENCE.md`
