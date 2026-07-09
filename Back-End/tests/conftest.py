"""Shared pytest fixtures."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_provider import StubProvider, init_provider


@pytest.fixture(scope="session", autouse=True)
def _default_provider() -> None:  # type: ignore[return]
    """Initialise the LLM provider singleton for the test session.

    Test modules that want a different provider can override with a
    module-scoped fixture that calls init_provider() with a mock.
    """
    init_provider(StubProvider())


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)
