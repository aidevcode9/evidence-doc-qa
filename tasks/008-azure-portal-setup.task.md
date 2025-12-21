# Task 008 - Azure Portal Setup (Demo Infrastructure)

## Scope
- Create Azure resource group for demo.
- Provision Azure Blob Storage for raw PDFs and snapshots.
- Provision Azure AI Search (basic tier) for hybrid retrieval.
- Provision Azure Container Apps environment and app for API.
- Provision Container Apps Job (or alternative) for ingestion/indexing.
- Configure Application Insights (minimal sampling).
- Document required env vars and connection strings.

## Acceptance tests
- Azure resources exist and are tagged for the demo project.
- API container can read required secrets via env vars.
- Blob Storage and AI Search endpoints are reachable from the API.
- Application Insights receives at least one test trace.

## Files likely touched
- `docs/ARCHITECTURE.md`
- `docs/PROJECT_PLAN_CODEX.md`
- `README.md`
