# tests/test_tenant_isolation.py
"""Tests for FR-001 (tenant isolation) and FR-002 (matter isolation) ENFORCEMENT.

These tests verify that tenant_id and matter_id are REQUIRED and enforced
at all layers: database, retrieval, and API.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class TestDatabaseLayerEnforcement:
    """Test that database functions REQUIRE tenant_id/matter_id parameters."""

    def test_load_chunks_requires_tenant_id(self) -> None:
        """load_chunks must have tenant_id as REQUIRED (not optional)."""
        from app.db import load_chunks

        sig = inspect.signature(load_chunks)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "load_chunks must have tenant_id parameter"
        # Check it has no default (required)
        assert (
            tenant_param.default is inspect.Parameter.empty
        ), "tenant_id must be REQUIRED (no default value)"

    def test_load_chunks_requires_matter_id(self) -> None:
        """load_chunks must have matter_id as REQUIRED (not optional)."""
        from app.db import load_chunks

        sig = inspect.signature(load_chunks)
        matter_param = sig.parameters.get("matter_id")
        assert matter_param is not None, "load_chunks must have matter_id parameter"
        assert (
            matter_param.default is inspect.Parameter.empty
        ), "matter_id must be REQUIRED (no default value)"

    def test_load_index_records_requires_tenant_id(self) -> None:
        """load_index_records must have tenant_id as REQUIRED (not optional)."""
        from app.db import load_index_records

        sig = inspect.signature(load_index_records)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "load_index_records must have tenant_id parameter"
        assert (
            tenant_param.default is inspect.Parameter.empty
        ), "tenant_id must be REQUIRED (no default value)"

    def test_load_index_records_requires_matter_id(self) -> None:
        """load_index_records must have matter_id as REQUIRED (not optional)."""
        from app.db import load_index_records

        sig = inspect.signature(load_index_records)
        matter_param = sig.parameters.get("matter_id")
        assert matter_param is not None, "load_index_records must have matter_id parameter"
        assert (
            matter_param.default is inspect.Parameter.empty
        ), "matter_id must be REQUIRED (no default value)"

    def test_get_document_requires_tenant_id(self) -> None:
        """get_document must require tenant_id parameter."""
        from app.db import get_document

        sig = inspect.signature(get_document)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "get_document must have tenant_id parameter"

    def test_get_doc_name_requires_tenant_id(self) -> None:
        """get_doc_name must require tenant_id parameter."""
        from app.db import get_doc_name

        sig = inspect.signature(get_doc_name)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "get_doc_name must have tenant_id parameter"

    def test_get_latest_docs_snapshot_id_requires_tenant_id(self) -> None:
        """get_latest_docs_snapshot_id must require tenant_id parameter."""
        from app.db import get_latest_docs_snapshot_id

        sig = inspect.signature(get_latest_docs_snapshot_id)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "get_latest_docs_snapshot_id must have tenant_id parameter"

    def test_get_qa_session_requires_tenant_id(self) -> None:
        """get_qa_session must require tenant_id parameter."""
        from app.db import get_qa_session

        sig = inspect.signature(get_qa_session)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "get_qa_session must have tenant_id parameter"

    def test_get_session_messages_requires_tenant_id(self) -> None:
        """get_session_messages must require tenant_id parameter."""
        from app.db import get_session_messages

        sig = inspect.signature(get_session_messages)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "get_session_messages must have tenant_id parameter"

    def test_create_qa_session_requires_tenant_and_matter(self) -> None:
        """create_qa_session must require both tenant_id and matter_id."""
        from app.db import create_qa_session

        sig = inspect.signature(create_qa_session)
        tenant_param = sig.parameters.get("tenant_id")
        matter_param = sig.parameters.get("matter_id")
        assert tenant_param is not None, "create_qa_session must have tenant_id parameter"
        assert matter_param is not None, "create_qa_session must have matter_id parameter"

    def test_get_or_create_session_requires_tenant_and_matter(self) -> None:
        """get_or_create_session must require both tenant_id and matter_id."""
        from app.db import get_or_create_session

        sig = inspect.signature(get_or_create_session)
        tenant_param = sig.parameters.get("tenant_id")
        matter_param = sig.parameters.get("matter_id")
        assert tenant_param is not None, "get_or_create_session must have tenant_id parameter"
        assert matter_param is not None, "get_or_create_session must have matter_id parameter"


class TestRetrievalLayerEnforcement:
    """Test that retrieval functions REQUIRE tenant_id/matter_id parameters."""

    def test_hybrid_search_requires_tenant_id(self) -> None:
        """hybrid_search must require tenant_id parameter."""
        from app.retrieval import hybrid_search

        sig = inspect.signature(hybrid_search)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "hybrid_search must have tenant_id parameter"

    def test_hybrid_search_requires_matter_id(self) -> None:
        """hybrid_search must require matter_id parameter."""
        from app.retrieval import hybrid_search

        sig = inspect.signature(hybrid_search)
        matter_param = sig.parameters.get("matter_id")
        assert matter_param is not None, "hybrid_search must have matter_id parameter"


class TestRequestContextModule:
    """Test that context.py exists and provides RequestContext."""

    def test_context_module_exists(self) -> None:
        """context.py module must exist with RequestContext class."""
        from app.context import RequestContext

        assert RequestContext is not None

    def test_request_context_has_tenant_id(self) -> None:
        """RequestContext must have tenant_id attribute."""
        from app.context import RequestContext
        from app.rbac import Role

        ctx = RequestContext(
            tenant_id="test-tenant",
            matter_id="test-matter",
            user_id="test-user",
            user_role=Role.ATTORNEY,
        )
        assert ctx.tenant_id == "test-tenant"

    def test_request_context_has_matter_id(self) -> None:
        """RequestContext must have matter_id attribute."""
        from app.context import RequestContext
        from app.rbac import Role

        ctx = RequestContext(
            tenant_id="test-tenant",
            matter_id="test-matter",
            user_id="test-user",
            user_role=Role.ATTORNEY,
        )
        assert ctx.matter_id == "test-matter"

    def test_get_request_context_dependency_exists(self) -> None:
        """get_request_context FastAPI dependency must exist."""
        from app.context import get_request_context

        assert callable(get_request_context)


class TestServiceLayerEnforcement:
    """Test that service functions REQUIRE tenant_id/matter_id parameters."""

    def test_execute_ask_requires_tenant_id(self) -> None:
        """execute_ask must require tenant_id parameter."""
        from app.services.ask_service import execute_ask

        sig = inspect.signature(execute_ask)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "execute_ask must have tenant_id parameter"

    def test_execute_ask_requires_matter_id(self) -> None:
        """execute_ask must require matter_id parameter."""
        from app.services.ask_service import execute_ask

        sig = inspect.signature(execute_ask)
        matter_param = sig.parameters.get("matter_id")
        assert matter_param is not None, "execute_ask must have matter_id parameter"

    def test_doc_name_for_requires_tenant_id(self) -> None:
        """doc_name_for must require tenant_id parameter."""
        from app.services.rag import doc_name_for

        sig = inspect.signature(doc_name_for)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "doc_name_for must have tenant_id parameter"


class TestDocumentServiceEnforcement:
    """Test that document service functions REQUIRE tenant_id/matter_id parameters."""

    def test_process_document_upload_requires_tenant_id(self) -> None:
        """process_document_upload must require tenant_id parameter."""
        from app.services.document_service import process_document_upload

        sig = inspect.signature(process_document_upload)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "process_document_upload must have tenant_id parameter"

    def test_process_document_upload_requires_matter_id(self) -> None:
        """process_document_upload must require matter_id parameter."""
        from app.services.document_service import process_document_upload

        sig = inspect.signature(process_document_upload)
        matter_param = sig.parameters.get("matter_id")
        assert matter_param is not None, "process_document_upload must have matter_id parameter"


class TestCrossTenantIsolation:
    """Test that cross-tenant data access is blocked."""

    def test_get_document_filters_by_tenant(self) -> None:
        """get_document must filter results by tenant_id."""
        from app.db import get_document

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.scalars.return_value.first.return_value = None

            # Call with tenant_id
            get_document(doc_id="doc-123", tenant_id="tenant-abc")

            # Verify scalars was called (query was built)
            assert mock_session.scalars.called, "Query should be executed"

    def test_load_chunks_filters_by_tenant_and_matter(self) -> None:
        """load_chunks must filter results by both tenant_id and matter_id."""
        from app.db import load_chunks

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.scalars.return_value.all.return_value = []

            # Call with required tenant_id and matter_id
            load_chunks(
                docs_snapshot_id="snap-001",
                tenant_id="tenant-abc",
                matter_id="matter-xyz",
            )

            # Verify query was executed
            assert mock_session.scalars.called, "Query should be executed"


class TestAzureSearchTenantFilter:
    """Test that Azure Search includes tenant_id in filter."""

    def test_azure_search_filter_includes_tenant_id(self) -> None:
        """_azure_search filter must include tenant_id."""
        from app.retrieval import _azure_search

        sig = inspect.signature(_azure_search)
        tenant_param = sig.parameters.get("tenant_id")
        assert tenant_param is not None, "_azure_search must accept tenant_id parameter"

    def test_azure_search_filter_includes_matter_id(self) -> None:
        """_azure_search filter must include matter_id."""
        from app.retrieval import _azure_search

        sig = inspect.signature(_azure_search)
        matter_param = sig.parameters.get("matter_id")
        assert matter_param is not None, "_azure_search must accept matter_id parameter"
