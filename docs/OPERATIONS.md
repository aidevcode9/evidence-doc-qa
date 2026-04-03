# Operations Runbook

> How to deploy, monitor, diagnose, and recover Evidence-Bound in production.

---

## Infrastructure

| Component | Service | Resource |
|-----------|---------|----------|
| API | Azure Container Apps | `docqa-api` in `doc-qa-demo` |
| Database | Azure Flexible Server | PostgreSQL 15 |
| Search | Azure AI Search | `doc-qa-search` |
| LLM | Azure OpenAI | `az-openai-docqa` |
| Storage | Azure Blob | `docqafiles` container `docqa-raw` |
| Frontend | Vercel | `evidence-doc-qa-v2.vercel.app` |
| Knowledge Site | Vercel | `knowledge.bound.legal` (Nextra, `apps/docs/`) |
| Registry | Azure Container Registry | `docqaregistry.azurecr.io` |
| Observability | Langfuse | `us.cloud.langfuse.com` |

---

## Deployment

### Automatic (CI/CD)

Push to `main` triggers GitHub Actions:

```
git push origin main
  → .github/workflows/deploy-container.yml
  → Docker build → ACR push → Container Apps update
```

**Triggers on changes to:** `apps/api/**`, `packages/shared/**`, `.github/workflows/deploy-container.yml`

**Frontend:** Vercel auto-deploys on push to `main` for `apps/web/` changes.

### Manual Deploy

```bash
# Build and push image
docker build -f apps/api/Dockerfile -t docqaregistry.azurecr.io/docqa-api:manual .
az acr login --name docqaregistry
docker push docqaregistry.azurecr.io/docqa-api:manual

# Update container
az containerapp update \
  --name docqa-api \
  --resource-group doc-qa-demo \
  --image docqaregistry.azurecr.io/docqa-api:manual
```

---

## Monitoring

### Health Check

```bash
curl https://docqa-api.nicedesert-f48be8e2.canadacentral.azurecontainerapps.io/healthz
```

Returns: `{"status": "ok", "parser_provider": "pypdf", "auth_bypass_enabled": false, ...}`

### Live Logs

```bash
# Stream logs
az containerapp logs show \
  --name docqa-api \
  --resource-group doc-qa-demo \
  --type console \
  --tail 100

# Follow (real-time)
az containerapp logs show \
  --name docqa-api \
  --resource-group doc-qa-demo \
  --type console \
  --follow
```

### Key Log Patterns

| Pattern | Meaning |
|---------|---------|
| `INFO: "GET /healthz" 200` | Health check OK |
| `INFO: "POST /v1/ask" 200` | Question answered |
| `ERROR: Background indexing failed` | Document processing error |
| `list_matters_for_tenant: primary query FAILED` | Matters query fell back to legacy |
| `Non-retryable server side error` | OTEL/Azure Monitor issue (non-blocking) |

### Metrics Endpoint

```bash
curl -H "Authorization: Bearer <admin-token>" \
  https://docqa-api.../v1/metrics
```

Returns p50/p95/p99 latency, cost breakdown, cache stats, refusal rates.

### Langfuse Dashboard

LLM traces at: `https://us.cloud.langfuse.com`
- Every `/v1/ask` request creates a trace
- Shows: model, tokens, latency, verdict per sub-operation
- PII-safe: never logs raw questions or answers

---

## Incident Response

### Step 1: Assess

```bash
# Is the container running?
az containerapp show --name docqa-api --resource-group doc-qa-demo \
  --query "properties.runningStatus"

# Check health
curl -s https://docqa-api.nicedesert-f48be8e2.canadacentral.azurecontainerapps.io/healthz

# Recent logs (last 100 lines)
az containerapp logs show --name docqa-api --resource-group doc-qa-demo \
  --type console --tail 100
```

### Step 2: Diagnose

| Symptom | Check | Likely Cause |
|---------|-------|-------------|
| 500 on all endpoints | Logs for Python tracebacks | Code bug, missing env var |
| 500 on `/v1/matters` only | Logs for SQL errors | DB query issue |
| 500 on `/v1/ask` only | Logs for Azure OpenAI errors | LLM service down or key expired |
| Document upload fails | Logs for "Background indexing failed" | Parser crash, missing dep |
| Login fails | Check `AUTH_MODE`, JWT secret | Auth misconfiguration |
| Slow responses | Langfuse traces, `/v1/metrics` | Azure Search or OpenAI latency |
| OTEL 400 errors | Logs for "Bad Request" | Connection string issue (non-blocking) |

### Step 3: Rollback (if needed)

```bash
# List revisions
az containerapp revision list \
  --name docqa-api \
  --resource-group doc-qa-demo \
  -o table

# Activate previous good revision
az containerapp revision activate \
  --name docqa-api \
  --resource-group doc-qa-demo \
  --revision <revision-name>

# Verify
curl https://docqa-api.nicedesert-f48be8e2.canadacentral.azurecontainerapps.io/healthz
```

### Step 4: Hotfix

```bash
# Fix code locally
# Test against prod DB:
cd apps/api
python -c "from app.db import ...; # test your fix"

# Run quality gates
ruff check apps/ && mypy apps/api/app --strict && pytest tests/ -v

# Push (triggers automatic redeploy)
git add . && git commit -m "fix: description" && git push origin main
```

---

## Database Operations

### Connect to Prod DB

```bash
# Connection string is in .env or GitHub secrets
psql "postgresql://pgadmin:***@doc-qa.postgres.database.azure.com:5432/docqa?sslmode=require"
```

### Common Queries

```sql
-- Count matters by tenant
SELECT tenant_id, COUNT(*) FROM matters GROUP BY tenant_id;

-- Check document processing status
SELECT status, COUNT(*) FROM documents GROUP BY status;

-- Recent failed uploads
SELECT doc_id, doc_name, error_message, ingested_at_utc
FROM documents WHERE status = 'failed'
ORDER BY ingested_at_utc DESC LIMIT 10;

-- Telemetry: recent request latency
SELECT request_id, latency_ms, tokens_in, tokens_out, cost_est, refusal_code
FROM telemetry ORDER BY timestamp_utc DESC LIMIT 20;
```

### IMPORTANT: DB Change Policy

**All database changes require explicit user approval before execution:**
- No `DELETE`, `UPDATE`, `ALTER`, `DROP` without confirmation
- No Alembic migrations without confirmation
- This applies to ALL environments (dev, staging, prod)

---

## Container Configuration

### Current Container Settings

```bash
az containerapp show --name docqa-api --resource-group doc-qa-demo \
  --query "properties.template.containers[0].resources"
```

| Setting | Value |
|---------|-------|
| CPU | 2 vCPU |
| Memory | 4 GiB |
| Min replicas | 1 |
| Max replicas | 4 |
| Scale trigger | Concurrent requests > 15 |
| Health probe | `GET /healthz` every 30s |

### Environment Variables

```bash
# List all env vars (values redacted)
az containerapp show --name docqa-api --resource-group doc-qa-demo \
  --query "properties.template.containers[0].env[].name" -o tsv
```

---

## Scheduled Maintenance

| Task | Frequency | How |
|------|-----------|-----|
| Check container health | Continuous | Health probe (automatic) |
| Review Langfuse traces | Weekly | Dashboard at langfuse.com |
| Check OTEL errors in logs | After deploy | Log review |
| Review telemetry costs | Monthly | `/v1/metrics` endpoint |
| Rotate JWT secret | Quarterly | Update secret, redeploy |
| Rotate Azure API keys | Quarterly | Azure Portal → regenerate |
| PostgreSQL backup verify | Monthly | Azure Portal → backups |
