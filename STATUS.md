# STATUS.md

Last updated: 2026-01-18 (evening)

---

## Current Phase: 1 — Core RAG

**Goal:** Working Q&A with citations  
**Target:** End of January 2026

---

## Now

| Task | FR | Branch | Started | Notes |
|------|-----|--------|---------|-------|
| Citation validation | FR-025 | feat/citation-validation | 01-18 | Post-LLM check; ≥90% text match |

## Next (Priority Order)

| Task | FR | Depends On | Notes |
|------|-----|------------|-------|
| OCR + image support | FR-010, FR-012 | — | Implement ParserClient (NFR-036); LlamaParse (cloud) or Marker (on-prem) |
| Type annotations cleanup | NFR-040 | — | Fix 130+ mypy --strict errors; add generic type params, type stubs |

## Blocked

| Task | FR | Waiting On | Since | Action |
|------|-----|------------|-------|--------|
| — | — | — | — | — |

## Shipped (Phase 1)

| Task | FR | PR | Date |
|------|-----|-----|------|
| Project structure | — | #1 | 01-15 |
| Document upload (PDF only) | FR-010 | #2 | 01-16 |
| PDF text extraction (digital only) | FR-012 | #3 | 01-16 |
| Hybrid retrieval (BM25 + vector + RRF) | FR-021 | — | 01-18 |
| Chunking with page/char offsets | FR-013 | — | 01-18 |
| Evidence-grounded answers + Confidence gating | FR-023, FR-024 | — | 01-18 |

> ⚠️ **FR-010/FR-012 Partial:** Digital PDFs only. Image upload and OCR for scanned docs not yet implemented.

---

## Phase 1 Progress

| FR | Requirement | Status |
|----|-------------|--------|
| FR-010 | Upload PDFs/images | ⚠️ Partial (PDFs only; images crash) |
| FR-012 | Text extraction + OCR | ⚠️ Partial (digital PDFs; no OCR) |
| FR-013 | Chunking with page/char offsets | ✅ Shipped |
| FR-021 | Hybrid retrieval (BM25 + vector) | ✅ Shipped |
| FR-023 | Evidence-grounded answers | ✅ Shipped |
| FR-024 | Confidence refusal | ✅ Shipped |
| FR-025 | Citation validation | 🔄 In Progress |

**Remaining:** 1 of 7 FRs (+ FR-010/FR-012 need OCR + image support)

---

## Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 01-19 | **Parser options: LlamaParse (cloud), Marker (on-prem fast), Docling (tables)** | LlamaParse best OCR; Marker 25pg/s with --use_llm; Docling 97.9% on complex tables |
| 01-18 | **FR-010/FR-012 partial for MVP** | Digital PDFs work; OCR + image support deferred; scanned docs return empty text |
| 01-18 | **Template-based multi-citation** (FR-023) | MVP approach; up to 3 citations with `[N]` markers; LLM synthesis (FR-026) deferred |
| 01-18 | **Configurable threshold via .env** (FR-024) | DOCQA_CONFIDENCE_THRESHOLD=0.70 default; exposed in API response for UI display |
| 01-18 | **Provider abstraction planned** (NFR-032, 034, 035, 036) | Support Azure + pgvector + others via config; interfaces in ARCHITECTURE.md |
| 01-17 | **pgvector target for Phase 2** | Azure AI Search works but latency concerns; pgvector simpler long-term |
| 01-16 | Confidence threshold 0.70 | Per architecture review |
| 01-15 | Azure stack for MVP | Fastest path to working demo |

> **Current Stack:** Azure AI Search + Azure OpenAI + pypdf (see CLAUDE.md)
> **Target Stack:** Config-driven providers — LlamaParse/Marker/Docling for parsing (see ARCHITECTURE.md)

## Risks / Unknowns

| Risk | Impact | Mitigation | Status |
|------|--------|------------|--------|
| Hybrid retrieval latency | p95 > 3s | Load test before demo | ⬜ TODO |
| OCR accuracy on scanned docs | Bad citations | Test with real docs; add to EVALS.md | ⬜ TODO |
| Claude rate limits | Demo fails | Request increase; add caching | ⬜ TODO |
| Multi-page table extraction | Missing data | Test with sample contracts | ⬜ TODO |

## Kill Criteria

| Condition | Deadline | Action |
|-----------|----------|--------|
| p95 latency > 3s after optimization | 01-31 | Simplify retrieval or change arch |
| Citation accuracy < 95% | 01-31 | Revisit validation approach |
| No customer interest after demo | 02-15 | Pivot market or product |

---

## Upcoming Phases (Reference)

| Phase | FRs/NFRs | Goal |
|-------|----------|------|
| 2. Citations UI | FR-030, FR-031, FR-032 | Clickable citations, export |
| 3. Multi-tenancy | FR-001–004, FR-020 | Tenant + matter isolation |
| 4. Provider Abstraction | NFR-032, NFR-034, NFR-035, NFR-036 | Config-driven Parser/Search/LLM/Embeddings |
| 5. Auth | FR-050–052 | Login, SSO, admin |
| 6. Audit | FR-040–043 | Logging, retention, deletion |
| 7. Polish | FR-011, FR-014, FR-015, FR-022, FR-033 | Dedup, metadata, reranker |
| 8. NFRs | NFR-001–022 | Security, perf, reliability |

---

## Archive

<details>
<summary>Week of 01-08</summary>

| Task | PR | Date |
|------|-----|------|
| Initial repo setup | — | 01-08 |
| Requirements doc v1 | — | 01-10 |

</details>
