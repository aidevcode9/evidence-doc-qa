# Architecture Review: Is This Solving the Right Problem?

**Date:** 2026-03-31
**Question:** Does this architecture actually solve the problem of retrieving documents for lawyers by matter?

**Status note:** Several foundation items identified here shipped later on
2026-03-31: Azure Search timeout, DB QueuePool, safer auth defaults, matter
creation/access hardening, per-user/per-matter session isolation, zero-doc
matter visibility, and the matter dashboard follow-up fixes. The remaining
sections below should be read as the open roadmap after those changes.

---

## The Short Answer

The retrieval works. The architecture around it doesn't match how lawyers actually work.

The system correctly answers "given a question and a matter, find the relevant chunk and cite it." That's the core RAG loop, and it's implemented solidly: hybrid search, verification, citation validation, evidence grading. The technical pipeline is sound.

What's missing is everything around that loop -- the parts that make it a product lawyers would actually use instead of a technical demo.

---

## What the Architecture Gets Right

### 1. Evidence-First Design
The fundamental design decision -- every answer requires a retrievable, verifiable citation or the system refuses -- is correct for legal use. Lawyers cannot use a system that hallucinates. The confidence gating (`policy.py`), evidence grading (`evidence.py`), and citation validation (`evidence.py:139-188`) create a trust foundation that most legal AI products lack.

### 2. Matter-Level Isolation
Legal work is organized by matter (case). The decision to make `matter_id` a first-class filter on every query, every table, and every search request is architecturally correct. This maps to how law firms organize: documents belong to cases, not to users.

### 3. Tenant Isolation
The `tenant_id` on every row prevents cross-firm data leakage. This is non-negotiable for legal SaaS and it's implemented at the database level, not just the API level. Azure Search filters include `tenant_id` in every query.

### 4. Audit Trail
Immutable audit events with `user_id`, `tenant_id`, `matter_id`, and `timestamp` satisfy basic legal compliance requirements. The retention policy system (configurable per tenant, per resource type) is a thoughtful addition.

---

## What the Architecture Gets Wrong

### 1. The Verification Step Is Architecturally Redundant

The pipeline does three forms of relevance assessment:

```
Step 1: Azure Semantic Reranker (cross-encoder)
  "Given this query and this document chunk, how relevant is the chunk?"
  Output: Score 0-4

Step 2: LLM Verification (GPT-5-mini)
  "Given this question and this chunk, does the chunk contain the answer?"
  Output: YES/NO with span extraction

Step 3: Evidence Grading (rule-based)
  "Given reranker score, verification status, overlap, and RRF score, grade A/B/C"
  Output: Grade
```

Steps 1 and 2 are asking the same question in different ways. The Azure semantic reranker IS a cross-encoder transformer model trained on relevance. The LLM verification is a general-purpose language model re-evaluating relevance. You're paying 2-6 seconds of latency and $0.001-0.003 per query for a second opinion that agrees with the first 90%+ of the time.

**Recommendation:** Use the LLM for what it's uniquely good at -- span extraction and answer synthesis -- not binary relevance classification. The reranker already handles relevance. Restructure:

```
Azure Search (BM25 + vector + reranker) --> relevance ranking
  --> Confidence filter (reranker score threshold)
    --> LLM Answer Synthesis (one call, not verification)
      "Given this question and these top 3 chunks, write an answer with citations"
    --> Citation validation (verify spans exist in source)
```

This eliminates the verification loop entirely, replaces it with a single LLM call that produces the final answer, and uses citation validation as the safety net (which already exists in `evidence.py`).

### 2. No Conversational Memory Within a Matter

The system answers one question at a time. Each `/v1/ask` request starts fresh. But legal document review is inherently conversational:

```
Attorney: "What is the indemnification cap in the merger agreement?"
System:   "Section 8.2 states the cap is $15M [1]"
Attorney: "Does that include environmental liabilities?"
System:   ??? (no context from previous question)
```

