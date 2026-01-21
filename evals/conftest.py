"""Pytest fixtures and configuration for evals."""

import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


@dataclass
class AskResponse:
    """Response from /v1/ask endpoint."""

    answer_text: str | None
    refusal_code: str | None
    citations: list[dict[str, Any]]
    evidence: dict[str, Any] | None
    debug_candidates: list[dict[str, Any]]
    version_snapshot: dict[str, Any]
    raw: dict[str, Any]

    @property
    def has_answer(self) -> bool:
        return self.answer_text is not None and self.refusal_code is None

    @property
    def refused(self) -> bool:
        return self.refusal_code is not None


class EvalClient:
    """Client for calling the ask API during evals."""

    def __init__(self, api_url: str):
        self.api_url = api_url.rstrip("/")

    def ask(self, question: str, docs_snapshot_id: str | None = None) -> AskResponse:
        """Call /v1/ask and return structured response."""
        payload = {"question": question}
        if docs_snapshot_id:
            payload["docs_snapshot_id"] = docs_snapshot_id

        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.api_url}/v1/ask",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        return AskResponse(
            answer_text=data.get("answer_text"),
            refusal_code=data.get("refusal_code"),
            citations=data.get("citations") or [],
            evidence=data.get("evidence"),
            debug_candidates=data.get("debug_candidates") or [],
            version_snapshot=data.get("version_snapshot") or {},
            raw=data,
        )


@pytest.fixture(scope="session")
def api_url() -> str:
    """Get API URL from environment or use default."""
    return os.getenv("EVAL_API_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def client(api_url: str) -> EvalClient:
    """Create eval client for the test session."""
    return EvalClient(api_url)


@pytest.fixture(scope="session")
def demo_snapshot_id() -> str:
    """Default snapshot ID for demo documents."""
    return "snap_demo"


def load_suite(suite_name: str) -> list[dict[str, Any]]:
    """Load test cases from a suite file."""
    evals_dir = Path(__file__).parent

    # Try suites directory first
    suite_path = evals_dir / "suites" / f"{suite_name}.jsonl"
    if not suite_path.exists():
        suite_path = evals_dir / f"{suite_name}.jsonl"

    if not suite_path.exists():
        raise FileNotFoundError(f"Suite not found: {suite_name}")

    cases = []
    for line in suite_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line(
        "markers", "adversarial: marks tests as adversarial/security tests"
    )


# Allowed refusal codes for validation
ALLOWED_REFUSAL_CODES = {
    "NO_SUPPORTING_EVIDENCE",
    "LOW_RETRIEVAL_CONFIDENCE",
    "INJECTION_DETECTED",
    "PARSE_FAILED",
    "POLICY_REFUSAL",
    "EMPTY_QUESTION",
    "INVALID_REQUEST",
}
