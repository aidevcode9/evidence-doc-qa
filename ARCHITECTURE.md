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

#### TracedLLMClient Wrapper

```python
# apps/api/app/llm/traced_client.py

import time
from uuid import uuid4
from typing import Optional
from dataclasses import dataclass

from langfuse import Langfuse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import (
    LANGFUSE_ENABLED, 
    LANGFUSE_PUBLIC_KEY, 
    LANGFUSE_SECRET_KEY,
    LANGFUSE_HOST,
)
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
        self.langfuse: Optional[Langfuse] = None
        
        if LANGFUSE_ENABLED and LANGFUSE_PUBLIC_KEY:
            self.langfuse = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_HOST,
            )
    
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
        Logs to both llm_calls table AND Langfuse.
        """
        call_id = str(uuid4())
        langfuse_trace_id = None
        langfuse_generation_id = None
        
        # Start Langfuse trace
        trace = None
        generation = None
        if self.langfuse:
            trace = self.langfuse.trace(
                name="qa_completion",
                user_id=user_id,
                session_id=session_id,
                metadata={
                    "tenant_id": tenant_id,
                    "matter_id": matter_id,
                    "call_id": call_id,
                },
            )
            langfuse_trace_id = trace.id
            
            generation = trace.generation(
                name="llm_completion",
                model=self.client.model,
                input={"system": system_prompt, "user": user_prompt},
                model_parameters={
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
            langfuse_generation_id = generation.id
        
        # Make LLM call
        start_time = time.perf_counter()
        status = "success"
        error_message = None
        response = None
        
        try:
            response = await self.client.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            
            if generation:
                generation.end(
                    output=response.content,
                    usage={
                        "prompt_tokens": response.prompt_tokens,
                        "completion_tokens": response.completion_tokens,
                    },
                )
                
        except Exception as e:
            status = "error"
            error_message = str(e)
            
            if generation:
                generation.end(
                    output=None,
                    status_message=error_message,
                    level="ERROR",
                )
            raise
            
        finally:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Log to llm_calls table (ALWAYS, even on error)
            await self._log_to_database(
                call_id=call_id,
                tenant_id=tenant_id,
                session_id=session_id,
                message_id=message_id,
                provider=self.client.provider,
                model=self.client.model,
                prompt_tokens=response.prompt_tokens if response else 0,
                completion_tokens=response.completion_tokens if response else 0,
                latency_ms=latency_ms,
                status=status,
                error_message=error_message,
                langfuse_trace_id=langfuse_trace_id,
                langfuse_generation_id=langfuse_generation_id,
            )
            
            if self.langfuse:
                self.langfuse.flush()
        
        return TracedLLMResponse(
            content=response.content,
            provider=response.provider,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=latency_ms,
            langfuse_trace_id=langfuse_trace_id,
            langfuse_generation_id=langfuse_generation_id,
        )
    
    async def _log_to_database(
        self,
        call_id: str,
        tenant_id: str,
        session_id: str,
        message_id: Optional[str],
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        status: str,
        error_message: Optional[str],
        langfuse_trace_id: Optional[str],
        langfuse_generation_id: Optional[str],
    ) -> None:
        """Log to llm_calls table for billing and audit."""
        await self.db_session.execute(
            text("""
                INSERT INTO llm_calls (
                    id, tenant_id, session_id, message_id,
                    provider, model,
                    prompt_tokens, completion_tokens, latency_ms,
                    status, error_message,
                    langfuse_trace_id, langfuse_generation_id,
                    created_at
                ) VALUES (
                    :id, :tenant_id, :session_id, :message_id,
                    :provider, :model,
                    :prompt_tokens, :completion_tokens, :latency_ms,
                    :status, :error_message,
                    :langfuse_trace_id, :langfuse_generation_id,
                    NOW()
                )
            """),
            {
                "id": call_id,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "message_id": message_id,
                "provider": provider,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "latency_ms": latency_ms,
                "status": status,
                "error_message": error_message,
                "langfuse_trace_id": langfuse_trace_id,
                "langfuse_generation_id": langfuse_generation_id,
            }
        )
```

#### Usage in Services

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

> **Status:** ✅ IMPLEMENTED. See `apps/api/app/llm/` module.

Provider-agnostic interface. Swap via config, not code.

```python
# apps/api/app/llm/base.py

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
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        pass

# Implementations (all in apps/api/app/llm/)
class AzureOpenAIClient(LLMClient): ...  # Azure-hosted GPT-4o (default)
class AnthropicClient(LLMClient): ...    # Claude Sonnet 4 / Opus 4
class GeminiClient(LLMClient): ...       # Google Gemini 2.0 Flash
class OllamaClient(LLMClient): ...       # Local open-source (Llama 3.2, Mistral, etc.)
```

#### Supported Providers

| Provider | Config Value | Default Model | Notes |
|----------|--------------|---------------|-------|
| Azure OpenAI | `azure_openai` | Configured via `MODEL_ID` | Enterprise, managed |
| Anthropic | `anthropic` | `claude-sonnet-4-20250514` | Best reasoning |
| Google Gemini | `gemini` | `gemini-2.0-flash` | Fast, cost-effective |
| Ollama | `ollama` | `llama3.2:8b` | Local, air-gapped, open-source |

