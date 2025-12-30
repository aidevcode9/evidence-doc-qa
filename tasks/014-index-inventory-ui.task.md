# Task 014 - Index Inventory Endpoint + UI (Searchable Docs)

## Scope
- Add an API endpoint that returns the currently searchable documents (index inventory).
- Add a UI view that lists searchable docs with key metadata and status.
- Ensure this view reinforces demo rigor and traceability.

## Requirements
### API
- New endpoint: `GET /v1/index/inventory`
- Response fields (per doc):
  - `doc_id`
  - `doc_name`
  - `docs_snapshot_id`
  - `date_added_utc`
  - `size_bytes`
  - `page_count`
  - `parse_mode`
  - `index_version`
  - `indexed_at_utc`
  - `storage_path`
- Sort order: newest `date_added_utc` first.
- If no docs exist, return an empty array (200 OK).

### UI
- Add a "Searchable Docs" panel or page.
- Display: doc name, size, date added, pages, snapshot id, parse mode, index version.
- Include a short hint that the list reflects the current searchable index.
- Show an empty-state message if no docs are indexed.

## Acceptance tests
- `GET /v1/index/inventory` returns a stable, non-null list of docs (or empty list) with all fields present.
- UI displays the list with correct formatting (size in KB/MB, dates in readable form).
- UI empty state renders when the list is empty.
- Inventory view matches the newest snapshot and does not list deleted docs.

## Notes
- This is a demo-facing feature to emphasize traceability and engineering rigor.
- The API should derive data from the authoritative store (DB/index metadata), not cached UI state.

## Files likely touched
- `apps/api/app/main.py`
- `apps/api/app/db.py`
- `apps/api/app/schemas.py`
- `apps/web/app/*`
- `apps/web/components/*`
