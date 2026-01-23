"""Azure OpenAI LLM client implementation (NFR-032).

This module implements the LLMClient interface for Azure OpenAI deployments.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from app.llm.base import LLMClient, LLMError, LLMRateLimitError, LLMResponse, LLMTimeoutError


class AzureOpenAIClient(LLMClient):
    """Azure OpenAI LLM client.

    Connects to Azure-hosted OpenAI models via the REST API.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        *,
        api_version: str = "2024-02-15-preview",
        timeout: int = 30,
    ) -> None:
        """Initialize Azure OpenAI client.

        Args:
            endpoint: Azure OpenAI endpoint URL.
            api_key: API key for authentication.
            deployment: Deployment name (model ID).
            api_version: API version string.
            timeout: Request timeout in seconds.
        """
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._deployment = deployment
        self._api_version = api_version
        self._timeout = timeout

    @property
    def provider(self) -> str:
        """Return 'azure_openai' as provider name."""
        return "azure_openai"

    @property
    def model(self) -> str:
        """Return the deployment name as model identifier."""
        return self._deployment

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Generate completion using Azure OpenAI.

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
            LLMRateLimitError: If rate limit is exceeded.
        """
        url = (
            f"{self._endpoint}/openai/deployments/{self._deployment}"
            f"/chat/completions?api-version={self._api_version}"
        )

        # Determine correct token parameter based on model
        token_param = self._get_token_param()

        payload: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            token_param: max_tokens,
        }

        start_time = time.perf_counter()
        try:
            response = self._make_request(url, payload)
        except urllib.error.HTTPError as exc:
            # Try alternate token param if needed
            alt_param = self._alt_token_param_from_error(exc)
            if alt_param and alt_param != token_param:
                payload.pop(token_param, None)
                payload[alt_param] = max_tokens
                response = self._make_request(url, payload)
            else:
                raise

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract content
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {}) or {}
        content = message.get("content", "") or ""

        # Extract usage
        usage = response.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        return LLMResponse(
            content=content,
            provider=self.provider,
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
        )

    def _make_request(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP request to Azure OpenAI.

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
                "api-key": self._api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                result: dict[str, Any] = json.load(resp)
                return result
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429:
                raise LLMRateLimitError(f"Rate limit exceeded: {body}") from exc
            if exc.code >= 500:
                raise LLMError(f"Server error {exc.code}: {body}") from exc
            # Store body for retry logic
            setattr(exc, "body", body)
            raise
        except TimeoutError as exc:
            raise LLMTimeoutError(f"Request timed out after {self._timeout}s") from exc

    def _get_token_param(self) -> str:
        """Get the correct max tokens parameter name for this model."""
        model_lower = self._deployment.lower()
        if model_lower.startswith("gpt-5") or "o1" in model_lower:
            return "max_completion_tokens"
        return "max_tokens"

    def _alt_token_param_from_error(
        self, exc: urllib.error.HTTPError
    ) -> str | None:
        """Extract alternate token param from error response."""
        body = getattr(exc, "body", "") or ""
        lower = body.lower()
        if "max_completion_tokens" in lower and "max_tokens" in lower:
            if (
                "use 'max_completion_tokens' instead" in lower
                or "'max_tokens'" in lower
            ):
                return "max_completion_tokens"
            if (
                "use 'max_tokens' instead" in lower
                or "'max_completion_tokens'" in lower
            ):
                return "max_tokens"
        return None
