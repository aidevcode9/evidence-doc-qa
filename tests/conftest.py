# tests/conftest.py
"""Pytest configuration for unit and integration tests."""

import pytest

# Configure pytest-asyncio to auto-detect async tests
pytest_plugins = ("pytest_asyncio",)


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as an async test"
    )
