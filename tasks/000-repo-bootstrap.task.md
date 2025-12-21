# Task 000 - Repo Bootstrap and Scaffolding

## Scope
- Create initial repo structure (`apps/web`, `apps/api`, `packages/shared`, `docs`, `tasks`, `.github/workflows`).
- Add minimal scaffolds for API (FastAPI with `/healthz`) and Web (Next.js shell).
- Add baseline CI placeholders (lint/test/typecheck and evals stub).
- Ensure docs copied/linked as source of truth.
- Use `pyproject.toml` + `uv` as the canonical Python dependency source (no `requirements.txt`).

## Acceptance tests
- `apps/api` starts locally and serves `/healthz` with 200.
- `apps/web` builds successfully.
- OpenAPI loads at `/docs` for the API.
- No RAG/retrieval/LLM business logic exists yet.

## Files likely touched
- `README.md`
- `apps/api/*`
- `apps/web/*`
- `packages/shared/*`
- `.github/workflows/*`
