from __future__ import annotations

import atexit

import httpx

_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=10.0)
_DEFAULT_LIMITS = httpx.Limits(max_connections=50, max_keepalive_connections=20)

_azure_http_client: httpx.Client | None = None


def get_azure_http_client() -> httpx.Client:
    """Return a shared sync httpx client for Azure service calls."""
    global _azure_http_client
    if _azure_http_client is None:
        _azure_http_client = httpx.Client(
            timeout=_DEFAULT_TIMEOUT,
            limits=_DEFAULT_LIMITS,
            http2=True,
        )
    return _azure_http_client


def close_azure_http_client() -> None:
    """Close the shared sync client at process shutdown."""
    global _azure_http_client
    if _azure_http_client is not None:
        _azure_http_client.close()
        _azure_http_client = None


atexit.register(close_azure_http_client)
