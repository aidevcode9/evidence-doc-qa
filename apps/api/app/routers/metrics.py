from typing import Any

from fastapi import APIRouter, Header, HTTPException
from app.telemetry import compute_metrics, load_window_telemetry
from app.config import METRICS_ADMIN_TOKEN

router = APIRouter()


@router.get("/v1/metrics")
def metrics(x_admin_token: str | None = Header(default=None)) -> dict[str, Any]:
    if METRICS_ADMIN_TOKEN and x_admin_token != METRICS_ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized.")
    rows = load_window_telemetry()
    result = compute_metrics(rows)

    # Enhanced: cache stats + cost breakdown (NFR-022)
    result["embedding_cache"] = _get_embedding_cache_stats()
    result["query_cache"] = _get_query_cache_stats()
    result["cost_by_component"] = _get_cost_by_component(rows)

    return result


def _get_embedding_cache_stats() -> dict[str, int]:
    """Get embedding cache stats (or zeros if disabled)."""
    from app.embeddings import get_embedding_cache

    cache = get_embedding_cache()
    if cache is None:
        return {"hits": 0, "misses": 0, "size": 0, "max_size": 0, "enabled": False}
    stats = cache.stats()
    stats["enabled"] = True
    return stats


def _get_query_cache_stats() -> dict[str, int]:
    """Get query result cache stats (or zeros if disabled)."""
    from app.services.ask_service import get_query_cache

    cache = get_query_cache()
    if cache is None:
        return {"hits": 0, "misses": 0, "size": 0, "max_size": 0, "enabled": False}
    stats = cache.stats()
    stats["enabled"] = True
    return stats


def _get_cost_by_component(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Aggregate cost_est from telemetry rows by component (from trace_metadata)."""
    totals: dict[str, float] = {}
    for row in rows:
        meta = row.get("trace_metadata") or {}
        breakdown = meta.get("cost_breakdown") or {}
        for component, entry in breakdown.items():
            if isinstance(entry, dict):
                c = float(entry.get("cost_est", 0.0))
                totals[component] = round(totals.get(component, 0.0) + c, 6)
    return totals
