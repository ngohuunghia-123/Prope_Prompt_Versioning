"""Pytest fixtures for prope-agent tests."""
from __future__ import annotations

import pytest

from prope_agent.providers import MockProvider


@pytest.fixture
def provider() -> MockProvider:
    return MockProvider()
