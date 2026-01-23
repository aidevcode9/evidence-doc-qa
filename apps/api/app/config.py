import os
from dotenv import load_dotenv

try:
    load_dotenv(override=True)
except Exception as e:
    print(f"Warning: Failed to load .env file: {e}")


def _getenv(key: str, default: str | None = None) -> str:
    """Get environment variable with fallback to default."""
    value = os.getenv(key)
    if value is not None and value != "":
        return value
    return default if default is not None else ""


def _is_truthy(value: str | None) -> bool:
    """Check if a value is truthy (1, true, yes)."""
    if value is None:
        return False
    return str(value).lower() in ("1", "true", "yes")


PROMPT_VERSION = _getenv("DOCQA_PROMPT_VERSION", "v3.1.0")
RETRIEVAL_VERSION = _getenv("DOCQA_RETRIEVAL_VERSION", "v3.1.0")
MODEL_ID = _getenv("DOCQA_MODEL_ID", "gpt-5-nano")
PARSER_MODE = _getenv("DOCQA_PARSER_MODE", "tier0")
INDEX_VERSION = _getenv("DOCQA_INDEX_VERSION", "v3.1.0")
MODEL_COST_INPUT_PER_1K = float(_getenv("DOCQA_MODEL_COST_INPUT_PER_1K", "0.0004"))
MODEL_COST_OUTPUT_PER_1K = float(_getenv("DOCQA_MODEL_COST_OUTPUT_PER_1K", "0.0016"))
EMBEDDINGS_COST_PER_1K = float(_getenv("DOCQA_EMBEDDINGS_COST_PER_1K", "0.0001"))

