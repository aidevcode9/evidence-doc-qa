"""Security tests for path traversal, OData injection, and file confinement.

Covers:
- Vuln 1: Path traversal in save_raw_pdf filename sanitization
- Vuln 2: Directory confinement in view_doc endpoint
- Vuln 3: OData filter injection via docs_snapshot_id
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


class TestFilenamePathTraversal:
    """Vuln 1: save_raw_pdf must reject or sanitize path traversal in filenames."""

    def test_save_raw_pdf_strips_directory_traversal(self, tmp_path: Path) -> None:
        """Filename with ../ must not write outside RAW_DIR."""
        from unittest.mock import patch

        raw_dir = str(tmp_path / "raw")
        os.makedirs(raw_dir, exist_ok=True)

        with patch("app.ingestion.RAW_DIR", raw_dir), \
             patch("app.ingestion.AZURE_STORAGE_CONNECTION_STRING", ""):
            from app.ingestion import save_raw_pdf

            result_path = save_raw_pdf("abc123", "../../evil.pdf", b"data")

            # The file must be inside raw_dir, not above it
            resolved = os.path.realpath(result_path)
            assert resolved.startswith(os.path.realpath(raw_dir)), \
                f"File written outside RAW_DIR: {resolved}"

    def test_save_raw_pdf_strips_absolute_path(self, tmp_path: Path) -> None:
        """Filename with absolute path must not escape RAW_DIR."""
        from unittest.mock import patch

        raw_dir = str(tmp_path / "raw")
        os.makedirs(raw_dir, exist_ok=True)

        with patch("app.ingestion.RAW_DIR", raw_dir), \
             patch("app.ingestion.AZURE_STORAGE_CONNECTION_STRING", ""):
            from app.ingestion import save_raw_pdf

            result_path = save_raw_pdf("abc123", "/etc/passwd", b"data")

            resolved = os.path.realpath(result_path)
            assert resolved.startswith(os.path.realpath(raw_dir)), \
                f"File written outside RAW_DIR: {resolved}"

    def test_save_raw_pdf_strips_backslash_traversal(self, tmp_path: Path) -> None:
        """Filename with backslash traversal (Windows) must not escape RAW_DIR."""
        from unittest.mock import patch

        raw_dir = str(tmp_path / "raw")
        os.makedirs(raw_dir, exist_ok=True)

        with patch("app.ingestion.RAW_DIR", raw_dir), \
             patch("app.ingestion.AZURE_STORAGE_CONNECTION_STRING", ""):
            from app.ingestion import save_raw_pdf

            result_path = save_raw_pdf("abc123", "..\\..\\evil.pdf", b"data")

            resolved = os.path.realpath(result_path)
            assert resolved.startswith(os.path.realpath(raw_dir)), \
                f"File written outside RAW_DIR: {resolved}"

    def test_save_raw_pdf_normal_filename_works(self, tmp_path: Path) -> None:
        """Normal filenames must still work correctly."""
        from unittest.mock import patch

        raw_dir = str(tmp_path / "raw")
        os.makedirs(raw_dir, exist_ok=True)

        with patch("app.ingestion.RAW_DIR", raw_dir), \
             patch("app.ingestion.AZURE_STORAGE_CONNECTION_STRING", ""):
            from app.ingestion import save_raw_pdf

            result_path = save_raw_pdf("abc123", "my document.pdf", b"data")

            resolved = os.path.realpath(result_path)
            assert resolved.startswith(os.path.realpath(raw_dir))
            assert os.path.exists(result_path)
            assert "my_document.pdf" in os.path.basename(result_path)


class TestViewDocConfinement:
    """Vuln 2: view_doc must validate storage_path is within RAW_DIR."""

    def test_view_doc_rejects_path_outside_raw_dir(self, tmp_path: Path) -> None:
        """If storage_path points outside RAW_DIR, endpoint must return 403."""
        from unittest.mock import patch, MagicMock
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        # Create a file outside the expected directory
        outside_file = tmp_path / "secret.txt"
        outside_file.write_text("sensitive data")

        mock_doc = MagicMock()
        mock_doc.doc_id = "doc-1"
        mock_doc.doc_name = "secret.txt"
        mock_doc.storage_path = str(outside_file)

        with patch("app.routers.docs.get_document", return_value=mock_doc), \
             patch("app.routers.docs.has_permission", return_value=True), \
             patch("app.config.RAW_DIR", str(tmp_path / "raw")):
            from app.routers.docs import router

            app = FastAPI()
            app.include_router(router)
            client = TestClient(app, headers={
                "X-Tenant-Id": "t1",
                "X-Matter-Id": "m1",
                "X-User-Id": "u1",
                "X-User-Role": "admin",
            })

            response = client.get("/v1/docs/doc-1/view")
            assert response.status_code == 403, \
                f"Expected 403 for path outside RAW_DIR, got {response.status_code}"


class TestODataFilterInjection:
    """Vuln 3: docs_snapshot_id must be validated before OData filter interpolation."""

    def test_ask_request_rejects_odata_injection_in_snapshot_id(self) -> None:
        """docs_snapshot_id with OData injection chars must be rejected."""
        from app.schemas import AskRequest

        # This should raise a validation error — single quotes break OData filters
        with pytest.raises(Exception):  # ValidationError
            AskRequest(
                question="test",
                docs_snapshot_id="' or tenant_id eq 'evil-tenant",
            )

    def test_ask_request_accepts_valid_snapshot_id(self) -> None:
        """Normal snapshot IDs must be accepted."""
        from app.schemas import AskRequest

        req = AskRequest(question="test", docs_snapshot_id="snap_abc123def456")
        assert req.docs_snapshot_id == "snap_abc123def456"

    def test_ask_request_accepts_none_snapshot_id(self) -> None:
        """None snapshot ID must be accepted."""
        from app.schemas import AskRequest

        req = AskRequest(question="test")
        assert req.docs_snapshot_id is None

    def test_ask_request_rejects_parentheses_in_snapshot_id(self) -> None:
        """Parentheses in docs_snapshot_id must be rejected (OData injection)."""
        from app.schemas import AskRequest

        with pytest.raises(Exception):
            AskRequest(
                question="test",
                docs_snapshot_id="snap') or (tenant_id eq 'x",
            )
