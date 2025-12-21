from datetime import datetime, timedelta, timezone
from typing import Dict, List

from .db import Telemetry, insert_telemetry, load_telemetry


def record_telemetry(
    *,
    request_id: str,
    docs_snapshot_id: str,
    prompt_version: str,
    retrieval_version: str,
    model_id: str,
    parser_mode: str,
    timestamp_utc: str,
    latency_ms: int,
    tokens_in: int,
    tokens_out: int,
    cost_est: float,
    cache_hit: bool,
    refusal_code: str | None,
    failure_label: str | None,
) -> None:
    insert_telemetry(
        Telemetry(
            request_id=request_id,
            docs_snapshot_id=docs_snapshot_id,
            prompt_version=prompt_version,
            retrieval_version=retrieval_version,
            model_id=model_id,
            parser_mode=parser_mode,
            timestamp_utc=timestamp_utc,
            latency_ms=latency_ms,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_est=cost_est,
            cache_hit=cache_hit,
            refusal_code=refusal_code,
            failure_label=failure_label,
        )
    )


def load_window_telemetry(hours: int = 24, limit: int = 500) -> List[Dict]:
    rows = load_telemetry(hours=hours, limit=limit)
    return [
        {
            "request_id": row.request_id,
            "docs_snapshot_id": row.docs_snapshot_id,
            "prompt_version": row.prompt_version,
            "retrieval_version": row.retrieval_version,
            "model_id": row.model_id,
            "parser_mode": row.parser_mode,
            "timestamp_utc": row.timestamp_utc,
            "latency_ms": row.latency_ms,
            "tokens_in": row.tokens_in,
            "tokens_out": row.tokens_out,
            "cost_est": row.cost_est,
            "cache_hit": row.cache_hit,
            "refusal_code": row.refusal_code,
            "failure_label": row.failure_label,
        }
        for row in rows
    ]


def compute_metrics(rows: List[Dict]) -> Dict:
    if not rows:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "window_start_utc": now,
            "window_end_utc": now,
            "p50_latency_ms": 0,
            "p95_latency_ms": 0,
            "avg_cost_per_query": 0.0,
            "refusals_by_code": {},
            "cache_hit_rate": 0.0,
        }

    latencies = sorted(row["latency_ms"] for row in rows)
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    avg_cost = sum(row["cost_est"] for row in rows) / len(rows)
    refusal_counts = {}
    cache_hits = 0
    for row in rows:
        if row["refusal_code"]:
            refusal_counts[row["refusal_code"]] = refusal_counts.get(
                row["refusal_code"], 0
            ) + 1
        if row["cache_hit"]:
            cache_hits += 1

    window_end = rows[0]["timestamp_utc"]
    window_start = rows[-1]["timestamp_utc"]
    return {
        "window_start_utc": window_start,
        "window_end_utc": window_end,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "avg_cost_per_query": round(avg_cost, 6),
        "refusals_by_code": refusal_counts,
        "cache_hit_rate": round(cache_hits / len(rows), 4),
    }


def _percentile(values: List[int], pct: int) -> int:
    if not values:
        return 0
    k = (len(values) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return int(d0 + d1)
