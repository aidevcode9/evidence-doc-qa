# STATUS.md

Last updated: 2026-01-22

---

## Current Phase: 5 — Auth 🔜 NOT STARTED

**Goal:** Login, SSO, admin functionality
**Next:** FR-050, FR-051, FR-052

---

## Now

| Task | FR | Branch | Started | Notes |
|------|-----|--------|---------|-------|
| — | — | — | — | Phase 4 complete, awaiting next task |

## Next (Phase 5)

| Task | FR | Depends On | Notes |
|------|-----|------------|-------|
| User login flow | FR-050 | — | OAuth2/OIDC or custom |
| SSO integration | FR-051 | FR-050 | Azure AD, Okta, etc. |
| Admin dashboard | FR-052 | FR-050 | User management UI |

## Done (This Week)

| Task | FR | Date |
|------|-----|------|
| **Provider integration tests** | NFR-032, 034, 035 | 01-22 |
| **Provider config in .env.example** | NFR-032, 034, 035 | 01-22 |
| **Provider abstraction interfaces** | NFR-032, 034, 035 | 01-22 |
| **LLMClient + AzureOpenAIClient** | NFR-032 | 01-22 |
| **EmbeddingClient + Local/Azure implementations** | NFR-035 | 01-22 |
| **SearchClient + Local/Azure implementations** | NFR-034 | 01-22 |
| **Security hardening (wsskeptic review)** | — | 01-22 |
| **UUID validation for filter injection prevention** | — | 01-22 |
| **Query length limits (MAX_QUERY_LENGTH)** | — | 01-22 |
| **LLM retry with exponential backoff** | — | 01-22 |
| **Matter-level permissions** | FR-004 | 01-22 |
| **MatterAssignment model + migration 0006** | FR-004 | 01-22 |
| **user_has_matter_access() function** | FR-004 | 01-22 |
| **Context validates matter access** | FR-004 | 01-22 |
| **Admin bypasses matter permission check** | FR-004 | 01-22 |
| **RBAC with roles** | FR-003 | 01-22 |
| **Role enum + permissions** | FR-003 | 01-22 |
| **User model + migration 0005** | FR-003 | 01-22 |
| **RequestContext with user_id/user_role** | FR-003 | 01-22 |
| **Tenant/Matter isolation enforcement** | FR-001, FR-002 | 01-22 |
| **RequestContext dependency for header extraction** | FR-001, FR-002 | 01-22 |
| **Azure Search tenant/matter OData filters** | FR-001, FR-002 | 01-22 |
| **All routers use context dependency** | FR-001, FR-002 | 01-22 |
| **Add tenant_id to all models** | FR-001 | 01-21 |
| **Add matter_id to all models** | FR-002 | 01-21 |
| **Update load_chunks with tenant/matter filters** | FR-001, FR-002 | 01-21 |
| **Update load_index_records with tenant/matter filters** | FR-001, FR-002 | 01-21 |
| **Alembic migration 0004 for tenant/matter isolation** | FR-001, FR-002 | 01-21 |

## Blocked

| Task | FR | Waiting On | Since | Action |
|------|-----|------------|-------|--------|
| — | — | — | — | — |

## Shipped (Phase 2)

| Task | FR | PR | Date |
|------|-----|-----|------|
| **UI displays citations (doc, page, excerpt)** | FR-030 | — | 01-21 |
| **Click citation → document viewer** | FR-031 | — | 01-21 |
| **Export Q&A with citations (PDF/DOCX)** | FR-032 | — | 01-21 |
| **Security hardening (IDOR, temp file cleanup, rate limit)** | FR-032 | — | 01-21 |
| **Frontend export fix (fetch with headers)** | FR-032 | — | 01-21 |
| **Alembic migration for session tables** | FR-032 | — | 01-21 |

> ✅ **Phase 2 Complete:** All Citations UI features shipped. Session-based Q&A storage + PDF/DOCX export with citations. Security hardened per adversarial review.

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
| FR-032 | Export citations (PDF/DOCX) | ✅ Shipped |

**Phase 2 Complete:** 3/3 Citations UI features shipped.

---

## Phase 3 Progress

| FR | Requirement | Status |
|----|-------------|--------|
| FR-001 | Multi-tenant support (tenant_id) | ✅ Shipped |
| FR-002 | Multi-matter support (matter_id) | ✅ Shipped |
| FR-003 | RBAC with roles | ✅ Shipped |
| FR-004 | Matter-level permissions | ✅ Shipped |

**Phase 3 Complete:** 4/4 Multi-tenancy features shipped.

---

## Phase 4 Progress

| NFR | Requirement | Status |
|-----|-------------|--------|
| NFR-032 | LLM provider abstracted behind interface | ✅ Shipped |
| NFR-034 | Search/retrieval abstracted behind interface | ✅ Shipped |
| NFR-035 | Embeddings abstracted behind interface | ✅ Shipped |

**Phase 4 Complete:** 3/3 Provider abstraction features shipped. Config-driven provider selection via LLM_PROVIDER, SEARCH_PROVIDER, EMBEDDINGS_MODE.

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
| 01-21 | **Session-based Q&A storage for export** | qa_sessions + qa_messages tables; messages stored automatically; enables PDF/DOCX export |
| 01-21 | **IDOR prevention via session header** | X-DocQA-Session header required for export; prevents cross-session data access |
| 01-21 | **Alembic for schema migrations** | Standard migration tooling; documented in ARCHITECTURE.md; `0003_add_qa_session_tables.py` |
| 01-21 | **Tenant/Matter isolation columns** | FR-001/FR-002: All 6 models now have tenant_id + matter_id; indexed; migration `0004` |
| 01-22 | **Header-based tenant context (MVP)** | X-Tenant-Id/X-Matter-Id headers; JWT extraction planned for Phase 4 |
| 01-22 | **Matter-level permissions via MatterAssignment** | Users must be explicitly assigned to matters; admin bypasses check (FR-004) |
| 01-22 | **Provider abstraction pattern** | Abstract interfaces + factory functions; swap providers via SEARCH_PROVIDER, LLM_PROVIDER, EMBEDDINGS_MODE env vars |
| 01-22 | **UUID validation for identifiers** | Prevent filter injection; alphanumeric+hyphens only, max 64 chars |

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
