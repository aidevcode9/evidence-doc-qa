from __future__ import annotations

import difflib
import re
from typing import List, Tuple


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


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


def text_similarity(text1: str, text2: str) -> float:
    """Calculate text similarity using SequenceMatcher."""
    if not text1 or not text2:
        return 0.0
    # Normalize whitespace
    t1 = " ".join(text1.split()).lower()
    t2 = " ".join(text2.split()).lower()
    return difflib.SequenceMatcher(None, t1, t2).ratio()


# Negation words that can flip meaning - adversarial LLM detection
_NEGATION_WORDS = {
    "not", "no", "never", "none", "neither", "nobody", "nothing",
    "nowhere", "cannot", "can't", "won't", "wouldn't", "shouldn't",
    "couldn't", "doesn't", "don't", "didn't", "isn't", "aren't",
    "wasn't", "weren't", "hasn't", "haven't", "hadn't", "without",
    "exclude", "excluding", "except", "unless", "non", "un",
}


def _has_negation_mismatch(snippet: str, chunk_text: str) -> bool:
    """
    Detect if snippet has different negation than chunk.

    Catches adversarial cases like:
    - snippet: "The contract is NOT binding"
    - chunk:   "The contract is binding"

    Returns True if negation mismatch detected (snippet should be rejected).
    """
    snippet_tokens = set(tokenize(snippet))
    chunk_tokens = set(tokenize(chunk_text))

    snippet_negations = snippet_tokens & _NEGATION_WORDS
    chunk_negations = chunk_tokens & _NEGATION_WORDS

    # If snippet has negation words not in chunk, suspicious
    added_negations = snippet_negations - chunk_negations
    # If chunk has negation words not in snippet, also suspicious
    removed_negations = chunk_negations - snippet_negations

    # Flag if there's a meaningful difference in negation
    return bool(added_negations or removed_negations)


def validate_citation(
    snippet: str,
    chunk_text: str,
    similarity_threshold: float = 0.90,
    strict_negation_check: bool = True,
) -> Tuple[bool, float, str]:
    """
    Validate that a citation snippet exists in the source chunk.

    FR-025: Prevent fabricated citations by verifying text match >= threshold.

    Security: Includes negation mismatch detection to catch adversarial LLM
    outputs like "NOT binding" when chunk says "binding".

    Args:
        snippet: The cited text to validate
        chunk_text: The source chunk text
        similarity_threshold: Minimum similarity for VALID status (default 0.90)
        strict_negation_check: If True, reject citations with negation mismatch

    Returns:
        (is_valid, similarity_score, validation_status)
        - is_valid: True if similarity >= threshold AND no negation mismatch
        - similarity_score: 0.0-1.0 text match ratio
        - validation_status: "VALID" | "NEGATION_MISMATCH" | "PARTIAL_MATCH" | "NOT_FOUND"
    """
    if not snippet or not chunk_text:
        return False, 0.0, "NOT_FOUND"

    # Normalize for comparison
    snippet_norm = " ".join(snippet.split()).lower()
    chunk_norm = " ".join(chunk_text.split()).lower()

    # Security: Check for negation mismatch (adversarial LLM detection)
    if strict_negation_check and _has_negation_mismatch(snippet, chunk_text):
        # Even if text is similar, negation difference is dangerous
        return False, 0.0, "NEGATION_MISMATCH"

    # Check for exact substring match first
    if snippet_norm in chunk_norm:
        return True, 1.0, "VALID"

    # Find best matching substring in chunk using sliding window
    snippet_len = len(snippet_norm)
    best_ratio = 0.0

    # Check full chunk similarity as baseline
    full_ratio = text_similarity(snippet, chunk_text)
    best_ratio = max(best_ratio, full_ratio)

    # Sliding window for substring matching (step=1 for legal accuracy)
    if len(chunk_norm) >= snippet_len:
        # Use step=1 for accurate matching in legal contexts
        for i in range(0, len(chunk_norm) - snippet_len + 1):
            window = chunk_norm[i : i + snippet_len]
            ratio = difflib.SequenceMatcher(None, snippet_norm, window).ratio()
            best_ratio = max(best_ratio, ratio)
            if best_ratio >= similarity_threshold:
                break  # Early exit on good match

    if best_ratio >= similarity_threshold:
        return True, round(best_ratio, 4), "VALID"
    elif best_ratio >= 0.50:
        return False, round(best_ratio, 4), "PARTIAL_MATCH"
    else:
        return False, round(best_ratio, 4), "NOT_FOUND"
