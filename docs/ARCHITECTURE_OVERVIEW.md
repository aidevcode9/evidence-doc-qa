# Evidence-Bound: Technical Architecture

> **For Technical Investors** | Last Updated: January 2026

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                     │
│    Next.js Web App (Vercel)  │  Mobile (Future)  │  API Integrations    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTPS/REST
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY LAYER                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ Auth/SSO    │  │ Rate Limit  │  │ Tenant      │  │ Audit       │    │
│  │ Middleware  │  │ Middleware  │  │ Resolution  │  │ Logging     │    │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI APPLICATION                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    SERVICE LAYER                                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │   │
│  │  │ Ask Service │  │ Doc Service │  │ Session Svc │              │   │
│  │  │ (Q&A Orch.) │  │ (Upload)    │  │ (History)   │              │   │
│  │  └──────┬──────┘  └──────┬──────┘  └─────────────┘              │   │
│  │         │                │                                        │   │
│  │         ▼                ▼                                        │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │              CORE PIPELINE COMPONENTS                    │    │   │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │    │   │
│  │  │  │Retrieval │ │Evidence  │ │Policy    │ │Verifier  │   │    │   │
│  │  │  │(Search)  │ │(Citation)│ │(Gates)   │ │(LLM QA)  │   │    │   │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   POSTGRESQL    │    │  SEARCH INDEX   │    │   LLM PROVIDER  │
│  (Data Store)   │    │ (Azure/pgvector)│    │ (Azure OpenAI)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Frontend** | Next.js 14 + TypeScript | SSR, React ecosystem, Vercel deployment |
| **API** | FastAPI + Python 3.11 | Async performance, type hints, OpenAPI |
| **Database** | PostgreSQL 15 | ACID compliance, JSON support, pgvector ready |
| **Search** | Azure AI Search | Hybrid BM25+vector, semantic reranker |
| **Embeddings** | Azure OpenAI (text-embedding-3-large) | 3072 dimensions, multilingual |
| **LLM** | Azure OpenAI (GPT-4o) | Enterprise SLA, data residency |
| **Document Parsing** | Marker / LlamaParse | High-fidelity PDF extraction |
| **Observability** | OpenTelemetry + Langfuse | Distributed tracing, LLM-specific metrics |
| **Auth** | NextAuth.js + Google OAuth | Enterprise SSO ready |

---

## Core Components

### 1. Retrieval Pipeline (`retrieval.py`)

**Hybrid Search Strategy:**
```
Query → Embed → [BM25 Search] + [Vector Search] → Rerank → Top-K Chunks
```

| Stage | Purpose | Configuration |
|-------|---------|---------------|
| BM25 | Keyword matching, exact terms | Weight: 0.3 |
| Vector | Semantic similarity | Weight: 0.7, k=50 |
| Reranker | Cross-encoder reordering | Semantic configuration |
| Top-K | Final chunk selection | k=10 (configurable) |

**Tenant Isolation:**
```python
# Every search includes mandatory filters
filter_expression = f"tenant_id eq '{tenant_id}' and matter_id eq '{matter_id}'"
```

### 2. Evidence Validation (`evidence.py`)

**Post-LLM Citation Verification:**
1. Extract citation spans from LLM response
2. Verify each cited chunk exists in retrieval results
3. Validate page numbers match document metadata
4. Reject response if any citation is invalid

**Refusal Conditions:**
- No citations in response → Refuse
- Citation references non-existent chunk → Refuse
- Page number doesn't exist in document → Refuse

### 3. Policy Engine (`policy.py`)

**Pre-LLM Gates:**
- Query length validation
- Tenant/matter authorization
- Rate limiting check

**Post-LLM Gates:**
- Confidence threshold (< 0.70 → refuse)
- Citation validation (via evidence.py)
- Content policy compliance

### 4. LLM Verification (`verification.py`)

**Secondary LLM Check:**
```python
# Verifies answer relevance to retrieved chunks
relevance_score = verify_relevance(
    question=query,
    chunk_text=retrieved_context,
    answer=llm_response
)
```

