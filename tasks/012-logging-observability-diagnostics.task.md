# Task 012: Logging, Observability, and Diagnostics

## Description
Implement a robust structured logging system and enhanced diagnostic traces to debug issues like "Low Retrieval Confidence" and empty responses. This task ensures the "Full Traceability" invariant is met with developer-friendly logs.

## Objectives
- [x] **Structured Logging:** Implement a standard Python `logging` configuration in `apps/api/app/telemetry.py`.
- [x] **Request Tracing:** Log every `/v1/ask` request with its `request_id`, `question`, and `docs_snapshot_id`.
- [x] **Retrieval Diagnostics:** 
    - Log the raw count of hits from Azure AI Search.
    - Log the RRF scores and chunk IDs of the top candidates before confidence filtering.
- [x] **Ingestion Tracing:** Log storage container and local paths during PDF ingestion.
- [x] **Telemetry Enrichment:**
    - Estimate token counts (char_count / 4) in telemetry rows to avoid "0" values.
    - Added `trace_metadata` column for future session/user mapping.
    - Ensure every `_emit_refusal` call logs the specific reason to the console.
- [ ] **Frontend Error Transparency:** Update `apps/web/app/page.tsx` to display specific server-side error messages in the assistant bubble during failures.

## Acceptance Criteria
- [ ] The API console shows clear, structured logs for every search and refusal.
- [ ] Developers can see exactly why a query was refused (e.g., "Top score 0.12 < CONF_MIN 0.35").
- [ ] The `telemetry` table in Postgres contains realistic token estimations.
