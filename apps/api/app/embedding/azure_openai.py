"""Azure OpenAI embedding client implementation (NFR-035).

This module implements the EmbeddingClient interface for Azure OpenAI embeddings.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.embedding.base import EmbeddingClient, EmbeddingError, EmbeddingResult


class AzureOpenAIEmbeddingClient(EmbeddingClient):
    """Azure OpenAI embedding client.

    Connects to Azure-hosted OpenAI embedding models via the REST API.
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        *,
        api_version: str = "2024-02-15-preview",
        dimensions: int = 1536,
        timeout: int = 30,
    ) -> None:
        """Initialize Azure OpenAI embedding client.

        Args:
            endpoint: Azure OpenAI endpoint URL.
            api_key: API key for authentication.
            deployment: Deployment name for embeddings model.
            api_version: API version string.
            dimensions: Expected embedding dimensions.
            timeout: Request timeout in seconds.
        """
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._deployment = deployment
        self._api_version = api_version
        self._dimensions = dimensions
        self._timeout = timeout

    @property
    def provider(self) -> str:
        """Return 'azure_openai' as provider name."""
        return "azure_openai"

    @property
    def dimensions(self) -> int:
        """Return configured dimensions."""
        return self._dimensions

    def embed(self, texts: list[str]) -> EmbeddingResult:
        """Generate embeddings using Azure OpenAI.

        Args:
            texts: List of text strings to embed.

        Returns:
            EmbeddingResult with vectors and usage.

        Raises:
            EmbeddingError: If request fails.
        """
        url = (
            f"{self._endpoint}/openai/deployments/{self._deployment}"
            f"/embeddings?api-version={self._api_version}"
        )

        payload = {"input": texts}

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
                data: dict[str, Any] = json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise EmbeddingError(f"HTTP {exc.code}: {body}") from exc
        except TimeoutError as exc:
            raise EmbeddingError(f"Request timed out after {self._timeout}s") from exc

        if "data" not in data:
            raise EmbeddingError("Response missing 'data' field")

        vectors = [item["embedding"] for item in data["data"]]

        # Extract usage
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens")
        estimated = False

        if not isinstance(prompt_tokens, int):
            # Estimate tokens: ~4 chars per token
            prompt_tokens = sum(max(1, len(t) // 4) for t in texts)
            estimated = True

        return EmbeddingResult(
            vectors=vectors,
            model=self._deployment,
            dimensions=len(vectors[0]) if vectors else self._dimensions,
            prompt_tokens=prompt_tokens,
            estimated=estimated,
        )
