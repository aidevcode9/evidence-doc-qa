"""Tests for cited-only packet export (FR-033).

Exports a focused document listing only the exhibits/pages actually
cited in a Q&A session — a legal industry "cited-only packet".
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.context import RequestContext
from app.db import QAMessage, QASession
from app.rbac import Role


def make_context(
    tenant_id: str = "tenant-1",
    matter_id: str = "matter-1",
    user_id: str = "user-1",
    user_role: Role = Role.ATTORNEY,
) -> RequestContext:
    return RequestContext(
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=user_id,
        user_role=user_role,
    )


def _make_assistant_msg(
    citations: list[dict[str, Any]],
    content: str = "Answer with citations.",
    refusal_code: str | None = None,
) -> MagicMock:
    msg = MagicMock(spec=QAMessage)
    msg.role = "assistant"
    msg.content = content
    msg.citations_json = json.dumps(citations) if citations else None
    msg.evidence_json = None
    msg.refusal_code = refusal_code
    msg.created_at_utc = datetime.now(timezone.utc).isoformat()
    return msg


def _make_user_msg(content: str = "Question?") -> MagicMock:
    msg = MagicMock(spec=QAMessage)
    msg.role = "user"
    msg.content = content
    msg.citations_json = None
    msg.evidence_json = None
    msg.refusal_code = None
    msg.created_at_utc = datetime.now(timezone.utc).isoformat()
    return msg


SAMPLE_CITATIONS = [
    {
        "citation_index": 1,
        "doc_id": "doc-aaa",
        "doc_name": "Contract.pdf",
        "page_num": 5,
        "page_end": 5,
        "char_start": 100,
        "char_end": 200,
        "chunk_id": "chunk-1",
        "snippet": "Payment shall be due within thirty (30) days...",
        "score": 0.95,
    },
    {
        "citation_index": 2,
        "doc_id": "doc-bbb",
        "doc_name": "Lease.pdf",
        "page_num": 12,
        "page_end": 13,
        "char_start": 0,
        "char_end": 150,
        "chunk_id": "chunk-2",
        "snippet": "The lessee shall maintain the premises in good condition...",
        "score": 0.88,
    },
]

DUPLICATE_CITATIONS = [
    {
        "citation_index": 1,
        "doc_id": "doc-aaa",
        "doc_name": "Contract.pdf",
        "page_num": 5,
        "page_end": 5,
        "char_start": 100,
        "char_end": 200,
        "chunk_id": "chunk-1",
        "snippet": "Payment shall be due within thirty (30) days...",
        "score": 0.95,
    },
    {
        "citation_index": 2,
        "doc_id": "doc-aaa",
        "doc_name": "Contract.pdf",
        "page_num": 10,
        "page_end": 10,
        "char_start": 300,
        "char_end": 400,
        "chunk_id": "chunk-3",
        "snippet": "Termination clause states that either party may...",
        "score": 0.90,
    },
]


class TestExtractCitations:
    """Extract and deduplicate citations from session messages."""

    def test_extract_unique_citations_from_messages(self) -> None:
        """Extract deduplicated citation list across all messages."""
        from app.services.export_service import extract_cited_exhibits

        messages = [
            _make_user_msg(),
            _make_assistant_msg(SAMPLE_CITATIONS),
            _make_user_msg("Follow-up?"),
            _make_assistant_msg(SAMPLE_CITATIONS[:1]),  # Duplicate of first
        ]

        exhibits = extract_cited_exhibits(messages)

        # Should have 2 unique documents, not 3
        assert len(exhibits) == 2
        doc_names = {e["doc_name"] for e in exhibits}
        assert doc_names == {"Contract.pdf", "Lease.pdf"}

    def test_extract_citations_groups_pages_by_document(self) -> None:
        """Citations from same document grouped with all pages."""
        from app.services.export_service import extract_cited_exhibits

        messages = [
            _make_user_msg(),
            _make_assistant_msg(DUPLICATE_CITATIONS),
        ]

        exhibits = extract_cited_exhibits(messages)

        # One document with two page references
        assert len(exhibits) == 1
        assert exhibits[0]["doc_name"] == "Contract.pdf"
        pages = exhibits[0]["pages"]
        assert 5 in pages
        assert 10 in pages

    def test_extract_citations_includes_snippets(self) -> None:
        """Each exhibit includes snippets from cited chunks."""
        from app.services.export_service import extract_cited_exhibits

        messages = [
            _make_user_msg(),
            _make_assistant_msg(SAMPLE_CITATIONS),
        ]

        exhibits = extract_cited_exhibits(messages)

        for exhibit in exhibits:
            assert len(exhibit["snippets"]) > 0
            for snippet in exhibit["snippets"]:
                assert "text" in snippet
                assert "page_num" in snippet

    def test_extract_citations_handles_no_citations(self) -> None:
        """Empty result when no citations in session."""
        from app.services.export_service import extract_cited_exhibits

        messages = [
            _make_user_msg(),
            _make_assistant_msg([], content="No evidence found."),
        ]

        exhibits = extract_cited_exhibits(messages)
        assert exhibits == []

    def test_extract_citations_skips_malformed_json(self) -> None:
        """Malformed citations_json is safely skipped."""
        from app.services.export_service import extract_cited_exhibits

        msg = MagicMock(spec=QAMessage)
        msg.role = "assistant"
        msg.citations_json = "not valid json{{"
        msg.refusal_code = None

        messages = [_make_user_msg(), msg]

        exhibits = extract_cited_exhibits(messages)
        assert exhibits == []


class TestGenerateCitedPacketPdf:
    """PDF cited-packet generation."""

    def test_generate_cited_packet_pdf_returns_bytes(self) -> None:
        """PDF cited packet generation produces valid PDF."""
        from app.services.export_service import generate_cited_packet_pdf

        session = MagicMock(spec=QASession)
        session.session_id = "test-session-123"
        session.docs_snapshot_id = "snap_abc123"

        messages = [
            _make_user_msg(),
            _make_assistant_msg(SAMPLE_CITATIONS),
        ]

        result = generate_cited_packet_pdf(session, messages)

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:4] == b"%PDF"

    def test_generate_cited_packet_pdf_empty_citations(self) -> None:
        """PDF packet with zero citations still generates valid PDF."""
        from app.services.export_service import generate_cited_packet_pdf

        session = MagicMock(spec=QASession)
        session.session_id = "test-session"
        session.docs_snapshot_id = "snap_abc"

        messages = [
            _make_user_msg(),
            _make_assistant_msg([], content="No evidence found."),
        ]

        result = generate_cited_packet_pdf(session, messages)

        assert isinstance(result, bytes)
        assert result[:4] == b"%PDF"


class TestGenerateCitedPacketDocx:
    """DOCX cited-packet generation."""

    def test_generate_cited_packet_docx_returns_bytes(self) -> None:
        """DOCX cited packet generation produces valid DOCX."""
        from app.services.export_service import generate_cited_packet_docx

        session = MagicMock(spec=QASession)
        session.session_id = "test-session-123"
        session.docs_snapshot_id = "snap_abc123"

        messages = [
            _make_user_msg(),
            _make_assistant_msg(SAMPLE_CITATIONS),
        ]

        result = generate_cited_packet_docx(session, messages)

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:2] == b"PK"  # DOCX is ZIP

    def test_generate_cited_packet_docx_empty_citations(self) -> None:
        """DOCX packet with zero citations still generates valid DOCX."""
        from app.services.export_service import generate_cited_packet_docx

        session = MagicMock(spec=QASession)
        session.session_id = "test-session"
        session.docs_snapshot_id = "snap_abc"

        messages = [
            _make_user_msg(),
            _make_assistant_msg([], content="No evidence found."),
        ]

        result = generate_cited_packet_docx(session, messages)

        assert isinstance(result, bytes)
        assert result[:2] == b"PK"


class TestCitedPacketEndpoint:
    """Endpoint tests for GET /v1/sessions/{session_id}/export/cited-packet."""

    def _mock_bg(self) -> MagicMock:
        mock = MagicMock()
        mock.add_task = MagicMock()
        return mock

    def _mock_session(self, session_id: str = "sess-123") -> MagicMock:
        session = MagicMock(spec=QASession)
        session.session_id = session_id
        session.docs_snapshot_id = "snap_abc"
        session.created_at_utc = datetime.now(timezone.utc).isoformat()
        return session

    def _mock_messages(self) -> list[MagicMock]:
        return [
            _make_user_msg(),
            _make_assistant_msg(SAMPLE_CITATIONS),
        ]

    @pytest.mark.asyncio
    async def test_cited_packet_endpoint_returns_pdf(self) -> None:
        """Cited packet endpoint returns PDF by default."""
        from app.routers.export import export_cited_packet

        with (
            patch("app.routers.export.get_qa_session", return_value=self._mock_session()),
            patch("app.routers.export.get_session_messages", return_value=self._mock_messages()),
            patch("app.routers.export.has_permission", return_value=True),
        ):
            result = await export_cited_packet(
                "sess-123",
                self._mock_bg(),
                context=make_context(),
                format="pdf",
                x_docqa_session="sess-123",
            )

            assert result.media_type == "application/pdf"
            assert "cited-packet-" in result.filename
            assert result.filename.endswith(".pdf")

    @pytest.mark.asyncio
    async def test_cited_packet_endpoint_returns_docx(self) -> None:
        """Cited packet endpoint supports DOCX format."""
        from app.routers.export import export_cited_packet

        with (
            patch("app.routers.export.get_qa_session", return_value=self._mock_session()),
            patch("app.routers.export.get_session_messages", return_value=self._mock_messages()),
            patch("app.routers.export.has_permission", return_value=True),
        ):
            result = await export_cited_packet(
                "sess-123",
                self._mock_bg(),
                context=make_context(),
                format="docx",
                x_docqa_session="sess-123",
            )

            assert result.media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            assert result.filename.endswith(".docx")

    @pytest.mark.asyncio
    async def test_cited_packet_requires_session_header(self) -> None:
        """IDOR protection — session header required."""
        from app.routers.export import export_cited_packet
        from fastapi import HTTPException

        with patch("app.routers.export.has_permission", return_value=True):
            with pytest.raises(HTTPException) as exc_info:
                await export_cited_packet(
                    "sess-123",
                    self._mock_bg(),
                    context=make_context(),
                    format="pdf",
                    x_docqa_session=None,
                )
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_cited_packet_404_unknown_session(self) -> None:
        """Unknown session returns 404."""
        from app.routers.export import export_cited_packet
        from fastapi import HTTPException

        with (
            patch("app.routers.export.get_qa_session", return_value=None),
            patch("app.routers.export.has_permission", return_value=True),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await export_cited_packet(
                    "nonexistent",
                    self._mock_bg(),
                    context=make_context(),
                    format="pdf",
                    x_docqa_session="nonexistent",
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cited_packet_rbac_enforced(self) -> None:
        """RBAC blocks unauthorized users."""
        from app.routers.export import export_cited_packet
        from fastapi import HTTPException

        with patch("app.routers.export.has_permission", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await export_cited_packet(
                    "sess-123",
                    self._mock_bg(),
                    context=make_context(user_role=Role.VIEWER),
                    format="pdf",
                    x_docqa_session="sess-123",
                )
            assert exc_info.value.status_code == 403
