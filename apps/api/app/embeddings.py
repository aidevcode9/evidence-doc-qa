import hashlib
from typing import List

from .config import EMBEDDINGS_DIM, EMBEDDINGS_MODE


def embed_texts(texts: List[str]) -> List[List[float]]:
    if EMBEDDINGS_MODE != "local":
        raise ValueError("Only local embeddings are supported in demo mode.")
    return [_hash_embed(text) for text in texts]


def _hash_embed(text: str) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    vec = []
    for i in range(EMBEDDINGS_DIM):
        vec.append(digest[i % len(digest)] / 255.0)
    return vec
