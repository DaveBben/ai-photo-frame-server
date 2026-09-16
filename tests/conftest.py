"""Pytest fixtures for local_shazam tests."""

import os

import pytest
from hypothesis import settings as hypothesis_settings

hypothesis_settings.register_profile("dev", max_examples=20)
hypothesis_settings.register_profile("ci", max_examples=500, deadline=None)
hypothesis_settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


@pytest.fixture
def settings() -> dict[str, str]:
    """Return test settings."""
    return {"log_level": "DEBUG"}
