# STATUS.md

Last updated: 2026-03-20

---

## Current Phase: 8 — NFRs (Performance & Scaling)

**Goal:** Query latency p95 < 8s, 50 concurrent users, rate limiting, metrics
**Progress:** NFR-011, NFR-012 in progress

---

## Now

| Task | FR | Branch | Started | Notes |
|------|-----|--------|---------|-------|
| Query latency p95 < 8s (metrics, tracing, targets) | NFR-011 | main | 03-15 | Enhanced metrics endpoint, latency breakdown, OTEL custom metrics |
| 50 concurrent users + horizontal scaling | NFR-012 | main | 03-15 | Rate limiting, async FastAPI, cache thread-safety, load testing |

## Next

| Task | FR | Depends On | Notes |
|------|-----|------------|-------|
| Security NFRs | NFR-001–022 | — | Phase 8 |

## Done (This Week)

| Task | FR | Date |
|------|-----|------|
| **Test suite stability: 582 pass, 0 fail (was 53 fail + 13 error)** | FR-060 | 03-20 |
| **409 duplicate upload UX fix (shows existing document name)** | FR-011 | 03-15 |
| **401 demo mode console noise fix (fetchCapabilities pattern)** | FR-054 | 03-15 |
| **Slash commands reorganization (wsauto, persona frontmatter)** | INFRA | 03-15 |
| **NFR-022 observability + caching (OTEL metrics, Langfuse, cost tracking)** | NFR-022 | 03-15 |
| **Async ingestion status (queued→processing→ready/failed)** | FR-015 | 03-15 |
| **Optional local reranker (term+phrase analysis post-RRF)** | FR-022 | 03-15 |
| **Cited-only packet export (PDF/DOCX)** | FR-033 | 03-15 |
| **Document deduplication (SHA256 matter-level)** | FR-011 | 03-15 |
| **Metadata extraction (title, author, page_count)** | FR-014 | 03-15 |
| **User menu with sign out** | FR-056 | 03-15 |
| **Fix LANGFUSE_HOST + PARSER_PROVIDER in CI workflow** | INFRA | 03-15 |
| **Auth bypass mode for demos (validated)** | FR-054 | 03-15 |
| **PyPDF-only mode (validated)** | FR-055 | 03-15 |

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
| NFR-033 | Default providers by tier (4 LLM providers) | ✅ Shipped |
| NFR-034 | Search/retrieval abstracted behind interface | ✅ Shipped |
| NFR-035 | Embeddings abstracted behind interface | ✅ Shipped |

**Phase 4 Complete:** 4/4 Provider abstraction features shipped. LLM providers: azure_openai, anthropic, gemini, ollama. Config-driven selection via LLM_PROVIDER, SEARCH_PROVIDER, EMBEDDINGS_MODE.

---

## Phase 5 Progress

| FR | Requirement | Status |
|----|-------------|--------|
| FR-050 | User login flow (OAuth2/JWT) | ✅ Shipped |
| FR-051 | SSO integration (OIDC) | ✅ Shipped |
| FR-052 | Admin dashboard | ✅ Shipped |
| FR-053 | Frontend login UI + Google SSO | ✅ Shipped |

**Phase 5 Complete:** 4/4 Auth features shipped. JWT + Google SSO login, httpOnly cookies, protected routes, wsskeptic approved.

---

## Phase 6 Progress

| FR | Requirement | Status |
|----|-------------|--------|
| FR-040 | Audit logging | ✅ Shipped |
| FR-041 | Immutable logs + export | ✅ Shipped |
| FR-042 | Retention policies | ✅ Shipped |
| FR-043 | Hard delete workflow | ✅ Shipped |

**Phase 6 Complete:** 4/4 Audit features shipped. Audit events with PII redaction, CSV export, configurable retention per tenant, matter hard delete with cascading cleanup.

---

## NFR Observability Progress

| NFR | Requirement | Status |
|-----|-------------|--------|
| NFR-045 | Langfuse LLM observability integration | ✅ Complete (Full Pipeline) |
| NFR-046 | LLM trace debugging UI | 🔲 Pending (Langfuse dashboard) |

