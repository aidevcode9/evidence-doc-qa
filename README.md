# evidence-docqa (DocQ&A v3.1 demo)

A demo-first, near-free **evidence-bound Document Q&A** system.

## Demo invariants (non-negotiable)
1. **No answer** without retrieved evidence + **valid citations**  
2. If retrieval confidence < threshold → **refuse** (no clarifying questions in MVP)  
3. Persist `request_id` + version snapshot for every request  
4. Evals gate config promotions

## Repo layout
```
/apps/web        Next.js UI (Vercel)
/apps/api        FastAPI service (Azure Container Apps)
/packages/shared Shared schemas/types
/docs            PRD + architecture + eval requirements
/tasks           One file per task
/evals           Eval runner + suites
```

## Quickstart (3 commands)
### 1) API
```bash
cd apps/api
uv sync
export DATABASE_URL="postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 2) Web
```bash
cd apps/web
pnpm install
pnpm dev
```

### 3) Run evals
```bash
python -m evals.run --suite golden
```

## Docs
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/EVALS_V1_REQUIREMENTS.md`
- `docs/OPEN_QUESTIONS.md`
