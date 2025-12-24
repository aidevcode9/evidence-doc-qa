# Open Questions — DocQ&A Demo (v3.1)

**Last updated:** 2025-12-21  
**Status:** Demo defaults locked; deferred items explicitly marked

---

## 0) Purpose

This document tracks **spec ambiguities and decisions** for the DocQ&A demo.

- Section A lists **defaults locked for v3.1 demo** so implementation can proceed.
- Section B lists **decisions to revisit after baseline evals**.
- Section C lists **enterprise / out-of-scope questions** that must NOT block the demo.

Codex should treat **Section A as authoritative**.

---

## A) Defaults locked for v3.1 demo (DO NOT BLOCK IMPLEMENTATION)

### A1) LLM provider (demo default)
**Decision**
- Use an **OpenAI-compatible interface** by default.
- Support adapters via env:
  - `LLM_PROVIDER=openai`
  - `LLM_PROVIDER=azure_openai` (if available)

**Rationale**
- Avoids dependency on Azure OpenAI availability in personal accounts.
- Keeps code portable and interview-safe.

---

### A2) Embeddings provider
**Decision**
- Use managed embeddings from the same provider family as the LLM.
- Cache embeddings by `(doc_sha256, chunk_hash)`.

---

### A3) Deterministic chunking (Tier 0)
**Decision**
- `DOCQA_CHUNK_SIZE = 900` characters
- `DOCQA_CHUNK_OVERLAP = 150` characters
- Whitespace normalization enabled
- Header/footer stripping **disabled** in v3.1 demo

**Rationale**
- Deterministic, eval-stable, and citation-friendly.

---

### A4) Citation schema (locked)
Each citation MUST resolve to a retrieved chunk.

```json
{
  "doc_id": "string",
  "doc_name": "string",
  "page_num": 12,
  "chunk_id": "string",
  "snippet": "string",
  "score": 0.73
}
```

**Rules**
- `chunk_id` must be in the retrieved evidence set.
- `page_num` must match chunk lineage.
- `snippet` must be a substring or near-substring of chunk text.

---

### A5) Retrieval confidence scoring (v0)
**Decision**
- `confidence = top_evidence.score`
- Threshold:
- `DOCQA_CONF_MIN = 0.35`

**Behavior**
- No evidence → `NO_SUPPORTING_EVIDENCE`
- Evidence but `confidence < DOCQA_CONF_MIN` → `LOW_RETRIEVAL_CONFIDENCE`

---

### A6) Injection heuristics (v0)
**Decision**
Block (case-insensitive substring match) if question contains any of:
- ignore previous instructions
- system prompt
- developer message
- reveal your prompt
- jailbreak
- bypass
- print the hidden rules
- exfiltrate

**Behavior**
- Immediate refusal with `INJECTION_DETECTED`.

---

### A7) PII-safe logging policy (demo)
**Decision**
- Never log raw document text.
- Never log full user question.
- Log truncated (≤200 chars) or hashed user input.
- Redact patterns in any logged text:
  - emails
  - phone numbers
  - SSN-like patterns (###-##-####)

---

### A8) Metrics endpoint semantics
**Decision**
- Route: `GET /v1/metrics`
- Auth: static admin token header
- Window: last 24h OR last 500 requests
- Returns:
  - p50 / p95 latency
  - average cost per query
  - refusal counts by code
  - cache hit rate

---

### A9) Eval gate thresholds (initial demo defaults)
**Decision**
- Citation coverage (non-refusal): ≥ 95%
- Valid citation proxy: ≥ 90%
- Refusal correctness on low-confidence tests: ≥ 90%
- Injection tests: 100% must refuse
- p95 latency (golden suite): < 4s

---

## B) Decisions to revisit after baseline evals

These should NOT block Slice 1.

1. Tier 1 parser choice (PDF layout/tables):
   - candidates: PDFMarkerReader, SmartPDFLoader, Azure Document Intelligence
2. Optional reranker:
   - cross-encoder vs LLM-based rerank
   - enable only if evals show retrieval misses
3. Confidence scoring upgrade:
   - calibrated classifier
   - reranker-informed confidence
4. Header/footer stripping heuristics
5. Chunking strategy for tables (row-aware chunks)

---

## C) Enterprise / out-of-scope for demo

These are intentionally deferred.

- Azure Front Door / WAF / API Management
- Private networking
- Multi-tenant auth, billing, RBAC
- Long-term document retention policies
- AWS-specific deployment questions (ALB, Nginx sidecars, etc.)

---

## D) Retention defaults (demo)

**Decision**
- Uploaded PDFs: 7 days (or manual delete)
- Telemetry/logs: 30 days
- All retention periods configurable via env

---

## E) Change log
- v3.1: Locked demo defaults, removed ambiguities blocking Codex execution