The `qa_sessions` and `qa_messages` tables exist for storage, but the retrieval pipeline doesn't use conversation history. The LLM prompt doesn't include prior Q&A. This means every question must be fully self-contained, which is not how lawyers think.

**What's needed:**
- Pass last 3-5 QA messages as context to the LLM
- Use conversation history to expand ambiguous queries ("it" -> "the indemnification cap")
- This is a prompt engineering change, not an architecture change -- the data model already supports it

### 3. No Document-Level Understanding

The system chunks documents and retrieves chunks. It never builds a holistic understanding of a document. This matters because lawyers ask questions like:

- "Summarize the key terms of this agreement" (requires full document, not a chunk)
- "Compare the indemnification provisions across these three contracts" (requires multiple documents)
- "What's unusual about this lease compared to standard commercial leases?" (requires domain knowledge + full document)

These are the high-value questions. The current chunk-level retrieval can't answer them.

**What's needed:**
- Document-level embeddings in addition to chunk-level
- A "summarize" endpoint that operates on full documents, not just chunks
- Cross-document comparison capabilities
- This is a significant feature addition, not a fix

### 4. No Privileged Document Handling

Legal documents have privilege designations (attorney-client privilege, work product doctrine). The data model has `metadata_json` on documents but no first-class privilege flag. A paralegal searching across a matter might surface privileged documents that shouldn't appear in certain exports or client-facing reports.

The `metadata_json` field could contain privilege flags, but there's no enforcement in the retrieval pipeline. `retrieval.py` doesn't filter by privilege status. `evidence.py` doesn't flag privileged content.

**What's needed:**
- `privilege_status` column on `documents` (or in metadata with index)
- Retrieval filter: exclude privileged documents from non-privileged searches
- Export filter: strip privileged content from client-facing exports
- Audit: log when privileged documents are accessed

### 5. No Document Versioning

Legal documents go through drafts. A merger agreement might have v1 (initial draft), v2 (redline), v3 (execution copy). The current system deduplicates by SHA256 (`doc_sha256`), which means each version is a separate document. But there's no way to:

- Track that v1, v2, v3 are versions of the same document
- Ask "what changed between v2 and v3?"
- Pin a question to a specific version vs. "latest"

The `docs_snapshot_id` concept is close but serves a different purpose (deduplication, not versioning).

### 6. The "Which Documents Can I See" Problem

You identified this as confusing. Here's why:

The current access model is:
```
User signs in --> JWT has tenant_id + user_id + role
User picks a matter --> X-Matter-Id header
System checks --> Does user have MatterAssignment for this matter?
If yes --> User sees ALL documents in that matter
If admin --> User sees ALL documents in ALL matters
```

The confusion is that there's no middle ground:
- You either see everything in a matter or nothing
- You can't share a specific document with someone without giving them the entire matter
- There's no "view-only on this document but full access on that one"

For small firms with 2-3 attorneys per matter, this is fine. For large firms with 50+ attorneys and complex case teams, this is too coarse.

**What's missing:**
- Document-level permissions (optional, for firms that need it)
- Sharing a document or set of documents without sharing the entire matter
- "Review sets" -- curated collections of documents within a matter for specific reviewers

This is a Phase 3+ feature, not a bug. But it's worth knowing the access model is coarse-grained before selling to large firms.

---

## Architecture Comparison: What Best-in-Class Legal AI Does (2026)

