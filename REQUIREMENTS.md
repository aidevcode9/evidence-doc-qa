# Evidence-Bound Requirements — v1 (January 2026)

**Target:** MVP for law firm pilots (5-50 attorneys)
**Status:** Active
**Source:** EvidenceBound_Technical_Requirements_v1.docx

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| v1.8 | Jan 2026 | Added LLM Observability NFRs (NFR-045, NFR-046) — Langfuse Cloud + self-hosted option |
| v1.7 | Jan 2026 | Added Deployment NFRs (NFR-042 to NFR-044) — Docker Compose, on-prem docs, pgvector search |
| v1.6 | Jan 2026 | Added FR-001/FR-002 implementation checklist from security review — query enforcement, retrieval layer, API layer |
| v1.5 | Jan 2026 | Added Document Parsing NFRs (NFR-036 to NFR-039) — OCR, table extraction, Marker LLM mode |
| v1.4 | Jan 2026 | Added Code Quality NFRs (NFR-040, NFR-041) |
| v1.3 | Jan 2026 | Added LLM synthesis and cross-doc aggregation FRs (FR-026, FR-027) |
| v1.2 | Jan 2026 | Added Search/Embedding abstraction NFRs (NFR-034, NFR-035) |
| v1.1 | Jan 2026 | Added LLM Provider NFRs (NFR-030 to NFR-033) |
| v1 | Jan 2026 | Initial release — 27 FRs, 11 NFRs |

---

## Product Goals

1. Enable attorneys to ask questions over case materials and receive answers with court-usable citations (page/line anchors)
2. Support matter-centric isolation (tenant_id + matter_id) across all storage, retrieval, caches, and logs
3. Provide audit trail suitable for internal review (who asked what, when, which exhibits were accessed)
4. Ship as portable container stack (hosted / VPC / on-prem)

## Non-Goals (v1)

- Not a full eDiscovery platform (collections, legal holds, productions, review workflows)
- Not a compliance guarantee; we implement security best practices but don't claim compliance by default
- Not a "zero hallucination" system; we enforce evidence-grounded behavior and graceful refusal

---

## Functional Requirements

### 4.1 Tenancy, Matters, and Permissions

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-001 | Multi-tenant support; all data partitioned by tenant_id | Every table with user data has tenant_id; queries always filter by it |
| FR-002 | Multi-matter support; artifacts partitioned by matter_id | Docs, chunks, vectors, chats, logs all have matter_id; no cross-matter queries |
| FR-003 | RBAC with roles: Admin, Attorney, Paralegal, Viewer | Role checked on every API call; permissions enforced |
| FR-004 | Matter-level permissions: users granted/removed per matter | User can only access matters they're assigned to |

#### FR-001/FR-002 Implementation Checklist (Security Review Findings)

Schema (✅ Complete):
- [x] All 6 models have tenant_id column (Document, Chunk, IndexRecord, Telemetry, QASession, QAMessage)
- [x] All 6 models have matter_id column
- [x] Alembic migration 0004 adds columns with NOT NULL + indexes

Query Enforcement (✅ Complete):
- [x] `load_index_records()` — tenant_id/matter_id REQUIRED (not optional)
- [x] `load_chunks()` — tenant_id/matter_id REQUIRED (not optional)
- [x] `get_document()` — add tenant_id parameter, filter by it
- [x] `get_doc_name()` — add tenant_id parameter, filter by it
- [x] `get_latest_docs_snapshot_id()` — add tenant_id parameter, filter by it
- [x] `get_session_messages()` — add tenant_id parameter, filter by it
- [x] `load_telemetry()` — add tenant_id parameter, filter by it
- [x] `create_qa_session()` — REQUIRE tenant_id and matter_id parameters
- [x] `get_qa_session()` — add tenant_id parameter, filter by it

