from __future__ import annotations

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
) -> Tuple[str, str]:
    if verified and rrf_score >= 0.6 and overlap >= 0.3 and rrf_margin >= 0.05:
        return "A", "Strong"
    if verified and rrf_score >= 0.45 and overlap >= 0.2:
        return "B", "Moderate"
    return "C", "Weak"
