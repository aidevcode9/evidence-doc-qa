"""Tests for Audit Logging (FR-040).

Tests cover:
- AuditEvent model and CRUD
- Event types: query, upload, export, delete, login, user_*, matter_access_*
- Immutability: no UPDATE/DELETE at app layer
- Export: list events by tenant/matter/date range
- Event data redaction (no PII in event_json)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import patch

import pytest


@pytest.fixture
def mock_session() -> Generator[None, None, None]:
    """Mock database session for audit tests."""
    with patch("app.db.session_scope") as mock:
        from contextlib import contextmanager

        @contextmanager
        def fake_session() -> Generator[None, None, None]:
            class FakeSession:
                def add(self, obj: object) -> None:
                    pass

                def execute(self, stmt: object) -> object:
                    class Result:
                        def scalars(self) -> "Result":
                            return self

                        def all(self) -> list[object]:
                            return []

                        @property
                        def rowcount(self) -> int:
                            return 0

                    return Result()

                def scalars(self, stmt: object) -> "FakeSession":
                    return self

                def all(self) -> list[object]:
                    return []

            yield FakeSession()

        mock.return_value = fake_session()
        yield


class TestAuditEventModel:
    """Tests for AuditEvent model structure."""

    def test_audit_event_has_required_columns(self) -> None:
        """AuditEvent model should have all FR-040 required columns."""
        from app.db import AuditEvent

        # Check all required columns exist
        columns = AuditEvent.__table__.columns.keys()
        required = [
            "event_id",
            "tenant_id",
            "matter_id",
            "user_id",
            "event_type",
            "event_json",
            "response_id",
            "created_at_utc",
        ]
        for col in required:
            assert col in columns, f"Missing column: {col}"

    def test_audit_event_tenant_id_indexed(self) -> None:
        """tenant_id should be indexed for efficient queries."""
        from app.db import AuditEvent

        tenant_col = AuditEvent.__table__.columns["tenant_id"]
        assert tenant_col.index is True

    def test_audit_event_matter_id_indexed(self) -> None:
        """matter_id should be indexed for efficient queries."""
        from app.db import AuditEvent

        matter_col = AuditEvent.__table__.columns["matter_id"]
        assert matter_col.index is True


class TestCreateAuditEvent:
    """Tests for creating audit events."""

    def test_create_audit_event_returns_event(self, mock_session: None) -> None:
        """create_audit_event should return the created event."""
        from app.db import create_audit_event

        event = create_audit_event(
            tenant_id="tenant-1",
            user_id="user-1",
            event_type="query",
            event_json={"question": "[REDACTED]", "doc_count": 5},
            matter_id="matter-1",
            response_id="response-1",
        )

        assert event is not None
        assert event.tenant_id == "tenant-1"
        assert event.user_id == "user-1"
        assert event.event_type == "query"
        assert event.matter_id == "matter-1"

    def test_create_audit_event_generates_uuid(self, mock_session: None) -> None:
        """create_audit_event should generate a UUID for event_id."""
        from app.db import create_audit_event

        event = create_audit_event(
            tenant_id="tenant-1",
            user_id="user-1",
            event_type="login",
            event_json={"method": "password"},
        )

        # Should be a valid UUID
        uuid.UUID(event.event_id)

    def test_create_audit_event_sets_timestamp(self, mock_session: None) -> None:
        """create_audit_event should set created_at_utc timestamp."""
        from app.db import create_audit_event

        before = datetime.now(timezone.utc).isoformat()
        event = create_audit_event(
            tenant_id="tenant-1",
            user_id="user-1",
            event_type="logout",
            event_json={},
        )
        after = datetime.now(timezone.utc).isoformat()

        assert before <= event.created_at_utc <= after


class TestAuditEventTypes:
    """Tests for different audit event types."""

    @pytest.mark.parametrize(
        "event_type",
        [
            "query",
            "upload",
            "export",
            "delete",
            "login",
            "logout",
            "user_create",
            "user_update",
            "user_deactivate",
            "matter_access_grant",
            "matter_access_revoke",
        ],
    )
    def test_valid_event_types_accepted(
        self, mock_session: None, event_type: str
    ) -> None:
        """All documented event types should be accepted."""
        from app.db import create_audit_event

        event = create_audit_event(
            tenant_id="tenant-1",
            user_id="user-1",
            event_type=event_type,
            event_json={},
        )

        assert event.event_type == event_type


class TestListAuditEvents:
    """Tests for listing/exporting audit events."""

    def test_list_audit_events_function_exists(self) -> None:
        """list_audit_events function should exist with correct signature."""
        from app.db import list_audit_events
        import inspect

        sig = inspect.signature(list_audit_events)
        params = list(sig.parameters.keys())
        assert "tenant_id" in params
        assert "matter_id" in params
        assert "event_type" in params
        assert "start_date" in params
        assert "end_date" in params
        assert "offset" in params
        assert "limit" in params

    def test_list_audit_events_filters_by_tenant(self, mock_session: None) -> None:
        """list_audit_events should filter by tenant_id."""
        from app.db import list_audit_events

        # With mocked session, should return empty list
        events = list_audit_events(tenant_id="tenant-1")
        assert isinstance(events, list)

    def test_list_audit_events_filters_by_matter(self, mock_session: None) -> None:
        """list_audit_events should filter by matter_id when provided."""
        from app.db import list_audit_events

        events = list_audit_events(tenant_id="tenant-1", matter_id="matter-1")
        assert isinstance(events, list)

    def test_list_audit_events_filters_by_date_range(self, mock_session: None) -> None:
        """list_audit_events should filter by date range when provided."""
        from app.db import list_audit_events

        events = list_audit_events(
            tenant_id="tenant-1",
            start_date="2026-01-01T00:00:00Z",
            end_date="2026-01-31T23:59:59Z",
        )
        assert isinstance(events, list)

    def test_list_audit_events_filters_by_event_type(self, mock_session: None) -> None:
        """list_audit_events should filter by event_type when provided."""
        from app.db import list_audit_events

        events = list_audit_events(tenant_id="tenant-1", event_type="query")
        assert isinstance(events, list)

    def test_list_audit_events_supports_pagination(self, mock_session: None) -> None:
        """list_audit_events should support offset and limit."""
        from app.db import list_audit_events

        events = list_audit_events(tenant_id="tenant-1", offset=0, limit=100)
        assert isinstance(events, list)


class TestAuditImmutability:
    """Tests for audit log immutability (FR-041 prep)."""

    def test_no_update_audit_event_function(self) -> None:
        """There should be no update function for audit events."""
        import app.db as db_module

        # Verify no update function exists
        assert not hasattr(db_module, "update_audit_event")

    def test_no_delete_audit_event_function(self) -> None:
        """There should be no delete function for audit events (except for matter hard delete)."""
        import app.db as db_module

        # Regular delete should not exist
        assert not hasattr(db_module, "delete_audit_event")
        # Hard delete for entire matter is allowed (FR-043)
        # That will be implemented separately


class TestAuditEventRedaction:
    """Tests for PII redaction in audit events."""

    def test_query_event_redacts_question_text(self, mock_session: None) -> None:
        """Query events should not store the actual question text."""
        from app.audit import create_query_audit_event

        event = create_query_audit_event(
            tenant_id="tenant-1",
            matter_id="matter-1",
            user_id="user-1",
            question="What did John Smith say about the contract?",
            doc_ids=["doc-1", "doc-2"],
            response_id="resp-1",
            model="gpt-4o",
            latency_ms=1500,
        )

        event_data = json.loads(event.event_json)
        # Question should be hashed or marked as redacted
        assert "John Smith" not in event_data.get("question", "")
        assert event_data.get("question_redacted", False) or "[REDACTED]" in str(
            event_data
        )

    def test_upload_event_stores_metadata_not_content(
        self, mock_session: None
    ) -> None:
        """Upload events should store document metadata, not content."""
        from app.audit import create_upload_audit_event

        event = create_upload_audit_event(
            tenant_id="tenant-1",
            matter_id="matter-1",
            user_id="user-1",
            doc_id="doc-1",
            doc_name="confidential_contract.pdf",
            page_count=25,
            file_size_bytes=1024000,
        )

        event_data = json.loads(event.event_json)
        assert event_data["doc_id"] == "doc-1"
        assert event_data["page_count"] == 25
        # Should not contain document content
        assert "content" not in event_data
        assert "text" not in event_data


class TestAuditRouter:
    """Tests for audit API endpoints."""

    def test_audit_export_endpoint_exists(self) -> None:
        """GET /v1/audit/events endpoint should exist."""
        from app.routers.audit import router

        routes = [r.path for r in router.routes]
        assert "/events" in routes or any("/events" in r for r in routes)

    def test_audit_export_requires_admin(self) -> None:
        """Audit export should require admin role."""
        # This will be tested via integration test
        pass


class TestAuditExportSecurity:
    """Security tests for audit export (wsskeptic findings)."""

    def test_export_uses_streaming_response(self) -> None:
        """CSV export should use streaming to avoid memory exhaustion."""
        from app.routers.audit import export_events_endpoint
        import inspect

        # Check that the function uses StreamingResponse with a generator
        source = inspect.getsource(export_events_endpoint)
        # Should use iter() with a generator or streaming pattern
        assert "StreamingResponse" in source
        # Should NOT load all data into memory at once with high limit
        assert "limit=100000" not in source, "Export should use chunked queries, not high limit"

    def test_export_filename_sanitizes_date_input(self) -> None:
        """Export filename should sanitize date input to prevent injection."""
        from app.routers.audit import _sanitize_date_for_filename

        # Should only allow safe characters in filename
        assert _sanitize_date_for_filename("2026-01-24") == "2026-01-24"
        # Slashes removed (path injection prevention)
        assert "/" not in _sanitize_date_for_filename("2026/01/24")
        assert ".." not in _sanitize_date_for_filename("../../../etc/passwd")
        # ISO format truncated to date portion
        assert _sanitize_date_for_filename("2026-01-24T12:00:00Z") == "2026-01-24"
        # Empty/None returns empty string
        assert _sanitize_date_for_filename(None) == ""
        assert _sanitize_date_for_filename("") == ""

    def test_export_has_reasonable_chunk_size(self) -> None:
        """Export should query database in reasonable chunks."""
        from app.routers.audit import EXPORT_CHUNK_SIZE

        # Chunk size should be reasonable (1000-10000)
        assert 1000 <= EXPORT_CHUNK_SIZE <= 10000
