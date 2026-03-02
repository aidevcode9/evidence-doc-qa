# Evidence-Bound: Technical Architecture

> **For Technical Investors** | Last Updated: February 2026

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
│  │ JWT Auth    │  │ Rate Limit  │  │ Tenant      │  │ Audit       │    │
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
│  (Data Store)   │    │ (Azure/pgvector)│    │ (Multi-provider)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Frontend** | Next.js 14 + TypeScript | SSR, React ecosystem, Vercel deployment |
| **API** | FastAPI + Python 3.11 | Async performance, type hints, OpenAPI |
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

### Core Tables

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    documents    │     │     chunks      │     │  index_records  │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ doc_id (PK)     │────<│ chunk_id (PK)   │────<│ chunk_id (PK)   │
│ tenant_id       │     │ doc_id (FK)     │     │ tenant_id       │
│ matter_id       │     │ tenant_id       │     │ matter_id       │
│ docs_snapshot_id│     │ matter_id       │     │ embedding_json  │
│ doc_name        │     │ page_num        │     │ indexed_at_utc  │
│ doc_sha256      │     │ chunk_text      │     │ index_version   │
│ storage_path    │     │ char_start/end  │     └─────────────────┘
└─────────────────┘     └─────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   qa_sessions   │     │   qa_messages   │     │    telemetry    │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ session_id (PK) │────<│ message_id (PK) │     │ request_id (PK) │
│ tenant_id       │     │ session_id (FK) │     │ tenant_id       │
│ matter_id       │     │ tenant_id       │     │ matter_id       │
│ docs_snapshot_id│     │ role            │     │ tokens_in/out   │
│ created_at_utc  │     │ content         │     │ latency_ms      │
└─────────────────┘     │ citations_json  │     │ cost_est        │
                        │ evidence_json   │     │ trace_metadata  │
                        └─────────────────┘     └─────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│      users      │     │matter_assignments│     │ refresh_tokens  │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ user_id (PK)    │────<│ assignment_id   │     │ token_id (PK)   │
│ tenant_id       │     │ user_id (FK)    │     │ user_id (FK)    │
│ email           │     │ tenant_id       │     │ tenant_id       │
│ role            │     │ matter_id       │     │ token_hash      │
│ password_hash   │     │ granted_by      │     │ expires_at_utc  │
│ auth_provider   │     │ granted_at_utc  │     │ revoked_at_utc  │
│ is_active       │     └─────────────────┘     └─────────────────┘
│ failed_login_ct │
│ locked_until_utc│     ┌─────────────────┐     ┌─────────────────┐
└─────────────────┘     │   sso_states    │     │  audit_events   │
                        ├─────────────────┤     ├─────────────────┤
                        │ state_token (PK)│     │ event_id (PK)   │
                        │ provider        │     │ tenant_id       │
                        │ tenant_id       │     │ matter_id       │
                        │ code_verifier   │     │ user_id         │
                        │ nonce           │     │ event_type      │
                        │ expires_at_utc  │     │ event_json      │
                        └─────────────────┘     │ created_at_utc  │
                                                └─────────────────┘
```

### Tenant Isolation Pattern

Every query enforces tenant/matter scope:
```sql
SELECT * FROM chunks
WHERE tenant_id = :tenant_id
  AND matter_id = :matter_id
  AND docs_snapshot_id = :snapshot_id
```

**See [data-model.md](./architecture/data-model.md) for complete schemas.**

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

### Provider Interfaces

```python
# LLM Provider (NFR-032) - app/llm/
class LLMClient(Protocol):
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
    ) -> LLMResponse: ...

# Implementations: AzureOpenAIClient, AnthropicClient, GeminiClient, OllamaClient

# Search Provider (NFR-034) - app/search/
class SearchClient(Protocol):
    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        tenant_id: str,
        matter_id: str,
        top_k: int = 10,
    ) -> SearchResponse: ...

# Implementations: AzureSearchClient, LocalSearchClient (pgvector)

# Embedding Provider (NFR-035) - app/embedding/
class EmbeddingClient(Protocol):
    async def embed(
        self,
        texts: list[str],
    ) -> EmbeddingResult: ...

# Implementations: AzureOpenAIEmbeddingClient, LocalEmbeddingClient

# Parser Provider (NFR-036) - app/parser/
class ParserClient(Protocol):
    async def parse(
        self,
        file_path: str,
    ) -> ParseResult: ...

# Implementations: MarkerClient, LlamaParseClient, PyPDFClient
```

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

```
┌──────────┐                                                    ┌──────────┐
│  Client  │                                                    │   API    │
└────┬─────┘                                                    └────┬─────┘
     │                                                                │
     │ 1. POST /auth/login (email, password)                         │
     │───────────────────────────────────────────────────────────────>│
     │                                                                │
     │                                      2. Validate credentials   │
     │                                         Check failed_login_ct  │
     │                                         Check locked_until_utc │
     │                                                                │
     │ 3. Return JWT access token (15 min) + refresh token (7 days)  │
     │<───────────────────────────────────────────────────────────────│
     │                                                                │
     │ 4. API request with Authorization: Bearer <access_token>      │
     │───────────────────────────────────────────────────────────────>│
     │                                                                │
     │                                      5. Validate JWT signature │
     │                                         Extract tenant_id      │
     │                                         Check expiration       │
     │                                                                │
     │ 6. Response with data                                          │
     │<───────────────────────────────────────────────────────────────│
     │                                                                │
     │ (After 15 min, access token expires)                           │
     │                                                                │
     │ 7. POST /auth/refresh (refresh_token)                          │
     │───────────────────────────────────────────────────────────────>│
     │                                                                │
     │                                      8. Validate refresh token │
     │                                         Check revoked_at_utc   │
     │                                         Check expires_at_utc   │
     │                                                                │
     │ 9. Return new access token + refresh token                    │
     │<───────────────────────────────────────────────────────────────│
```

**SSO Flow (Microsoft/Google OIDC):**
```
User → /auth/sso/microsoft → OIDC Provider → Callback → Validate ID Token
  → Create/Link User → Issue JWT + Refresh Token
```

**Security Features (FR-050):**
- Password hashing: bcrypt (cost factor 12)
- Account lockout: 5 failed attempts → 15 min lock
- Refresh token rotation: New token on each refresh
- Token revocation: All tokens revoked on password change
- PKCE for SSO: Protects against authorization code interception

### Tenant Isolation Enforcement

```python
# Middleware enforces tenant context on every request
@app.middleware("http")
async def tenant_middleware(request: Request, call_next):
    # Extract from JWT claims
    token = extract_jwt(request)
    tenant_id = token["tenant_id"]
    user_id = token["sub"]

    # Resolve matter from request (path/query)
    matter_id = resolve_matter(request)

    # Verify user has matter access (FR-004)
    if not user_has_matter_access(user_id, tenant_id, matter_id):
        raise HTTPException(403, "Access denied")

    # Inject into request state - available to all handlers
    request.state.tenant_id = tenant_id
    request.state.matter_id = matter_id
    request.state.user_id = user_id

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
mypy apps/api/app --strict    # Type checking (NFR-040)
pytest tests/ -v              # Unit + integration
pytest evals/ -v              # Golden query evals (>95% pass required)
```

### Test Coverage

| Category | Coverage Target | Current |
|----------|-----------------|---------|
| Unit tests | >80% | ~85% |
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
