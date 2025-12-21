# PRD — DocQ&A: Trustworthy Document Q&A (v3.1 Demo)

**Project codename:** DocQ&A  
**Version:** v3.1 (Demo / Near‑Free)  
**Last updated:** 2025-12-21  
**Status:** Draft (living doc; demo‑accurate)

---

## 0) Demo‑First Constraints (Read First)

This PRD defines a **demo‑first**, **near‑free** implementation intended for interviews and technical evaluations.

**Key constraints**
- Must run on **Vercel free (UI)** + **personal Azure (API/search/storage)**.
- Enterprise edge services (Azure Front Door, WAF, APIM, private networking) are **out of scope** for the demo.
- Correctness and auditability take precedence over UX polish.

**Non‑negotiable demo invariants**
1. No answer may be returned unless supported by retrieved evidence with **valid citations**.
2. If retrieval confidence is below threshold, the system **refuses** (no clarifying‑question flow in MVP).
3. Every response (answer or refusal) logs: `request_id`, `prompt_version`, `retrieval_version`, `model_id`, `docs_snapshot_id`.
4. Any change to prompt, retrieval, or model **must pass evals** before promotion.

---

## 1) Problem Statement

Most document‑Q&A demos fail in production because they:
- hallucinate without grounding,
- regress when prompts/models change,
- leak sensitive data in logs,
- have unknown latency/cost behavior,
- lack release gates and observability.

**DocQ&A proves the opposite**: trustworthy answers **only when supported by sources**, measurable quality, and operational discipline.

---

## 2) Target Users & Use Cases

### Primary users
1. Hiring managers / interviewers (e.g., Director GenAI, Manager AI Eng)
2. Internal operator (you) running evals and tuning retrieval

### MVP journeys

**Journey A — End user**
- Upload a PDF
- Ask a question
- Receive an answer **with citations** (doc + page + snippet)  
- If unsupported → system **refuses with a reason code and guidance**

**Journey B — Operator**
- Run eval suite (golden questions)
- View pass/fail + metrics (groundedness proxy, citation correctness, latency, cost)
- Change config → re‑run evals → promote only if gates pass

---

## 3) Success Metrics

### Trust & correctness
- Citation coverage ≥ 95% of non‑refusal answers
- Refusal correctness when retrieval confidence below threshold
- Hallucination proxy rate trending downward (evals + spot checks)

### Performance & cost
- p95 latency < 4s (small dataset)
- Cost/query tracked; caching improves median cost ≥ 20% where enabled

### Operational discipline
- Eval gates block releases
- request_id + version snapshot logged for every request

---

## 4) MVP Scope

### In scope
- PDF upload + ingestion
- Hybrid retrieval (vector + BM25 + RRF)
- Mandatory citations per answer
- Refusal on insufficient evidence
- Eval harness + CI gate
- Basic metrics endpoint/page
- PII‑safe logging + injection heuristics

### Out of scope
- Clarifying multi‑turn flows
- Multi‑tenant auth/billing
- Enterprise SSO/RBAC
- Large‑scale ingestion
- Fine‑tuning

---

## 5) Key Product Requirements

### 5.1 Retrieval & ranking (hybrid)
- Vector + BM25 retrieval
- Reciprocal Rank Fusion (RRF)
- Optional reranker
- Retrieval logs expose component scores for evals

### 5.2 Parsing & normalization (tiered)
- **Tier 0 (default):** per‑page text extraction, deterministic chunking, page fidelity
- **Tier 1 (selective):** layout/table‑aware parsing via heuristics or query intent
- **Tier 2 (optional):** highest‑fidelity managed parsing — **disabled in demo**

### 5.3 Answer + citations
- Response schema includes `answer_text` and `citations[]`
- Missing/invalid citations → refusal
- Contract-first schemas live in `packages/shared/schemas/contract.md`

### 5.4 Evals
- Golden set (~30 questions)
- CLI + CI execution
- JSON artifacts stored for trend analysis

### 5.5 Cost & latency tracking
- Log tokens, provider, cost estimate
- p50/p95 latency visible

### 5.6 Governance & safety
- PII redaction in logs
- Injection heuristics
- Versioned config snapshot per request

---

## 6) Non‑Functional Requirements

### Security & privacy
- Docs stored only in controlled storage (Blob or local)
- Secrets via env vars only

### Reliability
- Graceful failures; actionable errors
- Bounded retries for providers

### Cost constraints
- Redis optional (in‑process cache acceptable for MVP)
- Use smallest viable cloud tiers

---

## 7) Deployment (Demo)

- **Web:** Next.js on Vercel free tier
- **API:** Azure Container Apps (public ingress)
- **Ingestion:** Container Apps Jobs (or local for dev)
- **Storage:** Azure Blob Storage
- **Search:** Azure AI Search (basic tier)
- **DB:** Supabase Free Postgres OR smallest Azure Postgres

Enterprise edge services explicitly **not required** for demo.

---

## 8) Acceptance Criteria

- Upload → ingest → ask → cite or refuse works end‑to‑end
- Evals run in CI and gate merges
- Metrics endpoint shows latency + cost
- Docs and architecture match code behavior

---
