import hashlib
import json
import logging
import urllib.request
import urllib.error
from typing import List, Tuple, Dict

from app.config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    EMBEDDINGS_DIM,
    EMBEDDINGS_MODE,
)

logger = logging.getLogger("docqa")


def embed_texts(texts: List[str]) -> List[List[float]]:
    embeddings, _usage = embed_texts_with_usage(texts)
    return embeddings


def embed_texts_with_usage(texts: List[str]) -> Tuple[List[List[float]], Dict[str, object]]:
    if EMBEDDINGS_MODE != "local":
        return _azure_openai_embeddings_with_usage(texts)
    embeddings = [_hash_embed(text) for text in texts]
    return embeddings, {"prompt_tokens": 0, "total_tokens": 0, "estimated": False, "source": "local"}


def _hash_embed(text: str) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vec = []
    for i in range(EMBEDDINGS_DIM):
        vec.append(digest[i % len(digest)] / 255.0)
    return vec


def _azure_openai_embeddings_with_usage(texts: List[str]) -> Tuple[List[List[float]], Dict[str, object]]:
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
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        logger.error("Azure OpenAI embeddings HTTP %s: %s", exc.code, body)
        raise
    if "data" not in data:
        raise RuntimeError("Azure OpenAI embeddings response missing data.")
    usage = _extract_usage(data, texts)
    return [item["embedding"] for item in data["data"]], usage


def _extract_usage(response: dict, texts: List[str]) -> Dict[str, object]:
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


def _estimate_prompt_tokens(texts: List[str]) -> int:
    total = 0
    for text in texts:
        if not text:
            continue
        total += max(1, len(text) // 4)
    return total
