"""Tests for /api/admin endpoints — role enforcement and happy paths."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.auth import Role, UserIdentity
from app.services.auth import get_current_user
from tests.conftest import _TEST_USER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _override_user(user: UserIdentity) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def _restore_it_admin() -> None:
    app.dependency_overrides[get_current_user] = lambda: _TEST_USER


# ---------------------------------------------------------------------------
# Role-enforcement tests
# ---------------------------------------------------------------------------

class TestAdminRoleEnforcement:
    """All /admin routes require it-admin; any lesser role → 403."""

    @pytest.fixture(autouse=True)
    def _restore(self) -> None:
        yield  # type: ignore[misc]
        _restore_it_admin()

    def test_regular_user_cannot_get_audit_log(self, client: TestClient) -> None:
        _override_user(UserIdentity("u", "u@t.com", "U", roles=(Role.user,)))
        assert client.get("/api/admin/audit-log").status_code == 403

    def test_reviewer_cannot_get_audit_log(self, client: TestClient) -> None:
        _override_user(UserIdentity("r", "r@t.com", "R", roles=(Role.reviewer,)))
        assert client.get("/api/admin/audit-log").status_code == 403

    def test_brand_admin_cannot_get_audit_log(self, client: TestClient) -> None:
        _override_user(UserIdentity("b", "b@t.com", "B", roles=(Role.brand_admin,)))
        assert client.get("/api/admin/audit-log").status_code == 403

    def test_regular_user_cannot_purge(self, client: TestClient) -> None:
        _override_user(UserIdentity("u", "u@t.com", "U", roles=(Role.user,)))
        assert client.post("/api/admin/purge").status_code == 403

    def test_regular_user_cannot_force_delete(self, client: TestClient) -> None:
        _override_user(UserIdentity("u", "u@t.com", "U", roles=(Role.user,)))
        assert client.delete("/api/admin/jobs/some-job-id").status_code == 403


# ---------------------------------------------------------------------------
# Happy-path tests (IT-admin, provided by conftest override)
# ---------------------------------------------------------------------------

class TestAdminHappyPath:
    def test_audit_log_returns_200_list(self, client: TestClient) -> None:
        resp = client.get("/api/admin/audit-log")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_audit_log_respects_n_param(self, client: TestClient) -> None:
        resp = client.get("/api/admin/audit-log?n=5")
        assert resp.status_code == 200

    def test_purge_returns_200_with_result_keys(self, client: TestClient) -> None:
        resp = client.post("/api/admin/purge")
        assert resp.status_code == 200
        body = resp.json()
        assert "purged" in body
        assert "errors" in body

    def test_force_delete_unknown_job_returns_404(self, client: TestClient) -> None:
        resp = client.delete("/api/admin/jobs/nonexistent-job-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Asset route role enforcement
# ---------------------------------------------------------------------------

class TestAssetRoleEnforcement:
    """POST /api/assets and PATCH /api/assets/{id} require brand-admin or it-admin."""

    @pytest.fixture(autouse=True)
    def _restore(self) -> None:
        yield  # type: ignore[misc]
        _restore_it_admin()

    def test_regular_user_cannot_create_asset(self, client: TestClient) -> None:
        _override_user(UserIdentity("u", "u@t.com", "U", roles=(Role.user,)))
        import io
        resp = client.post(
            "/api/assets",
            files={"file": ("icon.svg", io.BytesIO(b"<svg/>"), "image/svg+xml")},
            data={"name": "test-icon", "type": "icon", "slot": "content"},
        )
        assert resp.status_code == 403

    def test_reviewer_cannot_create_asset(self, client: TestClient) -> None:
        _override_user(UserIdentity("r", "r@t.com", "R", roles=(Role.reviewer,)))
        import io
        resp = client.post(
            "/api/assets",
            files={"file": ("icon.svg", io.BytesIO(b"<svg/>"), "image/svg+xml")},
            data={"name": "test-icon", "type": "icon", "slot": "content"},
        )
        assert resp.status_code == 403

    def test_brand_admin_can_create_asset(self, client: TestClient) -> None:
        _override_user(UserIdentity("ba", "ba@t.com", "BA", roles=(Role.brand_admin,)))
        import io
        resp = client.post(
            "/api/assets",
            files={"file": ("icon.svg", io.BytesIO(b"<svg/>"), "image/svg+xml")},
            data={"name": "test-icon", "type": "icon", "slot": "content"},
        )
        assert resp.status_code == 201
