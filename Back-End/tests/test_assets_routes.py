"""Route tests for /api/assets endpoints."""

import io

from fastapi.testclient import TestClient

ASSET_KEYS = {"id", "name", "type", "slot", "status", "version", "owner", "tags", "thumbnailUrl"}


class TestListAssets:
    def test_returns_200_list(self, client: TestClient) -> None:
        response = client.get("/api/assets")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) > 0

    def test_assets_are_camel_case(self, client: TestClient) -> None:
        body = client.get("/api/assets").json()
        asset = body[0]
        assert ASSET_KEYS.issubset(asset.keys())

    def test_accepts_type_filter(self, client: TestClient) -> None:
        response = client.get("/api/assets?type=icon")
        assert response.status_code == 200

    def test_accepts_status_filter(self, client: TestClient) -> None:
        response = client.get("/api/assets?status=approved")
        assert response.status_code == 200

    def test_rejects_invalid_type(self, client: TestClient) -> None:
        response = client.get("/api/assets?type=notavalidtype")
        assert response.status_code == 422


class TestCreateAsset:
    def test_returns_201_brand_asset(self, client: TestClient) -> None:
        fake_file = io.BytesIO(b"fake image data")
        response = client.post(
            "/api/assets",
            files={"file": ("icon.png", fake_file, "image/png")},
            data={
                "name": "New Icon",
                "type": "icon",
                "slot": "content",
                "version": "v1.0",
                "owner": "Design",
                "tags": "new,test",
                "thumbnail_url": "https://placehold.co/240x160",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert ASSET_KEYS.issubset(body.keys())


class TestUpdateAsset:
    def test_returns_200_brand_asset(self, client: TestClient) -> None:
        response = client.patch(
            "/api/assets/a1",
            json={"name": "Updated Name", "version": "v4.0"},
        )
        assert response.status_code == 200
        body = response.json()
        assert ASSET_KEYS.issubset(body.keys())

    def test_empty_patch_is_valid(self, client: TestClient) -> None:
        response = client.patch("/api/assets/a1", json={})
        assert response.status_code == 200