Returns confidence score (0.0-1.0) used by policy engine.

---

## Data Model

### Core Tables

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    documents    │     │     chunks      │     │  index_records  │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ doc_id (PK)     │────<│ chunk_id (PK)   │────<│ chunk_id (PK)   │
│ tenant_id       │     │ doc_id (FK)     │     │ tenant_id       │
│ matter_id       │     │ tenant_id       │     │ matter_id       │
│ docs_snapshot_id│     │ matter_id       │     │ embedding_json  │
│ file_name       │     │ page_num        │     │ indexed_at_utc  │
│ sha256          │     │ chunk_text      │     │ index_version   │
│ uploaded_at     │     │ char_start/end  │     └─────────────────┘
└─────────────────┘     └─────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   qa_sessions   │     │   qa_messages   │     │    telemetry    │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ session_id (PK) │────<│ message_id (PK) │     │ request_id (PK) │
│ tenant_id       │     │ session_id (FK) │     │ tenant_id       │
│ matter_id       │     │ tenant_id       │     │ matter_id       │
│ docs_snapshot_id│     │ role            │     │ tokens_in/out   │
│ created_at      │     │ content         │     │ latency_ms      │
│ user_id         │     │ citations_json  │     │ cost_est        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Tenant Isolation Pattern

Every query enforces tenant/matter scope:
```sql
SELECT * FROM chunks
WHERE tenant_id = :tenant_id
  AND matter_id = :matter_id
  AND docs_snapshot_id = :snapshot_id
```

---

## Provider Abstraction

The architecture supports pluggable providers for deployment flexibility:

### Current Implementation
```python
# config.py - Provider selection
PARSER_PROVIDER = "marker"       # marker | llamaparse | pypdf
SEARCH_PROVIDER = "azure"        # azure | pgvector (planned)
LLM_PROVIDER = "azure_openai"    # azure_openai | openai | anthropic (planned)
EMBEDDING_PROVIDER = "azure"     # azure | openai (planned)
```

### Abstraction Interfaces (Planned)

```python
# Target interface for search provider
class SearchProvider(Protocol):
    async def search(
        self,
        query: str,
        embedding: list[float],
        tenant_id: str,
        matter_id: str,
        top_k: int = 10,
    ) -> list[ChunkResult]: ...

# Implementations
class AzureSearchProvider(SearchProvider): ...
class PgVectorProvider(SearchProvider): ...
```

---

## Deployment Architecture

### Cloud Deployment (Current)

```
┌─────────────────────────────────────────────────────────────────┐
│                         AZURE                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ Container Apps  │  │ Flexible Server │  │  AI Search      │ │
│  │ (FastAPI)       │  │ (PostgreSQL)    │  │  (Hybrid Index) │ │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘ │
│           │                    │                    │          │
│           └────────────────────┼────────────────────┘          │
│                                │                                │
│  ┌─────────────────┐  ┌───────┴───────┐  ┌─────────────────┐  │
│  │ Azure OpenAI    │  │ Blob Storage  │  │ Key Vault       │  │
│  │ (GPT-4o + Embed)│  │ (Documents)   │  │ (Secrets)       │  │
│  └─────────────────┘  └───────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        VERCEL                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Next.js Frontend                       │   │
│  │              (SSR, Static Assets, Edge)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Deployment Tiers

| Tier | Components | Monthly Cost Estimate |
|------|------------|----------------------|
| **Development** | Container Apps (B1), PostgreSQL (Burstable B1), AI Search (Free) | ~$50 |
| **Production** | Container Apps (P1v3), PostgreSQL (GP D2s), AI Search (Standard S1) | ~$500-800 |
| **Enterprise** | Dedicated VNet, Premium PostgreSQL, Reserved capacity | ~$2,000+ |

### On-Premises Option (Planned)

```
Customer Data Center
├── Kubernetes Cluster
│   ├── API Pods (FastAPI)
│   ├── Worker Pods (Document Processing)
│   └── Ingress Controller
├── PostgreSQL (+ pgvector extension)
├── MinIO (S3-compatible storage)
└── Local LLM (Ollama/vLLM) OR VPN to cloud LLM
```

---

## Security Architecture

### Data Protection

| Layer | Mechanism |
|-------|-----------|
| Transport | TLS 1.3 (enforced) |
| Storage | AES-256 encryption at rest |
| Secrets | Azure Key Vault / env injection |
| Logs | PII redaction before write |

### Authentication Flow

```
User → Google OAuth → NextAuth.js → Session Cookie → API Auth Middleware
                                                            │
                                                            ▼
                                                    Tenant Resolution
                                                            │
                                                            ▼
                                                    Request Processing
