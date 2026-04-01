# tests/test_qa_session.py
"""Tests for QA session storage (FR-032)."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

# Default tenant/matter IDs for tests
TEST_TENANT_ID = "tenant-1"
TEST_MATTER_ID = "matter-1"
TEST_USER_ID = "user-1"


class TestQASessionModel:
    """Tests for QASession database model."""

    def test_create_session_stores_in_db(self) -> None:
        """Creating a session stores it in the database."""
        from app.db import QASession, create_qa_session

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = create_qa_session(
                session_id="test-session-123",
                docs_snapshot_id="snap_abc",
                tenant_id=TEST_TENANT_ID,
                matter_id=TEST_MATTER_ID,
                user_id=TEST_USER_ID,
            )

            assert result.session_id == "test-session-123"
            assert result.docs_snapshot_id == "snap_abc"
            assert result.tenant_id == TEST_TENANT_ID
            assert result.user_id == TEST_USER_ID
            assert result.matter_id == TEST_MATTER_ID
            mock_session.add.assert_called_once()

    def test_get_session_returns_session(self) -> None:
        """Getting an existing session returns it."""
        from app.db import QASession, get_qa_session

        mock_session_obj = MagicMock(spec=QASession)
        mock_session_obj.session_id = "test-session-123"
        mock_session_obj.docs_snapshot_id = "snap_abc"

        with patch("app.db.session_scope") as mock_scope:
            mock_db_session = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)
            mock_db_session.scalars.return_value.first.return_value = mock_session_obj

            result = get_qa_session(
                "test-session-123",
                tenant_id=TEST_TENANT_ID,
                user_id=TEST_USER_ID,
                matter_id=TEST_MATTER_ID,
            )

            assert result is not None
            assert result.session_id == "test-session-123"

    def test_get_session_not_found_returns_none(self) -> None:
        """Getting a non-existent session returns None."""
        from app.db import get_qa_session

        with patch("app.db.session_scope") as mock_scope:
            mock_db_session = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)
            mock_db_session.scalars.return_value.first.return_value = None

            result = get_qa_session(
                "nonexistent",
                tenant_id=TEST_TENANT_ID,
                user_id=TEST_USER_ID,
                matter_id=TEST_MATTER_ID,
            )

            assert result is None


class TestQAMessageModel:
    """Tests for QAMessage database model."""

    def test_insert_message_stores_in_db(self) -> None:
        """Inserting a message stores it in the database."""
        from app.db import QAMessage, insert_qa_message

        message = QAMessage(
            message_id="msg-123",
            session_id="session-abc",
            tenant_id=TEST_TENANT_ID,
            matter_id=TEST_MATTER_ID,
            role="user",
            content="What are the payment terms?",
            citations_json=None,
            evidence_json=None,
            refusal_code=None,
            version_snapshot_json=None,
            created_at_utc="2026-01-21T12:00:00Z",
        )

        with patch("app.db.session_scope") as mock_scope:
            mock_db_session = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            insert_qa_message(message)

            mock_db_session.add.assert_called_once_with(message)

    def test_get_session_messages_returns_ordered(self) -> None:
        """Getting session messages returns them in order."""
        from app.db import QAMessage, get_session_messages

        mock_messages = [
            MagicMock(spec=QAMessage, message_id="msg-1", created_at_utc="2026-01-21T12:00:00Z"),
            MagicMock(spec=QAMessage, message_id="msg-2", created_at_utc="2026-01-21T12:01:00Z"),
        ]

        with patch("app.db.session_scope") as mock_scope:
            mock_db_session = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)
            mock_db_session.scalars.return_value.all.return_value = mock_messages

            result = get_session_messages(
                "session-abc",
                tenant_id=TEST_TENANT_ID,
                matter_id=TEST_MATTER_ID,
            )

            assert len(result) == 2
            assert result[0].message_id == "msg-1"
            assert result[1].message_id == "msg-2"

    def test_message_stores_citations_json(self) -> None:
        """Message can store citations as JSON."""
        import json

        from app.db import QAMessage

        citations_data = [
            {"citation_index": 1, "doc_name": "contract.pdf", "page_num": 5},
            {"citation_index": 2, "doc_name": "contract.pdf", "page_num": 7},
        ]

        message = QAMessage(
            message_id="msg-123",
            session_id="session-abc",
            tenant_id=TEST_TENANT_ID,
            matter_id=TEST_MATTER_ID,
            role="assistant",
            content="The payment terms are...",
            citations_json=json.dumps(citations_data),
            evidence_json=None,
            refusal_code=None,
            version_snapshot_json=None,
            created_at_utc="2026-01-21T12:00:00Z",
        )

        assert message.citations_json is not None
        parsed = json.loads(message.citations_json)
        assert len(parsed) == 2
        assert parsed[0]["doc_name"] == "contract.pdf"

    def test_message_stores_evidence_json(self) -> None:
        """Message can store evidence support as JSON."""
        import json

        from app.db import QAMessage

        evidence_data = {
            "verdict": "VERIFIED",
            "evidence_grade": "A",
            "evidence_label": "Strong",
            "support_count": 2,
        }

        message = QAMessage(
            message_id="msg-123",
            session_id="session-abc",
            tenant_id=TEST_TENANT_ID,
            matter_id=TEST_MATTER_ID,
            role="assistant",
            content="The payment terms are...",
            citations_json=None,
            evidence_json=json.dumps(evidence_data),
            refusal_code=None,
            version_snapshot_json=None,
            created_at_utc="2026-01-21T12:00:00Z",
        )

        assert message.evidence_json is not None
        parsed = json.loads(message.evidence_json)
        assert parsed["verdict"] == "VERIFIED"
        assert parsed["evidence_grade"] == "A"


class TestGetOrCreateSession:
    """Tests for get_or_create_session function."""

    def test_get_or_create_returns_existing(self) -> None:
        """Returns existing session if found."""
        from app.db import QASession, get_or_create_session

        mock_session = MagicMock(spec=QASession)
        mock_session.session_id = "existing-session"

        with patch("app.db.get_qa_session", return_value=mock_session):
            result = get_or_create_session(
                "existing-session",
                "snap_abc",
                tenant_id=TEST_TENANT_ID,
                matter_id=TEST_MATTER_ID,
                user_id=TEST_USER_ID,
            )

            assert result.session_id == "existing-session"

    def test_get_or_create_creates_new(self) -> None:
        """Creates new session if not found."""
        from app.db import QASession, get_or_create_session

        with patch("app.db.get_qa_session", return_value=None):
            with patch("app.db.create_qa_session") as mock_create:
                mock_new = MagicMock(spec=QASession)
                mock_new.session_id = "new-session"
                mock_create.return_value = mock_new

                result = get_or_create_session(
                    "new-session",
                    "snap_abc",
                    tenant_id=TEST_TENANT_ID,
                    matter_id=TEST_MATTER_ID,
                    user_id=TEST_USER_ID,
                )

                assert result.session_id == "new-session"
                mock_create.assert_called_once()

    def test_get_or_create_handles_race_condition(self) -> None:
        """Handles race condition when two requests try to create same session."""
        from app.db import get_or_create_session
        from sqlalchemy.exc import IntegrityError

        # Simulate race: get returns None, but create fails due to duplicate
        with patch("app.db.get_qa_session", side_effect=[None, MagicMock(session_id="race-session")]):
            with patch("app.db.create_qa_session", side_effect=IntegrityError("", {}, Exception())):
                # Should recover by fetching the existing session
                result = get_or_create_session(
                    "race-session",
                    "snap_abc",
                    tenant_id=TEST_TENANT_ID,
                    matter_id=TEST_MATTER_ID,
                    user_id=TEST_USER_ID,
                )
                assert result.session_id == "race-session"
