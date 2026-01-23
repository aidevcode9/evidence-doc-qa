"""Google Gemini LLM client implementation (NFR-032).

This module implements the LLMClient interface for Google's Gemini models.

Supported models:
- gemini-2.0-flash - Fast, cost-effective (recommended)
- gemini-1.5-pro - Best quality, longer context
- gemini-1.5-flash - Balance of speed and quality
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from app.llm.base import (
    LLMClient,
    LLMError,
    LLMRateLimitError,
    LLMResponse,
    LLMTimeoutError,
)


class GeminiClient(LLMClient):
    """Google Gemini LLM client.

    Connects to Google's Generative AI API.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        *,
        timeout: int = 30,
    ) -> None:
        """Initialize Gemini client.

        Args:
            api_key: Google AI API key.
            model: Model name (e.g., 'gemini-2.0-flash', 'gemini-1.5-pro').
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"

    @property
    def provider(self) -> str:
        """Return 'gemini' as provider name."""
        return "gemini"

    @property
    def model(self) -> str:
        """Return the model name."""
        return self._model

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate completion using Gemini.

        Args:
            system_prompt: System instruction for the model.
            user_prompt: User message/query.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.

        Returns:
            LLMResponse with content and usage.

        Raises:
            LLMError: If request fails.
            LLMTimeoutError: If request times out.
            LLMRateLimitError: If rate limit exceeded.
        """
        url = (
            f"{self._base_url}/models/{self._model}:generateContent"
            f"?key={self._api_key}"
        )

        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        start_time = time.perf_counter()
        response = self._make_request(url, payload)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract content
        candidates = response.get("candidates", [])
        if not candidates:
            raise LLMError("Gemini returned no candidates")

        content_parts = candidates[0].get("content", {}).get("parts", [])
        content = content_parts[0].get("text", "") if content_parts else ""

        # Extract usage
        usage = response.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)

        return LLMResponse(
            content=content,
            provider=self.provider,
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )

    def _make_request(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP request to Gemini API.

        Args:
            url: Request URL.
            payload: Request payload.

        Returns:
            Response JSON.

        Raises:
            LLMError: If request fails.
        """
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                result: dict[str, Any] = json.load(resp)
                return result
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            # Sanitize error body to remove any echoed API key
            sanitized_body = self._sanitize_error(body)
            if exc.code == 429:
                raise LLMRateLimitError(
                    f"Gemini rate limit exceeded: {sanitized_body}"
                ) from exc
            if exc.code == 400:
                raise LLMError(f"Gemini bad request: {sanitized_body}") from exc
            if exc.code == 403:
                raise LLMError(
                    "Gemini API key invalid or quota exceeded"
                ) from exc
            raise LLMError(f"Gemini HTTP {exc.code}: {sanitized_body}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMTimeoutError(
                f"Gemini request timed out after {self._timeout}s"
            ) from exc

    def _sanitize_error(self, body: str) -> str:
        """Remove sensitive data from error messages.

        Args:
            body: Raw error body.

        Returns:
            Sanitized error message.
        """
        # Remove API key if echoed back
        if self._api_key and self._api_key in body:
            body = body.replace(self._api_key, "[REDACTED]")
        return body
