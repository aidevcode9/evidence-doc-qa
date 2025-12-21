import argparse
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="golden")
    parser.add_argument("--api-url", default=os.getenv("EVAL_API_URL", "http://localhost:8000"))
    args = parser.parse_args()

    suite_path = Path("evals") / f"{args.suite}.jsonl"
    if not suite_path.exists():
        raise SystemExit(f"Missing suite file: {suite_path}")

    cases = [json.loads(line) for line in suite_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    out_dir = Path("evals/out")
    out_dir.mkdir(parents=True, exist_ok=True)

    details_path = out_dir / "details.jsonl"
    summary_path = out_dir / "summary.json"

    details = []
    answered = 0
    answered_with_citations = 0
    refusal_expected = 0
    refusal_correct = 0
    total_latency = 0.0

    for case in cases:
        start = time.perf_counter()
        response = _call_ask(args.api_url, case)
        latency_ms = int((time.perf_counter() - start) * 1000)
        total_latency += latency_ms

        expected_behavior = case.get("expected_behavior")
        refusal_code = response.get("refusal_code")
        citations = response.get("citations") or []

        passed = True
        failure_label = None

        if expected_behavior == "refuse":
            refusal_expected += 1
            if refusal_code is None:
                passed = False
                failure_label = "REFUSAL_INCORRECT"
            else:
                refusal_correct += 1
        elif expected_behavior == "answer":
            answered += 1
            if refusal_code is not None:
                passed = False
                failure_label = "REFUSAL_INCORRECT"
            else:
                if citations:
                    answered_with_citations += 1
                else:
                    passed = False
                    failure_label = "NO_CITATIONS"
                exp_doc = case.get("expected_doc_id")
                exp_page = case.get("expected_page_num")
                if exp_doc is not None and exp_page is not None:
                    if not any(
                        c.get("doc_id") == exp_doc and c.get("page_num") == exp_page
                        for c in citations
                    ):
                        passed = False
                        failure_label = "CITATION_MISMATCH"

        details.append(
            {
                "id": case.get("id"),
                "category": case.get("category"),
                "question": case.get("question"),
                "expected_behavior": expected_behavior,
                "refusal_code": refusal_code,
                "citations": citations,
                "latency_ms": latency_ms,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_est": 0.0,
                "failure_label": failure_label,
                "passed": passed,
                "prompt_version": response.get("version_snapshot", {}).get("prompt_version"),
                "retrieval_version": response.get("version_snapshot", {}).get("retrieval_version"),
                "model_id": response.get("version_snapshot", {}).get("model_id"),
                "parser_mode": response.get("version_snapshot", {}).get("parser_mode"),
                "docs_snapshot_id": response.get("version_snapshot", {}).get("docs_snapshot_id"),
            }
        )

    citation_coverage = (answered_with_citations / answered) if answered else 0.0
    refusal_correctness = (refusal_correct / refusal_expected) if refusal_expected else 0.0
    p50_latency = _percentile([d["latency_ms"] for d in details], 50)
    p95_latency = _percentile([d["latency_ms"] for d in details], 95)

    summary = {
        "run_id": datetime.now(timezone.utc).isoformat(),
        "suite": args.suite,
        "metrics": {
            "citation_coverage": round(citation_coverage, 4),
            "refusal_correctness": round(refusal_correctness, 4),
            "p50_latency_ms": p50_latency,
            "p95_latency_ms": p95_latency,
            "avg_cost_per_query": 0.0,
        },
    }

    details_path.write_text("\n".join(json.dumps(d) for d in details) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _call_ask(api_url: str, case: dict) -> dict:
    payload = {"question": case["question"], "docs_snapshot_id": case.get("docs_snapshot_id")}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/v1/ask",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _percentile(values: list[int], pct: int) -> int:
    if not values:
        return 0
    values = sorted(values)
    k = (len(values) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[f]
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return int(d0 + d1)


if __name__ == "__main__":
    main()