**NFR-045 Complete:** Full pipeline traced: `execute_ask` → `hybrid_search` → `embed_texts_with_usage` → `verify_relevance` → `call_openai`. Model, tokens, latency, verdict, tenant/session context. DB correlation via `langfuse_trace_id`. PII-safe: `capture_input=False, capture_output=False` on all decorators; `redact_for_langfuse()` sends safe metrics only (question_len, citation_count, evidence_grade — never raw text). Deploy with `LANGFUSE_ENABLED=1` + Langfuse Cloud keys.

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
| 01-22 | **4 LLM providers implemented** | azure_openai (default), anthropic, gemini, ollama; swap via LLM_PROVIDER env var |
| 01-22 | **OAuth2 with JWT tokens** | Access (30m) + Refresh (7d) tokens; Argon2id password hashing; dual-mode auth (jwt/headers) |
| 01-22 | **AUTH_MODE env var** | `jwt` for production, `headers` for dev/backward compat; JWT extracts from Bearer token |
| 01-22 | **Microsoft + Google SSO** | OIDC with PKCE flow; covers 95%+ of law firms; JIT provisioning creates users as Viewer |
| 01-22 | **Admin endpoints with manage_users** | User CRUD, matter access, pagination; admin cannot deactivate self |
| 01-22 | **Rate limiting via slowapi** | Per-endpoint configurable limits; protects LLM costs |
| 01-22 | **JWKS token validation** | ID tokens validated with provider JWKS; prevents forged tokens |
| 01-22 | **Database SSO state** | SSOState table replaces in-memory dict; supports multi-instance |
| 01-22 | **Nonce replay protection** | Nonce validated in ID token to prevent replay attacks |
| 01-22 | **Audit event PII redaction** | Question text hashed, not stored; only metadata in event_json (FR-040) |
| 01-22 | **Immutable audit logs** | No UPDATE/DELETE functions for AuditEvent; only hard_delete_matter removes them |
| 01-22 | **7-year audit retention** | DEFAULT_AUDIT_RETENTION_DAYS=2555; legal compliance requirement |
| 01-22 | **Configurable retention per tenant** | RetentionPolicy table; qa_messages=365d, telemetry=90d, audit=7yrs default |
| 01-22 | **Hard delete cascades** | Documents→Chunks→IndexRecords→QASessions→Messages→Audit→Assignments |
| 01-24 | **Azure Container Apps migration** | App Service build timeout (17min) due to marker-pdf/torch; Container Apps pre-builds Docker image |
| 01-24 | **Atomic hard delete transaction** | All 7 resource deletions in single session_scope() for rollback safety |
| 01-24 | **Modular ARCHITECTURE.md** | Split 1100→113 lines; detailed docs in `docs/architecture/`; reduces context per conversation |
| 01-25 | **Demo headers workaround** | Frontend uses hardcoded X-Tenant-Id etc. until JWT frontend integration; AUTH_MODE=headers |
| 01-25 | **httpOnly cookies for JWT** | Access + refresh tokens stored in httpOnly/Secure/SameSite=Lax cookies; prevents XSS; wsskeptic approved |
| 01-25 | **Google SSO redirect flow** | Backend redirects to frontend /auth/callback with tokens; frontend stores in cookies immediately |
| 01-24 | **Langfuse for LLM observability** | Optional dependency; graceful degradation; @observe decorators for LLM tracing (NFR-045) |

> **Current Stack:** Azure AI Search + Azure OpenAI + configurable parser
> **LLM Providers:** Azure OpenAI, Anthropic Claude, Google Gemini, Ollama (local)
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

## Phase 7 Progress

| FR | Requirement | Status |
|----|-------------|--------|
| FR-011 | Document deduplication (SHA256) | ✅ Shipped |
| FR-014 | Metadata extraction (title, author, pages) | ✅ Shipped |
| FR-015 | Async ingestion status tracking | ✅ Shipped |
| FR-022 | Optional reranker (local term+phrase) | ✅ Shipped |
| FR-033 | Cited-only packet export (PDF/DOCX) | ✅ Shipped |

**Phase 7 Complete:** 5/5 Polish features shipped. Async upload with status polling, configurable local reranker, cited exhibits export. All wsskeptic-reviewed.

---

## Upcoming Phases (Reference)

| Phase | FRs/NFRs | Goal |
|-------|----------|------|
| 2. Citations UI | FR-030, FR-031, FR-032 | Clickable citations, export |
| 3. Multi-tenancy | FR-001–004, FR-020 | Tenant + matter isolation |
| 4. Provider Abstraction | NFR-032, NFR-034, NFR-035, NFR-036 | Config-driven Parser/Search/LLM/Embeddings |
| 5. Auth | FR-050–053 | Login, SSO, admin, frontend UI |
| 6. Audit | FR-040–043 | Logging, retention, deletion |
| 7. Polish | FR-011, FR-014, FR-015, FR-022, FR-033 | ✅ Complete |
| 8. NFRs | NFR-001–022 | Security, perf, reliability |

---

## Archive

<details>
<summary>Week of 01-22 (Phase 5-6)</summary>

| Task | FR | Date |
|------|-----|------|
| Phase 6 Audit complete (59 tests) | FR-040-043 | 01-22 |
| Audit logging with PII redaction | FR-040 | 01-22 |
| Immutable logs + CSV export | FR-041 | 01-22 |
| Retention policies | FR-042 | 01-22 |
| Matter hard delete workflow | FR-043 | 01-22 |
| Phase 5 Auth complete (64 tests) | FR-050-052 | 01-22 |
| SSO security hardening (wsskeptic) | FR-051 | 01-22 |
| JWKS ID token signature validation | FR-051 | 01-22 |
| Database-backed SSO state | FR-051 | 01-22 |
| Admin JWT auth in jwt mode | FR-052 | 01-22 |
| SQL wildcard escaping | FR-052 | 01-22 |
| Rate limiting middleware | FR-052 | 01-22 |
| Auth security hardening (wsskeptic) | FR-050 | 01-22 |
| Atomic failed_login_count | FR-050 | 01-22 |
| Tenant isolation in refresh token | FR-050 | 01-22 |
| Access token type validation | FR-050 | 01-22 |
| 4 LLM providers (azure, anthropic, gemini, ollama) | NFR-032-033 | 01-22 |
| Provider abstraction interfaces | NFR-032-035 | 01-22 |
| Matter-level permissions | FR-004 | 01-22 |
| RBAC with roles | FR-003 | 01-22 |
| Tenant/Matter isolation | FR-001-002 | 01-21 |
| Citations UI + export | FR-030-032 | 01-21 |

</details>

<details>
<summary>Week of 01-08</summary>

| Task | PR | Date |
|------|-----|------|
| Initial repo setup | — | 01-08 |
| Requirements doc v1 | — | 01-10 |

</details>
