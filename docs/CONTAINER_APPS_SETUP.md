# Azure Container Apps Setup

This document describes the Azure Container Apps infrastructure for the DocQ&A API.

## Why Container Apps?

The original Azure App Service deployment timed out (17+ minutes) when installing `marker-pdf` and its `torch` dependency via Kudu's pip install. Container Apps solves this by:

1. Building the Docker image once with all dependencies
2. Deploying the pre-built container (fast, ~2 min)
3. Supporting OCR via marker-pdf in production

## Azure Resources

| Resource | Name | Purpose |
|----------|------|---------|
| Container Registry | `docqaregistry.azurecr.io` | Stores Docker images |
| Container Apps Environment | `docqa-env` | Networking, logging |
| Container App | `docqa-api` | Runs the API |

## Initial Setup (One-Time)

These commands were used to create the Azure resources:

```bash
# Variables
RESOURCE_GROUP="doc-qa-demo"
LOCATION="eastus"
ACR_NAME="docqaregistry"
ENV_NAME="docqa-env"
APP_NAME="docqa-api"

# 1. Create Container Registry
az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true

# 2. Create Container Apps Environment
az containerapp env create \
  --name $ENV_NAME \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION

# 3. Create Container App (initial placeholder)
az containerapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENV_NAME \
  --image mcr.microsoft.com/azuredocs/containerapps-helloworld:latest \
  --target-port 8000 \
  --ingress external \
  --registry-server $ACR_NAME.azurecr.io \
  --registry-username $ACR_NAME \
  --registry-password $(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)
```

## GitHub Secrets Required

Add these secrets to the repository (Settings → Secrets → Actions):

| Secret | Value | Source |
|--------|-------|--------|
| `ACR_LOGIN_SERVER` | `docqaregistry.azurecr.io` | Fixed |
| `ACR_USERNAME` | `docqaregistry` | Fixed |
| `ACR_PASSWORD` | (password) | `az acr credential show --name docqaregistry --query passwords[0].value -o tsv` |

Existing secrets (already configured for App Service):
- `AZURE_CREDENTIALS` - Service principal JSON
- `DATABASE_URL` - PostgreSQL connection string
- `AZURE_OPENAI_*` - OpenAI credentials
- `AZURE_SEARCH_*` - Search service credentials
- `VERCEL_URL` - Frontend URL for CORS

## Deployment Workflow

The workflow `.github/workflows/deploy-container.yml` runs on push to main:

1. Builds Docker image from `apps/api/Dockerfile`
2. Pushes to ACR with commit SHA and `latest` tags
3. Updates Container App with new image and environment variables

## Dockerfile

Multi-stage build in `apps/api/Dockerfile`:
- **Builder stage**: Installs Python dependencies (marker-pdf, torch)
- **Production stage**: Slim image with runtime dependencies only

## Environment Variables

Set via GitHub Actions on every deploy:
- Database, OpenAI, Search credentials from secrets
- `PARSER_PROVIDER=marker` - Enables OCR
- `EMBEDDINGS_MODE=remote` - Uses Azure OpenAI embeddings
- `DOCQA_ALLOWED_ORIGINS` - CORS for localhost and Vercel

## Vercel Frontend Configuration

After first successful Container Apps deployment:

1. Get the Container App URL:
   ```bash
   az containerapp show --name docqa-api --resource-group doc-qa-demo --query properties.configuration.ingress.fqdn -o tsv
   ```

2. Update Vercel environment variable:
   - Go to Vercel project → Settings → Environment Variables
   - Update `NEXT_PUBLIC_API_URL` to `https://<container-app-url>`

## Troubleshooting

### View Container Logs
```bash
az containerapp logs show \
  --name docqa-api \
  --resource-group doc-qa-demo \
  --follow
```

### Check Container App Status
```bash
az containerapp show \
  --name docqa-api \
  --resource-group doc-qa-demo \
  --query "{status:properties.runningStatus,url:properties.configuration.ingress.fqdn}"
```

### Restart Container App
```bash
az containerapp revision restart \
  --name docqa-api \
  --resource-group doc-qa-demo \
  --revision $(az containerapp revision list --name docqa-api --resource-group doc-qa-demo --query "[0].name" -o tsv)
```

### Manual Deploy (Testing)
```bash
cd apps/api
docker build -t docqaregistry.azurecr.io/docqa-api:test .
az acr login --name docqaregistry
docker push docqaregistry.azurecr.io/docqa-api:test
az containerapp update --name docqa-api --resource-group doc-qa-demo --image docqaregistry.azurecr.io/docqa-api:test
```

## Rollback

If Container Apps has issues, you can temporarily revert to App Service:

1. Re-enable `.github/workflows/deploy.yml` (change trigger back to `main`)
2. Remove marker-pdf from requirements.txt (no OCR)
3. Push to trigger App Service deploy

Note: This disables OCR support until Container Apps is fixed.
