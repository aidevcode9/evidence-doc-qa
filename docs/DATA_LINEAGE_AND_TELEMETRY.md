# Evidence Bound: Data Lineage & Telemetry

> Technical one-pager for advisors. How data flows through the system and how every step is tracked.

---

## System Overview

Evidence Bound is a retrieval-augmented Q&A system for law firms. Every answer must cite a specific document span or the system refuses to answer. No hallucination by design.

**Stack:** FastAPI (Python) | PostgreSQL | Azure AI Search | Azure OpenAI (GPT-5-mini) | Next.js | Langfuse

---

## Data Lineage: Document Ingestion

```
 PDF Upload                Parse               Chunk              Embed              Index
 ─────────────────────────────────────────────────────────────────────────────────────────────
                                                                   Azure OpenAI
 ┌──────────┐          ┌──────────┐       ┌──────────┐       ┌──────────────┐    ┌──────────┐
 │ PDF file │──SHA256──│ Marker / │──────│ 512-char │──────│ text-embed-  │───│ Azure AI │
 │ (upload) │  hash    │ PyPDF /  │ pages │ windows  │ texts │ ding-3-large │   │ Search   │
 │          │          │ LlamaPrse│       │ w/overlap│       │ (3072-dim)   │   │ (hybrid) │
 └──────────┘          └──────────┘       └──────────┘       └──────────────┘   └──────────┘
      │                     │                  │                    │                 │
      ▼                     ▼                  ▼                    ▼                 ▼
 Azure Blob            Page text          chunk_id             Vectors          HNSW index
 + local disk          per page           per chunk            per chunk        + BM25 text
                                          (page, offsets)                       + semantic
```

**Key artifacts at each stage:**

| Stage | Output | Storage | Isolation |
|-------|--------|---------|-----------|
| Upload | Raw PDF + SHA-256 hash | Azure Blob + local disk | `tenant_id`, `matter_id` |
| Parse | Page text (1 string per page) | In-memory (transient) | -- |
| Chunk | 512-char windows with 64-char overlap | `chunks` table (PostgreSQL) | `tenant_id`, `matter_id`, `docs_snapshot_id` |
| Embed | 3072-dim float vectors | Embedded in index record | -- |
| Index | Searchable document chunks | Azure AI Search index OR `index_records` table | `tenant_id`, `matter_id` filter on every query |

---

## Data Lineage: Query Pipeline

```
 User Question
      │
      ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  execute_ask()                                          [trace root]   │
 │                                                                        │
 │  1. Policy Gate ─── injection heuristics ─── block if detected         │
 │       │                                                                │
 │       ▼                                                                │
 │  2. hybrid_search() ──────────────────────────────── [@observe span]   │
 │       │                                                                │
 │       ├── embed_texts_with_usage() ──── embed query ── [@observe span] │
 │       │         │                                                      │
 │       │         └── Azure OpenAI text-embedding-3-large                │
 │       │                                                                │
 │       └── Azure AI Search (BM25 + vector + semantic reranker)          │
 │              │                                                         │
 │              ▼  top-K chunks (scored, ranked)                          │
 │                                                                        │
 │  3. Confidence Gate ─── score < threshold? ─── refuse                  │
 │       │                                                                │
 │       ▼                                                                │
 │  4. verify_relevance() ──────────────────────────── [@observe span]    │
 │       │                                                                │
 │       └── call_openai() ── GPT-5-mini judges chunk [@observe generation]│
 │              │                                                         │
 │              ▼  verdict: VERIFIED / REJECTED + exact span              │
 │                                                                        │
 │  5. Evidence Grading ─── A/B/C/D grade from scores + verification      │
 │       │                                                                │
 │       ▼                                                                │
 │  6. Citation Assembly ─── doc name, page, char offsets, snippet        │
 │       │                                                                │
 │       ▼                                                                │
 │  7. record_telemetry() ─── write to PostgreSQL telemetry table         │
 │                                                                        │
 └─────────────────────────────────────────────────────────────────────────┘
      │
      ▼
 JSON Response: answer_text + citations[] + evidence_support + version_snapshot
```

**Refusal points (system refuses rather than hallucinate):**

| Gate | Trigger | Refusal Code |
|------|---------|-------------|
| Policy | Injection heuristics match | `INJECTION_DETECTED` |
| Retrieval | No chunks found | `NO_SUPPORTING_EVIDENCE` |
| Confidence | Top score < threshold (0.70) | `LOW_RETRIEVAL_CONFIDENCE` |
| Verification | LLM rejects all top candidates | `NO_SUPPORTING_EVIDENCE` |
| Evidence | Grade below Strong + strict mode | `LOW_RETRIEVAL_CONFIDENCE` |

---

## Telemetry: Dual Logging Strategy

Every request is logged to **two independent systems**:

