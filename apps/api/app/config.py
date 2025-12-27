import os
from dotenv import load_dotenv

try:
    load_dotenv(override=True)
except Exception as e:
    print(f"Warning: Failed to load .env file: {e}")


def _getenv(key, default=None):
    value = os.getenv(key)
    if value not in (None, ""):
        return value
    return default


def _is_truthy(value):
    return str(value).lower() in ("1", "true", "yes")


PROMPT_VERSION = _getenv("DOCQA_PROMPT_VERSION", "v3.1.0")
RETRIEVAL_VERSION = _getenv("DOCQA_RETRIEVAL_VERSION", "v3.1.0")
MODEL_ID = _getenv("DOCQA_MODEL_ID", "demo-no-llm")
PARSER_MODE = _getenv("DOCQA_PARSER_MODE", "tier0")
INDEX_VERSION = _getenv("DOCQA_INDEX_VERSION", "v3.1.0")

DATA_DIR = _getenv("DOCQA_DATA_DIR", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
DATABASE_URL = _getenv("DB_DATABASE_URL", "")

CHUNK_SIZE = int(_getenv("DOCQA_CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(_getenv("DOCQA_CHUNK_OVERLAP", "150"))

CONF_MIN = float(_getenv("DOCQA_CONF_MIN", "0.35"))

TOP_K = int(_getenv("DOCQA_TOP_K", "5"))
TOP_K_VECTOR = int(_getenv("DOCQA_TOP_K_VECTOR", "5"))
TOP_K_BM25 = int(_getenv("DOCQA_TOP_K_BM25", "5"))
RRF_K = int(_getenv("DOCQA_RRF_K", "60"))

_embeddings_local = _getenv("EMBEDDINGS_LOCAL")
if _embeddings_local is not None:
    EMBEDDINGS_MODE = "local" if _is_truthy(_embeddings_local) else "remote"
else:
    EMBEDDINGS_MODE = _getenv("EMBEDDINGS_MODE", "local")
EMBEDDINGS_DIM = int(_getenv("EMBEDDINGS_DIM", "16"))

AZURE_OPENAI_ENDPOINT = _getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = _getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION = _getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT = _getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "")

AZURE_STORAGE_CONNECTION_STRING = _getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_CONTAINER = _getenv("AZURE_STORAGE_CONTAINER", "docqa-raw")

AZURE_SEARCH_ENDPOINT = _getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY = _getenv("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_INDEX = _getenv("AZURE_SEARCH_INDEX", "")
AZURE_SEARCH_API_VERSION = _getenv("AZURE_SEARCH_API_VERSION", "2023-11-01")
AZURE_SEARCH_CREATE_INDEX = _is_truthy(_getenv("AZURE_SEARCH_CREATE_INDEX", "0"))
ENABLE_INDEXING = _is_truthy(_getenv("DOCQA_ENABLE_INDEXING", "1"))

METRICS_ADMIN_TOKEN = _getenv("DOCQA_METRICS_ADMIN_TOKEN", "")

# CORS
_allowed_origins = _getenv("DOCQA_ALLOWED_ORIGINS", "http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins.split(",") if o.strip()]
