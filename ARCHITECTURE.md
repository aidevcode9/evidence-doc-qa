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
llm_calls (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES qa_sessions(id),
    message_id UUID REFERENCES qa_messages(id),
    provider TEXT NOT NULL,      -- 'anthropic', 'openai', 'azure', 'ollama'
    model TEXT NOT NULL,         -- 'claude-3.5-sonnet', 'gpt-4o', 'llama-3.1-70b'
    prompt_tokens INT,
    completion_tokens INT,
    latency_ms INT,
    status TEXT NOT NULL,        -- 'success', 'error', 'timeout'
    created_at TIMESTAMP DEFAULT NOW()
);
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

## Interfaces (Target Architecture)

> **Status:** These interfaces are PLANNED but not yet implemented. Current code uses Azure services directly. Implement these when doing NFR-032, 034, 035.

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

class AzureEmbeddingClient(EmbeddingClient):
    """Azure OpenAI embeddings"""
    pass
```

### SearchClient (Retrieval Abstraction)

Provider-agnostic search interface. **Swap Azure AI Search ↔ pgvector via config only.**

```python
# apps/api/app/search/client.py

from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class SearchResult:
    chunk_id: str
    text: str
    score: float
    page_number: int
    document_id: str
    metadata: dict

class SearchClient(ABC):
    @abstractmethod
    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        tenant_id: str,
        matter_id: str,
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """
        Hybrid search: BM25 (keyword) + vector (semantic) with fusion.
        
        All implementations MUST:
        - Filter by tenant_id and matter_id (isolation)
        - Return results sorted by fused score
        - Include chunk_id for citation mapping
        """
        pass

# Implementations
class AzureSearchClient(SearchClient):
    """
    Azure AI Search with:
    - BM25 keyword search
    - Vector search (HNSW index)
    - Semantic reranker (optional)
    """
    pass

class PgVectorSearchClient(SearchClient):
    """
    PostgreSQL with:
    - Full-text search (tsvector + GIN index) for BM25
    - pgvector (ivfflat index) for vector search
    - Reciprocal Rank Fusion (RRF) for combining results
    """
    pass
```

**Config-driven selection:**

```python
# config.py
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "pgvector")  # 'pgvector' or 'azure'

def get_search_client() -> SearchClient:
    if SEARCH_PROVIDER == "azure":
        return AzureSearchClient(
            endpoint=os.getenv("AZURE_SEARCH_ENDPOINT"),
            api_key=os.getenv("AZURE_SEARCH_API_KEY"),
            index_name=os.getenv("AZURE_SEARCH_INDEX", "evidence-chunks"),
        )
    elif SEARCH_PROVIDER == "pgvector":
        return PgVectorSearchClient(
            database_url=os.getenv("DATABASE_URL"),
        )
    else:
        raise ValueError(f"Unknown SEARCH_PROVIDER: {SEARCH_PROVIDER}")
```

**RRF Fusion (for pgvector implementation):**

```python
def reciprocal_rank_fusion(
    bm25_results: list[SearchResult],
    vector_results: list[SearchResult],
    k: int = 60,
) -> list[SearchResult]:
    """
    Combine BM25 and vector results using RRF.
    Score = sum(1 / (k + rank)) for each list where doc appears.
    """
    scores = defaultdict(float)
    docs = {}
    
    for rank, result in enumerate(bm25_results):
        scores[result.chunk_id] += 1 / (k + rank + 1)
        docs[result.chunk_id] = result
    
    for rank, result in enumerate(vector_results):
        scores[result.chunk_id] += 1 / (k + rank + 1)
        docs[result.chunk_id] = result
    
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [docs[chunk_id] for chunk_id in sorted_ids]
```

---

## Deployment Tiers (NFR-033, NFR-034)

> **All providers controlled by environment variables.** No code changes to switch tiers.

### Provider Matrix

| Tier | Search | Embeddings | LLM Primary | LLM Fallback |
|------|--------|------------|-------------|--------------|
| **Azure (current)** | Azure AI Search | Azure OpenAI | Azure OpenAI (GPT-4o) | — |
| **Cloud OSS** | pgvector + FTS | OpenAI | Anthropic Claude 3.5 Sonnet | OpenAI GPT-4o |
| **VPC** | pgvector + FTS | Azure OpenAI | Azure OpenAI (customer tenant) | Anthropic API |
| **On-Prem** | pgvector + FTS | local (nomic) | Ollama + Llama 3.1 70B | Ollama + Qwen 2.5 72B |

### Config by Tier

**Azure Mode (current implementation):**

```bash
# Search
SEARCH_PROVIDER=azure
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=xxx
AZURE_SEARCH_INDEX=evidence-chunks

# Embeddings
EMBEDDING_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com
AZURE_OPENAI_API_KEY=xxx
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-large

# LLM
LLM_PROVIDER=azure
AZURE_LLM_DEPLOYMENT=gpt-4o
```

**Cloud OSS Mode (new direction):**

```bash
# Search
SEARCH_PROVIDER=pgvector
DATABASE_URL=postgresql://user:pass@host:5432/evidence

# Embeddings
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=xxx

# LLM
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=xxx
LLM_MODEL=claude-3.5-sonnet
LLM_FALLBACK_PROVIDER=openai
LLM_FALLBACK_MODEL=gpt-4o
```

**VPC Mode (customer cloud):**

```bash
# Search
SEARCH_PROVIDER=pgvector
DATABASE_URL=postgresql://...  # Customer's managed Postgres

# Embeddings  
EMBEDDING_PROVIDER=azure
AZURE_OPENAI_ENDPOINT=https://customer.openai.azure.com
AZURE_OPENAI_API_KEY=xxx  # Customer's key

# LLM
LLM_PROVIDER=azure
AZURE_LLM_DEPLOYMENT=gpt-4o
```

**On-Prem Mode (air-gapped):**

```bash
# Search
SEARCH_PROVIDER=pgvector
DATABASE_URL=postgresql://localhost:5432/evidence

# Embeddings
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=nomic-embed-text-v1.5

# LLM
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.1:70b
LLM_FALLBACK_MODEL=qwen2.5:72b
```

### Switching Providers

To switch from Azure to pgvector:

```bash
# 1. Change config
export SEARCH_PROVIDER=pgvector
export DATABASE_URL=postgresql://...

# 2. Run migrations (create pgvector indexes)
python -m alembic upgrade head

# 3. Re-embed documents (if embedding model changed)
python -m app.tasks.reindex --all

# 4. Verify with evals
pytest evals/ -v
```

**No code changes required.** The `get_search_client()`, `get_embedding_client()`, and `get_llm_client()` functions read config and return the appropriate implementation.

### On-Prem Requirements (NFR-031)

- UI displays **"Local Model"** badge when using Ollama
- Documentation must state quality trade-offs:
  - Llama 3.1 70B: ~85-90% of Claude quality on legal reasoning
  - Higher latency (2-5x slower)
  - No external API calls (air-gap compatible)

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
| **All providers config-driven** | Swap Search/Embedding/LLM via env vars, no code changes (NFR-032, 034, 035) |
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