Retrieval Layer (✅ Complete):
- [x] `retrieval.py:_load_index_records()` — pass tenant_id/matter_id to db.load_index_records()
- [x] `retrieval.py:_fallback_overlap()` — pass tenant_id/matter_id to db.load_chunks()
- [x] `retrieval.py:hybrid_search()` — accept tenant_id/matter_id parameters
- [x] `retrieval.py:_azure_search()` — add tenant_id filter to Azure Search query

API Layer (✅ Complete):
- [x] `routers/docs.py:get_doc_metadata()` — extract tenant from context, pass to get_document()
- [x] `routers/docs.py:view_doc()` — extract tenant from context, pass to get_document()
- [x] `services/ask_service.py` — pass tenant_id/matter_id through entire call chain
- [x] `services/ask_service.py:_store_qa_messages()` — set tenant_id/matter_id on QAMessage

Tests Required (✅ Complete):
- [x] Test: Query with tenant_id=A cannot see tenant_id=B documents
- [x] Test: Query with matter_id=X cannot see matter_id=Y documents
- [x] Test: Document API rejects cross-tenant access
- [x] Test: QASession/QAMessage isolated by tenant

### 4.2 Document Ingestion & Normalization

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-010 | Upload PDFs and images; preserve filename and optional Bates/exhibit metadata | Upload endpoint accepts PDF/image; metadata stored |
| FR-011 | Checksum + deduplication at matter level | Same file uploaded twice → rejected or linked, not duplicated |
| FR-012 | PDF text extraction (digital); OCR for scanned PDFs/images | Digital PDFs → text extracted; scanned → OCR pipeline runs |
| FR-013 | Chunking preserves page numbers and character offsets | Each chunk has page_start, page_end, char_start, char_end |
| FR-014 | Metadata extraction: doc type, date, custodian/author, tags, privilege flag | Metadata stored in documents.metadata_json |
| FR-015 | Async ingestion; UI shows status (queued/processing/ready/failed) with retry | Status endpoint returns current state; retry button works |

### 4.3 Retrieval & Answering

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-020 | Retriever filters by tenant_id + matter_id + user permissions | Query with wrong tenant/matter returns 0 results |
| FR-021 | Hybrid retrieval (BM25 + vector) with metadata filters | Both BM25 and vector called; results fused (RRF); filters work |
| FR-022 | Optional reranker for legal language | Reranker can be enabled/disabled; improves top-k when enabled |
| FR-023 | Evidence-grounded answers: every factual claim backed by citation | No claim without [N] citation marker |
| FR-024 | Below-threshold confidence → explicit "insufficient evidence" response | Low confidence returns refusal message, not a guess |
| FR-025 | Prevent fabricated citations: cited spans must exist and match | Post-check validates chunk exists and text matches (≥90% similarity) |
| FR-026 | LLM-synthesized natural language answers | LLM generates coherent answer from multiple chunks; maintains [N] citation markers; fallback to template if LLM fails |
| FR-027 | Cross-document citation aggregation | Answer can cite spans from multiple documents; citations grouped by document in response |

### 4.4 Citations, Viewer, and Exports

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-030 | UI displays citations: document name, page number, highlighted excerpt | Each citation shows doc + page + excerpt |
| FR-031 | Click citation → opens source document at cited page with highlight | PDF viewer scrolls to page; text highlighted |
| FR-032 | Export Q&A: PDF/DOCX with question, answer, and citations | Export button produces downloadable file |
| FR-033 | Optional: "cited-only packet" export listing referenced exhibits/pages | Export option for just the cited materials |

### 4.5 Audit Logging & Retention

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-040 | Log: user_id, tenant_id, matter_id, timestamp, question, retrieved docs, model, response_id | All fields present in audit_events table |
| FR-041 | Audit logs immutable at app layer; admin can export per matter/date | No UPDATE/DELETE on audit_events; export endpoint works |
| FR-042 | Configurable retention per tenant (keep chats/logs N days) with deletion workflow | Setting exists; deletion job runs on schedule |
| FR-043 | Hard delete workflow for entire matter (docs, vectors, chats, logs) | Delete matter → all related data removed; audit entry created |

