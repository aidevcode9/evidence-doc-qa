import os

PROMPT_VERSION = os.getenv("PROMPT_VERSION", "v3.1.0")
RETRIEVAL_VERSION = os.getenv("RETRIEVAL_VERSION", "v3.1.0")
MODEL_ID = os.getenv("MODEL_ID", "demo-no-llm")
PARSER_MODE = os.getenv("PARSER_MODE", "tier0")
INDEX_VERSION = os.getenv("INDEX_VERSION", "v3.1.0")

DATA_DIR = os.getenv("DATA_DIR", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
DATABASE_URL = os.getenv("DATABASE_URL", "")

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

CONF_MIN = float(os.getenv("CONF_MIN", "0.35"))

TOP_K = int(os.getenv("TOP_K", "5"))
TOP_K_VECTOR = int(os.getenv("TOP_K_VECTOR", "5"))
TOP_K_BM25 = int(os.getenv("TOP_K_BM25", "5"))
RRF_K = int(os.getenv("RRF_K", "60"))

_LOCAL_EMBEDDINGS = os.getenv("LOCAL_EMBEDDINGS")
if _LOCAL_EMBEDDINGS is not None:
    EMBEDDINGS_MODE = "local" if _LOCAL_EMBEDDINGS.lower() in ("1", "true", "yes") else "remote"
else:
    EMBEDDINGS_MODE = os.getenv("EMBEDDINGS_MODE", "local")
EMBEDDINGS_DIM = int(os.getenv("EMBEDDINGS_DIM", "16"))

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "")
AZURE_SEARCH_CREATE_INDEX = os.getenv("AZURE_SEARCH_CREATE_INDEX", "0") == "1"
ENABLE_INDEXING = os.getenv("ENABLE_INDEXING", "1") == "1"

METRICS_ADMIN_TOKEN = os.getenv("METRICS_ADMIN_TOKEN", "")
