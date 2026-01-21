# ARCHITECTURE.md — Evidence-Bound

> Implementation details: data model, interfaces, deployment tiers, and infrastructure decisions.

## Design Principles

1. **Open Source First** — PostgreSQL + pgvector, MinIO, OpenTelemetry, Prometheus/Grafana
2. **LLM Abstraction** — Swap providers via config, not code changes
3. **Deployment Portability** — Same images; Docker Compose (single-node) or Kubernetes (multi-node)
4. **Single Database** — PostgreSQL for metadata + vectors + FTS reduces operational complexity

---

## Data Model

All tables include: `created_at TIMESTAMP`, `updated_at TIMESTAMP`, `created_by UUID` where applicable.

### Core Tables

```sql
-- Tenant isolation
tenants (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    settings_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Users scoped to tenant
users (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    email TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'admin', 'attorney', 'paralegal', 'viewer'
    mfa_enabled BOOL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Matters (cases) scoped to tenant
matters (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    name TEXT NOT NULL,
    status TEXT DEFAULT 'active',  -- 'active', 'closed', 'hold'
    retention_days INT DEFAULT 365,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Matter membership (RBAC per matter)
matter_members (
    matter_id UUID REFERENCES matters(id),
    user_id UUID REFERENCES users(id),
    role TEXT NOT NULL,  -- 'owner', 'editor', 'viewer'
    PRIMARY KEY (matter_id, user_id)
);
```

### Document & Chunk Tables

```sql
-- Uploaded documents
documents (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    matter_id UUID REFERENCES matters(id),
    filename TEXT NOT NULL,
    storage_uri TEXT NOT NULL,  -- S3/MinIO path
    sha256 TEXT NOT NULL,       -- Deduplication
    page_count INT,
    metadata_json JSONB,        -- doc_type, date, custodian, tags
    privilege_flag BOOL DEFAULT FALSE,
    status TEXT DEFAULT 'queued',  -- 'queued', 'processing', 'ready', 'failed'
    created_at TIMESTAMP DEFAULT NOW()
);

-- Document chunks with embeddings
doc_chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    tenant_id UUID REFERENCES tenants(id),
    matter_id UUID REFERENCES matters(id),
    page_number INT NOT NULL,
    char_start INT NOT NULL,
    char_end INT NOT NULL,
    text TEXT NOT NULL,
    embedding_model TEXT NOT NULL,  -- Track which model generated embedding
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- pgvector column and index
ALTER TABLE doc_chunks ADD COLUMN embedding vector(1536);
CREATE INDEX idx_chunks_embedding ON doc_chunks 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Full-text search index (for BM25 hybrid)
ALTER TABLE doc_chunks ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('english', text)) STORED;
CREATE INDEX idx_chunks_fts ON doc_chunks USING gin(search_vector);
```

### Q&A & Session Tables

```sql
-- Chat sessions per matter
qa_sessions (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    matter_id UUID REFERENCES matters(id),
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Messages in session (user + assistant)
qa_messages (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES qa_sessions(id),
    role TEXT NOT NULL,  -- 'user', 'assistant'
    content TEXT NOT NULL,
    citations_json JSONB,  -- [{chunk_id, page, text_snippet}, ...]
    created_at TIMESTAMP DEFAULT NOW()
);
```

### LLM Tracking (NFR-030)