| Capability | Evidence-Bound | Best-in-Class (Relativity, Casetext, Harvey) |
|------------|---------------|---------------------------------------------|
| Chunk-level retrieval | Yes | Yes |
| Document-level understanding | No | Yes (full-doc embeddings, summaries) |
| Cross-document analysis | No | Yes (comparative analysis) |
| Conversation memory | Storage only | Active context (multi-turn) |
| Privilege handling | No | Yes (privilege log, auto-detection) |
| Document versioning | No | Yes (version chains, redline comparison) |
| Batch review | No | Yes (review sets, bulk Q&A) |
| Citation verification | Yes (strong) | Varies (some trust LLM output) |
| Multi-tenant isolation | Yes | Yes |
| On-prem deployment | Yes (Ollama tier) | Rare (Harvey does, most don't) |

**Evidence-Bound's competitive advantages:**
1. On-prem option (Ollama + pgvector) -- most competitors are cloud-only
2. Evidence-first refusal policy -- stronger citation validation than most
3. Provider abstraction -- swap LLM/search/parser without code changes
4. Open-source friendly stack -- no vendor lock-in to proprietary vector DBs

**Evidence-Bound's gaps:**
1. No document-level intelligence (the "summarize this contract" use case)
2. No conversational context (multi-turn Q&A)
3. No privilege handling
4. Single-question, single-answer UX (not batch review)

---

## Architectural Debt Inventory

| Debt Item | Location | Impact | Effort to Fix |
|-----------|----------|--------|---------------|
| Sync pipeline | `ask_service.py` | Blocks scaling | Large (async migration) |
| urllib.request | `retrieval.py`, `verification.py`, `embeddings.py` | No connection reuse | Medium (httpx swap) |
| 700-line execute_ask() | `ask_service.py` | Hard to modify/test | Medium (decompose) |
| In-memory caches | `retrieval.py`, `cache.py` | Don't scale horizontally | Medium (Redis) |
| No request deadline | `ask_service.py` | No latency guarantee | Small (add timeout) |
| Global mutable state | `_BM25_CACHE`, `_PROMPT_TEXT` | Thread safety risk | Small (use lru_cache) |
| config.py flat list | `config.py` | Error-prone, no validation | Medium (pydantic Settings) |
| Unbounded BM25 cache | `retrieval.py:509-515` | Memory leak | Small (add TTL/max size) |
| Azure Search API 2023-11-01 | `config.py:93` | Missing vector compression | Small (bump version) |

---

## Recommended Architecture Evolution

### Phase 8a: Remaining Foundation Work (post 03-31, 1-2 weeks)
- Finish the remaining latency fixes from `LATENCY_FIXES.md` (high-confidence auto-verify, `httpx`, Redis follow-up)
- Add request deadline/timeout to `execute_ask()`
- Add load tests for NFR-011 and NFR-012

### Phase 8b: Restructure the Pipeline (2-3 weeks)
- Decompose `execute_ask()` into: `retrieve()`, `verify()`, `synthesize()`, `cite()`
- Replace verification loop with single LLM answer synthesis call
- Add conversation context to LLM prompt (pass last 3 messages)
- Replace urllib with httpx

### Phase 9: Document Intelligence (4-6 weeks)
- Document-level embeddings and summaries
- "Summarize this document" endpoint
- Cross-document comparison endpoint
- Privilege flag on documents with retrieval filtering

### Phase 10: Production Hardening (2-4 weeks)
- Async pipeline migration
- Redis cache layer
- Circuit breakers on external services
- Structured logging
- Horizontal scaling validation

---

## The Fundamental Question

> Is this actually solving the problem of retrieving documents for lawyers by matter?

**Yes, for the narrow use case of "ask a question about documents in this case."** The retrieval pipeline works. The citation validation is strong. The matter isolation is correct.

**No, for the broader use case of "help lawyers understand their cases."** Lawyers don't just ask questions -- they review, compare, summarize, and analyze. The system does one of those things well. The other three are missing entirely.

The architecture is a solid foundation for a question-answering product. Making it a document intelligence product requires the additions outlined in Phase 9 above. The priority question is: do you need all of that for a beta pilot, or can you sell the Q&A capability on its own?

For a beta pilot with 5-10 attorneys: Fix the latency, add conversation context, and ship Q&A only. That's a viable product for firms who already know which questions they want to ask.

For a paid product competing with Harvey/Casetext: You need document-level intelligence, batch review, and privilege handling. That's 2-3 more phases of work.
