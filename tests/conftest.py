"""Pytest fixtures for local_shazam tests."""

import pytest


@pytest.fixture
def settings() -> dict[str, str]:
    """Return test settings."""
    return {"log_level": "DEBUG"}
