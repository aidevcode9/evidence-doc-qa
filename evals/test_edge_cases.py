"""Edge case tests - boundary conditions and error handling.

These tests verify graceful handling of:
- Empty or whitespace-only questions
- Non-existent documents/snapshots
- Empty retrieval results
- OCR failures / empty document extraction
- Large or complex queries
"""

import pytest

from evals.conftest import ALLOWED_REFUSAL_CODES, EvalClient, load_suite


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.fixture(scope="class")
    def cases(self) -> list[dict]:
        return load_suite("edge_cases")

    def test_edge_cases_handled_gracefully(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """All edge cases should be handled without errors."""
        for case in cases:
            try:
                response = client.ask(
                    question=case["question"],
                    docs_snapshot_id=case.get("docs_snapshot_id"),
                )

                # Should either answer or refuse gracefully
                if case.get("expected_behavior") == "refuse":
                    assert response.refused, (
                        f"Case {case['id']} should refuse but got answer"
                    )
                    assert response.refusal_code in ALLOWED_REFUSAL_CODES, (
                        f"Case {case['id']} has invalid refusal code: {response.refusal_code}"
                    )

            except Exception as e:
                pytest.fail(f"Case {case['id']} raised exception: {e}")


class TestEmptyQuestions:
    """Tests for empty or invalid question handling."""

    def test_empty_question_refused(self, client: EvalClient) -> None:
        """Empty string question should be refused."""
        response = client.ask(question="", docs_snapshot_id="snap_demo")
        assert response.refused, "Empty question should be refused"

    def test_whitespace_question_refused(self, client: EvalClient) -> None:
        """Whitespace-only question should be refused."""
        response = client.ask(question="   ", docs_snapshot_id="snap_demo")
        assert response.refused, "Whitespace question should be refused"

    def test_single_char_question(self, client: EvalClient) -> None:
        """Single character question should be refused or handled."""
        response = client.ask(question="a", docs_snapshot_id="snap_demo")
        # Either refuse or return low-quality answer
        assert response.refused or response.has_answer


class TestNonExistentResources:
    """Tests for handling non-existent documents/snapshots."""

    def test_nonexistent_snapshot_refused(self, client: EvalClient) -> None:
        """Query against non-existent snapshot should refuse."""
        response = client.ask(
            question="What are the terms?",
            docs_snapshot_id="snap_does_not_exist_xyz",
        )
        assert response.refused, "Non-existent snapshot should refuse"


class TestEmptyRetrieval:
    """Tests for handling empty retrieval results."""

    def test_no_matching_content_refused(self, client: EvalClient) -> None:
        """Query with no matching content should refuse gracefully."""
        response = client.ask(
            question="What is the quantum flux capacitor algorithm coefficient?",
            docs_snapshot_id="snap_demo",
        )
        assert response.refused, "No matching content should refuse"
        assert response.refusal_code in ALLOWED_REFUSAL_CODES


@pytest.mark.slow
class TestOCREdgeCases:
    """Tests for OCR-related edge cases (requires test fixtures)."""

    def test_empty_ocr_extraction_warned(self, client: EvalClient) -> None:
        """Document with empty OCR should return warning or refuse."""
        # This test requires snap_empty_ocr to exist
        response = client.ask(
            question="What are the terms?",
            docs_snapshot_id="snap_empty_ocr",
        )
        # Should refuse since no text was extracted
        assert response.refused, "Empty OCR extraction should refuse"

    def test_scanned_document_handling(self, client: EvalClient) -> None:
        """Scanned document should be handled (OCR or refuse)."""
        # This test requires snap_scanned to exist
        response = client.ask(
            question="What does the document say?",
            docs_snapshot_id="snap_scanned",
        )
        # Either OCR worked and we have answer, or we refuse gracefully
        assert response.has_answer or response.refused
