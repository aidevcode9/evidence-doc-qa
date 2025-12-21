# PROJECT_PLAN_CODEX — DocQ&A (v3.1) Demo Build Plan
**Last updated:** 2025-12-21
**Goal:** Build the DocQ&A demo exactly as specified in:
- PRD 
- Evidence-Bound DocQ&A Architecture (v3.1) Azure Demo / Near-Free Reference

This plan is written to be executed step-by-step using Codex CLI. It emphasizes doc↔code consistency and near-free infrastructure.

---

## 0) Non-Negotiable Demo Invariants (MUST be enforced in code)
**INVARIANT 1:** No answer may be returned unless supported by retrieved evidence with **valid citations**.  
**INVARIANT 2:** If retrieval confidence < threshold, the system MUST **refuse** (no clarifying-question flow in MVP).  
**INVARIANT 3:** Every request persists: `request_id`, `prompt_version`, `retrieval_version`, `model_id`, `docs_snapshot_id`.  
**INVARIANT 4:** Any change to prompt/retrieval/model requires passing eval suite before promotion (“release gate”).

---

## 1) Near-Free Deployment Targets (Demo Default)
- **Web UI:** Vercel free tier (Next.js)
- **API:** Azure Container Apps (single service) with public ingress
- **Async ingestion/indexing:** Azure Container Apps Jobs (or run locally for early dev)
- **Docs storage:** Azure Blob Storage (raw PDFs + snapshots)
- **Hybrid retrieval:** Azure AI Search (vector + BM25)
- **DB (near-free):** Supabase Free Postgres (preferred) OR Azure Postgres smallest tier
- **Redis:** optional; default OFF for MVP unless needed for caching
- **Observability:** Application Insights (minimal sampling); PII-safe logs only

> **Explicitly out of scope for demo:** Front Door/WAF, APIM, private networking.

---

## 2) Repo Skeleton (create first)
Create:
- `/apps/web` (Next.js UI)
- `/apps/api` (FastAPI)
- `/packages/shared` (schemas/types)
- `/docs` (PRD + Architecture + runbook + evals)
- `/.github/workflows` (CI: lint/test/evals)

---

## 3) Data Model + Versioning (implement early)
### 3.1 Core IDs
- `request_id` (UUID)
- `docs_snapshot_id` (immutable snapshot of uploaded docs + chunk ids)
- `prompt_version`, `retrieval_version`, `model_id`, `parser_mode`

### 3.2 Telemetry table (Postgres)
Store per request:
- timestamps, latency_ms
- tokens_in/out, cost_est
- cache_hit
- refusal_code + failure_label
- version snapshot fields

Schema is managed by Alembic migrations; no SQLite fallback.

---

## 4) Ingestion Pipeline (Tier 0 + Tier 1; Tier 2 disabled)
### Tier 0 (default)
- Parse PDF per page
- Deterministic chunking (size + overlap)
- Store lineage: doc_id, doc_sha256, page_num, chunk_index, char_start/end

### Tier 1 (selective)
Triggered by heuristics or query intent (“table”, “row/column”, etc.).
- Produce layout-aware text/markdown
- Preserve table readability for retrieval/citations

### Tier 2 (disabled in demo)
- Only document the interface; do not implement.

---

## 5) Retrieval Pipeline (Hybrid)
- Azure AI Search index(s): lexical BM25 + vector
- Query:
  - vector K + bm25 K
  - fuse ranks (RRF)
  - optional rerank top-N
- Emit retrieval debug fields for evals:
  - vector score, bm25 score, fused rank, rerank score (if used)

---

## 6) Ask Endpoint (Hard gates + citation enforcement)
Implement `/ask` (and streaming variant if needed):
1) Init request + load version snapshot
2) Retrieve evidence
3) Pre-LLM gates:
   - retrieval confidence threshold
   - injection heuristics
   - parse integrity
   - PII-safe logging checks
4) Generate answer from evidence only
5) Post-LLM citation gate:
   - validate citations resolve to retrieved evidence
   - if missing/invalid → refuse with reason code
6) Persist telemetry (always)
7) Return answer+citations OR refusal+reason_code

---

## 7) Refusal Codes (v3)
- `NO_SUPPORTING_EVIDENCE`
- `LOW_RETRIEVAL_CONFIDENCE`
- `INJECTION_DETECTED`
- `PARSE_FAILED`
- `POLICY_REFUSAL`

All refusals are first-class outputs (not errors). Always include `request_id`.

---

## 8) Evals + Release Gate (CI required)
### 8.1 Golden set
- ~30 questions across 3 documents
- Include lexical-heavy questions (IDs, ranges, dates)
- Include injection attempts

### 8.2 Eval runner
- CLI command: `python -m evals.run --suite golden`
- Output JSON artifact (pass/fail + metrics + labels)

### 8.3 Gate
- CI fails if eval thresholds not met
- Only then bump `prompt_version` / `retrieval_version`

---

## 9) Codex CLI Workflow (how to execute)
Use Codex to implement one vertical slice at a time:

**Slice 1:** Upload → Tier 0 parse → index → Ask with citations/refusal  
**Slice 2:** Hybrid retrieval + RRF  
**Slice 3:** Telemetry persistence + metrics endpoint  
**Slice 4:** Evals + CI gate  
**Slice 5:** Tier 1 parsing triggers (tables/layout)  

After each slice:
- run unit tests
- run golden evals
- update `/docs/OPEN_QUESTIONS.md` if decisions made

---

## 10) “Doc ↔ Code Consistency” Checklist (run before demo)
- [ ] Invariants enforced in code (no-answer-without-citations; refuse on low confidence)
- [ ] Refusal codes match docs exactly
- [ ] Azure services used match demo mapping (no Front Door/APIM)
- [ ] request_id + version snapshot persisted for every request
- [ ] Evals run in CI and block promotion
- [ ] Architecture diagrams match implemented deployment
