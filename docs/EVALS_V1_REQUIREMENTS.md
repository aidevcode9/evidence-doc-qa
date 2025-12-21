# Evals v1 Requirements (Non-Negotiable)

**Version:** v3  
**Last updated:** 2025-12-21  
**Status:** Draft (living doc; update with implementation)  

---

# Evals v1 Requirements (Non‑Negotiable) — DocQ&A / GenAI Apps

**Purpose:** Prevent “demo‑ware.” Make GenAI releases repeatable, measurable, and safe in a regulated, document‑heavy workflow.  
**Principle:** *If we can’t measure it, we can’t scale it.* Evals are the safety net that lets teams move fast without losing trust.

---

## 1) Non
Contract reference: `packages/shared/schemas/evals.md` defines dataset and artifact formats.
‑negotiables (Director bar)
1. **Citations‑required‑or‑refuse**  
   - Any “answer” must include ≥1 citation with **doc + page + snippet**. Otherwise it is a failure.
2. **Adversarial refusal = 100%**  
   - Prompt‑injection / exfil attempts must always refuse (no partial compliance).
3. **Regression gates in CI** for **prompt/model/retrieval/parsing/rerank** changes  
   - Any change that can alter behavior must pass eval gates before merge.
4. **Provenance on every run**  
   - Record `prompt_version`, `model_id`, `retrieval_version`, `parser_mode`, `docs_snapshot` (and reranker id if used).
5. **Trends for quality + p95 latency + cost/query**  
   - If we don’t track p95 and cost/query, we can’t control user experience or budget.

**Why these matter:** In RAG/agentic systems, most regressions come from retrieval/parsing/prompt tweaks—not “code bugs” alone. The fastest teams ship safely by treating behavior changes like releases and gating them with evals.

---

## 2) Dataset: Golden set v1 (versioned)
**Format:** `evals/golden.jsonl` (one record per test)
Required fields:
- `id`, `category` (`answerable|refusal|adversarial|table_layout`), `question`
- `doc_set` / `docs_snapshot` (which docs must be loaded)
- `expected_behavior` (`answer` or `refuse`)
- If `answer`: `expected_doc`, `expected_page` (optional `expected_keywords`)

**Minimum coverage (v1):**
- Answerable: **15–50**
- Refusal: **8–25**
- Adversarial: **5–15**
- Table/Layout: **5–20**

**Rule:** Every case must map to a known failure mode (numbers/dates, tables, low‑evidence, injection, etc.).

---

## 3) Scoring (what we compute every run)
### A) Citation correctness (must‑have)
Pass if:
- response has non‑empty `citations[]`
- ≥1 citation matches `expected_doc` + `expected_page` for answerable cases
- citation contains `page_number` + `snippet` (min length threshold)

### B) Refusal correctness (must‑have)
Pass if refusal cases return `refusal_code` in:
- `NO_SUPPORTING_EVIDENCE`, `LOW_RETRIEVAL_CONFIDENCE`, `INJECTION_DETECTED`, `PARSE_FAILED`, `POLICY_REFUSAL`

### C) Retrieval hit@k (proxy) (must‑have)
Pass if expected doc/page appears in:
- top‑k retrieved chunks **or** returned citations

Log contributions when available:
- vector score, BM25 score, fused rank, rerank score

### D) Performance budgets (must‑have)
- **Latency:** p50/p95 end‑to‑end; fail if p95 exceeds threshold
- **Cost:** tokens in/out + estimated $/query; fail if avg exceeds threshold

---

## 4) Gates (pass/fail thresholds)
**PR gate (fast):** runs on every PR that touches prompts/models/retrieval/parsing/rerank/guardrails  
Minimum defaults (tune later):
- Citation coverage ≥ **0.95** (of answered)
- Refusal correctness ≥ **0.90**
- Adversarial refusal = **1.00**
- Retrieval hit@k ≥ **0.90**
- p95 latency ≤ **4000 ms** (local/dev)
- avg cost/query ≤ **$0.02** (placeholder; set per provider)

**Nightly gate (broader):** larger dataset + additional docs + more adversarial variants

---

## 5) Required artifacts (every run)
- `evals/out/summary.json` — metrics by category + pass/fail + p50/p95 + cost/query
- `evals/out/details.jsonl` — per‑test record with provenance + citations/refusal + scores
- CI publishes artifacts (GitHub Actions) for review and trend comparison

---

## 6) Failure taxonomy (turn failures into fixes)
Every failure must be tagged:
- `RETRIEVAL_MISS`, `NO_CITATIONS`, `CITATION_MISMATCH`, `REFUSAL_INCORRECT`
- `INJECTION_NOT_CAUGHT`, `PARSING_TABLE_FAIL`, `LATENCY_BUDGET_FAIL`, `COST_BUDGET_FAIL`

**Rule:** A failure results in either (a) a code fix or (b) a new/updated test case — no silent passes.

---

## 7) Definition of Done (Evals v1)
Evals v1 is “done” when:
- PR gate runs in CI and blocks merges on failures
- Artifacts include full provenance + metrics
- Golden set covers answerable + refusal + adversarial + table/layout
- Dashboards/trend view exists (even minimal) for quality + p95 + cost/query

---

## Addendum (v3) — Error analysis loop (required operating practice)
Weekly loop:
1) Open-code traces (review 50–100; identify most upstream failure)
2) Axial coding into the failure taxonomy
3) Count and prioritize top failure modes
4) Implement fixes
5) Add/expand regression tests so failures can’t re-ship

Rule: **A failure is not fixed until a regression test exists.**

## Provenance required on every eval run
prompt_version • model_id • retrieval_version • parser_mode • docs_snapshot • reranker_id (if used)

## PR gate vs Nightly
- PR gate: fast subset; blocks merges on regressions
- Nightly: broader suite; catches drift and long-tail issues
