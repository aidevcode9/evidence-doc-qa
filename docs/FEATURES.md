# Evidence-Bound: Feature Overview

> **For Technical Investors** | Last Updated: January 2026

---

## Executive Summary

Evidence-Bound is an enterprise document Q&A platform designed for law firms and regulated industries where **every answer must be grounded in source documents**. Unlike general-purpose AI assistants, our system refuses to answer if it cannot cite specific evidence—eliminating hallucination risk in high-stakes legal contexts.

---

## Core Capabilities

### 1. Evidence-Grounded Q&A

**The Problem:** General LLMs hallucinate facts, cite non-existent sources, and cannot be trusted for legal work.

**Our Solution:**
- Every answer requires retrieval-backed citations from uploaded documents
- Post-LLM validation verifies cited chunks actually exist in the corpus
- Confidence scoring with configurable threshold (default: 70%)—below threshold triggers automatic refusal
- LLM verification layer cross-checks answer relevance against source material

**Technical Implementation:**
- Hybrid search: BM25 keyword + vector semantic + reranker
- Citation spans link to exact page numbers and character offsets
- Chunk-level verification ensures no phantom citations

---

### 2. Multi-Tenant Data Isolation

**The Problem:** Law firms handle confidential client data that must never cross matter boundaries.

**Our Solution:**
- Every database query includes `tenant_id` and `matter_id` filters
- Search index partitioned by tenant/matter at query time
- Complete audit trail of all document access and queries
- Supports multiple deployment models: shared cloud, dedicated instance, or on-premises

**Key Features:**
| Capability | Status |
|------------|--------|
| Tenant-level isolation | ✅ Implemented |
| Matter-level isolation | ✅ Implemented |
| Cross-tenant data leak prevention | ✅ Enforced at DB layer |
| Audit logging | ✅ Full request/response logging |

---

### 3. Document Processing Pipeline

**Supported Formats:**
- PDF (native, scanned with OCR)
- Microsoft Word (.docx)
- Plain text

**Processing Features:**
- Automatic chunking with configurable overlap
- Page-level and paragraph-level citation granularity
- SHA-256 content hashing for deduplication
- Incremental indexing (only process changed documents)

**Parser Options:**
| Parser | Use Case | Accuracy |
|--------|----------|----------|
| Marker (default) | High-fidelity PDF extraction with tables | High |
| LlamaParse | Cloud-based, handles complex layouts | High |
| PyPDF | Lightweight fallback | Medium |

---

### 4. Conversational Sessions

**Features:**
- Multi-turn conversations with context preservation
- Session history stored for audit and continuity
- Export conversations as PDF reports
- Configurable session timeouts

---

### 5. Authentication & Access Control

**Current Implementation:**
- Google SSO integration via NextAuth.js
- Azure AD/Entra ID support (planned)
- Session-based authentication with secure cookies

**Planned Enhancements:**
- Role-based access control (Admin, User, Viewer)
- Per-matter permission assignments
- API key authentication for integrations

---

### 6. Export & Reporting

**Export Formats:**
- PDF reports with embedded citations
- DOCX with hyperlinked sources
- Structured JSON for programmatic access

**Report Contents:**
- Question and answer pairs
- Source citations with page references
- Confidence scores
- Timestamp and session metadata

---

### 7. Observability & Compliance

**Telemetry:**
- OpenTelemetry integration for distributed tracing
- Langfuse LLM observability (token usage, latency, model performance)
- Per-request cost estimation
- No PII in logs (automatic redaction)

**Audit Capabilities:**
- Full request/response logging (excluding document content)
- Token usage tracking per tenant
- Latency percentiles (P50, P95)
- Refusal rate monitoring by category

---

## Deployment Options

| Tier | Infrastructure | Best For |
|------|---------------|----------|
| **SaaS Multi-Tenant** | Azure Container Apps + managed DBs | SMB law firms, quick start |
| **Dedicated Cloud** | Isolated Azure resources per client | Mid-market, compliance requirements |
| **On-Premises** | Customer infrastructure | Enterprise, data sovereignty |

All tiers support the same feature set with identical APIs.

---

## Technical Differentiators

### Why Not Just Use ChatGPT/Claude?

| Capability | General LLM | Evidence-Bound |
|------------|-------------|----------------|
| Hallucination prevention | ❌ None | ✅ Enforced refusal |
| Source citations | ❌ Often fabricated | ✅ Verified against corpus |
| Data isolation | ❌ Shared training data | ✅ Per-tenant/matter isolation |
| Audit trail | ❌ Limited | ✅ Complete logging |
| Cost control | ❌ Unpredictable | ✅ Per-query tracking |
| On-premises option | ❌ Cloud only | ✅ Full deployment flexibility |

### Why Not Build In-House?

Evidence-Bound encapsulates 6+ months of specialized development:
- Hybrid retrieval tuning (BM25 + vector weights, reranker thresholds)
- Citation validation pipeline (post-LLM verification)
- Multi-tenant security architecture
- Production-grade observability
- Enterprise authentication integration

---

## Roadmap Highlights

| Phase | Features | Timeline |
|-------|----------|----------|
| **Phase 2** (Current) | SSO, export, basic RBAC | Q1 2026 |
| **Phase 3** | Full multi-tenancy, admin dashboard | Q2 2026 |
| **Phase 4** | On-prem deployment, advanced RBAC | Q3 2026 |

---

## Integration Points

**APIs:**
- RESTful API with OpenAPI 3.0 specification
- Webhook callbacks for async processing
- Bulk document upload endpoint

**Authentication:**
- OAuth 2.0 / OIDC compatible
- SAML 2.0 (planned)
- API key authentication

**Data:**
- PostgreSQL-compatible (Azure Flexible Server, AWS RDS, on-prem)
- Azure AI Search or self-hosted vector search
- S3-compatible blob storage for documents

---

## Security Overview

- TLS 1.3 for all communications
- Encryption at rest (Azure-managed keys or customer-managed)
- No document content in logs
- Configurable data retention policies
- SOC 2 Type II compliance (planned)

---

*For technical architecture details, see [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md)*
