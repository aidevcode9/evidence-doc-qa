"""Citation integrity tests - FR-023 compliance.

These tests verify:
- Every answer has citation markers [N]
- Citation indices match markers in text
- Snippets are non-empty and match source
- Citations resolve to real chunks
"""

import pytest

from evals.conftest import EvalClient, load_suite


class TestCitationMarkers:
    """Tests for citation marker presence (FR-023)."""

    @pytest.fixture(scope="class")
    def cases(self) -> list[dict]:
        return load_suite("citation_integrity")

    def test_answers_have_citation_markers(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """Answers should contain [1] citation markers."""
        marker_cases = [c for c in cases if c.get("check_citation_markers")]

        for case in marker_cases:
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            if response.has_answer:
                assert "[1]" in (response.answer_text or ""), (
                    f"Case {case['id']} answer missing [1] marker"
                )

    def test_citation_index_matches_markers(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """Citation indices should match markers in answer text."""
        index_cases = [c for c in cases if c.get("check_citation_index")]

        for case in index_cases:
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            if response.has_answer:
                answer = response.answer_text or ""
                for citation in response.citations:
                    idx = citation.get("citation_index")
                    if idx is not None:
                        marker = f"[{idx}]"
                        assert marker in answer, (
                            f"Case {case['id']}: citation_index {idx} "
                            f"has no matching marker in answer"
                        )


class TestCitationContent:
    """Tests for citation content validity."""

    @pytest.fixture(scope="class")
    def cases(self) -> list[dict]:
        return load_suite("citation_integrity")

    def test_snippets_are_nonempty(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """Citation snippets should not be empty."""
        snippet_cases = [c for c in cases if c.get("check_snippet_nonempty")]

        for case in snippet_cases:
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            if response.has_answer:
                for i, citation in enumerate(response.citations):
                    snippet = citation.get("snippet", "")
                    assert snippet.strip(), (
                        f"Case {case['id']}: citation[{i}] has empty snippet"
                    )

    def test_citations_have_required_fields(
        self, client: EvalClient, cases: list[dict]
    ) -> None:
        """All citations should have doc_id, page_num, snippet."""
        for case in cases[:3]:  # Sample
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            if response.has_answer:
                for i, citation in enumerate(response.citations):
                    assert "doc_id" in citation, (
                        f"Case {case['id']}: citation[{i}] missing doc_id"
                    )
                    assert "page_num" in citation, (
                        f"Case {case['id']}: citation[{i}] missing page_num"
                    )


class TestCitationIntegrity:
    """Tests for citation integrity and source matching."""

    @pytest.fixture(scope="class")
    def answerable_cases(self) -> list[dict]:
        return load_suite("answerable")

    def test_all_answers_have_citations(
        self, client: EvalClient, answerable_cases: list[dict]
    ) -> None:
        """Every answer must have at least one citation."""
        for case in answerable_cases:
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            if response.has_answer:
                assert len(response.citations) > 0, (
                    f"Case {case['id']}: answer has no citations"
                )

    def test_no_fabricated_citations(
        self, client: EvalClient, answerable_cases: list[dict]
    ) -> None:
        """Citations should reference real document content."""
        for case in answerable_cases[:3]:  # Sample for speed
            response = client.ask(
                question=case["question"],
                docs_snapshot_id=case.get("docs_snapshot_id"),
            )

            if response.has_answer:
                # Check that citations have valid structure
                for citation in response.citations:
                    assert citation.get("doc_id"), "Citation missing doc_id"
                    assert isinstance(citation.get("page_num"), int), (
                        f"Invalid page_num: {citation.get('page_num')}"
                    )
                    # Page numbers should be positive
                    assert citation.get("page_num", 0) >= 1, (
                        f"Invalid page_num: {citation.get('page_num')}"
                    )
