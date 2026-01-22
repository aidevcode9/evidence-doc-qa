"""Happy path tests - questions that should return answers with citations.

These tests verify FR-021 (retrieval) and FR-023 (citation integrity).
"""

import pytest

from evals.conftest import EvalClient, load_suite


class TestAnswerable:
    """Tests for questions that should be answered with citations."""

    @pytest.fixture(scope="class")
    def cases(self) -> list[dict]:
        return load_suite("answerable")

    def test_all_answerable_get_responses(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """All answerable questions should return answers, not refusals."""
        for case in cases:
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            assert response.has_answer, (
                f"Case {case['id']} was refused: {response.refusal_code}"
            )
            assert response.citations, (
                f"Case {case['id']} has no citations"
            )

    def test_citations_have_required_fields(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """All citations should have doc_id, page_num, and snippet."""
        for case in cases[:3]:  # Sample for speed
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            if response.has_answer:
                for citation in response.citations:
                    assert "doc_id" in citation, f"Citation missing doc_id in {case['id']}"
                    assert "page_num" in citation, f"Citation missing page_num in {case['id']}"
                    assert citation.get("snippet"), f"Citation has empty snippet in {case['id']}"

    def test_expected_document_cited(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """Answers should cite the expected document and page."""
        for case in cases:
            if not case.get("expected_doc_id"):
                continue

            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            if response.has_answer:
                expected_doc = case["expected_doc_id"]
                expected_page = case.get("expected_page_num")

                doc_match = any(
                    c.get("doc_id") == expected_doc
                    for c in response.citations
                )
                page_match = any(
                    c.get("doc_id") == expected_doc and c.get("page_num") == expected_page
                    for c in response.citations
                ) if expected_page else True

                assert doc_match, (
                    f"Case {case['id']} did not cite expected doc {expected_doc}"
                )
                assert page_match, (
                    f"Case {case['id']} did not cite expected page {expected_page}"
                )
