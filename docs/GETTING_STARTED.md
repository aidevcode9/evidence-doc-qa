# Getting Started

> Clone to running locally in 10 minutes.

---

## Prerequisites

- Python 3.12+
- Node.js 18+
- PostgreSQL 15+ (local or Azure)
- Git

---

## 1. Clone and Setup Backend

```bash
git clone https://github.com/aidevcode9/evidence-doc-qa.git
cd evidence-doc-qa

# Python virtual environment
cd apps/api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# For slim mode (no OCR, ~500MB instead of ~4GB):
# pip install -r requirements-slim.txt
```

## 2. Configure Environment

```bash
# Copy template
cp ../../.env.example ../../.env

# Edit .env with your values (see Required Variables below)
```

### Required Variables

| Variable | Example | Notes |
|----------|---------|-------|
| `DB_DATABASE_URL` | `postgresql+psycopg://user:pass@localhost:5432/docqa` | PostgreSQL connection |
| `AZURE_OPENAI_ENDPOINT` | `https://your-resource.openai.azure.com/` | Azure OpenAI |
| `AZURE_OPENAI_API_KEY` | `your-key` | API key |
| `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` | `text-embedding-3-large` | Embedding model |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` | Generate fresh |

### Local-Only Mode (No Azure)

```bash
# Use local embeddings + search (no Azure required)
EMBEDDINGS_MODE=local
SEARCH_PROVIDER=local
LLM_PROVIDER=ollama        # Requires Ollama running locally
AUTH_MODE=headers           # Skip JWT for dev
AUTH_BYPASS_ENABLED=1       # Skip auth entirely for dev
PARSER_PROVIDER=pypdf       # No OCR dependencies needed
```

## 3. Initialize Database

```bash
# Database tables are auto-created on first startup
cd apps/api
python -c "from app.db import init_db; init_db(); print('DB ready')"
```

## 4. Start Backend

```bash
cd apps/api
uvicorn app.main:app --reload --port 8000

# Verify:
curl http://localhost:8000/healthz
```

## 5. Setup Frontend

```bash
cd apps/web
npm install

# Create .env.local
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local

npm run dev
# Opens http://localhost:3000
```

## 6. Create a User (JWT mode)

```bash
# If using AUTH_MODE=jwt, create an admin user:
cd apps/api
python -c "
from app.db import init_db, create_user
init_db()
user = create_user(
    tenant_id='demo-tenant',
    email='admin@demo.com',
    role='admin',
    display_name='Admin',
    password='changeme123',
)
print(f'Created user: {user.user_id}')
"
```

Then login at `http://localhost:3000/login` with those credentials.

---

## Quick Verification

| Check | Command | Expected |
|-------|---------|----------|
| Backend health | `curl localhost:8000/healthz` | `{"status": "ok", ...}` |
| Frontend loads | Open `localhost:3000` | Login page or dashboard |
| DB connected | `python -c "from app.db import init_db; init_db()"` | No errors |

---

## Development Commands

```bash
# Lint
ruff check apps/

# Type check
mypy apps/api/app --strict

# Tests
pytest tests/ -v

# Evals (golden queries)
pytest evals/ -v

# All quality gates
ruff check apps/ && mypy apps/api/app --strict && pytest tests/ -v
```

---

## Project Structure

```
evidence-doc-qa/
├── apps/
│   ├── api/                    # FastAPI backend (Python 3.12)
│   │   ├── app/
│   │   │   ├── main.py         # App entry, routers, startup
│   │   │   ├── config.py       # All env var loading
│   │   │   ├── db.py           # SQLAlchemy models + queries
│   │   │   ├── routers/        # API endpoints
│   │   │   ├── services/       # Business logic
│   │   │   ├── retrieval.py    # Hybrid search
│   │   │   ├── evidence.py     # Citation validation
│   │   │   ├── policy.py       # Security gates
│   │   │   └── verification.py # LLM verification
│   │   ├── requirements.txt    # Full deps (OCR)
│   │   ├── requirements-slim.txt # Slim deps (PyPDF only)
│   │   ├── Dockerfile          # Full build
│   │   └── Dockerfile.slim     # Slim build
│   └── web/                    # Next.js frontend
│       ├── app/                # App router pages
│       ├── components/         # React components
│       └── lib/api.ts          # Backend API client
├── packages/shared/python/     # Shared Pydantic schemas
├── tests/                      # 624 unit + integration tests
├── evals/                      # Golden query evals
├── docs/                       # Architecture, ops, diagrams
├── .claude/                    # Claude Code config + skills
├── CLAUDE.md                   # AI assistant instructions
├── REQUIREMENTS.md             # FRs/NFRs with acceptance criteria
├── ARCHITECTURE.md             # High-level architecture
└── STATUS.md                   # Current work tracking
```

---

## Next Steps

- [Architecture Diagrams](./ARCHITECTURE_DIAGRAM.md) — system overview, RAG pipeline, data model
- [Operations Runbook](./OPERATIONS.md) — deploy, monitor, rollback
- [Technical Deep Dive](./TECHNICAL_DEEP_DIVE.md) — RAG pipeline internals
- [Workflow](./WORKFLOW.md) — development process with TDD + review gates
