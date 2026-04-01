"""Startup security checks."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))


def test_startup_rejects_header_auth_in_production() -> None:
    """Header-based auth must not start in production."""
    from app.main import startup_event

    with (
        patch("app.main.AUTH_MODE", "headers"),
        patch("app.main.IS_PRODUCTION", True),
        patch("app.main.otel.setup_langfuse"),
        patch("app.main.init_db"),
        patch("app.main.ensure_index"),
        patch("app.main.os.makedirs"),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            startup_event()

    assert "AUTH_MODE=headers" in str(exc_info.value)
