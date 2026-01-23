"""Anthropic Claude LLM client implementation (NFR-032).

This module implements the LLMClient interface for Anthropic's Claude models.

Supported models:
- claude-sonnet-4-20250514 - Best balance (recommended)
- claude-opus-4-20250514 - Highest capability
- claude-3-5-sonnet-20241022 - Previous generation, still excellent
- claude-3-5-haiku-20241022 - Fast and cost-effective
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


class AnthropicClient(LLMClient):
    """Anthropic Claude LLM client.

    Connects to Anthropic's Messages API.
    """

    API_VERSION = "2023-06-01"

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        *,
        timeout: int = 30,
    ) -> None:
        """Initialize Anthropic client.

        Args:
            api_key: Anthropic API key.
            model: Model name (e.g., 'claude-sonnet-4-20250514').
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._base_url = "https://api.anthropic.com/v1"

    @property
    def provider(self) -> str:
        """Return 'anthropic' as provider name."""
        return "anthropic"

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
        """Generate completion using Claude.

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
        url = f"{self._base_url}/messages"

        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        # Only include temperature if non-zero (Claude default is 1.0)
        if temperature > 0:
            payload["temperature"] = temperature

        start_time = time.perf_counter()
        response = self._make_request(url, payload)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract content
        content_blocks = response.get("content", [])
        content = ""
        for block in content_blocks:
            if block.get("type") == "text":
                content += block.get("text", "")

        # Extract usage
        usage = response.get("usage", {})
        prompt_tokens = usage.get("input_tokens", 0)
        completion_tokens = usage.get("output_tokens", 0)

        return LLMResponse(
            content=content,
            provider=self.provider,
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )

    def _make_request(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP request to Anthropic API.

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
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": self.API_VERSION,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                result: dict[str, Any] = json.load(resp)
                return result
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                raise LLMRateLimitError(
                    f"Anthropic rate limit exceeded: {body}"
                ) from exc
            if exc.code == 401:
                raise LLMError(f"Anthropic API key invalid: {body}") from exc
            if exc.code == 400:
                raise LLMError(f"Anthropic bad request: {body}") from exc
            raise LLMError(f"Anthropic HTTP {exc.code}: {body}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMTimeoutError(
                f"Anthropic request timed out after {self._timeout}s"
            ) from exc
