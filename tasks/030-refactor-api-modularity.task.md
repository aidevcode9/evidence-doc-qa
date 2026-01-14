# Task 030 - Refactor API Modularity

## Scope
- Break the monolithic `apps/api/app/main.py` (~900 lines) into smaller, dedicated router modules (e.g., `app/routers/ask.py`, `app/routers/ingest.py`, `app/routers/observability.py`).
- Move orchestration logic (RAG pipeline, verification steps) out of route handlers and into dedicated `services/` or `logic/` modules if they don't already exist.
- Ensure `main.py` is reserved for FastAPI app instantiation, middleware configuration, and exception handlers.
- **NEW**: Create automated integration tests using FastAPI's `TestClient` to verify all core endpoints (`/ask`, `/upload`, `/metrics`) maintain existing behavior.

## Acceptance tests
- `apps/api/app/main.py` is significantly reduced in size (aim for < 200 lines).
- All endpoints continue to function identically, verified by **automated integration tests**.
- Regression tests pass for all refactored routes.
- No circular imports introduced.

## Files likely touched
- `apps/api/app/main.py`
- `apps/api/app/routers/*.py` (NEW)
- `apps/api/app/services/*.py` (NEW or modified)
- `tests/integration/test_api.py` (NEW)
