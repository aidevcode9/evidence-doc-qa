# Task 008 - Azure Services Setup (DocQ&A Demo)

## Scope
- Create or reuse a dedicated Azure resource group for the demo.
- Provision Azure Container Apps (API) with public ingress.
- Provision Azure Container Apps Job for ingestion/indexing.
- Provision Azure Blob Storage for raw PDFs and snapshots.
- Provision Azure AI Search (basic tier) with vector + BM25 index.
- Provision Azure OpenAI (if available) or document alternate provider config.
- Provision Application Insights with minimal sampling.
- Optional: Redis (Azure Cache for Redis) for caching.
- Capture all required connection strings, keys, and endpoints.

## Acceptance tests
- All resources exist in the target subscription and resource group.
- API can read secrets via env vars and connect to Storage and Search.
- Ingestion job can run with required permissions.
- Application Insights shows at least one trace from the API.

## Manual setup checklist (Azure Portal)
- Create or select the target subscription and resource group.
- Create Azure Container Apps environment and API app with public ingress.
- Create Container Apps Job for ingestion/indexing.
- Create Storage account + Blob container for raw PDFs/snapshots.
- Create Azure AI Search (basic tier) and record endpoint/key/index name.
- Create Application Insights and connect it to the API.
- Optional: create Azure Cache for Redis if caching is needed.
- If Azure OpenAI is available, create a resource and record endpoint/key.

## Environment variable mapping (capture values)
- `DB_DATABASE_URL`: Postgres connection string.
- `AZURE_STORAGE_ACCOUNT`: Storage account name.
- `AZURE_STORAGE_CONTAINER`: Blob container name for raw PDFs/snapshots.
- `AZURE_STORAGE_CONNECTION_STRING`: Storage connection string.
- `AZURE_SEARCH_ENDPOINT`: Search endpoint URL.
- `AZURE_SEARCH_API_KEY`: Search admin/query key.
- `AZURE_SEARCH_INDEX`: Index name used by the API.
- `AZURE_SEARCH_CREATE_INDEX`: Set to `1` for first-time index creation.
- `DOCQA_ENABLE_INDEXING`: Set to `1` to enable indexing jobs.
- `DOCQA_METRICS_ADMIN_TOKEN`: Admin token for `/v1/metrics`.
- `EMBEDDINGS_MODE` / `EMBEDDINGS_LOCAL`: Set based on local vs remote embeddings.

## Files likely touched
- `docs/ARCHITECTURE.md`
- `docs/PROJECT_PLAN_CODEX.md`
- `docs/ENVIRONMENT.md`
- `README.md`
