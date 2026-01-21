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
    return result
