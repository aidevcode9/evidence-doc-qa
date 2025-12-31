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
