import json
import os
import time
import hashlib
import re
import urllib.request
from typing import Optional, Tuple

from .config import (
    AZURE_OPENAI_CHAT_API_KEY,
    AZURE_OPENAI_CHAT_API_VERSION,
    AZURE_OPENAI_CHAT_ENDPOINT,
    MODEL_ID,
)
from .telemetry import logger


def verify_relevance(
    question: str,
    chunk_text: str,
    *,
    request_id: Optional[str] = None,
    chunk_id: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """
    Uses the LLM to verify if the chunk actually contains the answer.
    Returns True if relevant, False if not.
    """
    if not _llm_enabled():
        logger.warning("LLM Verification skipped: Azure OpenAI not configured.")
        return "unverified", None

    system_prompt = (
        "You are a strict evidence verifier. "
        "Decide if the document chunk contains the exact answer to the question. "
        "If it does, respond with 'YES: <exact answer span from the chunk>'. "
        "If it does not, respond with 'NO'. "
        "Do not explain. Do not answer the question outside the span."
    )

    user_prompt = f"Question: {question}\n\nDocument Chunk:\n{chunk_text}\n\nContains Answer?"

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": 1000,
    }

    start_time = time.perf_counter()
    question_hash = _hash_text(question)
    logger.info(
        "Verifier start: request_id=%s chunk_id=%s question_hash=%s question_len=%s chunk_len=%s",
        request_id or "unknown",
        chunk_id or "unknown",
        question_hash[:12],
        len(question),
        len(chunk_text),
    )

    try:
        response = _call_openai(payload)
        choice = response["choices"][0]
        content = choice["message"].get("content", "") or ""
        raw = content.strip()
        upper = raw.upper()
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info(
            "Verifier result: request_id=%s chunk_id=%s verdict=%s latency_ms=%s",
            request_id or "unknown",
            chunk_id or "unknown",
            "VERIFIED" if upper.startswith("YES") else "REJECTED",
            latency_ms,
        )
        if _debug_verifier():
            logger.info("Verifier debug (redacted): %s", _redact_text(raw)[:200])
        if upper.startswith("YES"):
            span = raw[3:].lstrip(":").strip()
            if not span:
                return "rejected", raw
            return "verified", span
        if upper.startswith("NO"):
            return "rejected", raw
        return "rejected", raw
    except Exception as e:
        logger.error(f"Verification Failed: {e}")
        return "unverified", None  # Fail closed handled by caller


def is_enabled() -> bool:
    return _llm_enabled()


def verifier_model() -> Optional[str]:
    return MODEL_ID if _llm_enabled() else None


def _llm_enabled() -> bool:
    return bool(AZURE_OPENAI_CHAT_ENDPOINT and AZURE_OPENAI_CHAT_API_KEY and MODEL_ID)


def _call_openai(payload: dict) -> dict:
    url = f"{AZURE_OPENAI_CHAT_ENDPOINT.rstrip('/')}/openai/deployments/{MODEL_ID}/chat/completions?api-version={AZURE_OPENAI_CHAT_API_VERSION}"
    headers = {
        "Content-Type": "application/json",
        "api-key": AZURE_OPENAI_CHAT_API_KEY,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers=headers,
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _debug_verifier() -> bool:
    return os.getenv("DOCQA_DEBUG_VERIFIER", "").lower() in ("1", "true", "yes")


def _redact_text(text: str) -> str:
    redacted = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", text)
    redacted = re.sub(r"\\b\\d{3}[-.\\s]?\\d{3}[-.\\s]?\\d{4}\\b", "[REDACTED_PHONE]", redacted)
    return redacted
