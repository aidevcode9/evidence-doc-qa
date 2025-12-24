# ARCHITECTURE — Evidence‑Bound DocQ&A (v3.1 Demo)

**Version:** v3.1 (Demo / Near‑Free)  
**Last updated:** 2025-12-21

---

## 0) Demo‑First Constraints

This architecture implements PRD — DocQ&A (v3.1) with a **near‑free demo default**.

**Not required for demo**
- Azure Front Door / WAF
- Azure API Management
- Private networking

These are enterprise hardening options only.

**Demo invariants**
1. Evidence‑bound answers only (else refuse)
2. Refuse when retrieval confidence < threshold (no clarifying questions in MVP)
3. Version snapshot + request_id logged for replay
4. Eval suite must pass before config promotion

---

## 1) System Overview

The system enforces evidence‑bound generation with **hard gates** and full telemetry.

Planes:
- Query serving
- Retrieval & evidence
- Policy & safety
- Generation
- Telemetry & audit
- Ingestion & indexing

---

## 2) Core Request Path (Ask)

1. Assign `request_id`; load version snapshot
2. Retrieve evidence (vector + BM25 → RRF → optional rerank)
3. Pre‑LLM policy gates:
   - retrieval confidence
   - injection heuristics
   - parse integrity
   - PII‑safe logging
4. Generate from evidence only
5. Hard citation gate → missing/invalid → refusal
6. Return answer + citations OR refusal + reason code
7. Persist telemetry (always)

Contract reference: `packages/shared/schemas/contract.md` defines the request/response and telemetry fields used by the ask path.
Retrieval reference: `packages/shared/schemas/retrieval.md` defines hybrid retrieval, fusion, and confidence scoring.
Policy reference: `packages/shared/schemas/policy.md` defines pre/post-LLM gates and refusal mappings.

### Refusal codes (v3)
- NO_SUPPORTING_EVIDENCE
- LOW_RETRIEVAL_CONFIDENCE
- INJECTION_DETECTED
- PARSE_FAILED
- POLICY_REFUSAL

---

## 3) Ingestion & Indexing

- Raw PDFs stored immutably
- Parsing is async and isolated from serving

### Tiered parsing
- Tier 0: deterministic per‑page parsing
- Tier 1: layout/table‑aware parsing (heuristics)
- Tier 2: highest‑fidelity parsing (**disabled in demo**)

- Chunks embedded and indexed for hybrid retrieval

Contract reference: `packages/shared/schemas/ingestion.md` defines ingestion flow, chunk lineage, and indexing inputs.
Indexing reference: `packages/shared/schemas/indexing.md` defines embeddings and index record fields.

---

## 4) Azure Mapping (Demo Default)

- **API:** Azure Container Apps (public ingress)
- **Jobs:** Container Apps Jobs (ingestion/indexing)
- **Storage:** Azure Blob Storage
- **Search:** Azure AI Search (vector + BM25)
- **LLM:** Azure OpenAI (demo default)
- **DB:** Supabase Free Postgres OR smallest Azure Postgres
- **Cache:** Optional Redis (may be disabled)
- **Observability:** Application Insights (minimal sampling)

---

## 5) Release Discipline (Eval Gate)

A change to any of:
- `prompt_version`
- `retrieval_version`
- `model_id`
- `parser_mode`

is not considered released unless the eval suite passes configured thresholds.
Eval gates run in GitHub Actions.

---

## 6) Telemetry (Minimum)

Per request:
- request_id + version snapshot
- latency (p50/p95)
- tokens + cost_est
- cache hit/miss
- refusal_code + failure label

Telemetry reference: `packages/shared/schemas/telemetry.md` defines telemetry fields and metrics output.

---

## 7) Scaling Notes

- Serving and ingestion scale independently
- SSE/WS timeouts tuned conservatively
- Connection pooling protects DB/cache

---
