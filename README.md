# evidence-docqa (DocQ&A v3.1 demo)

A demo-first, near-free **evidence-bound Document Q&A** system.

## Demo invariants (non-negotiable)
1. **No answer** without retrieved evidence + **valid citations**  
2. If retrieval confidence < threshold -> **refuse** (no clarifying questions in MVP)  
3. Persist `request_id` + version snapshot for every request  
4. Evals gate config promotions

## Repo layout
```
/apps/web        Next.js UI (Vercel)
/apps/api        FastAPI service (Azure App Service)
/packages/shared Shared schemas/types
/docs            PRD + architecture + eval requirements
/tasks           One file per task
/evals           Eval runner + suites
```

## Quickstart (3 commands)
### 1) API
```bash
cd apps/api
python -m venv .venv
./.venv/Scripts/activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2) Web
```bash
cd apps/web
npm install
npm run dev
```

### 3) Run evals
```bash
python -m evals.run --suite golden
```

## Environment Variables
See `docs/ENVIRONMENT.md` for required variables, secret handling, and
environment-specific guidance.

## Docs
- `ARCHITECTURE.md` — Overview + pointers to modular docs
- `docs/architecture/` — Detailed architecture (data model, interfaces, deployment)
- `docs/PRD.md`
- `docs/EVALS_V1_REQUIREMENTS.md`
- `docs/OPEN_QUESTIONS.md`
- `docs/ENVIRONMENT.md`
- `docs/DECISION_RECORD_001_LLM_VERIFICATION.md`
