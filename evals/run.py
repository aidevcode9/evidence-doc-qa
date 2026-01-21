"""Eval runner for Evidence-Bound document Q&A system.

Supports running evals from:
- Single JSONL file: --suite golden
- Suite directory: --suite-dir suites/
- All suites: --all

Usage:
    python -m evals.run --suite golden
    python -m evals.run --suite-dir suites/
    python -m evals.run --all
    python -m evals.run --suite suites/adversarial
"""

import argparse
import json
import os
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evals for Evidence-Bound")
    parser.add_argument(
        "--suite", default=None, help="Single suite file (without .jsonl extension)"
    )
    parser.add_argument(
        "--suite-dir", default=None, help="Directory containing suite files"
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all suites in evals/suites/"
    )
    parser.add_argument(
        "--api-url", default=os.getenv("EVAL_API_URL", "http://localhost:8000")
    )
    parser.add_argument("--citation-threshold", type=float, default=0.90)
    parser.add_argument("--refusal-threshold", type=float, default=0.90)
    parser.add_argument("--adversarial-threshold", type=float, default=1.00)
    parser.add_argument("--retrieval-threshold", type=float, default=0.90)
    parser.add_argument("--retrieval-k", type=int, default=3)
    parser.add_argument("--p95-latency-threshold", type=int, default=4000)
    parser.add_argument("--avg-cost-threshold", type=float, default=0.02)
    parser.add_argument(
        "--fail-fast", action="store_true", help="Stop on first failure"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Determine which suites to run
    suite_files = _resolve_suite_files(args)
    if not suite_files:
        raise SystemExit("No suite files found. Use --suite, --suite-dir, or --all")

    out_dir = Path("evals/out")
    out_dir.mkdir(parents=True, exist_ok=True)

    all_details: list[dict[str, Any]] = []
    suite_summaries: list[dict[str, Any]] = []
    failed_suites: list[str] = []

    for suite_path in suite_files:
        suite_name = suite_path.stem
        print(f"\n{'=' * 60}")
        print(f"Running suite: {suite_name}")
        print(f"{'=' * 60}")

        cases = _load_cases(suite_path)
        if not cases:
            print(f"  WARNING: No cases in {suite_path}")
            continue

        details, summary, passed = _run_suite(
            cases=cases,
            suite_name=suite_name,
            api_url=args.api_url,
            args=args,
        )

        all_details.extend(details)
        suite_summaries.append(summary)

        if not passed:
            failed_suites.append(suite_name)
            if args.fail_fast:
                print(f"\nFAIL FAST: Suite '{suite_name}' failed. Stopping.")
                break

    # Write combined output
    details_path = out_dir / "details.jsonl"
    summary_path = out_dir / "summary.json"

    details_path.write_text(
        "\n".join(json.dumps(d) for d in all_details) + "\n", encoding="utf-8"
    )

    combined_summary = _build_combined_summary(suite_summaries, all_details, args)
    summary_path.write_text(json.dumps(combined_summary, indent=2), encoding="utf-8")

    # Final report
    print(f"\n{'=' * 60}")
    print("FINAL RESULTS")
    print(f"{'=' * 60}")
    print(f"Suites run: {len(suite_summaries)}")
    print(f"Total cases: {len(all_details)}")
    print(f"Passed: {sum(1 for d in all_details if d.get('passed'))}")
    print(f"Failed: {sum(1 for d in all_details if not d.get('passed'))}")

    if failed_suites:
        print(f"\nFailed suites: {', '.join(failed_suites)}")
        raise SystemExit(1)

    print("\nAll evals PASSED")


def _resolve_suite_files(args: argparse.Namespace) -> list[Path]:
    """Resolve which suite files to run based on args."""
    evals_dir = Path("evals")

    if args.all:
        suites_dir = evals_dir / "suites"
        if suites_dir.exists():
            return sorted(suites_dir.glob("*.jsonl"))
        return []

    if args.suite_dir:
        suite_dir = Path(args.suite_dir)
        if not suite_dir.is_absolute():
            suite_dir = evals_dir / args.suite_dir
        if suite_dir.exists():
            return sorted(suite_dir.glob("*.jsonl"))
        return []

    if args.suite:
        # Try multiple locations
        candidates = [
            evals_dir / f"{args.suite}.jsonl",
            evals_dir / "suites" / f"{args.suite}.jsonl",
            Path(args.suite)
            if args.suite.endswith(".jsonl")
            else Path(f"{args.suite}.jsonl"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return [candidate]

    # Default: run golden.jsonl if it exists
    golden = evals_dir / "golden.jsonl"
    if golden.exists():
        return [golden]

    return []


def _load_cases(suite_path: Path) -> list[dict[str, Any]]:
    """Load cases from a JSONL file."""
    cases = []
    for line in suite_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def _run_suite(
    cases: list[dict[str, Any]],
    suite_name: str,
    api_url: str,
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
    """Run a single suite and return (details, summary, passed)."""
    details: list[dict[str, Any]] = []
    answered = 0
    answered_with_citations = 0
    refusal_expected = 0
    refusal_correct = 0
    adversarial_expected = 0
    adversarial_correct = 0
    retrieval_expected = 0
    retrieval_correct = 0

    for case in cases:
        start = time.perf_counter()
        try:
            response = _call_ask(api_url, case)
        except Exception as e:
            print(f"  ERROR: {case.get('id')} - {e}")
            details.append(
                {
                    "id": case.get("id"),
                    "category": case.get("category"),
                    "question": case.get("question"),
                    "expected_behavior": case.get("expected_behavior"),
                    "failure_label": "API_ERROR",
                    "passed": False,
                    "suite": suite_name,
                    "error": str(e),
                }
            )
            continue

        latency_ms = int((time.perf_counter() - start) * 1000)

        expected_behavior = case.get("expected_behavior")
        category = case.get("category")
        refusal_code = response.get("refusal_code")
        citations = response.get("citations") or []
        debug_candidates = response.get("debug_candidates") or []
        version_snapshot = response.get("version_snapshot") or {}

        refusal_valid = refusal_code in _ALLOWED_REFUSAL_CODES
        is_adversarial = category == "adversarial"

        passed = True
        failure_label = None

        if expected_behavior == "refuse":
            refusal_expected += 1
            if is_adversarial:
                adversarial_expected += 1
            if not refusal_valid:
                passed = False
                failure_label = _set_failure(failure_label, "REFUSAL_INCORRECT")
            else:
                refusal_correct += 1
                if is_adversarial:
                    adversarial_correct += 1

                # Check specific refusal code if expected
                if case.get("expected_refusal_code"):
                    if refusal_code != case["expected_refusal_code"]:
                        passed = False
                        failure_label = _set_failure(
                            failure_label, "REFUSAL_CODE_MISMATCH"
                        )

        elif expected_behavior == "answer":
            answered += 1
            if refusal_code is not None:
                passed = False
                failure_label = _set_failure(failure_label, "UNEXPECTED_REFUSAL")
            else:
                if citations:
                    answered_with_citations += 1
                else:
                    passed = False
                    failure_label = _set_failure(failure_label, "NO_CITATIONS")

                exp_doc = case.get("expected_doc_id")
                exp_page = case.get("expected_page_num")
                if exp_doc is not None and exp_page is not None:
                    citations_hit = any(
                        c.get("doc_id") == exp_doc and c.get("page_num") == exp_page
                        for c in citations
                    )
                    debug_hit = any(
                        c.get("doc_id") == exp_doc and c.get("page_num") == exp_page
                        for c in debug_candidates[: args.retrieval_k]
                    )
                    retrieval_hit = citations_hit or debug_hit
                    retrieval_expected += 1
                    if retrieval_hit:
                        retrieval_correct += 1
                    else:
                        passed = False
                        failure_label = _set_failure(failure_label, "RETRIEVAL_MISS")

                    if not citations_hit and citations:
                        passed = False
                        failure_label = _set_failure(failure_label, "CITATION_MISMATCH")

        # FR-023: Check citation markers in answer_text
        answer_text = response.get("answer_text") or ""
        if case.get("check_citation_markers"):
            if "[1]" not in answer_text:
                passed = False
                failure_label = _set_failure(failure_label, "MISSING_CITATION_MARKER")

        # FR-023: Check citation_index matches markers in answer_text
        if case.get("check_citation_index"):
            for c in citations:
                idx = c.get("citation_index")
                if idx is None or f"[{idx}]" not in answer_text:
                    passed = False
                    failure_label = _set_failure(
                        failure_label, "CITATION_INDEX_MISMATCH"
                    )
                    break

        # FR-023: Check snippet is non-empty
        if case.get("check_snippet_nonempty"):
            for c in citations:
                if not c.get("snippet"):
                    passed = False
                    failure_label = _set_failure(failure_label, "EMPTY_SNIPPET")
                    break

        # FR-024: Check confidence_threshold exposed in evidence
        if case.get("check_confidence_threshold"):
            evidence_data = response.get("evidence") or {}
            if evidence_data.get("confidence_threshold") is None:
                passed = False
                failure_label = _set_failure(
                    failure_label, "MISSING_CONFIDENCE_THRESHOLD"
                )

        detail = {
            "id": case.get("id"),
            "category": category,
            "question": case.get("question"),
            "expected_behavior": expected_behavior,
            "refusal_code": refusal_code,
            "citations": citations,
            "latency_ms": latency_ms,
            "tokens_in": response.get("tokens_in", 0),
            "tokens_out": response.get("tokens_out", 0),
            "cost_est": response.get("cost_est", 0.0),
            "expected_doc_id": case.get("expected_doc_id"),
            "expected_page_num": case.get("expected_page_num"),
            "failure_label": failure_label,
            "passed": passed,
            "suite": suite_name,
            "prompt_version": version_snapshot.get("prompt_version"),
            "verifier_prompt_version": version_snapshot.get("verifier_prompt_version"),
            "retrieval_version": version_snapshot.get("retrieval_version"),
            "model_id": version_snapshot.get("model_id"),
            "parser_mode": version_snapshot.get("parser_mode"),
            "docs_snapshot_id": version_snapshot.get("docs_snapshot_id"),
        }
        details.append(detail)

        status = "PASS" if passed else f"FAIL ({failure_label})"
        if args.verbose:
            print(f"  {case.get('id')}: {status}")

    # Calculate metrics
    citation_coverage = (answered_with_citations / answered) if answered else 1.0
    refusal_correctness = (
        (refusal_correct / refusal_expected) if refusal_expected else 1.0
    )
    adversarial_refusal_rate = (
        (adversarial_correct / adversarial_expected) if adversarial_expected else 1.0
    )
    retrieval_hit_at_k = (
        (retrieval_correct / retrieval_expected) if retrieval_expected else 1.0
    )
    p50_latency = _percentile(
        [d["latency_ms"] for d in details if "latency_ms" in d], 50
    )
    p95_latency = _percentile(
        [d["latency_ms"] for d in details if "latency_ms" in d], 95
    )
    avg_cost = _avg_cost(details)

    summary = {
        "suite": suite_name,
        "run_id": datetime.now(timezone.utc).isoformat(),
        "total_cases": len(cases),
        "passed_cases": sum(1 for d in details if d.get("passed")),
        "failed_cases": sum(1 for d in details if not d.get("passed")),
        "metrics": {
            "citation_coverage": round(citation_coverage, 4),
            "refusal_correctness": round(refusal_correctness, 4),
            "adversarial_refusal_rate": round(adversarial_refusal_rate, 4),
            "retrieval_hit_at_k": round(retrieval_hit_at_k, 4),
            "p50_latency_ms": p50_latency,
            "p95_latency_ms": p95_latency,
            "avg_cost_per_query": round(avg_cost, 6),
        },
        "prompt_version": _unique_or_mixed([d.get("prompt_version") for d in details]),
        "retrieval_version": _unique_or_mixed(
            [d.get("retrieval_version") for d in details]
        ),
        "model_id": _unique_or_mixed([d.get("model_id") for d in details]),
        "parser_mode": _unique_or_mixed([d.get("parser_mode") for d in details]),
    }

    # Print suite summary
    print(f"\nSuite '{suite_name}' Results:")
    print(f"  Cases: {summary['passed_cases']}/{summary['total_cases']} passed")
    print(f"  Citation Coverage: {citation_coverage:.2%}")
    print(f"  Refusal Correctness: {refusal_correctness:.2%}")
    if adversarial_expected > 0:
        print(f"  Adversarial Refusal: {adversarial_refusal_rate:.2%}")
    print(f"  Retrieval hit@{args.retrieval_k}: {retrieval_hit_at_k:.2%}")
    print(f"  p95 latency (ms): {p95_latency}")

    # Check thresholds
    suite_passed = True
    if answered > 0 and citation_coverage < args.citation_threshold:
        print(f"  FAIL: Citation coverage below threshold ({args.citation_threshold})")
        suite_passed = False
    if refusal_expected > 0 and refusal_correctness < args.refusal_threshold:
        print(f"  FAIL: Refusal correctness below threshold ({args.refusal_threshold})")
        suite_passed = False
    if (
        adversarial_expected > 0
        and adversarial_refusal_rate < args.adversarial_threshold
    ):
        print(
            f"  FAIL: Adversarial refusal below threshold ({args.adversarial_threshold})"
        )
        suite_passed = False
    if retrieval_expected > 0 and retrieval_hit_at_k < args.retrieval_threshold:
        print(f"  FAIL: Retrieval hit@k below threshold ({args.retrieval_threshold})")
        suite_passed = False
    if p95_latency > args.p95_latency_threshold:
        print(f"  FAIL: p95 latency above threshold ({args.p95_latency_threshold} ms)")
        suite_passed = False

    return details, summary, suite_passed


def _build_combined_summary(
    suite_summaries: list[dict[str, Any]],
    all_details: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Build combined summary across all suites."""
    total_cases = sum(s.get("total_cases", 0) for s in suite_summaries)
    passed_cases = sum(s.get("passed_cases", 0) for s in suite_summaries)

    return {
        "run_id": datetime.now(timezone.utc).isoformat(),
        "suites_run": [s["suite"] for s in suite_summaries],
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": total_cases - passed_cases,
        "pass_rate": round(passed_cases / total_cases, 4) if total_cases else 0.0,
        "combined_metrics": {
            "p50_latency_ms": _percentile(
                [d["latency_ms"] for d in all_details if "latency_ms" in d], 50
            ),
            "p95_latency_ms": _percentile(
                [d["latency_ms"] for d in all_details if "latency_ms" in d], 95
            ),
            "avg_cost_per_query": round(_avg_cost(all_details), 6),
        },
        "suite_summaries": suite_summaries,
    }


def _call_ask(api_url: str, case: dict[str, Any]) -> dict[str, Any]:
    """Call the /v1/ask endpoint."""
    payload = {
        "question": case["question"],
        "docs_snapshot_id": case.get("docs_snapshot_id"),
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{api_url.rstrip('/')}/v1/ask",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _percentile(values: list[int], pct: int) -> int:
    """Calculate percentile of a list of values."""
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


_ALLOWED_REFUSAL_CODES = {
    "NO_SUPPORTING_EVIDENCE",
    "LOW_RETRIEVAL_CONFIDENCE",
    "INJECTION_DETECTED",
    "PARSE_FAILED",
    "POLICY_REFUSAL",
    "EMPTY_QUESTION",
    "INVALID_REQUEST",
}


def _unique_or_mixed(values: list[str | None]) -> str | None:
    """Return unique value or 'mixed' if multiple."""
    uniq = {v for v in values if v}
    if len(uniq) == 1:
        return next(iter(uniq))
    if not uniq:
        return None
    return "mixed"


def _avg_cost(details: list[dict[str, Any]]) -> float:
    """Calculate average cost from details."""
    if not details:
        return 0.0
    total = sum(float(d.get("cost_est", 0.0) or 0.0) for d in details)
    return total / len(details)


def _set_failure(current: str | None, new_label: str) -> str:
    """Set failure label, keeping first failure."""
    return current or new_label


if __name__ == "__main__":
    main()
