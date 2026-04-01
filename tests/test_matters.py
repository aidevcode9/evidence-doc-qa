"""Tests for Case Picker + Document Library endpoints.

Covers:
- GET /v1/matters — list matters for tenant with doc counts
- GET /v1/matters/{matter_id}/docs — list documents in a matter
- list_matters_for_tenant DB function
- list_documents_for_matter DB function
- get_latest_snapshot_for_matter DB function
- Tenant isolation on all queries
- Admin vs non-admin access
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


# --- DB Function Tests ---


class TestListMattersForTenant:
    """list_matters_for_tenant returns distinct matters with doc counts."""

    def test_returns_matters_with_doc_count(self) -> None:
        """Should return matters with doc_count and latest_snapshot_id."""
        from app.db import list_matters_for_tenant

        # Mock session to return test data
        mock_rows = [
            ("matter-a", 3, "2026-03-15T12:00:00Z", "snap_aaa111", None),
            ("matter-b", 1, "2026-03-14T12:00:00Z", "snap_bbb222", None),
        ]
        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.all.return_value = mock_rows
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = list_matters_for_tenant(
                tenant_id="t1", user_id="u1", user_role="admin"
            )

        assert len(result) == 2
        assert result[0]["matter_id"] == "matter-a"
        assert result[0]["doc_count"] == 3
        assert result[0]["latest_snapshot_id"] == "snap_aaa111"
        # Display name should be formatted from slug
        assert result[0]["display_name"] == "Matter A"

    def test_formats_slug_to_display_name(self) -> None:
        """Slug 'acme-v-widget-corp' becomes 'Acme V Widget Corp'."""
        from app.db import list_matters_for_tenant

        mock_rows = [
            ("acme-v-widget-corp", 2, "2026-03-15T12:00:00Z", "snap_xxx", None),
        ]
        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.all.return_value = mock_rows
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = list_matters_for_tenant(
                tenant_id="t1", user_id="u1", user_role="admin"
            )

        assert result[0]["display_name"] == "Acme V Widget Corp"

    def test_empty_tenant_returns_empty_list(self) -> None:
        """Tenant with no documents returns empty list."""
        from app.db import list_matters_for_tenant

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.all.return_value = []
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = list_matters_for_tenant(
                tenant_id="t1", user_id="u1", user_role="admin"
            )

        assert result == []


class TestListDocumentsForMatter:
    """list_documents_for_matter returns docs for a specific matter."""

    def test_returns_documents_for_matter(self) -> None:
        """Should return documents with expected fields."""
        from app.db import list_documents_for_matter

        mock_doc = MagicMock()
        mock_doc.doc_id = "d1"
        mock_doc.doc_name = "contract.pdf"
        mock_doc.status = "ready"
        mock_doc.ingested_at_utc = "2026-03-15T12:00:00Z"
        mock_doc.metadata_json = '{"page_count": 15}'
        mock_doc.docs_snapshot_id = "snap_aaa"

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_doc]
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = list_documents_for_matter(tenant_id="t1", matter_id="m1")

        assert len(result) == 1
        assert result[0].doc_id == "d1"
        assert result[0].doc_name == "contract.pdf"
        assert result[0].status == "ready"


class TestGetLatestSnapshotForMatter:
    """get_latest_snapshot_for_matter returns matter-scoped snapshot."""

    def test_returns_snapshot_for_correct_matter(self) -> None:
        """Should return snapshot scoped to the specific matter."""
        from app.db import get_latest_snapshot_for_matter

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.first.return_value = ("snap_abc123",)
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = get_latest_snapshot_for_matter(tenant_id="t1", matter_id="m1")

        assert result == "snap_abc123"

    def test_returns_none_when_no_docs(self) -> None:
        """Should return None when no documents exist for the matter."""
        from app.db import get_latest_snapshot_for_matter

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.first.return_value = None
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = get_latest_snapshot_for_matter(tenant_id="t1", matter_id="m1")

        assert result is None


# --- Endpoint Tests ---


class TestListMattersEndpoint:
    """GET /v1/matters returns matters list."""

    def test_list_matters_returns_200(self) -> None:
        """Endpoint returns 200 with matters list."""
        mock_matters = [
            {
                "matter_id": "demo-matter",
                "display_name": "Demo Matter",
                "doc_count": 2,
                "latest_snapshot_id": "snap_abc",
            },
        ]

        with (
            patch("app.routers.matters.list_matters_for_tenant", return_value=mock_matters),
            patch("app.routers.matters.has_permission", return_value=True),
        ):
            from app.routers.matters import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, headers={
                "X-Tenant-Id": "t1",
                "X-User-Id": "u1",
                "X-User-Role": "admin",
            })

            response = client.get("/v1/matters")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["matter_id"] == "demo-matter"
            assert data[0]["doc_count"] == 2


class TestListMatterDocsEndpoint:
    """GET /v1/matters/{matter_id}/docs returns document list."""

    def test_list_docs_returns_200(self) -> None:
        """Endpoint returns 200 with documents for the matter."""
        mock_doc = MagicMock()
        mock_doc.doc_id = "d1"
        mock_doc.doc_name = "contract.pdf"
        mock_doc.status = "ready"
        mock_doc.ingested_at_utc = "2026-03-15T12:00:00Z"
        mock_doc.metadata_json = '{"page_count": 10}'

        with (
            patch("app.routers.matters.list_documents_for_matter", return_value=[mock_doc]),
            patch("app.routers.matters.has_permission", return_value=True),
            patch("app.routers.matters.user_has_matter_access", return_value=True),
        ):
            from app.routers.matters import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, headers={
                "X-Tenant-Id": "t1",
                "X-User-Id": "u1",
                "X-User-Role": "admin",
            })

            response = client.get("/v1/matters/demo-matter/docs")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["doc_name"] == "contract.pdf"
            assert data[0]["page_count"] == 10

    def test_list_docs_no_access_returns_403(self) -> None:
        """User without matter access gets 403."""
        with (
            patch("app.routers.matters.has_permission", return_value=True),
            patch("app.routers.matters.user_has_matter_access", return_value=False),
        ):
            from app.routers.matters import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, headers={
                "X-Tenant-Id": "t1",
                "X-User-Id": "u1",
                "X-User-Role": "viewer",
            })

            response = client.get("/v1/matters/secret-matter/docs")
            assert response.status_code == 403


# --- Matter Naming Tests ---


class TestListMattersWithDisplayName:
    """list_matters_for_tenant uses display_name from matters table when available."""

    def test_uses_matters_table_display_name(self) -> None:
        """When matters table has a display_name, use it instead of slug."""
        from app.db import list_matters_for_tenant

        mock_rows = [
            ("smith-claim", 2, "2026-03-15T12:00:00Z", "snap_x", "Smith Insurance Claim"),
        ]
        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.all.return_value = mock_rows
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = list_matters_for_tenant(
                tenant_id="t1", user_id="u1", user_role="admin"
            )

        assert result[0]["display_name"] == "Smith Insurance Claim"

    def test_falls_back_to_slug_when_no_matter_row(self) -> None:
        """When matters table returns None, derive from slug."""
        from app.db import list_matters_for_tenant

        mock_rows = [
            ("old-matter", 1, "2026-03-15T12:00:00Z", "snap_y", None),
        ]
        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.all.return_value = mock_rows
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = list_matters_for_tenant(
                tenant_id="t1", user_id="u1", user_role="admin"
            )

        assert result[0]["display_name"] == "Old Matter"


class TestDisplayNameFromFilename:
    """_display_name_from_filename derives human-readable names."""

    def test_strips_extension_and_titlecases(self) -> None:
        from app.services.document_service import _display_name_from_filename

        assert _display_name_from_filename("Smith_Claim_2024.pdf") == "Smith Claim 2024"

    def test_handles_hyphens(self) -> None:
        from app.services.document_service import _display_name_from_filename

        assert _display_name_from_filename("medical-records-jan.pdf") == "Medical Records Jan"

    def test_handles_no_extension(self) -> None:
        from app.services.document_service import _display_name_from_filename

        assert _display_name_from_filename("report") == "Report"


class TestCreateMatterEndpoint:
    """POST /v1/matters creates a matter with user-provided display name."""

    def test_create_matter_returns_201(self) -> None:
        with (
            patch("app.routers.matters.has_permission", return_value=True),
            patch("app.routers.matters.ensure_matter_exists") as mock_ensure,
        ):
            from app.routers.matters import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, headers={
                "X-Tenant-Id": "t1",
                "X-User-Id": "u1",
                "X-User-Role": "admin",
            })

            response = client.post(
                "/v1/matters",
                json={"matter_id": "smith-v-jones", "display_name": "Smith v. Jones"},
            )
            assert response.status_code == 201
            assert response.json()["matter_id"] == "smith-v-jones"
            assert response.json()["display_name"] == "Smith v. Jones"
            mock_ensure.assert_called_once_with("smith-v-jones", "t1", "Smith v. Jones")

    def test_create_matter_invalid_id_returns_400(self) -> None:
        with (
            patch("app.routers.matters.has_permission", return_value=True),
        ):
            from app.routers.matters import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, headers={
                "X-Tenant-Id": "t1",
                "X-User-Id": "u1",
                "X-User-Role": "admin",
            })

            response = client.post(
                "/v1/matters",
                json={"matter_id": "'; DROP TABLE--", "display_name": "Bad"},
            )
            assert response.status_code == 400

    def test_create_matter_empty_name_returns_400(self) -> None:
        with (
            patch("app.routers.matters.has_permission", return_value=True),
        ):
            from app.routers.matters import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, headers={
                "X-Tenant-Id": "t1",
                "X-User-Id": "u1",
                "X-User-Role": "admin",
            })

            response = client.post(
                "/v1/matters",
                json={"matter_id": "valid-id", "display_name": "   "},
            )
            assert response.status_code == 400

    def test_ensure_matter_does_not_overwrite_existing_name(self) -> None:
        """After creating with user name, ensure_matter_exists should NOT overwrite."""
        from app.db import ensure_matter_exists, Matter

        mock_existing = Matter(
            matter_id="smith-v-jones",
            tenant_id="t1",
            display_name="Smith v. Jones",
            created_at_utc="2026-03-20T00:00:00Z",
        )

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.get.return_value = mock_existing  # Already exists
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            # Try to overwrite with filename-derived name
            ensure_matter_exists("smith-v-jones", "t1", "Contract Draft")

            # Should NOT have added a new matter (existing was found)
            mock_session.add.assert_not_called()


class TestRenameMatterEndpoint:
    """PUT /v1/matters/{matter_id}/name renames a matter."""

    def test_rename_returns_200(self) -> None:
        with (
            patch("app.routers.matters.has_permission", return_value=True),
            patch("app.routers.matters.user_has_matter_access", return_value=True),
            patch("app.routers.matters.update_matter_display_name", return_value=True),
        ):
            from app.routers.matters import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, headers={
                "X-Tenant-Id": "t1",
                "X-User-Id": "u1",
                "X-User-Role": "admin",
            })

            response = client.put(
                "/v1/matters/smith-case/name",
                json={"display_name": "Smith vs Acme Corp"},
            )
            assert response.status_code == 200
            assert response.json()["display_name"] == "Smith vs Acme Corp"

    def test_rename_not_found_returns_404(self) -> None:
        with (
            patch("app.routers.matters.has_permission", return_value=True),
            patch("app.routers.matters.user_has_matter_access", return_value=True),
            patch("app.routers.matters.update_matter_display_name", return_value=False),
        ):
            from app.routers.matters import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, headers={
                "X-Tenant-Id": "t1",
                "X-User-Id": "u1",
                "X-User-Role": "admin",
            })

            response = client.put(
                "/v1/matters/nonexistent/name",
                json={"display_name": "New Name"},
            )
            assert response.status_code == 404


# --- Last Question Activity Tests (FR-UI-001) ---


class TestGetMatterLastQuestions:
    """get_matter_last_questions returns last user message per matter."""

    def test_get_matter_last_questions_returns_data(self) -> None:
        """Should return last_question_at and last_question_preview for each matter."""
        from app.db import get_matter_last_questions

        mock_rows = [
            ("matter-a", "2026-03-15T14:30:00Z", "What is the contract term?"),
            ("matter-b", "2026-03-14T10:00:00Z", "Who signed this agreement?"),
        ]
        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.all.return_value = mock_rows
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = get_matter_last_questions(
                tenant_id="t1",
                matter_ids=["matter-a", "matter-b"],
            )

        assert result["matter-a"]["last_question_at"] == "2026-03-15T14:30:00Z"
        assert result["matter-a"]["last_question_preview"] == "What is the contract term?"
        assert result["matter-b"]["last_question_at"] == "2026-03-14T10:00:00Z"
        assert result["matter-b"]["last_question_preview"] == "Who signed this agreement?"

    def test_get_matter_last_questions_empty_list(self) -> None:
        """Empty matter_ids list returns empty dict without DB query."""
        from app.db import get_matter_last_questions

        result = get_matter_last_questions(tenant_id="t1", matter_ids=[])
        assert result == {}

    def test_get_matter_last_questions_no_messages(self) -> None:
        """Matters with no QAMessages return None values."""
        from app.db import get_matter_last_questions

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.all.return_value = []
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = get_matter_last_questions(
                tenant_id="t1",
                matter_ids=["matter-a", "matter-b"],
            )

        assert result["matter-a"]["last_question_at"] is None
        assert result["matter-a"]["last_question_preview"] is None
        assert result["matter-b"]["last_question_at"] is None
        assert result["matter-b"]["last_question_preview"] is None

    def test_get_matter_last_questions_truncates_to_80_chars(self) -> None:
        """Long message content is truncated to 80 characters."""
        from app.db import get_matter_last_questions

        long_msg = "A" * 120
        mock_rows = [
            ("matter-a", "2026-03-15T14:30:00Z", long_msg),
        ]
        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_session.execute.return_value.all.return_value = mock_rows
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)

            result = get_matter_last_questions(
                tenant_id="t1",
                matter_ids=["matter-a"],
            )

        preview = result["matter-a"]["last_question_preview"]
        assert preview is not None
        assert len(preview) == 80


class TestListMattersIncludesQuestionFields:
    """GET /v1/matters includes last_question_at and last_question_preview."""

    def test_list_matters_includes_question_fields(self) -> None:
        """Endpoint merges last question data into matters response."""
        mock_matters = [
            {
                "matter_id": "matter-a",
                "display_name": "Matter A",
                "doc_count": 2,
                "latest_snapshot_id": "snap_abc",
            },
            {
                "matter_id": "matter-b",
                "display_name": "Matter B",
                "doc_count": 1,
                "latest_snapshot_id": "snap_def",
            },
        ]
        mock_questions = {
            "matter-a": {
                "last_question_at": "2026-03-15T14:30:00Z",
                "last_question_preview": "What is the contract term?",
            },
            "matter-b": {
                "last_question_at": None,
                "last_question_preview": None,
            },
        }

        with (
            patch("app.routers.matters.list_matters_for_tenant", return_value=mock_matters),
            patch("app.routers.matters.get_matter_last_questions", return_value=mock_questions),
            patch("app.routers.matters.has_permission", return_value=True),
        ):
            from app.routers.matters import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, headers={
                "X-Tenant-Id": "t1",
                "X-User-Id": "u1",
                "X-User-Role": "admin",
            })

            response = client.get("/v1/matters")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

            # matter-a has question data
            assert data[0]["last_question_at"] == "2026-03-15T14:30:00Z"
            assert data[0]["last_question_preview"] == "What is the contract term?"

            # matter-b has null question data
            assert data[1]["last_question_at"] is None
            assert data[1]["last_question_preview"] is None