### 4.6 Authentication, SSO, and Admin

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| FR-050 | Email/password + MFA (hosted); OIDC/SAML SSO (VPC/on-prem) | Login works; MFA enforced; SSO integrates |
| FR-051 | Admin UI: manage users, roles, matters, retention, API keys | Admin can CRUD all entities |

#### FR-050 Implementation Checklist (Security Review Findings)

Core Implementation (✅ Complete):
- [x] Password hashing with Argon2id (OWASP recommended)
- [x] JWT access tokens (30 min TTL) + refresh tokens (7 days TTL)
- [x] Account lockout after 5 failed attempts (30 min)
- [x] Dual-mode auth: AUTH_MODE=jwt (prod) or headers (dev)
- [x] Refresh token hashing (SHA256, not stored raw)
- [x] User enumeration prevention (same error for wrong email/password)

Security Hardening (✅ Complete):
- [x] Atomic failed_login_count increment (prevent race condition TOCTOU)
- [x] Add tenant_id filter to get_refresh_token() (prevent cross-tenant token probing)
- [x] Validate access token type in decode_access_token() (reject refresh tokens)

Tests (✅ Complete):
- [x] Test: Concurrent login attempts respect lockout threshold
- [x] Test: Refresh token lookup validates tenant isolation
- [x] Test: Refresh token cannot be used as access token
| FR-052 | Rate limiting and abuse controls; per-tenant quotas | Rate limits enforced; quota exceeded → 429 |
| FR-053 | Frontend login UI with Google SSO | Login page redirects to Google; callback stores JWT; protected routes redirect unauthenticated users |

#### FR-053 Implementation Checklist (Frontend Login UI)

Login Page:
- [ ] `/login` route with Google SSO button
- [ ] Redirect to backend `/v1/auth/google/login` endpoint
- [ ] Display error messages from failed auth
- [ ] "Sign in with Google" branding per Google guidelines

OAuth Callback:
- [ ] `/auth/callback` route handles redirect from Google
- [ ] Extracts `access_token` and `refresh_token` from URL params
- [ ] Stores tokens in httpOnly cookies (via API route)
- [ ] Redirects to main app on success

Auth Context:
- [ ] `AuthProvider` wraps app with auth state
- [ ] `useAuth()` hook returns: `user`, `isAuthenticated`, `isLoading`, `logout`
- [ ] Extracts user info from JWT (decode client-side for display only)
- [ ] Auto-refresh token before expiry (30 min access, 7 day refresh)

Protected Routes:
- [ ] `withAuth()` HOC or middleware redirects to `/login` if unauthenticated
- [ ] Main app page requires authentication
- [ ] Logout clears cookies and redirects to `/login`

API Client Update:
- [ ] `getAuthHeaders()` reads JWT from cookie
- [ ] Returns `Authorization: Bearer <token>` header
- [ ] Falls back to demo headers if `AUTH_MODE=headers`

Tests:
- [ ] Test: Unauthenticated user redirected to /login
- [ ] Test: Successful OAuth callback stores tokens
- [ ] Test: Expired token triggers refresh
- [ ] Test: API calls include Bearer token
- [ ] Test: Logout clears auth state

---

## Non-Functional Requirements

### 5.1 Security Baseline

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| NFR-001 | TLS for all traffic; HSTS for web UI | No HTTP; HSTS header present |
| NFR-002 | Encryption at rest for object storage and databases | Storage encrypted; keys managed per tier |
| NFR-003 | Least-privilege service accounts; no shared admin creds; secrets via manager | No hardcoded secrets; service accounts scoped |
| NFR-004 | PII minimization in logs; redact doc excerpts by default | Logs don't contain raw document text |
| NFR-005 | Dependency scanning and container image scanning in CI | Scan runs on every PR; blocking on critical vulns |

