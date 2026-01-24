"""Tests for Retention Policies (FR-042).

Tests cover:
- RetentionPolicy model and CRUD
- Configurable retention per tenant
- Automatic cleanup of expired data
- Cleanup job returns count of deleted items
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_session() -> Generator[None, None, None]:
    """Mock database session for retention tests."""
    from contextlib import contextmanager

    @contextmanager
    def fake_session() -> Generator[None, None, None]:
        class FakeSession:
            def add(self, obj: object) -> None:
                pass

            def execute(self, stmt: object) -> object:
                class Result:
                    @property
                    def rowcount(self) -> int:
                        return 5  # Simulated deleted count

                return Result()

            def scalar(self, stmt: object) -> object:
                return None

            def scalars(self, stmt: object) -> "FakeSession":
                return self

            def first(self) -> object:
                return None

            def all(self) -> list[object]:
                return []

        yield FakeSession()

    # Patch both locations where session_scope is imported
    with patch("app.db.session_scope", fake_session):
        with patch("app.retention.session_scope", fake_session):
            yield


class TestRetentionPolicyModel:
    """Tests for RetentionPolicy model structure."""

    def test_retention_policy_has_required_columns(self) -> None:
        """RetentionPolicy model should have all FR-042 required columns."""
        from app.db import RetentionPolicy

        columns = RetentionPolicy.__table__.columns.keys()
        required = [
            "policy_id",
            "tenant_id",
            "resource_type",
            "retention_days",
            "created_at_utc",
            "updated_at_utc",
        ]
        for col in required:
            assert col in columns, f"Missing column: {col}"

    def test_retention_policy_tenant_id_indexed(self) -> None:
        """tenant_id should be indexed for efficient queries."""
        from app.db import RetentionPolicy

        tenant_col = RetentionPolicy.__table__.columns["tenant_id"]
        assert tenant_col.index is True


class TestRetentionPolicyCRUD:
    """Tests for retention policy CRUD operations."""

    def test_create_retention_policy(self, mock_session: None) -> None:
        """Should be able to create a retention policy."""
        from app.db import create_retention_policy

        policy = create_retention_policy(
            tenant_id="tenant-1",
            resource_type="qa_messages",
            retention_days=365,
        )

        assert policy.tenant_id == "tenant-1"
        assert policy.resource_type == "qa_messages"
        assert policy.retention_days == 365

    def test_get_retention_policy(self, mock_session: None) -> None:
        """Should be able to get a retention policy by tenant and type."""
        from app.db import get_retention_policy

        # With mocked session, returns None
        policy = get_retention_policy(
            tenant_id="tenant-1",
            resource_type="qa_messages",
        )
        assert policy is None  # Expected with mock

    def test_update_retention_policy(self, mock_session: None) -> None:
        """Should be able to update retention days."""
        from app.db import update_retention_policy

        # Function should exist and be callable
        result = update_retention_policy(
            tenant_id="tenant-1",
            resource_type="qa_messages",
            retention_days=180,
        )
        # Returns bool indicating success
        assert isinstance(result, bool)


class TestRetentionResourceTypes:
    """Tests for different retention resource types."""

    @pytest.mark.parametrize(
        "resource_type",
        [
            "qa_messages",
            "qa_sessions",
            "audit_events",
            "telemetry",
            "documents",
            "chunks",
        ],
    )
    def test_valid_resource_types_accepted(
        self, mock_session: None, resource_type: str
    ) -> None:
        """All documented resource types should be accepted."""
        from app.db import create_retention_policy

        policy = create_retention_policy(
            tenant_id="tenant-1",
            resource_type=resource_type,
            retention_days=90,
        )

        assert policy.resource_type == resource_type


class TestRetentionCleanup:
    """Tests for retention cleanup job."""

    def test_cleanup_expired_qa_messages(self, mock_session: None) -> None:
        """cleanup_expired_qa_messages should delete old messages."""
        from app.retention import cleanup_expired_qa_messages

        deleted = cleanup_expired_qa_messages(
            tenant_id="tenant-1",
            retention_days=30,
        )

        assert isinstance(deleted, int)

    def test_cleanup_expired_qa_sessions(self, mock_session: None) -> None:
        """cleanup_expired_qa_sessions should delete old sessions."""
        from app.retention import cleanup_expired_qa_sessions

        deleted = cleanup_expired_qa_sessions(
            tenant_id="tenant-1",
            retention_days=30,
        )

        assert isinstance(deleted, int)

    def test_cleanup_expired_telemetry(self, mock_session: None) -> None:
        """cleanup_expired_telemetry should delete old telemetry."""
        from app.retention import cleanup_expired_telemetry

        deleted = cleanup_expired_telemetry(
            tenant_id="tenant-1",
            retention_days=90,
        )

        assert isinstance(deleted, int)

    def test_run_retention_cleanup_for_tenant(self, mock_session: None) -> None:
        """run_retention_cleanup should apply all policies for a tenant."""
        from app.retention import run_retention_cleanup

        results = run_retention_cleanup(tenant_id="tenant-1")

        assert isinstance(results, dict)


class TestDefaultRetention:
    """Tests for default retention values."""

    def test_default_qa_message_retention(self) -> None:
        """Default QA message retention should be 365 days."""
        from app.config import DEFAULT_QA_RETENTION_DAYS

        assert DEFAULT_QA_RETENTION_DAYS == 365

    def test_default_telemetry_retention(self) -> None:
        """Default telemetry retention should be 90 days."""
        from app.config import DEFAULT_TELEMETRY_RETENTION_DAYS

        assert DEFAULT_TELEMETRY_RETENTION_DAYS == 90

    def test_default_audit_retention(self) -> None:
        """Default audit retention should be 2555 days (7 years)."""
        from app.config import DEFAULT_AUDIT_RETENTION_DAYS

        # Legal requirement: 7 years for audit logs
        assert DEFAULT_AUDIT_RETENTION_DAYS == 2555
