# STATUS.md

Last updated: 2026-01-18

---

## Current Phase: 1 — Core RAG

**Goal:** Working Q&A with citations  
**Target:** End of January 2026

---

## Now

| Task | FR | Branch | Started | Notes |
|------|-----|--------|---------|-------|
| Dev tooling setup | FR-060–063 | — | 01-18 | ruff, mypy, pytest, security tests |

## Next (Priority Order)

| Task | FR | Depends On | Notes |
|------|-----|------------|-------|
| Evidence-grounded answers | FR-023 | FR-021 | Every claim needs `[N]` citation |
| Confidence gating | FR-024 | FR-023 | Threshold 0.70; refuse below |
| Citation validation | FR-025 | FR-024 | Post-LLM check; ≥90% text match |

## Done (This Week)

| Task | FR | Date | Notes |
|------|-----|------|-------|
| Chunking with offsets | FR-013 | 01-18 | page_end, char_start, char_end through pipeline |
| Security hardening | — | 01-18 | H-1: injection detection, H-2: span filtering, H-3: LLM timeout |
| Dev tooling FRs | FR-060–063 | 01-18 | Added to REQUIREMENTS.md |

## Blocked

| Task | FR | Waiting On | Since | Action |
|------|-----|------------|-------|--------|
| — | — | — | — | — |

## Shipped (Phase 1)

| Task | FR | PR | Date |
|------|-----|-----|------|
| Project structure | — | #1 | 01-15 |
| Document upload | FR-010 | #2 | 01-16 |
| PDF text extraction + OCR | FR-012 | #3 | 01-16 |
| Hybrid retrieval (BM25 + vector + RRF) | FR-021 | — | 01-18 |

---

## Phase 1 Progress

| FR | Requirement | Status |
|----|-------------|--------|
| FR-010 | Upload PDFs/images | ✅ Shipped |
| FR-012 | Text extraction + OCR | ✅ Shipped |
| FR-013 | Chunking with page/char offsets | ✅ Shipped |
| FR-021 | Hybrid retrieval (BM25 + vector) | ✅ Shipped |
| FR-023 | Evidence-grounded answers | ⬜ Next |
| FR-024 | Confidence refusal | ⬜ Next |
| FR-025 | Citation validation | ⬜ Next |

**Remaining:** 3 of 7 FRs

---

## Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 01-18 | **Dev tooling FRs added** (FR-060–063) | Need ruff, mypy, pytest before more features |
| 01-18 | **Security hardening before commit** | /wsskeptic review found 3 HIGH issues; fixed |
| 01-18 | **Provider abstraction planned** (NFR-032, 034, 035) | Support Azure + pgvector + others via config; interfaces in ARCHITECTURE.md |
| 01-17 | **pgvector target for Phase 2** | Azure AI Search works but latency concerns; pgvector simpler long-term |
| 01-16 | Confidence threshold 0.70 | Per architecture review |
| 01-15 | Azure stack for MVP | Fastest path to working demo |

> **Current Stack:** Azure AI Search + Azure OpenAI (see CLAUDE.md)
> **Target Stack:** Config-driven providers (see ARCHITECTURE.md)

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
| 4. Provider Abstraction | NFR-032, NFR-034, NFR-035 | Config-driven Search/LLM/Embeddings |
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