#### Ollama Models for Legal/RAG Use Cases

| Model | RAM Required | Quality | Speed | Notes |
|-------|--------------|---------|-------|-------|
| `llama3.2:8b` | 16GB | Good | Fast | Recommended for most cases |
| `llama3.3:70b` | 40GB+ VRAM | Excellent | Slow | Best quality, GPU required |
| `mistral:7b` | 16GB | Good | Very fast | Strong reasoning |
| `qwen2.5:7b` | 16GB | Good | Fast | Excellent on structured tasks |

**Config-driven selection:**

```python
# apps/api/app/llm/__init__.py
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "azure_openai")

def get_llm_client() -> LLMClient:
    if LLM_PROVIDER == "azure_openai":
        return AzureOpenAIClient(...)
    elif LLM_PROVIDER == "anthropic":
        return AnthropicClient(api_key=ANTHROPIC_API_KEY, model=ANTHROPIC_MODEL)
    elif LLM_PROVIDER == "gemini":
        return GeminiClient(api_key=GEMINI_API_KEY, model=GEMINI_MODEL)
    elif LLM_PROVIDER == "ollama":
        return OllamaClient(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)
```

#### Environment Variables

```bash
# LLM Provider Selection
LLM_PROVIDER=azure_openai  # azure_openai | anthropic | gemini | ollama

# Azure OpenAI (default)
AZURE_OPENAI_CHAT_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_CHAT_API_KEY=xxx
MODEL_ID=gpt-4o

# Anthropic Claude
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Google Gemini
GEMINI_API_KEY=xxx
GEMINI_MODEL=gemini-2.0-flash

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:8b
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

### ParserClient (NFR-036) — Document Parsing

> **Status:** ✅ IMPLEMENTED. See `apps/api/app/parsers/` module.

Provider-agnostic interface for PDF/DOCX parsing with OCR. Critical for legal documents.

```python
# apps/api/app/parser/client.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class ParserProvider(Enum):
    LLAMAPARSE = "llamaparse"    # Cloud API, best scanned OCR
    MARKER = "marker"            # Open source, fast, good with --use_llm
    DOCLING = "docling"          # IBM, 97.9% on complex tables
    UNSTRUCTURED = "unstructured" # Fallback, works offline

@dataclass
class PageContent:
    page_number: int
    text: str
    tables: list[dict]  # Structured table data
    images: list[dict]  # Image metadata (not raw bytes)

@dataclass
class ParseResult:
    text: str                      # Full extracted text (markdown format)
    pages: list[PageContent]       # Per-page content with metadata
    tables: list[dict]             # All extracted tables (structured)
    metadata: dict                 # Title, author, dates, page_count
    parse_time_ms: int
    provider: str                  # 'llamaparse' | 'marker' | 'docling' | 'unstructured'
    cached: bool                   # True if loaded from cache

class ParserClient(ABC):
    @abstractmethod
    async def parse(
        self,
        file_path: str,
        *,
        parsing_instructions: str | None = None,  # Natural language hints
        extract_tables: bool = True,
        force_ocr: bool = False,                  # Force OCR even on digital PDFs
        use_cache: bool = True,
    ) -> ParseResult:
        """Parse document to structured text/markdown."""
        pass
```

---

## Deployment Tiers (NFR-033, NFR-034)

> **All providers controlled by environment variables.** No code changes to switch tiers.

### Provider Matrix

| Tier | Parser | Search | Embeddings | LLM Primary | LLM Fallback |
|------|--------|--------|------------|-------------|--------------|
| **Starter** | pypdf | pgvector + FTS | local (nomic) | Gemini Flash | Anthropic Claude |
| **Professional** | LlamaParse | pgvector + FTS | Azure OpenAI | Azure OpenAI GPT-4o | Anthropic Claude |
| **Enterprise** | LlamaParse | Azure AI Search | Azure OpenAI | Azure OpenAI GPT-4o | Anthropic Claude |
| **VPC** | LlamaParse | pgvector + FTS | Azure OpenAI | Azure OpenAI (customer) | Gemini |
| **On-Prem (GPU)** | Marker | pgvector + FTS | local (nomic) | Ollama + Llama 3.2 | Ollama + Mistral |
| **On-Prem (tables)** | Docling | pgvector + FTS | local (nomic) | Ollama + Llama 3.3 70B | Ollama + Qwen 2.5 |

#### LLM Provider Comparison

| Provider | Latency | Cost | Quality | Air-Gap | Best For |
|----------|---------|------|---------|---------|----------|
| Azure OpenAI | Low | $$$ | Excellent | No | Enterprise with Azure |
| Anthropic Claude | Low | $$$ | Excellent | No | Best reasoning, legal analysis |
| Google Gemini | Very Low | $$ | Very Good | No | Cost-effective, fast queries |
| Ollama (local) | Medium | Free | Good | Yes | On-prem, data sovereignty |

### Config by Tier

**Starter/Professional Mode:**

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/evidence

# Parser
PARSER_PROVIDER=llamaparse  # or pypdf for Starter
LLAMAPARSE_API_KEY=xxx

# Search
SEARCH_PROVIDER=pgvector

# Embeddings
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=xxx

# LLM
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=xxx
LLM_MODEL=claude-3.5-sonnet
LLM_FALLBACK_PROVIDER=openai
LLM_FALLBACK_MODEL=gpt-4o

# Langfuse (cloud)
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

**Enterprise/VPC/On-Prem Mode:**

```bash
# ... same as above, plus:

