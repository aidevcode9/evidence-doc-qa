import json
import urllib.request
from typing import Optional, Tuple

from .config import (
    AZURE_OPENAI_CHAT_API_KEY,
    AZURE_OPENAI_CHAT_API_VERSION,
    AZURE_OPENAI_CHAT_ENDPOINT,
    MODEL_ID,
)
from .telemetry import logger


def verify_relevance(question: str, chunk_text: str) -> Tuple[str, Optional[str]]:
    """
    Uses the LLM to verify if the chunk actually contains the answer.
    Returns True if relevant, False if not.
    """
    if not _llm_enabled():
        logger.warning("LLM Verification skipped: Azure OpenAI not configured.")
        return "unverified", None

    system_prompt = (
        "You are a strict relevance evaluator. "
        "Your only job is to determine if the provided document chunk contains "
        "the specific information needed to answer the user's question. "
        "If the chunk contains the answer, output 'YES'. "
        "If the chunk is irrelevant or does not contain the answer, output 'NO'. "
        "Do not answer the question itself."
    )

    user_prompt = f"Question: {question}\n\nDocument Chunk:\n{chunk_text}\n\nContains Answer?"

    payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_completion_tokens": 1000,
    }

    logger.info(f"Verifying Relevance: Q='{question}' Chunk='{chunk_text[:50]}...'")

    try:
        response = _call_openai(payload)
        # DEBUG: Log full response
        logger.info(f"LLM Raw Response: {json.dumps(response)}")
        
        choice = response["choices"][0]
        content = choice["message"].get("content", "") or ""
        content = content.strip().upper()
        
        logger.info(f"Verification Result: '{content}' for Q: '{question[:20]}...'")
        if "YES" in content:
            return "verified", content
        if "NO" in content:
            return "rejected", content
        return "rejected", content
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