```sql
-- Track every LLM call for audit + cost
# ARCHITECTURE.md — LLM Observability Update

> **Instructions:** Replace the existing "LLM Tracking (NFR-030)" section (lines ~457-473) with this content.
> Also add the new "LLM Observability" section immediately after.

---

### LLM Tracking (NFR-030)

```sql
-- Track every LLM call for audit + cost + Langfuse correlation
llm_calls (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    session_id UUID REFERENCES qa_sessions(id),
    message_id UUID REFERENCES qa_messages(id),
    
    -- Provider info
    provider TEXT NOT NULL,           -- 'anthropic', 'openai', 'azure', 'ollama'
    model TEXT NOT NULL,              -- 'claude-3.5-sonnet', 'gpt-4o', 'llama-3.1-70b'
    
    -- Usage metrics
    prompt_tokens INT,
    completion_tokens INT,
    latency_ms INT,
    
    -- Status
    status TEXT NOT NULL,             -- 'success', 'error', 'timeout'
    error_message TEXT,               -- Error details if status != 'success'
    
    -- Langfuse correlation (for debugging UI)
    langfuse_trace_id TEXT,           -- Links to Langfuse trace for debugging
    langfuse_generation_id TEXT,      -- Links to specific generation span
    
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for billing queries
CREATE INDEX idx_llm_calls_tenant_date ON llm_calls(tenant_id, created_at);

-- Index for Langfuse correlation lookups
CREATE INDEX idx_llm_calls_langfuse ON llm_calls(langfuse_trace_id);
```

### LLM Observability with Langfuse

> **Dual logging:** Every LLM call is logged to BOTH `llm_calls` table (for billing/audit) AND Langfuse (for debugging UI).

#### Why Dual Logging?

| Concern | Solution |
|---------|----------|
| **Billing accuracy** | `llm_calls` table — you own the data |
| **Legal audit trail** | `llm_calls` table — data stays in your DB |
| **Debugging UI** | Langfuse — trace viewer, prompt playground |
| **Cost dashboard** | Langfuse — built-in cost tracking |
| **Offline access** | `llm_calls` table — no external dependency |

#### Langfuse Configuration

```python
# apps/api/app/config.py

import os

# Langfuse settings
LANGFUSE_ENABLED = os.getenv("LANGFUSE_ENABLED", "true").lower() == "true"
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")  # or self-hosted URL
```

#### Environment Variables

```bash
# Langfuse (add to existing env vars)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com  # or http://localhost:3000 for self-hosted
```

#### TracedLLMClient Interface

```python
# apps/api/app/llm/traced_client.py

from dataclasses import dataclass
from typing import Optional

from app.llm.client import LLMClient, LLMResponse


@dataclass
class TracedLLMResponse(LLMResponse):
    """LLM response with observability metadata."""
    langfuse_trace_id: Optional[str] = None
    langfuse_generation_id: Optional[str] = None


class TracedLLMClient:
    """
    Wrapper that logs all LLM calls to:
    1. llm_calls table (for billing + audit)
    2. Langfuse (for debugging UI)
    
    INVARIANT: Every LLM call MUST go through this wrapper.
    Direct calls to LLMClient are prohibited.
    """
    
    def __init__(self, client: LLMClient, db_session: AsyncSession):
        self.client = client
        self.db_session = db_session
        self.langfuse = self._init_langfuse()
    
    async def complete(
        self,
        tenant_id: str,
        session_id: str,
        message_id: Optional[str],
        system_prompt: str,
        user_prompt: str,
        user_id: Optional[str] = None,
        matter_id: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> TracedLLMResponse:
        """
        Complete with full observability.
        
        Flow:
        1. Start Langfuse trace
        2. Make LLM call
        3. Log to llm_calls table
        4. End Langfuse generation
        5. Return enriched response
        """
        # Implementation details in full file
        pass
```

#### Usage Pattern

```python
# apps/api/app/services/ask_service.py

class AskService:
    def __init__(self, db_session: AsyncSession):
        self.llm = TracedLLMClient(
            client=get_llm_client(),
            db_session=db_session,
        )
    
    async def answer_question(self, ...):
        # CORRECT: Use TracedLLMClient
        response = await self.llm.complete(
            tenant_id=tenant_id,
            session_id=session_id,
            message_id=message_id,
            system_prompt=prompt,
            user_prompt=question,
        )
        
        # WRONG: Direct LLM call (no telemetry)
        # response = await self.raw_client.complete(...)
```

#### Self-Hosted Langfuse (Enterprise/VPC/On-Prem)

```yaml
# docker-compose.langfuse.yml
services:
  langfuse:
    image: langfuse/langfuse:latest
    ports:
      - "3001:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:password@postgres-langfuse:5432/langfuse
      NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET}
      NEXTAUTH_URL: ${LANGFUSE_URL}
      SALT: ${LANGFUSE_SALT}
    depends_on:
      - postgres-langfuse
  
  postgres-langfuse:
    image: postgres:16
    environment:
      POSTGRES_USER: langfuse
      POSTGRES_PASSWORD: ${LANGFUSE_DB_PASSWORD}
      POSTGRES_DB: langfuse
    volumes:
      - langfuse_pgdata:/var/lib/postgresql/data

volumes:
  langfuse_pgdata:
```

#### Deployment Tiers

| Tier | Langfuse Deployment | Notes |
|------|---------------------|-------|
| Starter | Langfuse Cloud (free: 50k traces/mo) | Quick start |
| Professional | Langfuse Cloud (Pro: $59/mo) | More traces |
| Enterprise | Self-hosted Langfuse | Data sovereignty |
| VPC | Self-hosted in customer VPC | Customer controls |
| On-Prem | Self-hosted on-prem | Air-gapped option |

---

> **Add to Key Constraints section:**

| Constraint | Rationale |
|------------|-----------|
| **Dual logging to llm_calls + Langfuse** | Billing/audit in DB; debugging in Langfuse (NFR-030) |
| **langfuse_trace_id stored in llm_calls** | Correlation for debugging specific calls |
| **Self-hosted Langfuse for Enterprise+** | Data sovereignty for legal industry |
| **All LLM calls via TracedLLMClient** | No raw LLM calls allowed; ensures telemetry |
```

### Audit & Usage Tables

```sql
-- Immutable audit log
audit_events (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    matter_id UUID,
    user_id UUID REFERENCES users(id),
    event_type TEXT NOT NULL,    -- 'query', 'upload', 'export', 'delete'
    event_json JSONB NOT NULL,   -- Details (no PII, redacted excerpts)
    response_id UUID,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Daily usage rollup (billing)
usage_daily (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    date DATE NOT NULL,
    queries_count INT DEFAULT 0,
    pages_ingested INT DEFAULT 0,
    llm_tokens_prompt BIGINT DEFAULT 0,
    llm_tokens_completion BIGINT DEFAULT 0,
    storage_bytes BIGINT DEFAULT 0,
    PRIMARY KEY (tenant_id, date)
);
```

---

## Interfaces

### LLMClient (NFR-032)

Provider-agnostic interface. Swap via config, not code.

```python
# apps/api/app/llm/client.py

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class LLMResponse:
    content: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int

class LLMClient(ABC):
    @abstractmethod
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        pass

# Implementations
class AnthropicClient(LLMClient): ...   # Claude 3.5 Sonnet
class OpenAIClient(LLMClient): ...       # GPT-4o
class AzureOpenAIClient(LLMClient): ...  # Azure-hosted
class OllamaClient(LLMClient): ...       # Local (Llama 3.1)
```

**Config-driven selection:**

```python
# config.py
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # or 'openai', 'azure', 'ollama'
LLM_MODEL = os.getenv("LLM_MODEL", "claude-3.5-sonnet")
LLM_FALLBACK_PROVIDER = os.getenv("LLM_FALLBACK_PROVIDER", "openai")

def get_llm_client() -> LLMClient:
    if LLM_PROVIDER == "anthropic":
        return AnthropicClient(model=LLM_MODEL)
    elif LLM_PROVIDER == "openai":
        return OpenAIClient(model=LLM_MODEL)
    # ... etc
```

### EmbeddingClient (Section 6.2)

```python
# apps/api/app/embeddings/client.py

@dataclass
class EmbeddingResult:
    vector: list[float]
    model: str
    dimensions: int

class EmbeddingClient(ABC):
    @abstractmethod
    async def embed(self, text: str) -> EmbeddingResult:
        pass
    
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        pass

# Implementations
class LocalEmbeddingClient(EmbeddingClient):
    """Default: nomic-embed-text-v1.5 (local, no API calls)"""
    pass

class OpenAIEmbeddingClient(EmbeddingClient):
    """Cloud option: text-embedding-3-large (1536 dims)"""
    pass
```

---

## Deployment Tiers (NFR-033)

| Tier | LLM Primary | LLM Fallback | Embeddings | Notes |
|------|-------------|--------------|------------|-------|
| **Cloud/Hosted** | Anthropic Claude 3.5 Sonnet | OpenAI GPT-4o | OpenAI text-embedding-3-large | Multi-tenant SaaS |
| **VPC** | Azure OpenAI (customer tenant) | Anthropic API | Azure OpenAI embeddings | Single-tenant in customer cloud |
| **On-Prem** | Ollama + Llama 3.1 70B | Ollama + Qwen 2.5 72B | nomic-embed-text-v1.5 (local) | Air-gapped option |

### On-Prem Requirements (NFR-031)

- UI displays **"Local Model"** badge when using Ollama
- Documentation must state quality trade-offs:
  - Llama 3.1 70B: ~85-90% of Claude quality on legal reasoning
  - Higher latency (2-5x slower)
  - No external API calls (air-gap compatible)

### Environment Variables by Tier

```bash
# Cloud/Hosted
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3.5-sonnet
LLM_FALLBACK_PROVIDER=openai
LLM_FALLBACK_MODEL=gpt-4o
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-large

# VPC (Azure)
LLM_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://customer.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4o
EMBEDDING_PROVIDER=azure

# On-Prem
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:70b
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=nomic-embed-text-v1.5
OLLAMA_BASE_URL=http://localhost:11434
```

---

## Infrastructure

### Open Source Stack (Section 6.1)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Database | PostgreSQL 16 + pgvector | Metadata + vectors + FTS |
| Object Storage | MinIO (S3-compatible) | Document storage |
| Metrics | Prometheus + Grafana | Dashboards, alerts |
| Logs | Loki | Centralized logging |
| Tracing | OpenTelemetry + Jaeger | Distributed tracing |
| Ingestion Queue | PostgreSQL SKIP LOCKED | Simple job queue (or Redis for scale) |

### Docker Compose (Single Node)

```yaml
services:
  api:
    build: ./apps/api
    environment:
      DATABASE_URL: postgresql://...
      LLM_PROVIDER: anthropic
    depends_on:
      - postgres
      - minio

  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - pgdata:/var/lib/postgresql/data

  minio:
    image: minio/minio
    command: server /data
    volumes:
      - miniodata:/data

  worker:
    build: ./apps/api
    command: python -m app.worker
    # Ingestion worker (OCR, chunking, embedding)
```

### Kubernetes (Multi-Node)

Same images, Helm chart for:
- HPA on API pods
- StatefulSet for Postgres (or managed RDS/Cloud SQL)
- PVC for MinIO (or managed S3)
- Separate worker deployment (scale independently)

---

## Key Constraints

| Constraint | Rationale |
|------------|-----------|
| All queries filter by `tenant_id` | Tenant isolation (FR-001) |
| All artifacts scoped by `matter_id` | Matter isolation (FR-002) |
| `embedding_model` stored with vectors | Mixed-model deployments; future migrations |
| `llm_calls` logged for every response | Audit trail + cost tracking (NFR-030) |
| No hard cloud vendor deps | Deployment portability (Section 6.3) |
| pgvector over dedicated vector DB | Single database reduces ops complexity |

---

## Migration Notes

When adding new deployment tier or swapping providers:

1. Implement new `LLMClient` or `EmbeddingClient` subclass
2. Add config option in `config.py`
3. Update `get_llm_client()` / `get_embedding_client()`
4. Test with evals (`pytest evals/ -v`)
5. Document quality trade-offs if on-prem

**No code changes in business logic** — just config + new adapter.
