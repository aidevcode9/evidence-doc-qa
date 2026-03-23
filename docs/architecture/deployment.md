# Deployment

> How Evidence-Bound is deployed in production and how to run it locally.

## Production Architecture

```
┌─────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│   Vercel     │     │  Azure Container Apps │     │   Azure Services     │
│  (Frontend)  │────▶│  (FastAPI API)        │────▶│                      │
│  Next.js 14  │     │  Python 3.12          │     │  - PostgreSQL        │
└─────────────┘     └──────────────────────┘     │  - AI Search         │
                                                  │  - OpenAI (GPT-5-mini)   │
                                                  │  - Blob Storage      │
                                                  │  - App Insights      │
                                                  └──────────────────────┘
```

| Component | Service | Notes |
|-----------|---------|-------|
| **Frontend** | Vercel | Next.js 14, auto-deploy from `apps/web/` |
| **API** | Azure Container Apps | Docker image from `apps/api/Dockerfile` |
| **Database** | Azure PostgreSQL Flexible Server | Alembic migrations |
| **Search** | Azure AI Search | Hybrid BM25 + vector + semantic reranker |
| **LLM** | Azure OpenAI | GPT-5-mini (chat), text-embedding-3-large (embeddings) |
| **Storage** | Azure Blob Storage | Raw document uploads |
| **Observability** | Azure Application Insights + Langfuse | OTEL traces + LLM observability |

## Docker Images

### Full Image (`Dockerfile`)

Multi-stage build (~4GB) with marker-pdf + torch for OCR support:

```bash
# Build from repo root
docker build -f apps/api/Dockerfile -t evidence-bound-api .
```

- Python 3.12-slim base
- CPU-only torch (avoids 5GB+ CUDA)
- Runs as non-root `appuser`
- Health check on `/healthz`
- Supports all parser providers: pypdf, marker, llamaparse

### Slim Image (`Dockerfile.slim`)

Lightweight build (~500MB) for PyPDF-only mode (FR-055):

```bash
# Build from repo root
docker build -f apps/api/Dockerfile.slim -t evidence-bound-api-slim .
```

- No torch, marker-pdf, or OCR dependencies
- Forces `PARSER_PROVIDER=pypdf`
- Good for demos and development

Both images expose port 8000 and run uvicorn.

## Local Development

```bash
# API (with hot reload)
cd apps/api && uvicorn app.main:app --reload

# Frontend
cd apps/web && npm run dev
```

No docker-compose is provided. For local development, run the API directly with uvicorn and connect to a local or remote PostgreSQL instance.

## Environment Variables

All env vars are documented in [.env.example](../../.env.example) at the repo root. Key groups:

### Required for Production

```bash
# Database
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME

# Azure OpenAI (LLM + Embeddings)
AZURE_OPENAI_ENDPOINT=https://<name>.openai.azure.com
AZURE_OPENAI_API_KEY=xxx
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-3-large
DOCQA_MODEL_ID=gpt-5-mini

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://<name>.search.windows.net
AZURE_SEARCH_API_KEY=xxx
AZURE_SEARCH_INDEX=docqa-index-v3

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
AZURE_STORAGE_CONTAINER=docqa-raw

# Embeddings (production uses remote/Azure)
EMBEDDINGS_MODE=remote

# Auth (production)
AUTH_MODE=jwt
AUTH_BYPASS_ENABLED=0
JWT_SECRET_KEY=<generate-a-strong-secret>
```

### Observability (Optional but Recommended)

```bash
# Azure Application Insights
DOCQA_OTEL_ENABLED=1
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=xxx;...

# Langfuse LLM Tracing (NFR-045)
LANGFUSE_ENABLED=1
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Document Parsing

```bash
# Parser: pypdf (default), marker (OCR), llamaparse (cloud OCR)
PARSER_PROVIDER=marker
LLAMAPARSE_API_KEY=xxx          # Only for llamaparse
MARKER_USE_LLM=false            # Enable LLM enhancement for marker
MARKER_FORCE_OCR=false          # Force OCR even on digital PDFs
```

### Authentication & SSO

```bash
# Microsoft Entra ID (FR-051)
MICROSOFT_SSO_ENABLED=1
MICROSOFT_CLIENT_ID=xxx
MICROSOFT_CLIENT_SECRET=xxx
MICROSOFT_TENANT_ID=xxx

# Google Workspace (FR-051)
GOOGLE_SSO_ENABLED=1
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx

SSO_REDIRECT_URI=https://your-app.com/api/v1/auth/callback
```

See [.env.example](../../.env.example) for the full list with descriptions.

## Migrations

Database migrations use Alembic:

```bash
# Run all pending migrations
alembic upgrade head

# Check current revision
alembic current
```

Migrations are in `alembic/versions/`. Run before deploying new API versions.

## Planned (Not Yet Implemented)

The following are documented in REQUIREMENTS.md but not yet deployed:

- **Provider abstraction** (NFR-032, 034, 035): Config-driven swapping of LLM/search/embedding providers. Env vars (`LLM_PROVIDER`, `SEARCH_PROVIDER`) exist in `.env.example` but the abstraction layer is incomplete.
- **Deployment tiers** (Starter, Professional, Enterprise, On-Prem): Planned provider combinations for different deployment scenarios.
- **Self-hosted Langfuse** (NFR-046): Docker Compose with Langfuse container for air-gapped environments.
- **Kubernetes**: No Helm chart or K8s manifests exist yet.