# Langfuse (self-hosted)
LANGFUSE_HOST=http://langfuse.internal:3000
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
| LLM Observability | Langfuse (self-hosted or cloud) | LLM debugging, cost tracking |
| Ingestion Queue | PostgreSQL SKIP LOCKED | Simple job queue (or Redis for scale) |

### Docker Compose (Single Node)

```yaml
services:
  api:
    build: ./apps/api
    environment:
      DATABASE_URL: postgresql://...
      LLM_PROVIDER: anthropic
      LANGFUSE_ENABLED: "true"
      LANGFUSE_HOST: http://langfuse:3000
    depends_on:
      - postgres
      - minio
      - langfuse

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

  # Langfuse for LLM observability
  langfuse:
    image: langfuse/langfuse:latest
    ports:
      - "3001:3000"
    environment:
      DATABASE_URL: postgresql://langfuse:password@postgres-langfuse:5432/langfuse
      NEXTAUTH_SECRET: ${LANGFUSE_NEXTAUTH_SECRET}
      NEXTAUTH_URL: http://localhost:3001
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
  pgdata:
  miniodata:
  langfuse_pgdata:
```

### Kubernetes (Multi-Node)

Same images, Helm chart for:
- HPA on API pods
- StatefulSet for Postgres (or managed RDS/Cloud SQL)
- PVC for MinIO (or managed S3)
- Separate worker deployment (scale independently)
- Langfuse deployment (or use Langfuse Cloud)

---

## Key Constraints

| Constraint | Rationale |
|------------|-----------|
| **All providers config-driven** | Swap Parser/Search/Embedding/LLM via env vars, no code changes (NFR-032, 034, 035, 036) |
| **Dual logging to llm_calls + Langfuse** | Billing/audit in DB; debugging in Langfuse (NFR-030) |
| **langfuse_trace_id stored in llm_calls** | Correlation for debugging specific calls |
| **All LLM calls via TracedLLMClient** | No raw LLM calls allowed; ensures telemetry |
| **Self-hosted Langfuse for Enterprise+** | Data sovereignty for legal industry |
| All queries filter by `tenant_id` | Tenant isolation (FR-001) |
| All artifacts scoped by `matter_id` | Matter isolation (FR-002) |
| `embedding_model` stored with vectors | Mixed-model deployments; future migrations |
| No hard cloud vendor deps | Deployment portability (Section 6.3) |
| pgvector over dedicated vector DB | Single database reduces ops complexity |

---

## Database Migrations (Alembic)

The project uses **Alembic** for database schema migrations. This ensures reproducible schema changes across environments.

### Directory Structure

```
alembic/
├── alembic.ini          # Alembic configuration
├── env.py               # Migration environment setup
└── versions/            # Migration scripts
    ├── 0001_create_tables.py
    ├── 0002_add_page_char_offsets.py
    └── 0003_add_qa_session_tables.py
```

### Common Commands

```bash
# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current

# Show migration history
alembic history

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade 0002_add_page_char_offsets

# Create new migration (after modifying models in db.py)
alembic revision -m "add_new_table"
```

### Migration Naming Convention

```
NNNN_description.py

Examples:
0001_create_tables.py
0002_add_page_char_offsets.py
0003_add_qa_session_tables.py
```

### Auto-create vs Alembic

The app also calls `Base.metadata.create_all()` on startup via `init_db()`. This:
- Creates missing tables automatically (useful for fresh databases)
- Does NOT modify existing tables (won't add new columns)

**Use Alembic** when:
- Adding columns to existing tables
- Modifying column types
- Adding indexes
- Any schema change to production databases

### Migration Template

```python
"""description of change

Revision ID: NNNN_description
Revises: previous_revision
Create Date: YYYY-MM-DD

"""

from alembic import op
import sqlalchemy as sa

revision = "NNNN_description"
down_revision = "previous_revision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Forward migration
    op.create_table(...)
    op.add_column(...)


def downgrade() -> None:
    # Reverse migration (for rollback)
    op.drop_column(...)
    op.drop_table(...)
```

### Environment Variable

Alembic reads `DATABASE_URL` from environment:

```ini
# alembic.ini
sqlalchemy.url = ${DATABASE_URL}
```

---

## Migration Notes

When adding new deployment tier or swapping providers:

1. Implement new `LLMClient` or `EmbeddingClient` subclass
2. Add config option in `config.py`
3. Update `get_llm_client()` / `get_embedding_client()`
4. Test with evals (`pytest evals/ -v`)
5. Document quality trade-offs if on-prem

**No code changes in business logic** — just config + new adapter.
