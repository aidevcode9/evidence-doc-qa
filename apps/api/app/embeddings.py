import hashlib
import json
import logging
import urllib.request
import urllib.error
from typing import Any

from app.cache import EmbeddingCache
from app.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    EMBEDDING_CACHE_ENABLED,
    EMBEDDING_CACHE_MAX_SIZE,
    EMBEDDINGS_DIM,
    EMBEDDINGS_MODE,
)
from app.otel import get_observe_decorator, safe_update_observation, set_genai_span_attributes

logger = logging.getLogger("docqa")

_observe = get_observe_decorator()

UsageInfo = dict[str, int | bool | str]

# Singleton embedding cache
_embedding_cache: EmbeddingCache | None = (
    EmbeddingCache(max_size=EMBEDDING_CACHE_MAX_SIZE) if EMBEDDING_CACHE_ENABLED else None
)


def get_embedding_cache() -> EmbeddingCache | None:
    """Return the singleton embedding cache (for metrics endpoint)."""
    return _embedding_cache


def embed_texts(texts: list[str]) -> list[list[float]]:
    embeddings, _usage = embed_texts_with_usage(texts)
    return embeddings


@_observe(name="embed_texts_with_usage", capture_input=False, capture_output=False)
def embed_texts_with_usage(texts: list[str]) -> tuple[list[list[float]], UsageInfo]:
    # Check embedding cache for single-text queries (typical question embedding)
    if _embedding_cache is not None and len(texts) == 1:
        cache_key = hashlib.sha256(texts[0].encode("utf-8")).hexdigest()
        cached = _embedding_cache.get(cache_key)
        if cached is not None:
            usage: UsageInfo = {
                "prompt_tokens": 0, "total_tokens": 0,
                "estimated": False, "source": "cache",
            }
            safe_update_observation(
                metadata={"embeddings_mode": "cache", "text_count": 1},
            )
            return [cached], usage

    if EMBEDDINGS_MODE != "local":
        result = _azure_openai_embeddings_with_usage(texts)
        # Enrich Langfuse observation with embedding metadata (NFR-045)
        safe_update_observation(
            model=AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT or "text-embedding-3-large",
            usage={"input": int(result[1].get("prompt_tokens") or 0)},
            metadata={"embeddings_mode": "remote", "text_count": len(texts)},
        )
        # Set OTEL GenAI semantic convention attributes (NFR-022)
        set_genai_span_attributes(
            system="azure_openai",
            model=AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT or "text-embedding-3-large",
            prompt_tokens=int(result[1].get("prompt_tokens") or 0),
            completion_tokens=0,
            latency_ms=0,
        )
        # Cache single-text results
        if _embedding_cache is not None and len(texts) == 1:
            cache_key = hashlib.sha256(texts[0].encode("utf-8")).hexdigest()
            _embedding_cache.put(cache_key, result[0][0])
        return result
    embeddings = [_hash_embed(text) for text in texts]
    usage_local: UsageInfo = {"prompt_tokens": 0, "total_tokens": 0, "estimated": False, "source": "local"}
    # Enrich Langfuse observation for local embeddings (NFR-045)
    safe_update_observation(
        metadata={"embeddings_mode": "local", "text_count": len(texts)},
    )
    # Cache single-text local results too
    if _embedding_cache is not None and len(texts) == 1:
        cache_key = hashlib.sha256(texts[0].encode("utf-8")).hexdigest()
        _embedding_cache.put(cache_key, embeddings[0])
    return embeddings, usage_local


def _hash_embed(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vec: list[float] = []
    for i in range(EMBEDDINGS_DIM):
        vec.append(digest[i % len(digest)] / 255.0)
    return vec


def _azure_openai_embeddings_with_usage(texts: list[str]) -> tuple[list[list[float]], UsageInfo]:
    if not AZURE_OPENAI_ENDPOINT:
        raise RuntimeError("AZURE_OPENAI_ENDPOINT is required for remote embeddings.")
    if not AZURE_OPENAI_API_KEY:
        raise RuntimeError("AZURE_OPENAI_API_KEY is required for remote embeddings.")
    if not AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT:
        raise RuntimeError("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT is required for remote embeddings.")
    url = (
        f"{AZURE_OPENAI_ENDPOINT.rstrip('/')}"
        f"/openai/deployments/{AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT}/embeddings"
        f"?api-version={AZURE_OPENAI_API_VERSION}"
    )
    payload = {"input": texts}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"api-key": AZURE_OPENAI_API_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data: dict[str, Any] = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("Azure OpenAI embeddings HTTP %s: %s", exc.code, body)
        raise
    if "data" not in data:
        raise RuntimeError("Azure OpenAI embeddings response missing data.")
    usage = _extract_usage(data, texts)
    return [item["embedding"] for item in data["data"]], usage


def _extract_usage(response: dict[str, Any], texts: list[str]) -> UsageInfo:
    usage = response.get("usage", {}) if isinstance(response, dict) else {}
    prompt_tokens = usage.get("prompt_tokens")
    total_tokens = usage.get("total_tokens")
    if isinstance(prompt_tokens, int) and isinstance(total_tokens, int):
        return {
            "prompt_tokens": prompt_tokens,
            "total_tokens": total_tokens,
            "estimated": False,
            "source": "remote",
        }
    estimated = _estimate_prompt_tokens(texts)
    return {
        "prompt_tokens": estimated,
        "total_tokens": estimated,
        "estimated": True,
        "source": "remote",
    }


def _estimate_prompt_tokens(texts: list[str]) -> int:
    total = 0
    for text in texts:
        if not text:
            continue
        total += max(1, len(text) // 4)
    return total