```
                              ┌──────────────────────────┐
                              │     PostgreSQL            │
 execute_ask() ──────────────│   telemetry table        │  ◄── You own this data
    │                         │   (billing, audit, legal) │
    │  record_telemetry()     └──────────────────────────┘
    │
    │                         ┌──────────────────────────┐
    └── @observe decorators ──│   Langfuse Cloud         │  ◄── Debugging UI
                              │   (trace viewer, prompt   │
                              │    playground, analytics)  │
                              └──────────────────────────┘
                                        │
                              langfuse_trace_id stored
                              in telemetry table for
                              cross-reference
```

### Telemetry Table (PostgreSQL) — You Own This

Every request creates one row. No external dependency. Stays in your database.

| Column | Purpose | Example |
|--------|---------|---------|
| `request_id` | Primary key | `a1b2c3d4-...` |
| `tenant_id` | Tenant isolation | `acme-legal` |
| `matter_id` | Matter isolation | `case-2024-001` |
| `model_id` | Which LLM answered | `gpt-5-mini` |
| `tokens_in` / `tokens_out` | Token usage | `1250` / `85` |
| `cost_est` | Estimated cost (USD) | `0.0042` |
| `latency_ms` | End-to-end latency | `1850` |
| `refusal_code` | Why system refused (if it did) | `LOW_RETRIEVAL_CONFIDENCE` |
| `trace_metadata` | JSON: retrieval scores, verifier result, cost breakdown | `{...}` |
| `langfuse_trace_id` | Link to Langfuse trace | `trace-xyz-...` |
| `prompt_version` / `retrieval_version` | Version tracking for A/B testing | `v3.1.0` |

### Langfuse (Optional) — Debugging UI

When enabled, `@observe` decorators create a nested trace waterfall:

```
execute_ask                  (trace root — tenant, session, request_id)
  ├── hybrid_search          (mode: azure/local, result_count, latency_ms)
  │   └── embed_texts        (model: text-embedding-3-large, tokens, embeddings_mode)
  └── verify_relevance       (model: gpt-5-mini, tokens_in, tokens_out, verdict, latency_ms)
      └── call_openai        (generation span — model, token counts)
```

**PII safety:** All `@observe` decorators use `capture_input=False, capture_output=False`. Only metadata (model names, token counts, latencies, scores) is sent to Langfuse. No document content or user questions leave the system.

**Error safety:** All Langfuse calls wrapped in `try/except`. Langfuse outage never breaks the request pipeline.

---

## Version Tracking

Every response includes a `version_snapshot` for reproducibility:

```json
{
  "request_id": "a1b2c3d4-...",
  "docs_snapshot_id": "snap_7f8a9b0c1d2e",
  "prompt_version": "v3.1.0",
  "verifier_prompt_version": "2.0.1",
  "retrieval_version": "v1.0.0",
  "model_id": "gpt-5-mini",
  "parser_mode": "marker"
}
```

This means: for any past answer, you can identify exactly which document snapshot, prompt version, model, and retrieval algorithm produced it.

---

## Architecture Diagram

```
┌─────────────┐     HTTPS      ┌─────────────────────────────────────────────┐
│  Next.js    │ ◄─────────────│          Azure Container Apps               │
│  (Vercel)   │               │                                             │
│             │               │  FastAPI API                                │
│  - Q&A UI   │    /v1/ask    │  ┌─────────┐  ┌───────────┐  ┌──────────┐  │
│  - PDF view │──────────────│  │ Policy  │─│ Retrieval │─│ Verifier │  │
│  - Citations│               │  │ Gate    │  │ (hybrid)  │  │GPT-5-mini│  │
│             │               │  └─────────┘  └───────────┘  └──────────┘  │
└─────────────┘               │       │             │              │        │
                              │       ▼             ▼              ▼        │
                              │  ┌──────────────────────────────────────┐   │
                              │  │  telemetry table (PostgreSQL)       │   │
                              │  │  + Langfuse Cloud (optional)        │   │
                              │  └──────────────────────────────────────┘   │
                              └────────────────────────────────────────────┘
                                        │                │
                              ┌─────────┘                └──────────┐
                              ▼                                     ▼
                    ┌──────────────────┐              ┌──────────────────┐
                    │  Azure PostgreSQL │              │  Azure AI Search │
                    │  (docs, chunks,   │              │  (HNSW + BM25 +  │
                    │   telemetry,      │              │   semantic        │
                    │   sessions)       │              │   reranker)       │
                    └──────────────────┘              └──────────────────┘
                                                              │
                                                     ┌────────┘
                                                     ▼
                                           ┌──────────────────┐
                                           │  Azure OpenAI    │
                                           │  - GPT-5-mini    │
                                           │  - text-embed-   │
                                           │    3-large (vec)  │
                                           └──────────────────┘
```

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Refuse rather than hallucinate** | Legal domain — wrong answers have real consequences |
| **Dual logging (DB + Langfuse)** | Billing/audit data stays in your DB; Langfuse is optional for debugging |
| **PII never leaves the system** | Document content and user questions not sent to telemetry services |
| **Every query version-tracked** | Any past answer reproducible with exact prompt, model, and doc snapshot |
| **Tenant + matter isolation on every query** | Multi-tenant from day one — no data leakage between firms or cases |
| **LLM verification of retrieval** | GPT-5-mini independently confirms chunk answers the question before citing |