### 5.2 Performance & Scaling (v1)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| NFR-010 | Ingestion: 500–2,000 pages/hour per worker (OCR dependent) | Benchmark meets target |
| NFR-011 | Query latency: p95 < 8 seconds (top-k retrieval + LLM call) | Metrics show p95 under target |
| NFR-012 | Support 50 concurrent users (hosted); horizontal scaling | Load test passes; can add workers |

### 5.3 Reliability & Ops

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| NFR-020 | Graceful degradation if LLM unavailable (retry/backoff; user error) | LLM down → user sees error, not crash |
| NFR-021 | Backups: nightly Postgres + object store; documented restore | Backup runs; restore tested |
| NFR-022 | Observability: metrics, traces, logs via OpenTelemetry | Dashboards show latency, errors, backlog |

### 5.4 LLM & Search Provider Requirements

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| NFR-030 | LLM provider/model recorded in audit log for every response | `llm_calls` table has provider, model, tokens, latency |
| NFR-031 | On-prem local LLM displays "Local Model" badge in UI | Badge visible; docs state quality trade-offs |
| NFR-032 | LLM provider abstracted behind `LLMClient` interface | Swap providers via config only, no code changes |
| NFR-033 | Default providers by tier: Cloud (Azure OpenAI + Anthropic/Gemini fallback), VPC (Azure OpenAI), On-Prem (Ollama + Llama 3.2) | Each tier works with documented provider; 4 providers implemented: azure_openai, anthropic, gemini, ollama |
| NFR-034 | Search/retrieval abstracted behind `SearchClient` interface | Swap Azure AI Search ↔ pgvector via config only, no code changes |
| NFR-035 | Embeddings abstracted behind `EmbeddingClient` interface | Swap Azure ↔ OpenAI ↔ local via config only, no code changes |
| NFR-036 | Document parsing abstracted behind `ParserClient` interface | Swap LlamaParse ↔ Marker ↔ Docling ↔ Unstructured via config; cache parsed results |
| NFR-037 | OCR accuracy ≥95% on scanned legal documents | Measured via test corpus of scanned court filings |
| NFR-038 | Table extraction preserves structure for indemnification schedules | Complex tables extracted as structured data, not flattened text |
| NFR-039 | Parser supports LLM enhancement mode (Marker `--use_llm`) | Configurable via MARKER_USE_LLM env var; works with Gemini or Ollama |

### 5.5 Deployment & Containerization

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| NFR-042 | Docker Compose for local/on-prem development | `docker-compose up` starts API + PostgreSQL + pgvector; all services healthy |
| NFR-043 | On-prem deployment documentation | docs/DEPLOYMENT_ONPREM.md covers: Ollama setup, pgvector, local embeddings, air-gapped operation |
| NFR-044 | pgvector search provider implementation | `SEARCH_PROVIDER=pgvector` enables PostgreSQL-based hybrid search (BM25 + vector); no Azure dependency |

### 5.6 Code Quality & Maintainability

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| NFR-040 | Full type annotations; `mypy --strict` passes | Zero mypy errors; generic types parameterized; all functions typed |
| NFR-041 | Dev dependencies separated from production | `requirements-dev.txt` for ruff, mypy, pytest; not in main requirements.txt |

### 5.7 LLM Observability (Langfuse)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| NFR-045 | Langfuse Cloud integration for ALL LLM calls | Every LLM call logged to both `llm_calls` table AND Langfuse; `langfuse_trace_id` stored for correlation; visual trace viewer accessible |
| NFR-046 | Self-hosted Langfuse option for Enterprise/On-Prem | Docker Compose config for self-hosted Langfuse; `LANGFUSE_HOST` points to internal URL; data stays in customer VPC |

#### NFR-045 Setup (Langfuse Cloud)

