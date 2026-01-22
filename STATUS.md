# STATUS.md

Last updated: 2026-01-21 (Phase 2 Started)

---

## Current Phase: 2 — Citations UI

**Goal:** Clickable citations, document viewer, export
**Target:** End of January 2026

---

## Now

| Task | FR | Branch | Started | Notes |
|------|-----|--------|---------|-------|
| — | — | — | — | — |

## Next (Priority Order)

| Task | FR | Depends On | Notes |
|------|-----|------------|-------|
| Citation export (copy/download) | FR-032 | FR-030, FR-031 | Export citations to clipboard or file |

## Blocked

| Task | FR | Waiting On | Since | Action |
|------|-----|------------|-------|--------|
| — | — | — | — | — |

## Shipped (Phase 2)

| Task | FR | PR | Date |
|------|-----|-----|------|
| **UI displays citations (doc, page, excerpt)** | FR-030 | — | 01-21 |
| **Click citation → document viewer** | FR-031 | — | 01-21 |

> ✅ **FR-030/FR-031 Complete:** Citations display in EvidencePanel. Clicking citation opens document viewer modal at cited page.

## Shipped (Phase 1)

| Task | FR | PR | Date |
|------|-----|-----|------|
| Project structure | — | #1 | 01-15 |
| Document upload (PDF only) | FR-010 | #2 | 01-16 |
| PDF text extraction (digital only) | FR-012 | #3 | 01-16 |
| Hybrid retrieval (BM25 + vector + RRF) | FR-021 | — | 01-18 |
| Chunking with page/char offsets | FR-013 | — | 01-18 |
| Evidence-grounded answers + Confidence gating | FR-023, FR-024 | — | 01-18 |
| Citation validation | FR-025 | — | 01-19 |
| OCR + Image support | FR-010, FR-012, NFR-036 | — | 01-20 |
| ParserClient abstraction | NFR-036 | — | 01-20 |
| Eval suite reorganization | — | — | 01-20 |
| Type annotations (mypy --strict) | NFR-040 | — | 01-21 |
| pytest-asyncio configuration | — | — | 01-21 |
| Dev dependencies separation | NFR-041 | — | 01-21 |

> ✅ **Phase 1 Complete:** PDF + image upload with OCR support via Marker (default) or LlamaParse (cloud).

---

## Phase 2 Progress

| FR | Requirement | Status |
|----|-------------|--------|
| FR-030 | UI displays citations | ✅ Shipped |
| FR-031 | Click citation → document viewer | ✅ Shipped |
| FR-032 | Export citations | ⬜ Next |

**Phase 2 In Progress:** 2/3 Citations UI features shipped.

---

## Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 01-20 | **Marker as default parser** | Marker is fast (25pg/s on GPU), open-source, supports OCR; LlamaParse available for cloud OCR |
| 01-20 | **Eval suites by category** | Separate JSONL files per category (answerable, refusals, adversarial, etc.) for maintainability |
| 01-20 | **File size limit 50MB** | `MAX_UPLOAD_SIZE_MB` env var; prevents memory issues; returns HTTP 413 on violation |
| 01-20 | **OCR warning on low text extraction** | Returns warning when < 10 chars extracted; alerts user to potential OCR failures |
| 01-19 | **Parser options: LlamaParse (cloud), Marker (on-prem fast), Docling (tables)** | LlamaParse best OCR; Marker 25pg/s with --use_llm; Docling 97.9% on complex tables |
| 01-18 | **Template-based multi-citation** (FR-023) | MVP approach; up to 3 citations with `[N]` markers; LLM synthesis (FR-026) deferred |
| 01-18 | **Configurable threshold via .env** (FR-024) | DOCQA_CONFIDENCE_THRESHOLD=0.70 default; exposed in API response for UI display |
| 01-18 | **Provider abstraction planned** (NFR-032, 034, 035, 036) | Support Azure + pgvector + others via config; interfaces in ARCHITECTURE.md |
| 01-17 | **pgvector target for Phase 2** | Azure AI Search works but latency concerns; pgvector simpler long-term |
| 01-16 | Confidence threshold 0.70 | Per architecture review |
| 01-15 | Azure stack for MVP | Fastest path to working demo |
| 01-21 | **Iframe PDF viewer with page targeting** | Simple, reliable; native PDF support with #page= fragment; fallback to new tab |

> **Current Stack:** Azure AI Search + Azure OpenAI + configurable parser
> **Parser options:** `PARSER_PROVIDER=marker` (default, OCR), `pypdf` (digital only), `llamaparse` (cloud OCR)

## Risks / Unknowns

| Risk | Impact | Mitigation | Status |
|------|--------|------------|--------|
| Hybrid retrieval latency | p95 > 3s | Load test before demo | ⬜ TODO |
| OCR accuracy on scanned docs | Bad citations | Marker OCR implemented; evals added | ✅ Mitigated |
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
