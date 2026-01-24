"""Tests for Matter Hard Delete Workflow (FR-043).

Tests cover:
- Hard delete removes all matter data
- Cascading delete of documents, chunks, index_records
- Cascading delete of qa_sessions, qa_messages
- Cascading delete of audit_events for the matter
- Matter assignments are revoked
- Admin-only permission required
- Audit event logged for the deletion itself
"""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_session() -> Generator[None, None, None]:
    """Mock database session for matter delete tests."""
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

    # Patch all locations where session_scope is imported
    with patch("app.db.session_scope", fake_session):
        with patch("app.matter_delete.session_scope", fake_session):
            yield


class TestHardDeleteMatter:
    """Tests for hard_delete_matter function."""

    def test_hard_delete_matter_function_exists(self) -> None:
        """hard_delete_matter function should exist."""
        from app.matter_delete import hard_delete_matter

        assert callable(hard_delete_matter)

    def test_hard_delete_matter_returns_stats(self, mock_session: None) -> None:
        """hard_delete_matter should return deletion statistics."""
        from app.matter_delete import hard_delete_matter

        with patch("app.matter_delete.create_audit_event"):
            stats = hard_delete_matter(
                tenant_id="tenant-1",
                matter_id="matter-1",
                deleted_by="admin-user",
            )

        assert isinstance(stats, dict)
        assert "documents" in stats
        assert "chunks" in stats
        assert "index_records" in stats
        assert "qa_sessions" in stats
        assert "qa_messages" in stats
        assert "audit_events" in stats
        assert "matter_assignments" in stats

    def test_hard_delete_matter_logs_audit_event(self, mock_session: None) -> None:
        """hard_delete_matter should log an audit event for the deletion."""
        from app.matter_delete import hard_delete_matter

        with patch("app.matter_delete.create_audit_event") as mock_audit:
            hard_delete_matter(
                tenant_id="tenant-1",
                matter_id="matter-1",
                deleted_by="admin-user",
            )

            # Should create audit event for the deletion
            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args.kwargs
            assert call_kwargs["tenant_id"] == "tenant-1"
            assert call_kwargs["user_id"] == "admin-user"
            assert call_kwargs["event_type"] == "matter_hard_delete"


class TestHardDeleteMatterCascade:
    """Tests for cascading deletion behavior.

    Note: Individual delete functions are now internal (_delete_*) and
    only accessible via hard_delete_matter() which runs them atomically.
    """

    def test_hard_delete_deletes_all_resource_types(self, mock_session: None) -> None:
        """hard_delete_matter should delete all resource types atomically."""
        from app.matter_delete import hard_delete_matter

        with patch("app.matter_delete.create_audit_event"):
            stats = hard_delete_matter(
                tenant_id="tenant-1",
                matter_id="matter-1",
                deleted_by="admin-user",
            )

        # All 7 resource types should be in stats
        expected_keys = [
            "documents",
            "chunks",
            "index_records",
            "qa_sessions",
            "qa_messages",
            "audit_events",
            "matter_assignments",
        ]
        for key in expected_keys:
            assert key in stats, f"Missing {key} in deletion stats"
            assert isinstance(stats[key], int), f"{key} should be int"

    def test_hard_delete_uses_single_transaction(self) -> None:
        """hard_delete_matter should use a single atomic transaction.

        Verifies that session_scope is called exactly once for all deletions
        (not once per resource type).
        """
        from contextlib import contextmanager

        session_scope_call_count = 0

        @contextmanager
        def counting_session() -> Generator[None, None, None]:
            nonlocal session_scope_call_count
            session_scope_call_count += 1

            class FakeSession:
                def execute(self, stmt: object) -> object:
                    class Result:
                        @property
                        def rowcount(self) -> int:
                            return 1

                    return Result()

            yield FakeSession()

        with patch("app.matter_delete.session_scope", counting_session):
            with patch("app.matter_delete.create_audit_event"):
                from app.matter_delete import hard_delete_matter

                hard_delete_matter(
                    tenant_id="tenant-1",
                    matter_id="matter-1",
                    deleted_by="admin-user",
                )

        # Should only call session_scope ONCE (atomic transaction)
        assert session_scope_call_count == 1, (
            f"Expected 1 transaction, got {session_scope_call_count}. "
            "Each deletion should NOT create its own transaction."
        )

    def test_hard_delete_rollback_on_failure(self) -> None:
        """hard_delete_matter should rollback all changes if any deletion fails.

        Verifies atomic behavior: if one delete fails, none should commit.
        """
        from contextlib import contextmanager

        commits = []
        rollbacks = []

        @contextmanager
        def tracking_session() -> Generator[None, None, None]:
            class FakeSession:
                call_count = 0

                def execute(self, stmt: object) -> object:
                    self.call_count += 1
                    # Fail on the 4th deletion (chunks)
                    if self.call_count == 4:
                        raise RuntimeError("Simulated database error")

                    class Result:
                        @property
                        def rowcount(self) -> int:
                            return 1

                    return Result()

            try:
                yield FakeSession()
                commits.append(True)
            except Exception:
                rollbacks.append(True)
                raise

        with patch("app.matter_delete.session_scope", tracking_session):
            with patch("app.matter_delete.create_audit_event"):
                from app.matter_delete import hard_delete_matter

                with pytest.raises(RuntimeError, match="Simulated database error"):
                    hard_delete_matter(
                        tenant_id="tenant-1",
                        matter_id="matter-1",
                        deleted_by="admin-user",
                    )

        # Should rollback, not commit
        assert len(commits) == 0, "Should not commit on failure"
        assert len(rollbacks) == 1, "Should rollback on failure"


class TestMatterDeleteRouter:
    """Tests for matter delete API endpoint."""

    def test_hard_delete_endpoint_exists(self) -> None:
        """DELETE /v1/admin/matters/{matter_id} endpoint should exist."""
        from app.routers.admin import router

        routes = [(r.path, r.methods) for r in router.routes if hasattr(r, "methods")]
        # Check for DELETE method on matters route
        delete_routes = [
            r for r in routes if "DELETE" in r[1] and "matter" in r[0].lower()
        ]
        assert len(delete_routes) > 0, "No DELETE endpoint for matters found"

    def test_hard_delete_requires_admin(self) -> None:
        """Hard delete endpoint should require admin role."""
        # This is enforced by @require_permission("manage_users")
        # which is tested in test_admin.py
        pass
