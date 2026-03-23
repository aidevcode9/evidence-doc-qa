# Deployment Guide

This document describes how Evidence-Bound deploys to Azure (API) and Vercel (Web).

> **Migration note:** The API originally deployed to Azure App Service via ZIP deploy, but marker-pdf/torch installation caused 17+ minute build timeouts. On 2026-01-24 we migrated to Azure Container Apps, which pre-builds the Docker image in CI. See [CONTAINER_APPS_SETUP.md](CONTAINER_APPS_SETUP.md) for the full setup guide.

---

## Backend (API) — Azure Container Apps

### Deployment flow

1. Push to `main` (paths: `apps/api/**`, `packages/shared/**`)
2. GitHub Actions builds Docker image from `apps/api/Dockerfile`
3. Image pushed to Azure Container Registry (ACR) with SHA + `latest` tags
4. `az containerapp update` deploys the new image

Source: [`.github/workflows/deploy-container.yml`](../.github/workflows/deploy-container.yml)

### Docker images

| Dockerfile | Use case | Size |
|------------|----------|------|
| `apps/api/Dockerfile` | Full build (marker-pdf + torch + OCR) | ~4 GB |
| `apps/api/Dockerfile.slim` | PyPDF-only mode (FR-055) | ~500 MB |

Both are multi-stage builds with the repo root as build context (to access `packages/shared`).

### Required GitHub Secrets

**Azure Infrastructure:**
- `AZURE_CREDENTIALS` — Service principal for Azure CLI login
- `ACR_LOGIN_SERVER` — ACR hostname (e.g., `yourregistry.azurecr.io`)
- `ACR_USERNAME` / `ACR_PASSWORD` — ACR push credentials
- `API_URL` — Deployed API base URL (used for SSO redirect URI)

**Database:**
- `DATABASE_URL` — PostgreSQL connection string

**Azure OpenAI (Embeddings + Chat):**
- `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`
- `AZURE_OPENAI_CHAT_ENDPOINT` / `AZURE_OPENAI_CHAT_API_KEY` / `AZURE_OPENAI_CHAT_API_VERSION`
- `DOCQA_MODEL_ID`

**Azure AI Search:**
- `AZURE_SEARCH_ENDPOINT` / `AZURE_SEARCH_API_KEY` / `AZURE_SEARCH_INDEX`

**Auth & SSO:**
- `JWT_SECRET_KEY`
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`

**Observability:**
- `APPLICATIONINSIGHTS_CONNECTION_STRING`
- `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`
- `METRICS_ADMIN_TOKEN`

### Hardcoded env vars (set in workflow, not secrets)

| Variable | Value | Notes |
|----------|-------|-------|
| `PARSER_PROVIDER` | `pypdf` | Slim mode; change to `marker` for OCR support |
| `EMBEDDINGS_MODE` | `remote` | Uses Azure OpenAI embeddings |
| `AUTH_MODE` | `headers` | Demo mode; use `jwt` for production |
| `AUTH_BYPASS_ENABLED` | `true` | Demo mode; set `false` for production |
| `GOOGLE_SSO_ENABLED` | `true` | Google login enabled |
| `MICROSOFT_SSO_ENABLED` | `false` | Microsoft login disabled |
| `LANGFUSE_ENABLED` | `1` | LLM tracing enabled |
| `EMBEDDING_CACHE_ENABLED` | `1` | 5000-entry embedding cache |
| `QUERY_CACHE_ENABLED` | `0` | Result cache disabled (opt-in) |

### Container Apps resource

| Setting | Value |
|---------|-------|
| Resource Group | `doc-qa-demo` |
| App Name | `docqa-api` |
| Image | `{ACR}/docqa-api:{sha}` |

### Deprecated: App Service workflow

The old App Service deployment (`.github/workflows/deploy.yml`) is **disabled** — trigger branch is set to `"never-trigger-this-workflow"`. It references Bicep infra (`infra/main.bicep`) and ZIP deploy, which are no longer used.

---

## Frontend (Web) — Vercel

### Deployment flow
- Source: Vercel GitHub integration (auto-deploys on push)
- Root directory: `apps/web`
- Build command: default Next.js build

### Required Vercel environment variables
- `NEXT_PUBLIC_API_URL` — Points to the Azure Container Apps API base URL

### CORS
The API allows requests from `http://localhost:3000` (dev) and `https://evidence-doc-qa-v2.vercel.app` (prod) via `DOCQA_ALLOWED_ORIGINS`.

---

## CI (Evals Gate)

### CI flow
- Workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
- Runs on every PR and push to `main`
- Uses SQLite for testing: `DATABASE_URL=sqlite:///./ci_test.db`
- Embeddings in local mode: `EMBEDDINGS_MODE=local`
- No Docker, no Azure services — purely local testing
- Seeds eval data, starts API on `localhost:8000`, runs golden eval suite
