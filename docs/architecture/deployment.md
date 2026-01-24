# Deployment

> Same images; config-driven provider selection.

## Deployment Tiers

| Tier | Parser | Search | Embeddings | LLM |
|------|--------|--------|------------|-----|
| **Starter** | pypdf | pgvector | local (nomic) | Gemini Flash |
| **Professional** | LlamaParse | pgvector | Azure OpenAI | Azure GPT-4o |
| **Enterprise** | LlamaParse | Azure AI Search | Azure OpenAI | Azure GPT-4o |
| **VPC** | LlamaParse | pgvector | Azure OpenAI | Customer Azure |
| **On-Prem** | Marker | pgvector | local (nomic) | Ollama Llama 3.2 |

## Open Source Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Database | PostgreSQL 16 + pgvector | Metadata + vectors + FTS |
| Object Storage | MinIO (S3-compatible) | Document storage |
| Metrics | Prometheus + Grafana | Dashboards, alerts |
| Logs | Loki | Centralized logging |
| Tracing | OpenTelemetry + Jaeger | Distributed tracing |
| Queue | PostgreSQL SKIP LOCKED | Job queue |

## Docker Compose (Single Node)

```yaml
services:
  api:
    build: ./apps/api
    environment:
      DATABASE_URL: postgresql://user:pass@postgres:5432/evidence
      LLM_PROVIDER: azure_openai
      SEARCH_PROVIDER: pgvector
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

volumes:
  pgdata:
  miniodata:
```

## Kubernetes (Multi-Node)

Same images, Helm chart for:
- HPA on API pods
- StatefulSet for Postgres (or managed RDS)
- PVC for MinIO (or managed S3)
- Separate worker deployment

## Environment Variables

### Database

```bash
DATABASE_URL=postgresql://user:pass@host:5432/evidence
```

### Parser

```bash
PARSER_PROVIDER=marker  # pypdf | marker | llamaparse
LLAMAPARSE_API_KEY=xxx  # Only for llamaparse
```

### Search

```bash
SEARCH_PROVIDER=pgvector  # pgvector | azure

# Azure AI Search (if SEARCH_PROVIDER=azure)
AZURE_SEARCH_ENDPOINT=https://xxx.search.windows.net
AZURE_SEARCH_API_KEY=xxx
AZURE_SEARCH_INDEX=evidence-chunks
```

### Embeddings

```bash
EMBEDDINGS_MODE=local  # local | remote

# Azure OpenAI (if EMBEDDINGS_MODE=remote)
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com
AZURE_OPENAI_API_KEY=xxx
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-3-large
```

### LLM

```bash
LLM_PROVIDER=azure_openai  # azure_openai | anthropic | gemini | ollama

# Azure OpenAI
AZURE_OPENAI_CHAT_ENDPOINT=https://xxx.openai.azure.com
AZURE_OPENAI_CHAT_API_KEY=xxx
MODEL_ID=gpt-4o

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx

# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:8b
```

## Switching Providers

```bash
# 1. Change config
export SEARCH_PROVIDER=pgvector
export LLM_PROVIDER=ollama

# 2. Run migrations (if needed)
alembic upgrade head

# 3. Re-embed documents (if embedding model changed)
python -m app.tasks.reindex --all

# 4. Verify with evals
pytest evals/ -v
```

No code changes required.

## On-Prem Requirements (NFR-031)

- UI displays **"Local Model"** badge when using Ollama
- Document quality trade-offs:
  - Llama 3.1 70B: ~85-90% of Claude quality
  - Higher latency (2-5x slower)
  - No external API calls (air-gap compatible)
