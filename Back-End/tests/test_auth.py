"""Tests for app.services.auth — OIDC validator and FastAPI dependencies."""

from __future__ import annotations

import time
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.main import app
from app.models.auth import Role, UserIdentity
from app.services.auth import OIDCValidator, get_current_user, require_roles


# ---------------------------------------------------------------------------
# Helpers — generate an RSA key pair and build tokens for tests
# ---------------------------------------------------------------------------

def _make_keypair() -> tuple[Any, Any]:
    """Return (private_key, public_key) for test token signing."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _make_token(
    private_key: Any,
    kid: str = "test-kid",
    iss: str = "https://example.com",
    aud: str = "test-aud",
    roles: list[str] | None = None,
    exp_offset: int = 3600,
) -> str:
    payload: dict[str, Any] = {
        "iss": iss,
        "aud": aud,
        "sub": "user-sub-123",
        "oid": "user-oid-456",
        "preferred_username": "tester@imocha.io",
        "name": "Test Tester",
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
    }
    if roles is not None:
        payload["roles"] = roles
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


def _patch_validator(validator: OIDCValidator, kid: str, public_key: Any) -> None:
    """Inject a test public key into the validator, bypassing JWKS fetch."""
    validator._keys = {kid: public_key}  # type: ignore[attr-defined]
    validator._fetched_at = time.monotonic() + 9999  # prevent refresh


# ---------------------------------------------------------------------------
# OIDCValidator unit tests
# ---------------------------------------------------------------------------

class TestOIDCValidatorHappyPath:
    def test_valid_token_returns_user_identity(self) -> None:
        private_key, public_key = _make_keypair()
        validator = OIDCValidator("https://example.com", "test-aud")
        _patch_validator(validator, "test-kid", public_key)

        token = _make_token(private_key, roles=["it-admin", "reviewer"])
        identity = validator.validate(token)

        assert identity.user_id == "user-oid-456"
        assert identity.email == "tester@imocha.io"
        assert identity.name == "Test Tester"
        assert Role.it_admin in identity.roles
        assert Role.reviewer in identity.roles

    def test_empty_roles_claim_gives_no_roles(self) -> None:
        private_key, public_key = _make_keypair()
        validator = OIDCValidator("https://example.com", "test-aud")
        _patch_validator(validator, "test-kid", public_key)

        token = _make_token(private_key, roles=[])
        identity = validator.validate(token)
        assert identity.roles == ()

    def test_unknown_role_string_is_ignored(self) -> None:
        private_key, public_key = _make_keypair()
        validator = OIDCValidator("https://example.com", "test-aud")
        _patch_validator(validator, "test-kid", public_key)

        token = _make_token(private_key, roles=["user", "ghost-role"])
        identity = validator.validate(token)
        assert Role.user in identity.roles
        assert len(identity.roles) == 1  # "ghost-role" dropped


class TestOIDCValidatorErrors:
    def test_malformed_token_raises_value_error(self) -> None:
        validator = OIDCValidator("https://example.com", "test-aud")
        with pytest.raises(ValueError, match="Malformed"):
            validator.validate("not.a.jwt")

    def test_expired_token_raises_value_error(self) -> None:
        private_key, public_key = _make_keypair()
        validator = OIDCValidator("https://example.com", "test-aud")
        _patch_validator(validator, "test-kid", public_key)

        token = _make_token(private_key, exp_offset=-1)  # already expired
        with pytest.raises(ValueError, match="expired"):
            validator.validate(token)

    def test_unknown_kid_raises_value_error(self) -> None:
        private_key, _ = _make_keypair()
        _, other_public = _make_keypair()
        validator = OIDCValidator("https://example.com", "test-aud")
        _patch_validator(validator, "other-kid", other_public)  # different kid

        token = _make_token(private_key, kid="test-kid")
        with pytest.raises(ValueError, match="Unknown signing key"):
            validator.validate(token)

    def test_wrong_audience_raises_value_error(self) -> None:
        private_key, public_key = _make_keypair()
        validator = OIDCValidator("https://example.com", "expected-aud")
        _patch_validator(validator, "test-kid", public_key)

        token = _make_token(private_key, aud="wrong-aud")
        with pytest.raises(ValueError, match="Invalid token"):
            validator.validate(token)


# ---------------------------------------------------------------------------
# UserIdentity.has_role tests
# ---------------------------------------------------------------------------

class TestUserIdentityHasRole:
    def test_user_has_exact_role(self) -> None:
        u = UserIdentity("id", "e@e.com", "N", roles=(Role.reviewer,))
        assert u.has_role(Role.reviewer)

    def test_user_lacks_role(self) -> None:
        u = UserIdentity("id", "e@e.com", "N", roles=(Role.user,))
        assert not u.has_role(Role.it_admin)

    def test_has_role_any_of_multiple(self) -> None:
        u = UserIdentity("id", "e@e.com", "N", roles=(Role.brand_admin,))
        assert u.has_role(Role.it_admin, Role.brand_admin)

    def test_no_roles_always_false(self) -> None:
        u = UserIdentity("id", "e@e.com", "N")
        assert not u.has_role(Role.user)


# ---------------------------------------------------------------------------
# require_roles dependency — tested via a live route
# ---------------------------------------------------------------------------

class TestRequireRoles:
    """Test RBAC enforcement via a real protected route (GET /api/admin/audit-log)."""

    def test_it_admin_can_access(self, client: TestClient) -> None:
        # The conftest overrides get_current_user with IT-admin — should be 200.
        resp = client.get("/api/admin/audit-log")
        assert resp.status_code == 200

    def test_regular_user_gets_403(self, client: TestClient) -> None:
        regular = UserIdentity("u1", "u@t.com", "U", roles=(Role.user,))
        app.dependency_overrides[get_current_user] = lambda: regular
        try:
            resp = client.get("/api/admin/audit-log")
            assert resp.status_code == 403
        finally:
            # Restore IT-admin override from conftest
            from tests.conftest import _TEST_USER
            app.dependency_overrides[get_current_user] = lambda: _TEST_USER

    def test_reviewer_gets_403_on_admin_route(self, client: TestClient) -> None:
        reviewer = UserIdentity("u2", "r@t.com", "R", roles=(Role.reviewer,))
        app.dependency_overrides[get_current_user] = lambda: reviewer
        try:
            resp = client.get("/api/admin/audit-log")
            assert resp.status_code == 403
        finally:
            from tests.conftest import _TEST_USER
            app.dependency_overrides[get_current_user] = lambda: _TEST_USER


# ---------------------------------------------------------------------------
# get_current_user — missing / malformed Authorization header
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    """Test the auth dependency behaviour when the override is removed."""

    def test_missing_auth_header_returns_401(self) -> None:
        # Remove the global override so real auth runs.
        app.dependency_overrides.pop(get_current_user, None)
        try:
            c = TestClient(app, raise_server_exceptions=False)
            resp = c.get("/api/jobs")
            assert resp.status_code == 401
        finally:
            from tests.conftest import _TEST_USER
            app.dependency_overrides[get_current_user] = lambda: _TEST_USER

    def test_malformed_auth_scheme_returns_401(self) -> None:
        app.dependency_overrides.pop(get_current_user, None)
        try:
            c = TestClient(app, raise_server_exceptions=False)
            resp = c.get("/api/jobs", headers={"Authorization": "Basic abc123"})
            assert resp.status_code == 401
        finally:
            from tests.conftest import _TEST_USER
            app.dependency_overrides[get_current_user] = lambda: _TEST_USER
