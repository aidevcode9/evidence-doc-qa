def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    input_per_1k: float,
    output_per_1k: float,
) -> float:
    return (prompt_tokens / 1000.0) * input_per_1k + (completion_tokens / 1000.0) * output_per_1k


def merge_cost_breakdown(
    breakdown: dict[str, dict],
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
    entry["prompt_tokens"] += prompt_tokens
    entry["completion_tokens"] += completion_tokens
    entry["cost_est"] = round(entry["cost_est"] + cost_est, 6)
    if estimated:
        entry["estimated"] = True
    if source:
        entry["source"] = source
    breakdown[key] = entry


def attach_cost_trace(
    trace_metadata: dict | None,
    breakdown: dict[str, dict],
    usage_fallback: bool,
) -> dict | None:
    if not breakdown and not usage_fallback:
        return trace_metadata
    filtered: dict[str, dict] = {}
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
    merged = dict(trace_metadata or {})
    if filtered:
        merged["cost_breakdown"] = filtered
    if usage_fallback:
        merged["usage_fallback"] = True
    return merged
