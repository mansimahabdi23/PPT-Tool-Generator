"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.auth import Role, UserIdentity
from app.services.auth import get_current_user
from app.services.llm_provider import StubProvider, init_provider

# ---------------------------------------------------------------------------
# Test identity injected into all routes via dependency override
# ---------------------------------------------------------------------------

_TEST_USER = UserIdentity(
    user_id="test-user-id",
    email="test@imocha.io",
    name="Test User",
    roles=(Role.it_admin,),
)


@pytest.fixture(scope="session", autouse=True)
def _auth_override() -> Generator[None, None, None]:
    """Override get_current_user globally so route tests don't need real JWTs.

    Tests that need to verify role-enforcement behaviour can temporarily
    replace this override with ``monkeypatch.setitem(app.dependency_overrides,
    get_current_user, lambda: <lower-role identity>)``.
    """
    app.dependency_overrides[get_current_user] = lambda: _TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# LLM provider default
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _default_provider() -> None:  # type: ignore[return]
    """Initialise the LLM provider singleton for the test session."""
    init_provider(StubProvider())


# ---------------------------------------------------------------------------
# Shared TestClient
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)
