"""Confidence threshold tests - FR-024 compliance.

These tests verify:
- Confidence threshold is exposed in response
- Low confidence queries are refused
- Threshold boundary behavior (0.70)
"""

import pytest

from evals.conftest import ALLOWED_REFUSAL_CODES, EvalClient, load_suite


class TestConfidenceThreshold:
    """Tests for confidence threshold behavior (FR-024)."""

    @pytest.fixture(scope="class")
    def cases(self) -> list[dict]:
        return load_suite("confidence_threshold")

    def test_threshold_exposed_in_response(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """Confidence threshold should be exposed in evidence."""
        threshold_cases = [c for c in cases if c.get("check_confidence_threshold")]

        for case in threshold_cases:
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            if response.has_answer and response.evidence:
                threshold = response.evidence.get("confidence_threshold")
                assert threshold is not None, (
                    f"Case {case['id']}: confidence_threshold not in evidence"
                )
                assert threshold == 0.70, (
                    f"Case {case['id']}: threshold should be 0.70, got {threshold}"
                )


class TestLowConfidenceRefusal:
    """Tests for low confidence refusal behavior."""

    @pytest.fixture(scope="class")
    def cases(self) -> list[dict]:
        return load_suite("confidence_threshold")

    def test_low_confidence_refused(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """Queries with no matching content should refuse."""
        refusal_cases = [
            c for c in cases
            if c.get("expected_behavior") == "refuse"
        ]

        for case in refusal_cases:
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            assert response.refused, (
                f"Case {case['id']} should refuse but got answer"
            )
            assert response.refusal_code in ALLOWED_REFUSAL_CODES, (
                f"Case {case['id']} has invalid refusal code: {response.refusal_code}"
            )

    def test_no_supporting_evidence_code(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """Low confidence should return NO_SUPPORTING_EVIDENCE code."""
        no_evidence_cases = [
            c for c in cases
            if c.get("expected_refusal_code") == "NO_SUPPORTING_EVIDENCE"
        ]

        for case in no_evidence_cases:
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            assert response.refusal_code == "NO_SUPPORTING_EVIDENCE", (
                f"Case {case['id']} expected NO_SUPPORTING_EVIDENCE "
                f"but got {response.refusal_code}"
            )


class TestNoHallucination:
    """Tests to ensure no hallucination when confidence is low."""

    def test_nonsense_question_no_hallucination(
        self, client: EvalClient
    ) -> None:
        """Nonsense questions should not produce hallucinated answers."""
        nonsense_questions = [
            "What is the quantum flux capacitor coefficient?",
            "What color is the invisible unicorn in section 5?",
            "How many giraffes are mentioned in the contract?",
        ]

        for question in nonsense_questions:
            response = client.ask(question=question, docs_snapshot_id="snap_demo")

            assert response.refused, (
                f"Nonsense question should refuse: {question[:50]}..."
            )

    def test_off_topic_question_no_hallucination(
        self, client: EvalClient
    ) -> None:
        """Questions about content not in docs should refuse."""
        off_topic = [
            "What is the CEO's favorite color?",
            "What did they have for lunch at the meeting?",
            "What is the weather forecast for next Tuesday?",
        ]

        for question in off_topic:
            response = client.ask(question=question, docs_snapshot_id="snap_demo")

            assert response.refused, (
                f"Off-topic question should refuse: {question[:50]}..."
            )
