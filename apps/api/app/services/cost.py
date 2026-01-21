from typing import Any


CostEntry = dict[str, int | float | bool | str | None]
CostBreakdown = dict[str, CostEntry]
TraceMetadata = dict[str, Any]


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    input_per_1k: float,
    output_per_1k: float,
) -> float:
    return (prompt_tokens / 1000.0) * input_per_1k + (completion_tokens / 1000.0) * output_per_1k


def merge_cost_breakdown(
    breakdown: CostBreakdown,
    key: str,
    prompt_tokens: int,
    completion_tokens: int,
    cost_est: float,
    estimated: bool,
    source: str | None,
) -> None:
    entry = breakdown.get(
        key,
        {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_est": 0.0,
            "estimated": False,
        },
    )
    prompt_val = entry.get("prompt_tokens", 0)
    completion_val = entry.get("completion_tokens", 0)
    cost_val = entry.get("cost_est", 0.0)
    entry["prompt_tokens"] = (int(prompt_val) if isinstance(prompt_val, (int, float)) else 0) + prompt_tokens
    entry["completion_tokens"] = (int(completion_val) if isinstance(completion_val, (int, float)) else 0) + completion_tokens
    entry["cost_est"] = round((float(cost_val) if isinstance(cost_val, (int, float)) else 0.0) + cost_est, 6)
    if estimated:
        entry["estimated"] = True
    if source:
        entry["source"] = source
    breakdown[key] = entry


def attach_cost_trace(
    trace_metadata: TraceMetadata | None,
    breakdown: CostBreakdown,
    usage_fallback: bool,
) -> TraceMetadata | None:
    if not breakdown and not usage_fallback:
        return trace_metadata
    filtered: CostBreakdown = {}
    for key, entry in breakdown.items():
        if (
            entry.get("prompt_tokens")
            or entry.get("completion_tokens")
            or entry.get("cost_est")
            or entry.get("estimated")
        ):
            filtered[key] = entry
    if not filtered and not usage_fallback:
        return trace_metadata
    merged: TraceMetadata = dict(trace_metadata or {})
    if filtered:
        merged["cost_breakdown"] = filtered
    if usage_fallback:
        merged["usage_fallback"] = True
    return merged
