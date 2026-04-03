# Evidence-Bound: Technical Architecture

> **For Technical Investors** | Last Updated: April 2026

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                    │
│    Next.js Web App (Vercel)  │  Mobile (Future)  │  API Integrations    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ HTTPS/REST
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY LAYER                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ JWT Auth    │  │ Rate Limit  │  │ Tenant      │  │ Audit       │     │
│  │ Middleware  │  │ Middleware  │  │ Resolution  │  │ Logging     │     │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      FASTAPI APPLICATION                                │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    SERVICE LAYER                                │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │ Ask Service │  │ Doc Service │  │ Session Svc │              │    │
│  │  │ (Q&A Orch.) │  │ (Upload)    │  │ (History)   │              │    │
│  │  └──────┬──────┘  └──────┬──────┘  └─────────────┘              │    │
│  │         │                │                                      │    │
│  │         ▼                ▼                                      │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │              CORE PIPELINE COMPONENTS                   │    │    │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │    │    │
│  │  │  │Retrieval │ │Evidence  │ │Policy    │ │Verifier  │    │    │    │
│  │  │  │(Search)  │ │(Citation)│ │(Gates)   │ │(LLM QA)  │    │    │    │
│  │  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │    │    |
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   POSTGRESQL    │    │  SEARCH INDEX   │    │   LLM PROVIDER  │
│  (Data Store)   │    │ (Azure/pgvector)│    │ (Multi-provider)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Frontend** | Next.js 16 + TypeScript | SSR, React ecosystem, Vercel deployment |
| **API** | FastAPI + Python 3.12 | Async performance, type hints, OpenAPI |
| **Database** | PostgreSQL 15 | ACID compliance, JSON support, pgvector ready |
| **Search** | Azure AI Search / pgvector | Hybrid BM25+vector, configurable provider |
| **Embeddings** | Azure OpenAI / Local | text-embedding-3-large (3072D) or hash-based |
| **LLM** | Azure OpenAI / Anthropic / Gemini / Ollama | Multi-provider support via config |
| **Document Parsing** | Marker / LlamaParse / PyPDF | Configurable parser (NFR-036) |
| **Observability** | OpenTelemetry + Langfuse | Distributed tracing, LLM-specific metrics |
| **Auth** | JWT + OIDC (Microsoft/Google) | Refresh tokens, SSO, account lockout |

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

11 tables, all with `tenant_id` column (indexed). Every query enforces tenant/matter scope.

**Key tables:** `documents` → `chunks` → `index_records` (ingestion pipeline), `qa_sessions` → `qa_messages` (conversations), `users` → `matter_assignments` (RBAC), `telemetry` (per-request metrics), `audit_events` (immutable log).

See [Architecture Diagrams](./ARCHITECTURE_DIAGRAM.md#data-model) for the ER diagram and [data-model.md](./architecture/data-model.md) for complete SQL schemas.

---

## Provider Abstraction

**Status: ✅ Fully Implemented (NFR-032, NFR-034, NFR-035, NFR-036)**

The architecture supports pluggable providers for deployment flexibility:

### Implemented Abstractions

```python
# config.py - Provider selection (change via env vars only)
LLM_PROVIDER = "azure_openai"      # azure_openai | anthropic | gemini | ollama
SEARCH_PROVIDER = "local"          # local (pgvector) | azure
EMBEDDINGS_MODE = "remote"         # remote (Azure) | local (hash-based)
PARSER_PROVIDER = "marker"         # marker | llamaparse | pypdf
```

All four abstractions use Python Protocol interfaces. See [interfaces.md](./architecture/interfaces.md) for full definitions, method signatures, and per-provider configuration.

**No code changes needed** — swap providers via environment variables only.

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
│  │(GPT-5-mini+Emb) │  │ (Documents)   │  │ (Secrets)       │  │
│  └─────────────────┘  └───────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        VERCEL                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Next.js Frontend                      │    │
│  │              (SSR, Static Assets, Edge)                 │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Deployment Tiers

| Tier | Components | Monthly Cost Estimate |
|------|------------|----------------------|
| **Development** | Container Apps (B1), PostgreSQL (Burstable B1), AI Search (Free) | ~$50 |
| **Production** | Container Apps (P1v3), PostgreSQL (GP D2s), AI Search (Standard S1) | ~$500-800 |
| **Enterprise** | Dedicated VNet, Premium PostgreSQL, Reserved capacity | ~$2,000+ |

### On-Premises Deployment

```
Customer Data Center
├── Kubernetes Cluster
│   ├── API Pods (FastAPI)
│   ├── Worker Pods (Document Processing)
│   └── Ingress Controller
├── PostgreSQL (+ pgvector extension)
├── MinIO (S3-compatible storage)
└── Local LLM (Ollama) OR Anthropic/Gemini API via VPN
```

**Configuration:**
```bash
# On-prem deployment tier
LLM_PROVIDER=ollama                    # Local Llama 3.2
SEARCH_PROVIDER=local                  # PostgreSQL + pgvector
EMBEDDINGS_MODE=local                  # Hash-based (or remote via VPN)
PARSER_PROVIDER=marker                 # Marker (offline PDF parsing)
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
| Tokens | SHA256 hashes only (no plaintext) |

### Authentication Flow (FR-050, FR-051)

See [Architecture Diagrams — Authentication Flow](./ARCHITECTURE_DIAGRAM.md#authentication-flow) for the full sequence diagram.

**Security Features (FR-050):**
- Password hashing: Argon2id (OWASP recommended)
- Account lockout: 5 failed attempts → 30 min lock
- Refresh token rotation: New token on each refresh
- Token revocation: All tokens revoked on password change
- PKCE for SSO: Protects against authorization code interception

### Tenant Isolation Enforcement

```python
# FastAPI dependency injects tenant context on every request
def get_tenant_context(request: Request) -> TenantContext:
    # Extract from JWT claims (AUTH_MODE=jwt) or headers (dev mode)
    token = validate_jwt(request)
    tenant_id = token["tenant_id"]
    user_id = token["sub"]
    user_role = Role(token["role"])

    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=user_role,
    )

