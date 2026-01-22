# tests/test_export.py
"""Tests for Q&A export functionality (FR-032)."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from app.db import QAMessage, QASession


class TestGeneratePdfExport:
    """Tests for PDF export generation."""

    def test_generate_pdf_returns_bytes(self) -> None:
        """PDF export returns bytes."""
        from app.services.export_service import generate_pdf_export

        session = MagicMock(spec=QASession)
        session.session_id = "test-session-123"
        session.docs_snapshot_id = "snap_abc123"
        session.created_at_utc = datetime.now(timezone.utc).isoformat()

        messages = [
            MagicMock(spec=QAMessage),
            MagicMock(spec=QAMessage),
        ]
        messages[0].role = "user"
        messages[0].content = "What are the payment terms?"
        messages[0].citations_json = None
        messages[0].evidence_json = None
        messages[0].refusal_code = None
        messages[0].created_at_utc = datetime.now(timezone.utc).isoformat()

        messages[1].role = "assistant"
        messages[1].content = "According to Contract.pdf (page 5) [1], net-30 payment terms."
        messages[1].citations_json = json.dumps([{
            "citation_index": 1,
            "doc_id": "doc-123",
            "doc_name": "Contract.pdf",
            "page_num": 5,
            "page_end": 5,
            "char_start": 100,
            "char_end": 200,
            "chunk_id": "chunk-123",
            "snippet": "Payment shall be due within thirty (30) days...",
            "score": 0.95,
        }])
        messages[1].evidence_json = json.dumps({
            "verdict": "VERIFIED",
            "evidence_grade": "A",
            "evidence_label": "Strong",
        })
        messages[1].refusal_code = None
        messages[1].created_at_utc = datetime.now(timezone.utc).isoformat()

        result = generate_pdf_export(session, messages)

        assert isinstance(result, bytes)
        assert len(result) > 0
        # PDF files start with %PDF
        assert result[:4] == b"%PDF"

    def test_generate_pdf_includes_question(self) -> None:
        """PDF export includes user question."""
        from app.services.export_service import generate_pdf_export

        session = MagicMock(spec=QASession)
        session.session_id = "test-session"
        session.docs_snapshot_id = "snap_abc"
        session.created_at_utc = datetime.now(timezone.utc).isoformat()

        messages = [
            MagicMock(spec=QAMessage),
            MagicMock(spec=QAMessage),
        ]
        messages[0].role = "user"
        messages[0].content = "UNIQUE_QUESTION_TEXT_12345"
        messages[0].citations_json = None
        messages[0].evidence_json = None
        messages[0].refusal_code = None
        messages[0].created_at_utc = datetime.now(timezone.utc).isoformat()

        messages[1].role = "assistant"
        messages[1].content = "The answer is yes."
        messages[1].citations_json = None
        messages[1].evidence_json = None
        messages[1].refusal_code = None
        messages[1].created_at_utc = datetime.now(timezone.utc).isoformat()

        result = generate_pdf_export(session, messages)

        # PDF is binary but we can check it was generated
        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_generate_pdf_includes_citations(self) -> None:
        """PDF export includes citations from assistant message."""
        from app.services.export_service import generate_pdf_export

        session = MagicMock(spec=QASession)
        session.session_id = "test-session"
        session.docs_snapshot_id = "snap_abc"
        session.created_at_utc = datetime.now(timezone.utc).isoformat()

        messages = [
            MagicMock(spec=QAMessage),
            MagicMock(spec=QAMessage),
        ]
        messages[0].role = "user"
        messages[0].content = "Question?"
        messages[0].citations_json = None
        messages[0].evidence_json = None
        messages[0].refusal_code = None
        messages[0].created_at_utc = datetime.now(timezone.utc).isoformat()

        messages[1].role = "assistant"
        messages[1].content = "Answer with citation [1]."
        messages[1].citations_json = json.dumps([{
            "citation_index": 1,
            "doc_id": "doc-123",
            "doc_name": "Evidence.pdf",
            "page_num": 10,
            "page_end": 10,
            "char_start": 0,
            "char_end": 100,
            "chunk_id": "chunk-456",
            "snippet": "The relevant quoted text from the document...",
            "score": 0.88,
        }])
        messages[1].evidence_json = json.dumps({
            "verdict": "VERIFIED",
            "evidence_grade": "A",
            "evidence_label": "Strong",
        })
        messages[1].refusal_code = None
        messages[1].created_at_utc = datetime.now(timezone.utc).isoformat()

        result = generate_pdf_export(session, messages)

        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_generate_pdf_handles_refusal(self) -> None:
        """PDF export includes refusal messages."""
        from app.services.export_service import generate_pdf_export

        session = MagicMock(spec=QASession)
        session.session_id = "test-session"
        session.docs_snapshot_id = "snap_abc"
        session.created_at_utc = datetime.now(timezone.utc).isoformat()

        messages = [
            MagicMock(spec=QAMessage),
            MagicMock(spec=QAMessage),
        ]
        messages[0].role = "user"
        messages[0].content = "Off-topic question?"
        messages[0].citations_json = None
        messages[0].evidence_json = None
        messages[0].refusal_code = None
        messages[0].created_at_utc = datetime.now(timezone.utc).isoformat()

        messages[1].role = "assistant"
        messages[1].content = "No supporting evidence found."
        messages[1].citations_json = None
        messages[1].evidence_json = None
        messages[1].refusal_code = "NO_SUPPORTING_EVIDENCE"
        messages[1].created_at_utc = datetime.now(timezone.utc).isoformat()

        result = generate_pdf_export(session, messages)

        assert isinstance(result, bytes)
        assert len(result) > 100


class TestGenerateDocxExport:
    """Tests for DOCX export generation."""

    def test_generate_docx_returns_bytes(self) -> None:
        """DOCX export returns bytes."""
        from app.services.export_service import generate_docx_export

        session = MagicMock(spec=QASession)
        session.session_id = "test-session-123"
        session.docs_snapshot_id = "snap_abc123"
        session.created_at_utc = datetime.now(timezone.utc).isoformat()

        messages = [
            MagicMock(spec=QAMessage),
            MagicMock(spec=QAMessage),
        ]
        messages[0].role = "user"
        messages[0].content = "What are the payment terms?"
        messages[0].citations_json = None
        messages[0].evidence_json = None
        messages[0].refusal_code = None
        messages[0].created_at_utc = datetime.now(timezone.utc).isoformat()

        messages[1].role = "assistant"
        messages[1].content = "According to Contract.pdf (page 5) [1], net-30 payment terms."
        messages[1].citations_json = json.dumps([{
            "citation_index": 1,
            "doc_id": "doc-123",
            "doc_name": "Contract.pdf",
            "page_num": 5,
            "page_end": 5,
            "char_start": 100,
            "char_end": 200,
            "chunk_id": "chunk-123",
            "snippet": "Payment shall be due within thirty (30) days...",
            "score": 0.95,
        }])
        messages[1].evidence_json = json.dumps({
            "verdict": "VERIFIED",
            "evidence_grade": "A",
            "evidence_label": "Strong",
        })
        messages[1].refusal_code = None
        messages[1].created_at_utc = datetime.now(timezone.utc).isoformat()

        result = generate_docx_export(session, messages)

        assert isinstance(result, bytes)
        assert len(result) > 0
        # DOCX files are ZIP archives starting with PK
        assert result[:2] == b"PK"

    def test_generate_docx_includes_all_content(self) -> None:
        """DOCX export includes question, answer, and citations."""
        from app.services.export_service import generate_docx_export

        session = MagicMock(spec=QASession)
        session.session_id = "test-session"
        session.docs_snapshot_id = "snap_abc"
        session.created_at_utc = datetime.now(timezone.utc).isoformat()

        messages = [
            MagicMock(spec=QAMessage),
            MagicMock(spec=QAMessage),
        ]
        messages[0].role = "user"
        messages[0].content = "Complex question about contracts?"
        messages[0].citations_json = None
        messages[0].evidence_json = None
        messages[0].refusal_code = None
        messages[0].created_at_utc = datetime.now(timezone.utc).isoformat()

        messages[1].role = "assistant"
        messages[1].content = "Detailed answer with citations [1] [2]."
        messages[1].citations_json = json.dumps([
            {
                "citation_index": 1,
                "doc_id": "doc-1",
                "doc_name": "Contract.pdf",
                "page_num": 5,
                "page_end": 5,
                "char_start": 0,
                "char_end": 100,
                "chunk_id": "c1",
                "snippet": "First citation text...",
                "score": 0.95,
            },
            {
                "citation_index": 2,
                "doc_id": "doc-1",
                "doc_name": "Contract.pdf",
                "page_num": 10,
                "page_end": 10,
                "char_start": 200,
                "char_end": 300,
                "chunk_id": "c2",
                "snippet": "Second citation text...",
                "score": 0.88,
            },
        ])
        messages[1].evidence_json = json.dumps({
            "verdict": "VERIFIED",
            "evidence_grade": "A",
            "evidence_label": "Strong",
        })
        messages[1].refusal_code = None
        messages[1].created_at_utc = datetime.now(timezone.utc).isoformat()

        result = generate_docx_export(session, messages)

        assert isinstance(result, bytes)
        assert len(result) > 100

    def test_generate_docx_handles_empty_citations(self) -> None:
        """DOCX export handles messages without citations."""
        from app.services.export_service import generate_docx_export

        session = MagicMock(spec=QASession)
        session.session_id = "test-session"
        session.docs_snapshot_id = "snap_abc"
        session.created_at_utc = datetime.now(timezone.utc).isoformat()

        messages = [
            MagicMock(spec=QAMessage),
            MagicMock(spec=QAMessage),
        ]
        messages[0].role = "user"
        messages[0].content = "Simple question"
        messages[0].citations_json = None
        messages[0].evidence_json = None
        messages[0].refusal_code = None
        messages[0].created_at_utc = datetime.now(timezone.utc).isoformat()

        messages[1].role = "assistant"
        messages[1].content = "Simple answer"
        messages[1].citations_json = None
        messages[1].evidence_json = None
        messages[1].refusal_code = None
        messages[1].created_at_utc = datetime.now(timezone.utc).isoformat()

        result = generate_docx_export(session, messages)

        assert isinstance(result, bytes)
        assert len(result) > 0


class TestExportEndpoint:
    """Tests for export API endpoint."""

    def test_export_pdf_returns_file(self) -> None:
        """Export PDF endpoint returns file response."""
        from unittest.mock import patch, MagicMock
        from app.routers.export import export_session

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "test-session-123"
        mock_session.docs_snapshot_id = "snap_abc"
        mock_session.created_at_utc = datetime.now(timezone.utc).isoformat()

        mock_messages = [
            MagicMock(spec=QAMessage),
            MagicMock(spec=QAMessage),
        ]
        mock_messages[0].role = "user"
        mock_messages[0].content = "Question?"
        mock_messages[0].citations_json = None
        mock_messages[0].evidence_json = None
        mock_messages[0].refusal_code = None
        mock_messages[0].created_at_utc = datetime.now(timezone.utc).isoformat()

        mock_messages[1].role = "assistant"
        mock_messages[1].content = "Answer."
        mock_messages[1].citations_json = None
        mock_messages[1].evidence_json = None
        mock_messages[1].refusal_code = None
        mock_messages[1].created_at_utc = datetime.now(timezone.utc).isoformat()

        with patch("app.routers.export.get_qa_session", return_value=mock_session):
            with patch("app.routers.export.get_session_messages", return_value=mock_messages):
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(
                    export_session("test-session-123", "pdf")
                )

                assert result.media_type == "application/pdf"
                assert "qa-export-" in result.filename
                assert result.filename.endswith(".pdf")

    def test_export_docx_returns_file(self) -> None:
        """Export DOCX endpoint returns file response."""
        from unittest.mock import patch, MagicMock
        from app.routers.export import export_session

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "test-session-456"
        mock_session.docs_snapshot_id = "snap_def"
        mock_session.created_at_utc = datetime.now(timezone.utc).isoformat()

        mock_messages = [
            MagicMock(spec=QAMessage),
            MagicMock(spec=QAMessage),
        ]
        mock_messages[0].role = "user"
        mock_messages[0].content = "Question?"
        mock_messages[0].citations_json = None
        mock_messages[0].evidence_json = None
        mock_messages[0].refusal_code = None
        mock_messages[0].created_at_utc = datetime.now(timezone.utc).isoformat()

        mock_messages[1].role = "assistant"
        mock_messages[1].content = "Answer."
        mock_messages[1].citations_json = None
        mock_messages[1].evidence_json = None
        mock_messages[1].refusal_code = None
        mock_messages[1].created_at_utc = datetime.now(timezone.utc).isoformat()

        with patch("app.routers.export.get_qa_session", return_value=mock_session):
            with patch("app.routers.export.get_session_messages", return_value=mock_messages):
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(
                    export_session("test-session-456", "docx")
                )

                assert result.media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                assert "qa-export-" in result.filename
                assert result.filename.endswith(".docx")

    def test_export_invalid_session_returns_404(self) -> None:
        """Export with invalid session returns 404."""
        from unittest.mock import patch
        from app.routers.export import export_session
        from fastapi import HTTPException

        with patch("app.routers.export.get_qa_session", return_value=None):
            import asyncio
            with pytest.raises(HTTPException) as exc_info:
                asyncio.get_event_loop().run_until_complete(
                    export_session("nonexistent-session", "pdf")
                )
            assert exc_info.value.status_code == 404
            assert "Session not found" in str(exc_info.value.detail)

    def test_export_empty_session_returns_400(self) -> None:
        """Export session with no messages returns 400."""
        from unittest.mock import patch, MagicMock
        from app.routers.export import export_session
        from fastapi import HTTPException

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "empty-session"
        mock_session.docs_snapshot_id = "snap_abc"
        mock_session.created_at_utc = datetime.now(timezone.utc).isoformat()

        with patch("app.routers.export.get_qa_session", return_value=mock_session):
            with patch("app.routers.export.get_session_messages", return_value=[]):
                import asyncio
                with pytest.raises(HTTPException) as exc_info:
                    asyncio.get_event_loop().run_until_complete(
                        export_session("empty-session", "pdf")
                    )
                assert exc_info.value.status_code == 400
                assert "no messages" in str(exc_info.value.detail)
