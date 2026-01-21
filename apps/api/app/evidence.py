"""Evidence extraction and citation validation (FR-025).

This module provides functions for:
- Extracting supporting evidence from chunks
- Validating citations against source text
- Detecting adversarial citation manipulation
"""

from __future__ import annotations

import re
from typing import List, Tuple


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Negation words to detect semantic flipping
_NEGATION_WORDS = frozenset({
    "not", "no", "never", "neither", "nobody", "nothing", "nowhere",
    "without", "hardly", "barely", "scarcely", "don", "doesn", "didn",
    "won", "wouldn", "couldn", "shouldn", "isn", "aren", "wasn", "weren",
    "hasn", "haven", "hadn",
})


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def overlap_score(query_tokens: List[str], text: str) -> float:
    if not query_tokens:
        return 0.0
    text_tokens = set(tokenize(text))
    overlap = sum(1 for t in query_tokens if t in text_tokens)
    return overlap / max(len(query_tokens), 1)


def best_supporting_span(question: str, chunk_text: str, max_len: int = 160) -> str:
    cleaned = " ".join(chunk_text.split())
    if not cleaned:
        return ""
    sentences = _SENTENCE_SPLIT.split(cleaned)
    query_tokens = tokenize(question)
    best_sentence = ""
    best_score = -1.0
    for sentence in sentences:
        score = overlap_score(query_tokens, sentence)
        if score > best_score:
            best_score = score
            best_sentence = sentence
    if not best_sentence:
        best_sentence = cleaned
    if len(best_sentence) > max_len:
        best_sentence = best_sentence[:max_len].rstrip() + "..."
    return best_sentence


def evidence_grade(
    verified: bool,
    rrf_score: float,
    rrf_margin: float,
    overlap: float,
    reranker_score: float = 0.0,
) -> Tuple[str, str]:
    # 1. Semantic Ranker Override (High Confidence)
    # Azure Semantic Ranker scores are 0-4. A score > 2.5 is typically very strong.
    if reranker_score >= 2.5:
        return "A", "Strong (Semantic)"
    
    # 2. Strong Match (Verified + High Signal)
    # We allow a lower overlap (0.15 vs 0.3) if the LLM has explicitly verified the match,
    # to account for synonyms or short numeric answers.
    if verified and rrf_score >= 0.5 and (overlap >= 0.3 or (overlap >= 0.15 and rrf_margin >= 0.02)):
        return "A", "Strong"
        
    # 3. Moderate Match
    if verified and (rrf_score >= 0.4 or reranker_score >= 1.5) and overlap >= 0.1:
        return "B", "Moderate"
        
    return "C", "Weak"


def _normalize_text(text: str) -> str:
    """Normalize text for comparison (lowercase, collapse whitespace)."""
    return " ".join(text.lower().split())


def text_similarity(text1: str, text2: str) -> float:
    """Calculate token-based similarity between two texts.

    Uses Jaccard-like similarity based on word tokens.

    Args:
        text1: First text.
        text2: Second text.

    Returns:
        Similarity score between 0.0 and 1.0.
    """
    if not text1 or not text2:
        return 0.0

    tokens1 = set(tokenize(text1))
    tokens2 = set(tokenize(text2))

    if not tokens1 or not tokens2:
        return 0.0

    intersection = tokens1 & tokens2
    union = tokens1 | tokens2

    return len(intersection) / len(union)


def _has_negation_mismatch(snippet: str, chunk: str) -> bool:
    """Detect if negation differs between snippet and chunk.

    This catches adversarial LLM attempts to flip meaning by
    adding/removing negation words.

    Args:
        snippet: The cited text from LLM response.
        chunk: The source chunk text.

    Returns:
        True if negation mismatch detected, False otherwise.
    """
    snippet_tokens = set(tokenize(snippet))
    chunk_tokens = set(tokenize(chunk))

    snippet_negations = snippet_tokens & _NEGATION_WORDS
    chunk_negations = chunk_tokens & _NEGATION_WORDS

    # Mismatch if one has negation and the other doesn't
    # (symmetric difference is non-empty)
    return bool(snippet_negations ^ chunk_negations)


def validate_citation(
    snippet: str | None,
    chunk: str | None,
    similarity_threshold: float = 0.90,
    strict_negation_check: bool = True,
) -> Tuple[bool, float, str]:
    """Validate that a citation snippet matches the source chunk.

    FR-025: Prevent fabricated citations by verifying text match >= 90%.

    Args:
        snippet: The cited text from LLM response.
        chunk: The source chunk text to validate against.
        similarity_threshold: Minimum similarity for VALID status (default 0.90).
        strict_negation_check: If True, reject citations with negation mismatch.

    Returns:
        Tuple of (is_valid, similarity_score, status).
        Status is one of: "VALID", "PARTIAL_MATCH", "NOT_FOUND", "NEGATION_MISMATCH".
    """
    # Handle None/empty inputs
    if not snippet or not chunk:
        return False, 0.0, "NOT_FOUND"

    # Normalize texts
    norm_snippet = _normalize_text(snippet)
    norm_chunk = _normalize_text(chunk)

    if not norm_snippet or not norm_chunk:
        return False, 0.0, "NOT_FOUND"

    # Check for exact substring match first (fastest path)
    if norm_snippet in norm_chunk:
        return True, 1.0, "VALID"

    # Check for negation mismatch (adversarial detection)
    if strict_negation_check and _has_negation_mismatch(snippet, chunk):
        # Calculate similarity for reporting but reject
        similarity = text_similarity(norm_snippet, norm_chunk)
        return False, similarity, "NEGATION_MISMATCH"

    # Calculate token similarity
    similarity = text_similarity(norm_snippet, norm_chunk)

    if similarity >= similarity_threshold:
        return True, similarity, "VALID"
    elif similarity >= 0.50:
        return False, similarity, "PARTIAL_MATCH"
    else:
        return False, similarity, "NOT_FOUND"
