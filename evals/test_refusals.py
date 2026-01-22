"""Refusal tests - questions that should be refused gracefully.

These tests verify the system refuses appropriately when:
- Information is not in documents
- Query asks for speculation/prediction
- Query is too broad or ambiguous
"""

import pytest

from evals.conftest import ALLOWED_REFUSAL_CODES, EvalClient, load_suite


class TestRefusals:
    """Tests for questions that should be refused."""

    @pytest.fixture(scope="class")
    def cases(self) -> list[dict]:
        return load_suite("refusals")

    def test_all_refusal_cases_refused(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """All refusal cases should return a valid refusal code."""
        for case in cases:
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            assert response.refused, (
                f"Case {case['id']} should have refused but got answer: "
                f"{response.answer_text[:100] if response.answer_text else 'None'}"
            )
            assert response.refusal_code in ALLOWED_REFUSAL_CODES, (
                f"Case {case['id']} has invalid refusal code: {response.refusal_code}"
            )

    def test_specific_refusal_codes(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """Cases with expected_refusal_code should match exactly."""
        for case in cases:
            if not case.get("expected_refusal_code"):
                continue

            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            assert response.refusal_code == case["expected_refusal_code"], (
                f"Case {case['id']} expected {case['expected_refusal_code']} "
                f"but got {response.refusal_code}"
            )

    def test_no_hallucination_on_refusal(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """Refused responses should not contain fabricated answers."""
        for case in cases:
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            if response.refused:
                # Should not have citations since we refused
                # (unless it's a partial refusal which isn't implemented)
                assert not response.citations or len(response.citations) == 0, (
                    f"Case {case['id']} refused but still has citations"
                )
