# Deployment Guide

This document describes how the DocQ&A demo deploys to Azure (API) and Vercel (Web).

## Backend (API) - Azure App Service

### Deployment flow
- Source: GitHub Actions (`.github/workflows/deploy.yml`)
- Infra: `infra/main.bicep` (App Service + app settings)
- App: ZIP deploy to App Service

### Required GitHub Secrets
Azure and app configuration:
- `AZURE_CREDENTIALS`
- `AZURE_SEARCH_ENDPOINT`
- `AZURE_SEARCH_API_KEY`
- `AZURE_SEARCH_INDEX`
- `DATABASE_URL`
- `METRICS_ADMIN_TOKEN`
- `VERCEL_URL`

Azure OpenAI (embeddings + chat verification):
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`
- `AZURE_OPENAI_CHAT_ENDPOINT`
- `AZURE_OPENAI_CHAT_API_KEY`
- `AZURE_OPENAI_CHAT_API_VERSION`
- `DOCQA_MODEL_ID`

### App Service settings (from Bicep)
Set by `infra/main.bicep`:
- `DATABASE_URL`
- `AZURE_SEARCH_ENDPOINT`
- `AZURE_SEARCH_API_KEY`
- `AZURE_SEARCH_INDEX`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`
- `AZURE_OPENAI_CHAT_ENDPOINT`
- `AZURE_OPENAI_CHAT_API_KEY`
- `AZURE_OPENAI_CHAT_API_VERSION`
- `DOCQA_MODEL_ID`
- `EMBEDDINGS_MODE=remote`
- `EMBEDDINGS_LOCAL=false`
- `METRICS_ADMIN_TOKEN`
- `DOCQA_ALLOWED_ORIGINS`

### Notes
- Azure OpenAI resources must allow network access from App Service.
- If verification is required, ensure `DOCQA_MODEL_ID` matches the chat deployment name.

## Frontend (Web) - Vercel

### Deployment flow
- Source: Vercel GitHub integration
- Root directory: `apps/web`
- Build command: default Next.js build

### Required Vercel Environment Variables
- `NEXT_PUBLIC_API_URL` (points to the Azure API base URL)

## CI (Evals Gate)

### CI flow
- Workflow: `.github/workflows/ci.yml`
- Uses local SQLite for evals (`DATABASE_URL=sqlite:///./ci_test.db`)
- Embeddings run in local mode (`EMBEDDINGS_MODE=local`)
