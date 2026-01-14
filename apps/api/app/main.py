import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import otel
from app.config import (
    DATA_DIR,
    RAW_DIR,
    ALLOWED_ORIGINS,
)
from app.db import init_db
from app.indexing import ensure_index
from app.telemetry import logger
from app.routers import health, ask, docs, metrics

app = FastAPI(title="DocQ&A API", version="0.0.0")

# Setup Tracing
otel.setup_otel(app)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(health.router)
app.include_router(ask.router)
app.include_router(docs.router)
app.include_router(metrics.router)


@app.on_event("startup")
def startup_event():
    # Initialize DB
    try:
        init_db()
    except Exception as e:
        logger.error(f"DB initialization failed: {e}")

    # Ensure Search Index exists
    try:
        ensure_index()
    except Exception as e:
        logger.error(f"Search index initialization failed: {e}")

    # Bootstrap data directories
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)
