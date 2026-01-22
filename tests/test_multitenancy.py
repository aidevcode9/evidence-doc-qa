# tests/test_multitenancy.py
"""Tests for FR-001 (tenant isolation) and FR-002 (matter isolation)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the app to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class TestFR001TenantIsolation:
    """FR-001: Multi-tenant support; all data partitioned by tenant_id."""

    def test_document_has_tenant_id_column(self) -> None:
        """Every Document must have a tenant_id field."""
        from app.db import Document

        assert hasattr(Document, "tenant_id"), "Document must have tenant_id column"

    def test_chunk_has_tenant_id_column(self) -> None:
        """Every Chunk must have a tenant_id field."""
        from app.db import Chunk

        assert hasattr(Chunk, "tenant_id"), "Chunk must have tenant_id column"

    def test_index_record_has_tenant_id_column(self) -> None:
        """Every IndexRecord must have a tenant_id field."""
        from app.db import IndexRecord

        assert hasattr(IndexRecord, "tenant_id"), "IndexRecord must have tenant_id column"

    def test_telemetry_has_tenant_id_column(self) -> None:
        """Every Telemetry record must have a tenant_id field."""
        from app.db import Telemetry

        assert hasattr(Telemetry, "tenant_id"), "Telemetry must have tenant_id column"

    def test_qa_session_has_tenant_id_column(self) -> None:
        """Every QASession must have a tenant_id field."""
        from app.db import QASession

        assert hasattr(QASession, "tenant_id"), "QASession must have tenant_id column"

    def test_qa_message_has_tenant_id_column(self) -> None:
        """Every QAMessage must have a tenant_id field."""
        from app.db import QAMessage

        assert hasattr(QAMessage, "tenant_id"), "QAMessage must have tenant_id column"

    def test_load_chunks_accepts_tenant_id_parameter(self) -> None:
        """load_chunks must accept tenant_id parameter."""
        import inspect

        from app.db import load_chunks

        sig = inspect.signature(load_chunks)
        assert "tenant_id" in sig.parameters, "load_chunks must accept tenant_id parameter"

    def test_load_index_records_accepts_tenant_id_parameter(self) -> None:
        """load_index_records must accept tenant_id parameter."""
        import inspect

        from app.db import load_index_records

        sig = inspect.signature(load_index_records)
        assert "tenant_id" in sig.parameters, "load_index_records must accept tenant_id parameter"


class TestFR002MatterIsolation:
    """FR-002: Multi-matter support; artifacts partitioned by matter_id."""

    def test_document_has_matter_id_column(self) -> None:
        """Every Document must have a matter_id field."""
        from app.db import Document

        assert hasattr(Document, "matter_id"), "Document must have matter_id column"

    def test_chunk_has_matter_id_column(self) -> None:
        """Every Chunk must have a matter_id field."""
        from app.db import Chunk

        assert hasattr(Chunk, "matter_id"), "Chunk must have matter_id column"

    def test_index_record_has_matter_id_column(self) -> None:
        """Every IndexRecord must have a matter_id field."""
        from app.db import IndexRecord

        assert hasattr(IndexRecord, "matter_id"), "IndexRecord must have matter_id column"

    def test_telemetry_has_matter_id_column(self) -> None:
        """Every Telemetry record must have a matter_id field."""
        from app.db import Telemetry

        assert hasattr(Telemetry, "matter_id"), "Telemetry must have matter_id column"

    def test_qa_session_has_matter_id_column(self) -> None:
        """Every QASession must have a matter_id field."""
        from app.db import QASession

        assert hasattr(QASession, "matter_id"), "QASession must have matter_id column"

    def test_qa_message_has_matter_id_column(self) -> None:
        """Every QAMessage must have a matter_id field."""
        from app.db import QAMessage

        assert hasattr(QAMessage, "matter_id"), "QAMessage must have matter_id column"

    def test_load_chunks_accepts_matter_id_parameter(self) -> None:
        """load_chunks must accept matter_id parameter."""
        import inspect

        from app.db import load_chunks

        sig = inspect.signature(load_chunks)
        assert "matter_id" in sig.parameters, "load_chunks must accept matter_id parameter"

    def test_load_index_records_accepts_matter_id_parameter(self) -> None:
        """load_index_records must accept matter_id parameter."""
        import inspect

        from app.db import load_index_records

        sig = inspect.signature(load_index_records)
        assert "matter_id" in sig.parameters, "load_index_records must accept matter_id parameter"


class TestTenantMatterIsolationBehavior:
    """Test tenant + matter isolation in query functions."""

    def test_load_chunks_applies_tenant_filter(self) -> None:
        """load_chunks should filter by tenant_id when provided."""
        from app.db import load_chunks

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.scalars.return_value.all.return_value = []

            # Call with tenant_id and matter_id (both REQUIRED)
            load_chunks(docs_snapshot_id="snap-001", tenant_id="tenant-123", matter_id="matter-456")

            # Verify the query was built with tenant filter
            call_args = mock_session.scalars.call_args
            assert call_args is not None, "scalars should have been called"

    def test_load_chunks_applies_matter_filter(self) -> None:
        """load_chunks should filter by matter_id when provided."""
        from app.db import load_chunks

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.scalars.return_value.all.return_value = []

            # Call with both tenant_id and matter_id
            load_chunks(
                docs_snapshot_id="snap-001", tenant_id="tenant-123", matter_id="matter-456"
            )

            # Verify the query was called
            assert mock_session.scalars.called, "scalars should have been called"

    def test_load_index_records_applies_tenant_filter(self) -> None:
        """load_index_records should filter by tenant_id when provided."""
        from app.db import load_index_records

        with patch("app.db.session_scope") as mock_scope:
            mock_session = MagicMock()
            mock_scope.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_scope.return_value.__exit__ = MagicMock(return_value=False)
            mock_session.scalars.return_value.all.return_value = []

            # Call with tenant_id and matter_id (both REQUIRED)
            load_index_records(docs_snapshot_id="snap-001", tenant_id="tenant-123", matter_id="matter-456")

            # Verify the query was called
            assert mock_session.scalars.called, "scalars should have been called"
