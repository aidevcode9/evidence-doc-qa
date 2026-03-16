"""Reranker package (FR-022).

Factory function creates the appropriate reranker based on config.
"""

from __future__ import annotations

from app.config import RERANKER_ENABLED
from app.reranker.base import RerankerClient


def get_reranker_client() -> RerankerClient | None:
    """Return a reranker client if enabled, else None."""
    if not RERANKER_ENABLED:
        return None

    from app.reranker.local import LocalReranker

    return LocalReranker()


__all__ = ["RerankerClient", "get_reranker_client"]