DATA_DIR = _getenv("DOCQA_DATA_DIR", "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
DATABASE_URL = _getenv("DATABASE_URL", _getenv("DB_DATABASE_URL", ""))

CHUNK_SIZE = int(_getenv("DOCQA_CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(_getenv("DOCQA_CHUNK_OVERLAP", "150"))

CONFIDENCE_THRESHOLD = float(_getenv("DOCQA_CONFIDENCE_THRESHOLD", "0.70"))
AZURE_SEARCH_SCORE_MIN = float(_getenv("DOCQA_AZURE_SEARCH_SCORE_MIN", "0.02"))
AZURE_RERANK_MIN = float(_getenv("DOCQA_AZURE_RERANK_MIN", "1.5"))
CONFIDENCE_VERSION = _getenv("DOCQA_CONFIDENCE_VERSION", "v1")
STRICT_EVIDENCE = _is_truthy(_getenv("DOCQA_STRICT_EVIDENCE", "1"))
ALLOW_UNVERIFIED = _is_truthy(_getenv("DOCQA_ALLOW_UNVERIFIED", "0"))

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

# Dedicated Chat Configuration (Defaults to shared config if not set)
AZURE_OPENAI_CHAT_ENDPOINT = _getenv("AZURE_OPENAI_CHAT_ENDPOINT", AZURE_OPENAI_ENDPOINT)
AZURE_OPENAI_CHAT_API_KEY = _getenv("AZURE_OPENAI_CHAT_API_KEY", AZURE_OPENAI_API_KEY)
AZURE_OPENAI_CHAT_API_VERSION = _getenv("AZURE_OPENAI_CHAT_API_VERSION", AZURE_OPENAI_API_VERSION)

AZURE_STORAGE_CONNECTION_STRING = _getenv("AZURE_STORAGE_CONNECTION_STRING", "")
AZURE_STORAGE_CONTAINER = _getenv("AZURE_STORAGE_CONTAINER", "docqa-raw")

AZURE_SEARCH_ENDPOINT = _getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY = _getenv("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_INDEX = _getenv("AZURE_SEARCH_INDEX", "")
AZURE_SEARCH_API_VERSION = _getenv("AZURE_SEARCH_API_VERSION", "2023-11-01")
AZURE_SEMANTIC_ENABLED = _is_truthy(_getenv("DOCQA_AZURE_SEMANTIC_ENABLED", "1"))
AZURE_SEARCH_CREATE_INDEX = _is_truthy(_getenv("AZURE_SEARCH_CREATE_INDEX", "0"))
ENABLE_INDEXING = _is_truthy(_getenv("DOCQA_ENABLE_INDEXING", "1"))

# Document Parsing (NFR-036)
PARSER_PROVIDER = _getenv("PARSER_PROVIDER", "marker")  # pypdf | marker | llamaparse

# Marker-specific
MARKER_USE_LLM = _is_truthy(_getenv("MARKER_USE_LLM", "0"))
MARKER_FORCE_OCR = _is_truthy(_getenv("MARKER_FORCE_OCR", "0"))

# LlamaParse-specific (cloud)
LLAMAPARSE_API_KEY = _getenv("LLAMAPARSE_API_KEY", "")

# Upload limits
MAX_UPLOAD_SIZE_MB = int(_getenv("DOCQA_MAX_UPLOAD_SIZE_MB", "50"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
MIN_EXTRACTED_TEXT_CHARS = int(_getenv("DOCQA_MIN_EXTRACTED_TEXT_CHARS", "10"))

METRICS_ADMIN_TOKEN = _getenv(
    "METRICS_ADMIN_TOKEN", _getenv("DOCQA_METRICS_ADMIN_TOKEN", "")
)

# Query limits (security - prevents token overflow attacks)
MAX_QUERY_LENGTH = int(_getenv("DOCQA_MAX_QUERY_LENGTH", "4000"))  # ~1000 tokens

# OpenTelemetry
OTEL_ENABLED = _is_truthy(_getenv("DOCQA_OTEL_ENABLED", "0"))
OTEL_SERVICE_NAME = _getenv("OTEL_SERVICE_NAME", "docqa-api")

# Authentication (FR-050)
AUTH_MODE = _getenv("AUTH_MODE", "headers")  # jwt | headers (headers for backward compat)
JWT_SECRET_KEY = _getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")
JWT_ALGORITHM = _getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(_getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
JWT_REFRESH_TOKEN_EXPIRE_DAYS = int(_getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

# Account security
MAX_FAILED_LOGIN_ATTEMPTS = int(_getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
ACCOUNT_LOCKOUT_MINUTES = int(_getenv("ACCOUNT_LOCKOUT_MINUTES", "30"))
MIN_PASSWORD_LENGTH = int(_getenv("MIN_PASSWORD_LENGTH", "8"))

# SSO - Microsoft Entra ID (FR-051)
MICROSOFT_SSO_ENABLED = _is_truthy(_getenv("MICROSOFT_SSO_ENABLED", "0"))
MICROSOFT_CLIENT_ID = _getenv("MICROSOFT_CLIENT_ID", "")
MICROSOFT_CLIENT_SECRET = _getenv("MICROSOFT_CLIENT_SECRET", "")
MICROSOFT_TENANT_ID = _getenv("MICROSOFT_TENANT_ID", "common")

# SSO - Google Workspace (FR-051)
GOOGLE_SSO_ENABLED = _is_truthy(_getenv("GOOGLE_SSO_ENABLED", "0"))
GOOGLE_CLIENT_ID = _getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = _getenv("GOOGLE_CLIENT_SECRET", "")

# SSO common settings
SSO_REDIRECT_URI = _getenv("SSO_REDIRECT_URI", "")
SSO_DEFAULT_ROLE = _getenv("SSO_DEFAULT_ROLE", "viewer")

# Rate Limiting (FR-052)
RATE_LIMIT_ENABLED = _is_truthy(_getenv("RATE_LIMIT_ENABLED", "1"))
RATE_LIMIT_DEFAULT = _getenv("RATE_LIMIT_DEFAULT", "100/minute")
RATE_LIMIT_QUERY = _getenv("RATE_LIMIT_QUERY", "20/minute")
RATE_LIMIT_UPLOAD = _getenv("RATE_LIMIT_UPLOAD", "10/minute")

# CORS
_allowed_origins = _getenv("DOCQA_ALLOWED_ORIGINS", "http://localhost:3000")
_origins_raw = [o.strip() for o in _allowed_origins.split(",") if o.strip()]
ALLOWED_ORIGINS = []
for origin in _origins_raw:
    if "://" in origin:
        ALLOWED_ORIGINS.append(origin)
    else:
        ALLOWED_ORIGINS.append(f"https://{origin}")
        ALLOWED_ORIGINS.append(f"http://{origin}")
