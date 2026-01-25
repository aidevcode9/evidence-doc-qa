# Evidence-Bound

**Enterprise Document Q&A with Verified Citations**

Evidence-Bound is a production-ready RAG (Retrieval-Augmented Generation) system designed for law firms and regulated industries. Unlike general-purpose AI assistants, **every answer must be grounded in source documents**—the system refuses to answer if it cannot cite specific evidence.

## Key Features

- **Hallucination Prevention**: Post-LLM validation ensures cited chunks actually exist in the corpus
- **Confidence Gating**: Configurable threshold (default: 70%)—below threshold triggers automatic refusal
- **Multi-Tenant Isolation**: Every query scoped by `tenant_id` and `matter_id`
- **Hybrid Search**: BM25 keyword + vector semantic + reranker for optimal retrieval
- **Multiple LLM Providers**: Azure OpenAI, Ollama (local), Google Gemini, Anthropic Claude
- **Production Observability**: OpenTelemetry + Langfuse for LLM tracing

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Next.js UI    │────▶│   FastAPI API   │────▶│  Azure OpenAI   │
│   (Vercel)      │     │ (Container Apps)│     │  (GPT-4o)       │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            ▼
            ┌───────────┐ ┌───────────┐ ┌───────────┐
            │PostgreSQL │ │Azure AI   │ │ Langfuse  │
            │           │ │Search     │ │ (Tracing) │
            └───────────┘ └───────────┘ └───────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Azure account (for Azure OpenAI and Search) OR local Ollama

### 1. Clone and Install

```bash
git clone https://github.com/YOUR_USERNAME/evidence-doc-qa.git
cd evidence-doc-qa

# API
cd apps/api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend
cd ../web
npm install
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

**Minimum required variables:**
```bash
DATABASE_URL=postgresql://user:password@localhost:5432/docqa
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-3-large
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_API_KEY=your-key
AZURE_SEARCH_INDEX=docqa-index
```

**For local development with Ollama (no Azure required):**
```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:8b
EMBEDDINGS_MODE=local
SEARCH_PROVIDER=local
```

### 3. Run Database Migrations

```bash
cd apps/api
alembic upgrade head
```

### 4. Start Services

```bash
# Terminal 1: API
cd apps/api
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd apps/web
npm run dev
```

Open http://localhost:3000

## Project Structure

```
evidence-doc-qa/
├── apps/
│   ├── api/                 # FastAPI backend
│   │   ├── app/
│   │   │   ├── main.py      # Application entry
│   │   │   ├── config.py    # Environment config
│   │   │   ├── retrieval.py # Hybrid search
│   │   │   ├── evidence.py  # Citation validation
│   │   │   ├── policy.py    # Pre/post-LLM gates
│   │   │   ├── verification.py # LLM verification
│   │   │   └── services/    # Business logic
│   │   └── alembic/         # Database migrations
│   └── web/                 # Next.js frontend
├── packages/shared/         # Shared TypeScript schemas
├── docs/                    # Documentation
│   ├── FEATURES.md          # Feature overview
│   └── ARCHITECTURE_OVERVIEW.md
├── tests/                   # Unit + integration tests
├── evals/                   # Golden query evaluations
└── .github/workflows/       # CI/CD pipelines
```

## Core Concepts

### Evidence-Bound Answers

Every answer must satisfy:
1. **Retrieved Evidence**: Answer based on chunks retrieved from the document corpus
2. **Valid Citations**: Each citation verified against actual chunk content
3. **Confidence Threshold**: Combined retrieval + verification score >= 0.70

If any check fails, the system returns a refusal instead of hallucinating.

### Document Pipeline

```
Upload → Parse (Marker/LlamaParse) → Chunk → Embed → Index → Search
```

1. **Parse**: Extract text from PDF/DOCX with OCR support
2. **Chunk**: Split into 900-character segments with 150-char overlap
3. **Embed**: Generate vectors via Azure OpenAI or local embeddings
4. **Index**: Store in Azure AI Search or PostgreSQL with pgvector

### Multi-Tenant Isolation

```python
# Every query is scoped
SELECT * FROM chunks
WHERE tenant_id = :tenant_id
  AND matter_id = :matter_id
  AND docs_snapshot_id = :snapshot_id
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/ask` | POST | Ask a question against documents |
| `/v1/docs/upload` | POST | Upload a document |
| `/v1/docs` | GET | List documents |
| `/v1/sessions` | GET | List Q&A sessions |
| `/v1/health` | GET | Health check |
| `/v1/metrics` | GET | Telemetry metrics |

## Configuration

See [.env.example](.env.example) for all configuration options.

### LLM Providers

| Provider | Config | Notes |
|----------|--------|-------|
| Azure OpenAI | `LLM_PROVIDER=azure_openai` | Production default |
| Ollama | `LLM_PROVIDER=ollama` | Local, free, privacy-focused |
| Google Gemini | `LLM_PROVIDER=gemini` | Fast, cost-effective |
| Anthropic | `LLM_PROVIDER=anthropic` | Claude models |

### Observability

| Feature | Config | Dashboard |
|---------|--------|-----------|
| OpenTelemetry | `DOCQA_OTEL_ENABLED=1` | Azure Monitor / Jaeger |
| Langfuse | `LANGFUSE_ENABLED=1` | cloud.langfuse.com |

## Development

### Run Tests

```bash
# Lint
ruff check apps/ --fix
ruff format apps/

# Type check
mypy apps/api/app --strict

# Unit tests
pytest tests/ -v

# Golden query evals
pytest evals/ -v
```

### Quality Gates

All PRs must pass:
- `ruff check` - Linting
- `mypy --strict` - Type checking
- `pytest tests/` - Unit tests
- `pytest evals/` - Evaluation suite (>95% pass rate required)

## Deployment

### Azure Container Apps (Recommended)

See [.github/workflows/deploy-container.yml](.github/workflows/deploy-container.yml)

```bash
# Build and push
docker build -f apps/api/Dockerfile -t your-acr.azurecr.io/docqa-api:latest .
docker push your-acr.azurecr.io/docqa-api:latest

# Deploy
az containerapp update --name docqa-api --image your-acr.azurecr.io/docqa-api:latest
```

### Vercel (Frontend)

Connect your repository to Vercel and set environment variables in the dashboard.

## Documentation

- [Feature Overview](docs/FEATURES.md) - Capabilities and roadmap
- [Architecture](docs/ARCHITECTURE_OVERVIEW.md) - Technical deep-dive
- [Environment Variables](.env.example) - Configuration reference
- [CLAUDE.md](CLAUDE.md) - Development guidelines and AI assistant context

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests first (TDD enforced)
4. Make your changes
5. Run quality gates (`ruff check && mypy && pytest`)
6. Commit with conventional format (`feat(scope): description`)
7. Push and open a PR

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Next.js](https://nextjs.org/) - React framework
- [Azure OpenAI](https://azure.microsoft.com/products/ai-services/openai-service) - LLM provider
- [Azure AI Search](https://azure.microsoft.com/products/ai-services/cognitive-search) - Hybrid search
- [Marker](https://github.com/VikParuchuri/marker) - PDF extraction
- [Langfuse](https://langfuse.com/) - LLM observability
- [OpenTelemetry](https://opentelemetry.io/) - Distributed tracing
