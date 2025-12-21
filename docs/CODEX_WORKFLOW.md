# Codex Workflow — PRD → MVP (DocQ&A)

**Version:** v3  
**Last updated:** 2025-12-21  
**Status:** Draft (living doc; update with implementation)  

---

# Codex Workflow (PRD → MVP)

This repo is designed to work well with Codex/agents: **spec → tasks → implement → verify → harden**.

## Required docs (source of truth)
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/OPEN_QUESTIONS.md`
- `docs/EVALS_V1_REQUIREMENTS.md`

## Tasking model
- One file per task under `tasks/` with:
  - context, requirements, constraints
  - acceptance tests (mechanical)
  - files likely touched

## Operating macros (agent-friendly)
1) **Spec pass**: propose tasks + contracts, no code changes  
2) **Contract-first**: schemas + OpenAPI + stubs  
3) **Vertical slice**: UI → API → DB → metrics → tests  
4) **Verification**: run lint/test/typecheck/evals  
5) **Hardening**: logging, metrics, rate limits, rollback

## Definition of Done (MVP)
- Upload → ingest → ask → citations or refuse works end-to-end
- Evals run in CI and gate merges
- Cost/query and p95 latency visible
- PII-safe logs + injection defenses
- 3-command quickstart in README

---

## Addendum (v3) — How to use Codex effectively
- Start with contract-first (schemas + OpenAPI) to reduce thrash
- Require lint/tests/evals to pass before marking tasks done
- Unknowns go to OPEN_QUESTIONS.md; choose safest default
