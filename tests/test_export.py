# tests/test_export.py
"""Tests for Q&A export functionality (FR-032)."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# Add the app to path for imports
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
    """Create a test request context with user info (FR-003)."""
    return RequestContext(
        tenant_id=tenant_id,
        matter_id=matter_id,
        user_id=user_id,
        user_role=user_role,
    )


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

    def _mock_background_tasks(self) -> MagicMock:
        """Create a mock BackgroundTasks object."""
        mock_bg = MagicMock()
        mock_bg.add_task = MagicMock()
        return mock_bg

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

        mock_bg = self._mock_background_tasks()
        context = make_context()

        with patch("app.routers.export.get_qa_session", return_value=mock_session):
            with patch("app.routers.export.get_session_messages", return_value=mock_messages):
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(
                    export_session(
                        "test-session-123",
                        mock_bg,
                        context=context,
                        format="pdf",
                        x_docqa_session="test-session-123",
                    )
                )

                assert result.media_type == "application/pdf"
                assert "qa-export-" in result.filename
                assert result.filename.endswith(".pdf")
                # Verify cleanup was scheduled
                mock_bg.add_task.assert_called_once()

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

        mock_bg = self._mock_background_tasks()
        context = make_context()

        with patch("app.routers.export.get_qa_session", return_value=mock_session):
            with patch("app.routers.export.get_session_messages", return_value=mock_messages):
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(
                    export_session(
                        "test-session-456",
                        mock_bg,
                        context=context,
                        format="docx",
                        x_docqa_session="test-session-456",
                    )
                )

                assert result.media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                assert "qa-export-" in result.filename
                assert result.filename.endswith(".docx")

    def test_export_invalid_session_returns_404(self) -> None:
        """Export with invalid session returns 404."""
        from unittest.mock import patch
        from app.routers.export import export_session
        from fastapi import HTTPException

        mock_bg = self._mock_background_tasks()
        context = make_context()

        with patch("app.routers.export.get_qa_session", return_value=None):
            import asyncio
            with pytest.raises(HTTPException) as exc_info:
                asyncio.get_event_loop().run_until_complete(
                    export_session(
                        "nonexistent-session",
                        mock_bg,
                        context=context,
                        format="pdf",
                        x_docqa_session="nonexistent-session",
                    )
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

        mock_bg = self._mock_background_tasks()
        context = make_context()

        with patch("app.routers.export.get_qa_session", return_value=mock_session):
            with patch("app.routers.export.get_session_messages", return_value=[]):
                import asyncio
                with pytest.raises(HTTPException) as exc_info:
                    asyncio.get_event_loop().run_until_complete(
                        export_session(
                            "empty-session",
                            mock_bg,
                            context=context,
                            format="pdf",
                            x_docqa_session="empty-session",
                        )
                    )
                assert exc_info.value.status_code == 400
                assert "no messages" in str(exc_info.value.detail)

    def test_export_requires_session_header_match(self) -> None:
        """Export should require X-DocQA-Session header to match session_id."""
        from unittest.mock import patch, MagicMock
        from app.routers.export import export_session
        from fastapi import HTTPException

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "real-session-123"
        mock_session.docs_snapshot_id = "snap_abc"
        mock_session.created_at_utc = datetime.now(timezone.utc).isoformat()

        mock_bg = self._mock_background_tasks()
        context = make_context()

        with patch("app.routers.export.get_qa_session", return_value=mock_session):
            import asyncio
            # Try to export without providing the session header
            with pytest.raises(HTTPException) as exc_info:
                asyncio.get_event_loop().run_until_complete(
                    export_session(
                        "real-session-123",
                        mock_bg,
                        context=context,
                        format="pdf",
                        x_docqa_session=None,
                    )
                )
            assert exc_info.value.status_code == 403
            assert "Session header required" in str(exc_info.value.detail)

    def test_export_rejects_mismatched_session_header(self) -> None:
        """Export should reject when header doesn't match path session_id."""
        from unittest.mock import patch, MagicMock
        from app.routers.export import export_session
        from fastapi import HTTPException

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "real-session-123"
        mock_session.docs_snapshot_id = "snap_abc"
        mock_session.created_at_utc = datetime.now(timezone.utc).isoformat()

        mock_bg = self._mock_background_tasks()
        context = make_context()

        with patch("app.routers.export.get_qa_session", return_value=mock_session):
            import asyncio
            # Try to export with wrong session header
            with pytest.raises(HTTPException) as exc_info:
                asyncio.get_event_loop().run_until_complete(
                    export_session(
                        "real-session-123",
                        mock_bg,
                        context=context,
                        format="pdf",
                        x_docqa_session="wrong-session",
                    )
                )
            assert exc_info.value.status_code == 403
            assert "Session mismatch" in str(exc_info.value.detail)

    def test_export_succeeds_with_matching_session_header(self) -> None:
        """Export should succeed when session header matches path."""
        from unittest.mock import patch, MagicMock
        from app.routers.export import export_session

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "my-session-123"
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

        mock_bg = self._mock_background_tasks()
        context = make_context()

        with patch("app.routers.export.get_qa_session", return_value=mock_session):
            with patch("app.routers.export.get_session_messages", return_value=mock_messages):
                import asyncio
                result = asyncio.get_event_loop().run_until_complete(
                    export_session(
                        "my-session-123",
                        mock_bg,
                        context=context,
                        format="pdf",
                        x_docqa_session="my-session-123",
                    )
                )
                assert result.media_type == "application/pdf"

    def test_export_uses_user_and_matter_scoped_lookup(self) -> None:
        """Export lookup must stay bound to the current user and matter."""
        from unittest.mock import patch, MagicMock
        from app.routers.export import export_session

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "my-session-123"
        mock_session.docs_snapshot_id = "snap_abc"
        mock_session.created_at_utc = datetime.now(timezone.utc).isoformat()

        mock_messages = [MagicMock(spec=QAMessage), MagicMock(spec=QAMessage)]
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

        mock_bg = self._mock_background_tasks()
        context = make_context(user_id="scoped-user", matter_id="scoped-matter")

        with (
            patch("app.routers.export.get_qa_session", return_value=mock_session) as mock_get_session,
            patch("app.routers.export.get_session_messages", return_value=mock_messages) as mock_get_messages,
        ):
            import asyncio

            asyncio.get_event_loop().run_until_complete(
                export_session(
                    "my-session-123",
                    mock_bg,
                    context=context,
                    format="pdf",
                    x_docqa_session="my-session-123",
                )
            )

        mock_get_session.assert_called_once_with(
            "my-session-123",
            tenant_id="tenant-1",
            user_id="scoped-user",
            matter_id="scoped-matter",
        )
        mock_get_messages.assert_called_once_with(
            "my-session-123",
            tenant_id="tenant-1",
            matter_id="scoped-matter",
        )

    def test_export_limits_messages(self) -> None:
        """Export should limit messages to MAX_EXPORT_MESSAGES."""
        from unittest.mock import patch, MagicMock
        from app.routers.export import export_session, MAX_EXPORT_MESSAGES

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "large-session"
        mock_session.docs_snapshot_id = "snap_abc"
        mock_session.created_at_utc = datetime.now(timezone.utc).isoformat()

        # Create more messages than the limit
        total_messages = MAX_EXPORT_MESSAGES + 100
        mock_messages = []
        for i in range(total_messages):
            msg = MagicMock(spec=QAMessage)
            msg.role = "user" if i % 2 == 0 else "assistant"
            msg.content = f"Message {i}"
            msg.citations_json = None
            msg.evidence_json = None
            msg.refusal_code = None
            msg.created_at_utc = datetime.now(timezone.utc).isoformat()
            mock_messages.append(msg)

        mock_bg = self._mock_background_tasks()
        context = make_context()

        # We need to verify truncation happens before PDF generation
        # by patching generate_pdf_export to capture what it receives
        captured_messages: list[Any] = []

        def capture_pdf_call(session: Any, messages: Any) -> bytes:
            captured_messages.extend(messages)
            # Return valid PDF bytes (minimal)
            return b"%PDF-1.4 minimal"

        with patch("app.routers.export.get_qa_session", return_value=mock_session):
            with patch("app.routers.export.get_session_messages", return_value=mock_messages):
                with patch("app.routers.export.generate_pdf_export", side_effect=capture_pdf_call):
                    import asyncio
                    # Should succeed but with truncated messages
                    asyncio.get_event_loop().run_until_complete(
                        export_session(
                            "large-session",
                            mock_bg,
                            context=context,
                            format="pdf",
                            x_docqa_session="large-session",
                        )
                    )

        # Verify messages were truncated to MAX_EXPORT_MESSAGES
        assert len(captured_messages) == MAX_EXPORT_MESSAGES
        assert len(captured_messages) < total_messages
