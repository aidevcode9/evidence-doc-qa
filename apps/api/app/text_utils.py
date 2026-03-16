"""Shared text utilities for search and reranking.

Provides canonical stopwords and tokenization used across
LocalSearchClient and LocalReranker.
"""

from __future__ import annotations

import re

STOP_WORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "then", "else", "when",
    "at", "from", "by", "for", "with", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below",
    "to", "up", "down", "in", "out", "on", "off", "over", "under",
    "again", "further", "once", "here", "there", "where", "why", "how",
    "all", "any", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "can", "will", "just", "should", "now", "of", "is",
    "am", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "what", "who",
})


def tokenize(text: str) -> list[str]:
    """Lowercase tokenization for term matching."""
    return re.findall(r"[a-z0-9]+", text.lower())


def tokenize_content(text: str) -> list[str]:
    """Tokenize text, removing stop words."""
    return [t for t in tokenize(text) if t not in STOP_WORDS]
