# Task 031 - Shared Schema Codegen (SSOT) - COMPLETED

## Status: COMPLETED
- Consolidated Pydantic models into `packages/shared/python/evidence_shared/schemas.py`.
- Created a `pyproject.toml` for the shared package and installed it in editable mode.
- Established a Python-First generation strategy using `pydantic-to-typescript2`.
- Created an automated generation script: `scripts/gen-types.ps1`.
- Synchronized `apps/api` and `apps/web` to use the shared models and generated types.

## Acceptance tests - PASSED
- [x] A modification to the core schema automatically results in updated Typescript interfaces after running a build/gen command.
- [x] Frontend compile errors occur if the API contract changes partially (type safety).
- [x] Removed reliance on manually synced "magic strings" or duplicated interfaces.

## Implementation Details
1. **Shared Package**: `packages/shared/python` is now a proper Python package `evidence-shared`.
2. **SSOT**: `packages/shared/python/evidence_shared/schemas.py` defines all data contracts.
3. **Codegen**: `scripts/gen-types.ps1` runs `pydantic2ts` which uses `json2ts` (from `json-schema-to-typescript`) to generate `apps/web/types/generated.ts`.
4. **API Integration**: `apps/api/app/schemas.py` now re-exports from `evidence_shared.schemas`.
5. **Frontend Integration**: `apps/web/types/index.ts` imports from `generated.ts`.
6. **Enums**: Used `RefusalCode` Enum to replace magic strings in both API and Frontend.

## Files touched
- `packages/shared/python/evidence_shared/schemas.py`
- `packages/shared/python/pyproject.toml`
- `apps/api/app/schemas.py`
- `apps/api/app/services/ask_service.py`
- `apps/web/types/generated.ts`
- `apps/web/types/index.ts`
- `apps/web/components/MessageBubble.tsx`
- `scripts/gen-types.ps1`
