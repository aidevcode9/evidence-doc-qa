"""Reranker package (FR-022).

Factory function creates the appropriate reranker based on config.
"""

from __future__ import annotations

from app.config import RERANKER_ENABLED
from app.reranker.base import RerankerClient

_cached_client: RerankerClient | None = None
_client_initialized: bool = False


def get_reranker_client() -> RerankerClient | None:
    """Return a cached reranker client if enabled, else None."""
    global _cached_client, _client_initialized

    if _client_initialized:
        return _cached_client

    if not RERANKER_ENABLED:
        _client_initialized = True
        return None

    from app.reranker.local import LocalReranker

    _cached_client = LocalReranker()
    _client_initialized = True
    return _cached_client


__all__ = ["RerankerClient", "get_reranker_client"]
