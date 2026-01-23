"""Ollama LLM client implementation (NFR-032).

This module implements the LLMClient interface for Ollama, enabling
local open-source model inference without cloud dependencies.

Supported models (recommended for evidence verification):
- llama3.2:8b - Good balance of quality and speed (16GB RAM)
- llama3.3:70b - Best quality (requires 40GB+ VRAM)
- mistral:7b - Fast, good reasoning
- qwen2.5:7b - Strong on structured tasks

Usage:
    # Install Ollama: https://ollama.ai
    # Pull a model: ollama pull llama3.2:8b
    # Start server: ollama serve (runs on localhost:11434)
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from app.llm.base import LLMClient, LLMError, LLMResponse, LLMTimeoutError


class OllamaClient(LLMClient):
    """Ollama LLM client for local open-source models.

    Connects to a local Ollama server via REST API.
    """

    def __init__(
        self,
        model: str = "llama3.2:8b",
        *,
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ) -> None:
        """Initialize Ollama client.

        Args:
            model: Model name (e.g., 'llama3.2:8b', 'mistral:7b').
            base_url: Ollama server URL.
            timeout: Request timeout in seconds (longer for local inference).
        """
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def provider(self) -> str:
        """Return 'ollama' as provider name."""
        return "ollama"

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
        """Generate completion using Ollama.

        Args:
            system_prompt: System message for the model.
            user_prompt: User message/query.
            temperature: Sampling temperature.
            max_tokens: Maximum response tokens.

        Returns:
            LLMResponse with content and usage.

        Raises:
            LLMError: If request fails.
            LLMTimeoutError: If request times out.
        """
        url = f"{self._base_url}/api/chat"

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        start_time = time.perf_counter()
        response = self._make_request(url, payload)
        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract content
        message = response.get("message", {})
        content = message.get("content", "")

        # Extract usage (Ollama provides these in response)
        prompt_tokens = response.get("prompt_eval_count", 0)
        completion_tokens = response.get("eval_count", 0)

        return LLMResponse(
            content=content,
            provider=self.provider,
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )

    def _make_request(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP request to Ollama.

        Args:
            url: Request URL.
            payload: Request payload.

        Returns:
            Response JSON.

        Raises:
            LLMError: If request fails.
            LLMTimeoutError: If request times out.
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
        except urllib.error.URLError as exc:
            if "Connection refused" in str(exc):
                raise LLMError(
                    "Cannot connect to Ollama server. "
                    "Is Ollama running? Start with: ollama serve"
                ) from exc
            raise LLMError("Ollama request failed: connection error") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMTimeoutError(
                f"Ollama request timed out after {self._timeout}s. "
                "Try a smaller model or increase timeout."
            ) from exc