# Used on every endpoint via Depends()
@router.get("/v1/matters")
async def list_matters(ctx: TenantContext = Depends(get_tenant_context)):
    # ctx.tenant_id is guaranteed present — enforced at extraction
    matters = list_matters_for_tenant(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        user_role=ctx.user_role.value,
    )
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
    └── Langfuse Integration (NFR-045)
        ├── LLM Call Traces (@observe decorators)
        ├── Token Usage (gen_ai.usage.* metrics)
        ├── Latency Distributions (llm.latency_ms)
        └── Model Performance (by provider)
```

### Key Metrics Tracked

| Metric | Purpose | OTEL Semantic Convention |
|--------|---------|--------------------------|
| `llm.latency_ms` | LLM response time | Custom |
| `gen_ai.usage.prompt_tokens` | Input token count | GenAI |
| `gen_ai.usage.completion_tokens` | Output token count | GenAI |
| `gen_ai.request.model` | Model identifier | GenAI |
| `gen_ai.system` | Provider name | GenAI |
| `retrieval.latency_ms` | Search latency | Custom |
| `refusal_rate` | Percentage of refused queries | Custom |
| `cache_hit_rate` | Embedding cache efficiency | Custom |

**Database Telemetry Table:**
```sql
-- All LLM calls logged to telemetry table (NFR-030)
SELECT tenant_id, model_id,
       SUM(tokens_in) as total_prompt_tokens,
       SUM(tokens_out) as total_completion_tokens,
       SUM(cost_est) as total_cost_usd
FROM telemetry
WHERE timestamp_utc >= NOW() - INTERVAL '30 days'
GROUP BY tenant_id, model_id;
```

---

## Scalability Considerations

### Current Capacity

| Resource | Limit | Scaling Path |
|----------|-------|--------------|
| Concurrent requests | ~10-15 req/s per instance | Horizontal pod scaling |
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
mypy apps/api/app --strict    # Type checking (NFR-040)
pytest tests/ -v              # Unit + integration
pytest evals/ -v              # Golden query evals (>95% pass required)
```

### Test Coverage

| Category | Coverage Target | Current |
|----------|-----------------|---------|
| Unit tests (624 tests) | >80% | ~85% |
| Integration tests | Critical paths | ✅ |
| Golden query evals | >95% pass rate | ✅ |
| LLM behavior tests | Adversarial prompts | ✅ |

### Test-Driven Development (TDD)

**Enforced via CLAUDE.md:**
```
RED    → Write test that fails (proves test works)
GREEN  → Write minimum code to pass
REFACTOR → Clean up, maintain passing tests
COMMIT → Only after green
```

---

## Technical Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM hallucination | Post-LLM citation validation, confidence gating |
| Search relevance drift | Golden query evals in CI, reranker tuning |
| Vendor lock-in | Provider abstraction interfaces (implemented) |
| Cost overrun | Token tracking, caching, query limits, telemetry table |
| Data breach | Tenant isolation at DB layer, encryption, audit log |
| Account compromise | Account lockout, refresh token rotation, MFA (planned) |

---

## Roadmap (Technical)

| Phase | Focus | Status |
|-------|-------|--------|
| **Phase 2** | Production hardening | ✅ Complete (SSO, export, observability) |
| **Phase 3** | Multi-tenancy | ✅ Complete (RBAC, matter-level permissions) |
| **Phase 4** | Deployment flexibility | ✅ Complete (Provider abstraction) |
| **Phase 5** | Advanced features | 🚧 In Progress (Fine-tuned models, custom retrievers) |

---

## Implementation Status

| Feature | Status | FRs |
|---------|--------|-----|
| Tenant isolation | ✅ | FR-001 |
| Matter isolation | ✅ | FR-002 |
| RBAC | ✅ | FR-003 |
| Matter-level permissions | ✅ | FR-004 |
| JWT authentication | ✅ | FR-050 |
| OIDC SSO | ✅ | FR-051 |
| Audit logging | ✅ | FR-040 |
| Data retention policies | ✅ | FR-042 |
| Provider abstraction (LLM) | ✅ | NFR-032 |
| Provider abstraction (Search) | ✅ | NFR-034 |
| Provider abstraction (Embedding) | ✅ | NFR-035 |
| Provider abstraction (Parser) | ✅ | NFR-036 |
| Type safety (mypy --strict) | ✅ | NFR-040 |
| LLM telemetry | ✅ | NFR-030, NFR-045 |

---

*For detailed schemas, see [data-model.md](./architecture/data-model.md)*
*For provider interfaces, see [interfaces.md](./architecture/interfaces.md)*
*For feature descriptions, see [FEATURES.md](./FEATURES.md)*
