"""Azure AI Search client implementation (NFR-034).

This module implements the SearchClient interface for Azure AI Search
with hybrid BM25 + vector search and optional semantic reranking.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.search.base import SearchClient, SearchError, SearchResponse, SearchResult


class AzureSearchClient(SearchClient):
    """Azure AI Search client.

    Supports:
    - BM25 keyword search
    - Vector search (HNSW index)
    - Semantic reranker (optional)
    - Hybrid search with automatic fusion
    """

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        index_name: str,
        *,
        api_version: str = "2023-11-01",
        semantic_enabled: bool = True,
        top_k_vector: int = 5,
        timeout: int = 30,
    ) -> None:
        """Initialize Azure AI Search client.

        Args:
            endpoint: Azure Search endpoint URL.
            api_key: API key for authentication.
            index_name: Name of the search index.
            api_version: API version string.
            semantic_enabled: Enable semantic reranking.
            top_k_vector: Number of vector results for hybrid search.
            timeout: Request timeout in seconds.
        """
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._index_name = index_name
        self._api_version = api_version
        self._semantic_enabled = semantic_enabled
        self._top_k_vector = top_k_vector
        self._timeout = timeout

    @property
    def provider(self) -> str:
        """Return 'azure' as provider name."""
        return "azure"

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        tenant_id: str,
        matter_id: str,
        *,
        docs_snapshot_id: str | None = None,
        top_k: int = 5,
    ) -> SearchResponse:
        """Execute hybrid search using Azure AI Search.

        Args:
            query: Search query text.
            query_embedding: Pre-computed query embedding vector.
            tenant_id: Tenant ID for isolation (REQUIRED - FR-001).
            matter_id: Matter ID for isolation (REQUIRED - FR-002).
            docs_snapshot_id: Optional document snapshot filter.
            top_k: Maximum number of results to return.

        Returns:
            SearchResponse with ranked results.

        Raises:
            SearchError: If the search fails.
        """
        url = (
            f"{self._endpoint}/indexes/{self._index_name}/docs/search"
            f"?api-version={self._api_version}"
        )

        # Build filter with REQUIRED tenant/matter isolation
        filters: list[str] = [
            f"tenant_id eq '{tenant_id}'",
            f"matter_id eq '{matter_id}'",
        ]
        if docs_snapshot_id and docs_snapshot_id != "none":
            filters.append(f"docs_snapshot_id eq '{docs_snapshot_id}'")
        filter_string = " and ".join(filters)

        # Base payload for hybrid search
        base_payload: dict[str, Any] = {
            "search": query,
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": query_embedding,
                    "fields": "embedding_vector",
                    "k": self._top_k_vector,
                }
            ],
            "top": top_k,
            "filter": filter_string,
        }

        # Semantic payload (enhanced)
        semantic_payload: dict[str, Any] = {
            **base_payload,
            "queryType": "semantic",
            "semanticConfiguration": "default",
            "captions": "extractive|highlight-true",
            "answers": "extractive|count-3",
        }

        semantic_used = False
        fallback_reason: str | None = None
        data: dict[str, Any] = {}

        if self._semantic_enabled:
            try:
                data = self._make_request(url, semantic_payload)
                semantic_used = True
            except urllib.error.HTTPError as exc:
                reason = self._semantic_fallback_reason(exc)
                if exc.code in (400, 403) and reason:
                    fallback_reason = reason
                    # Retry without semantic
                    data = self._make_request(url, base_payload)
                else:
                    body = getattr(exc, "body", "")
                    raise SearchError(f"HTTP {exc.code}: {body}") from exc
        else:
            data = self._make_request(url, base_payload)

        # Parse results
        hits = data.get("value", [])
        results: list[SearchResult] = []

        for doc in hits:
            azure_score = doc.get("@search.score", 0.0)
            reranker_score = doc.get("@search.rerankerScore")

            # Extract captions if available
            captions = doc.get("@search.captions", [])
            highlighted = captions[0].get("highlights") if captions else None
            if not highlighted and captions:
                highlighted = captions[0].get("text")

            results.append(
                SearchResult(
                    chunk_id=doc["chunk_id"],
                    doc_id=doc["doc_id"],
                    text=doc["chunk_text"],
                    score=reranker_score if reranker_score is not None else azure_score,
                    page_number=doc["page_num"],
                    page_end=doc.get("page_end", doc["page_num"]),
                    char_start=doc.get("char_start", 0),
                    char_end=doc.get("char_end", 0),
                    doc_name=doc.get("doc_name"),
                    metadata={
                        "azure_search_score": azure_score,
                        "azure_reranker_score": reranker_score,
                        "highlighted_text": highlighted,
                        "semantic_used": semantic_used,
                        "semantic_fallback_reason": fallback_reason,
                    },
                )
            )

        return SearchResponse(
            results=results,
            provider=self.provider,
            embedding_usage={},
        )

    def _make_request(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP request to Azure Search.

        Args:
            url: Request URL.
            payload: Request payload.

        Returns:
            Response JSON.

        Raises:
            SearchError: If request fails.
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
            setattr(exc, "body", body)
            raise
        except TimeoutError as exc:
            raise SearchError(f"Request timed out after {self._timeout}s") from exc

    _SEMANTIC_UNSUPPORTED_CODES = {
        "SemanticQueriesNotAvailable",
        "FeatureNotSupportedInService",
    }

    def _semantic_fallback_reason(self, exc: urllib.error.HTTPError) -> str | None:
        """Extract semantic fallback reason from error."""
        body = getattr(exc, "body", "") or ""
        if not body:
            return None

        try:
            data = json.loads(body)
            error = data.get("error", {}) if isinstance(data, dict) else {}
            codes: list[str] = []

            code = error.get("code")
            if code:
                codes.append(code)
            for detail in error.get("details") or []:
                detail_code = detail.get("code")
                if detail_code:
                    codes.append(detail_code)

            for candidate in codes:
                if candidate in self._SEMANTIC_UNSUPPORTED_CODES:
                    return candidate

            message = (error.get("message") or "").lower()
            if "semantic" in message and (
                "not enabled" in message or "not supported" in message
            ):
                return "semantic_not_supported"

        except json.JSONDecodeError:
            pass

        lower = body.lower()
        if "semantic" in lower and (
            "not enabled" in lower or "not supported" in lower
        ):
            return "semantic_not_supported"

        return None
