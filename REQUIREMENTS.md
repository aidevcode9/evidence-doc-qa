# Evidence-Bound Requirements — v1 (January 2026)

**Target:** MVP for law firm pilots (5-50 attorneys)
**Status:** Active
**Source:** EvidenceBound_Technical_Requirements_v1.docx

## Changelog

| Version | Date | Changes |
|---------|------|---------|
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
| FR-052 | Rate limiting and abuse controls; per-tenant quotas | Rate limits enforced; quota exceeded → 429 |

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
| NFR-033 | Default providers by tier: Cloud (Claude 3.5 Sonnet + GPT-4o fallback), VPC (Azure OpenAI), On-Prem (Ollama + Llama 3.1 70B) | Each tier works with documented provider |
| NFR-034 | Search/retrieval abstracted behind `SearchClient` interface | Swap Azure AI Search ↔ pgvector via config only, no code changes |
| NFR-035 | Embeddings abstracted behind `EmbeddingClient` interface | Swap Azure ↔ OpenAI ↔ local via config only, no code changes |
| NFR-036 | Document parsing abstracted behind `ParserClient` interface | Swap LlamaParse ↔ Marker ↔ Docling ↔ Unstructured via config; cache parsed results |
| NFR-037 | OCR accuracy ≥95% on scanned legal documents | Measured via test corpus of scanned court filings |
| NFR-038 | Table extraction preserves structure for indemnification schedules | Complex tables extracted as structured data, not flattened text |
| NFR-039 | Parser supports LLM enhancement mode (Marker `--use_llm`) | Configurable via MARKER_USE_LLM env var; works with Gemini or Ollama |

### 5.5 Code Quality & Maintainability

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| NFR-040 | Full type annotations; `mypy --strict` passes | Zero mypy errors; generic types parameterized; all functions typed |
| NFR-041 | Dev dependencies separated from production | `requirements-dev.txt` for ruff, mypy, pytest; not in main requirements.txt |

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
| llm_calls | id, session_id, message_id, provider, model, prompt_tokens, completion_tokens, latency_ms |
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

| Phase | FRs | Goal |
|-------|-----|------|
| 1. Core RAG | FR-010, FR-012, FR-013, FR-021, FR-023, FR-024, FR-025 | Working Q&A with citations |
| 2. Citations UI | FR-030, FR-031, FR-032 | Clickable citations, export |
| 3. Multi-tenancy | FR-001, FR-002, FR-003, FR-004, FR-020 | Tenant + matter isolation |
| 4. Auth | FR-050, FR-051, FR-052 | Login, SSO, admin |
| 5. Audit | FR-040, FR-041, FR-042, FR-043 | Logging, retention, deletion |
| 6. Polish | FR-011, FR-014, FR-015, FR-022, FR-033 | Dedup, metadata, reranker |
| 7. NFRs | NFR-* | Security, performance, reliability |