```

### Tenant Isolation Enforcement

```python
# Middleware enforces tenant context on every request
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    tenant_id = resolve_tenant(request)
    matter_id = resolve_matter(request)

    # Inject into request state - available to all handlers
    request.state.tenant_id = tenant_id
    request.state.matter_id = matter_id

    return await call_next(request)
```

---

## Observability Stack

### Metrics & Tracing

```
Application
    │
    ├── OpenTelemetry SDK
    │   ├── Traces → Azure Monitor / Jaeger
    │   ├── Metrics → Prometheus / Azure Monitor
    │   └── Logs → stdout → Azure Log Analytics
    │
    └── Langfuse Integration
        ├── LLM Call Traces
        ├── Token Usage
        ├── Latency Distributions
        └── Model Performance
```

### Key Metrics Tracked

| Metric | Purpose |
|--------|---------|
| `llm.latency_ms` | LLM response time |
| `gen_ai.usage.prompt_tokens` | Input token count |
| `gen_ai.usage.completion_tokens` | Output token count |
| `retrieval.latency_ms` | Search latency |
| `refusal_rate` | Percentage of refused queries |
| `cache_hit_rate` | Embedding cache efficiency |

---

## Scalability Considerations

### Current Capacity

| Resource | Limit | Scaling Path |
|----------|-------|--------------|
| Concurrent requests | ~100/instance | Horizontal pod scaling |
| Document processing | ~10 docs/min | Worker queue + async |
| Search index | 1M chunks | Index partitioning |
| Database | 100 GB | Vertical scaling, read replicas |

### Scaling Strategy

1. **Stateless API**: Horizontal scaling via container replicas
2. **Async Processing**: Document ingestion queued (Azure Queue / Redis)
3. **Caching**: Embedding cache reduces LLM calls by ~40%
4. **Index Partitioning**: Per-tenant indexes for large deployments

---

## Development Practices

### Quality Gates (CI/CD)

```bash
# All must pass before merge
ruff check apps/              # Linting
mypy apps/api/app --strict    # Type checking
pytest tests/ -v              # Unit + integration
pytest evals/ -v              # Golden query evals (>95% pass required)
```

### Test Coverage

| Category | Coverage Target |
|----------|-----------------|
| Unit tests | >80% |
| Integration tests | Critical paths |
| Golden query evals | >95% pass rate |
| LLM behavior tests | Adversarial prompts |

---

## Technical Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM hallucination | Post-LLM citation validation, confidence gating |
| Search relevance drift | Golden query evals in CI, reranker tuning |
| Vendor lock-in | Provider abstraction interfaces |
| Cost overrun | Token tracking, caching, query limits |
| Data breach | Tenant isolation at DB layer, encryption |

---

## Roadmap (Technical)

| Phase | Focus | Key Deliverables |
|-------|-------|------------------|
| **Phase 2** | Production hardening | SSO, export, observability |
| **Phase 3** | Multi-tenancy | Admin dashboard, usage billing |
| **Phase 4** | Deployment flexibility | On-prem, alternative LLMs |
| **Phase 5** | Advanced features | Fine-tuned models, custom retrievers |

---

*For feature descriptions, see [FEATURES.md](./FEATURES.md)*