1. **Create Langfuse account:** https://cloud.langfuse.com
2. **Get API keys:** Settings → API Keys → Create new key pair
3. **Add environment variables:**
   ```bash
   LANGFUSE_ENABLED=true
   LANGFUSE_PUBLIC_KEY=pk-lf-xxx
   LANGFUSE_SECRET_KEY=sk-lf-xxx
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```
4. **Add GitHub secrets** (for Container Apps):
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`
5. **Verify:** Check Langfuse dashboard for traces after `/ask` calls

#### NFR-046 Setup (Self-Hosted) — Future

For Enterprise/VPC/On-Prem deployments requiring data sovereignty:
- Deploy via `docker-compose.langfuse.yml`
- Set `LANGFUSE_HOST=http://langfuse.internal:3000`
- See `docs/architecture/observability.md` for full config

---

## Data Model (Reference)

| Table | Key Columns |
|-------|-------------|
| tenants | id, name, settings_json |
| users | id, tenant_id, email, role, mfa_enabled |
| matters | id, tenant_id, name, status, retention_policy |
| matter_members | matter_id, user_id, role |
| documents | id, tenant_id, matter_id, filename, storage_uri, sha256, pages, metadata_json, privilege_flag, status |
| doc_chunks | id, document_id, tenant_id, matter_id, page_number, char_start, char_end, text, embedding |
| qa_sessions | id, tenant_id, matter_id, created_by |
| qa_messages | id, session_id, role, content, citations_json |
| llm_calls | id, session_id, message_id, provider, model, prompt_tokens, completion_tokens, latency_ms, langfuse_trace_id |
| audit_events | id, tenant_id, matter_id, user_id, event_type, event_json |
| usage_daily | tenant_id, date, queries_count, pages_ingested, llm_tokens_prompt, llm_tokens_completion |

> **Full schemas:** See `ARCHITECTURE.md` for complete DDL with indexes and constraints.

---

## API Surface (Minimum)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/matters | Create matter |
| GET | /api/matters | List matters (permission-filtered) |
| POST | /api/matters/{id}/documents | Upload document |
| GET | /api/matters/{id}/documents | List documents + status |
| POST | /api/matters/{id}/ask | Ask question → answer + citations |
| GET | /api/matters/{id}/sessions/{sid}/export | Export Q&A session |
| GET | /api/matters/{id}/audit | Audit export (admin only) |

---

## Evaluation & QA

- **Golden questions set** per matter type (PI, employment) with expected citations
- **Automated tests:** retrieval correctness (top-k includes expected spans), citation validation, refusal behavior
- **Red-team tests:** prompt injection in documents, citation fabrication attempts, cross-matter leakage

---

## Open Questions (for dev review)

1. Citation granularity: page-only vs page+line vs paragraph IDs?
2. Native DOCX ingestion in v1 or PDF-only?
3. Email forwarding / folder ingest or manual upload only?
4. Legal-specific metadata (custodian, privilege) now or minimal?

---

## Phasing (Suggested)

| Phase | FRs/NFRs | Goal |
|-------|----------|------|
| 1. Core RAG | FR-010, FR-012, FR-013, FR-021, FR-023, FR-024, FR-025 | Working Q&A with citations |
| 2. Citations UI | FR-030, FR-031, FR-032 | Clickable citations, export |
| 3. Multi-tenancy | FR-001, FR-002, FR-003, FR-004, FR-020 | Tenant + matter isolation |
| 4. Provider Abstraction | NFR-032, NFR-033, NFR-034, NFR-035 | Config-driven LLM/Search/Embeddings |
| 5. Auth | FR-050, FR-051, FR-052 | Login, SSO, admin |
| 6. Open-Source Deploy | NFR-042, NFR-043, NFR-044 | Docker Compose, pgvector, on-prem docs |
| 7. Audit | FR-040, FR-041, FR-042, FR-043 | Logging, retention, deletion |
| 8. Polish | FR-011, FR-014, FR-015, FR-022, FR-033 | Dedup, metadata, reranker |
| 9. NFRs | NFR-* | Security, performance, reliability |
