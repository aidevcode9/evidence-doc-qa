# Environment Variables

This project uses environment variables for configuration. Keep secrets out of
the repo; use `.env` for local development and managed secrets in hosted
environments.

## Local development
- Copy `.env.example` to `.env` and fill in values.
- Never commit `.env` or other files that contain secrets.

## Hosted environments
- Web (Vercel): use project environment variables (Development/Preview/Prod).
- API (Azure App Service): use "Configuration" settings in the Azure Portal or Bicep/GitHub Secrets.
- Jobs (Azure): In the current demo, ingestion runs within the main API App Service for simplicity.

## Required variables
Use `.env.example` as the source of truth for required keys and defaults.
`DATABASE_URL` is the primary Postgres connection string; `DB_DATABASE_URL` is a legacy alias.
All project-specific variables are prefixed (for example, `DOCQA_`, `DB_`,
`EMBEDDINGS_`, `AZURE_`) to avoid collisions.

## Azure OpenAI (optional)
When using remote embeddings or generation (e.g., gpt5-mini and text-embedding-3-large), set:
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION`
- `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`

If using a separate verification (chat) model, set:
- `AZURE_OPENAI_CHAT_ENDPOINT`
- `AZURE_OPENAI_CHAT_API_KEY`
- `AZURE_OPENAI_CHAT_API_VERSION`

## Logging and safety
- Do not log raw user questions or document text.
- Redact emails, phone numbers, and SSN-like patterns in any logged text.

## Cost tracking (optional)
Configure token pricing in `docs/ENVIRONMENT_REFERENCE.md` to populate `cost_est`
in telemetry. Demo defaults are enabled; update to match your Azure pricing.
