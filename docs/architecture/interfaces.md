# Provider Interfaces

> Swap providers via config, not code changes.

## LLMClient (NFR-032)

**Status:** Implemented in `apps/api/app/llm/`

```python
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
```

### Implementations

| Provider | Config Value | Default Model | Notes |
|----------|--------------|---------------|-------|
| Azure OpenAI | `azure_openai` | via `MODEL_ID` | Enterprise, managed |
| Anthropic | `anthropic` | `claude-sonnet-4-20250514` | Best reasoning |
| Google Gemini | `gemini` | `gemini-2.0-flash` | Fast, cost-effective |
| Ollama | `ollama` | `llama3.2:8b` | Local, air-gapped |

### Configuration

```bash
LLM_PROVIDER=azure_openai  # azure_openai | anthropic | gemini | ollama

# Azure OpenAI
AZURE_OPENAI_CHAT_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_CHAT_API_KEY=xxx
MODEL_ID=gpt-4o

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Ollama (local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:8b
```

## EmbeddingClient (NFR-035)

```python
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
```

### Implementations

- `LocalEmbeddingClient` — nomic-embed-text-v1.5 (default, no API)
- `AzureEmbeddingClient` — Azure OpenAI embeddings
- `OpenAIEmbeddingClient` — text-embedding-3-large

## SearchClient (NFR-034)

```python
@dataclass
class SearchResult:
    chunk_id: str
    text: str
    score: float
    page_number: int
    document_id: str

class SearchClient(ABC):
    @abstractmethod
    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        tenant_id: str,
        matter_id: str,
        top_k: int = 20,
    ) -> list[SearchResult]:
        """
        Hybrid search: BM25 + vector with RRF fusion.
        MUST filter by tenant_id and matter_id.
        """
        pass
```

### Implementations

- `PgVectorSearchClient` — PostgreSQL + pgvector + FTS (default)
- `AzureSearchClient` — Azure AI Search with semantic reranker

### RRF Fusion

```python
def reciprocal_rank_fusion(bm25_results, vector_results, k=60):
    """Score = sum(1 / (k + rank)) for each list where doc appears."""
    scores = defaultdict(float)
    for rank, r in enumerate(bm25_results):
        scores[r.chunk_id] += 1 / (k + rank + 1)
    for rank, r in enumerate(vector_results):
        scores[r.chunk_id] += 1 / (k + rank + 1)
    return sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
```

## ParserClient (NFR-036)

**Status:** Implemented in `apps/api/app/parsers/`

```python
@dataclass
class ParseResult:
    text: str                    # Full extracted text (markdown)
    pages: list[PageContent]     # Per-page content
    tables: list[dict]           # Extracted tables
    metadata: dict               # Title, author, page_count
    provider: str                # 'marker' | 'llamaparse' | 'pypdf'

class ParserClient(ABC):
    @abstractmethod
    async def parse(
        self,
        file_path: str,
        *,
        extract_tables: bool = True,
        force_ocr: bool = False,
    ) -> ParseResult:
        pass
```

### Implementations

| Provider | Best For | Notes |
|----------|----------|-------|
| pypdf | Simple PDFs | Fast, no OCR |
| Marker | Scanned docs | Open source, good OCR |
| LlamaParse | Complex tables | Cloud API, best accuracy |

### Configuration

```bash
PARSER_PROVIDER=marker  # pypdf | marker | llamaparse
LLAMAPARSE_API_KEY=xxx  # Only for llamaparse
MARKER_USE_LLM=0        # Enable LLM-enhanced parsing
```
