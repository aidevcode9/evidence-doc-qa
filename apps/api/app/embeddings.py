import hashlib
import json
import urllib.request
from typing import List

from .config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
    EMBEDDINGS_DIM,
    EMBEDDINGS_MODE,
)


def embed_texts(texts: List[str]) -> List[List[float]]:
    if EMBEDDINGS_MODE != "local":
        return _azure_openai_embeddings(texts)
    return [_hash_embed(text) for text in texts]


def _hash_embed(text: str) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vec = []
    for i in range(EMBEDDINGS_DIM):
        vec.append(digest[i % len(digest)] / 255.0)
    return vec


def _azure_openai_embeddings(texts: List[str]) -> List[List[float]]:
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
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if "data" not in data:
        raise RuntimeError("Azure OpenAI embeddings response missing data.")
    return [item["embedding"] for item in data["data"]]
