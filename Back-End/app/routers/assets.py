"""Stub router for all /assets endpoints (docs/architecture.md §8).

Every handler returns typed placeholder data from services/fixtures.py.
"""


from fastapi import APIRouter, Form, Query, UploadFile

from app.models.asset import BrandAsset, BrandAssetUpdate
from app.models.enums import AssetStatus, AssetType
from app.services import fixtures

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[BrandAsset])
async def list_assets(
    type: AssetType | None = Query(default=None),  # noqa: A002
    status: AssetStatus | None = Query(default=None),
) -> list[BrandAsset]:
    """GET /api/assets — Return the asset library.

    Stub: query params are accepted (and validated) but ignored.
    """
    return fixtures.STUB_ASSETS


@router.post("", response_model=BrandAsset, status_code=201)
async def create_asset(
    file: UploadFile,
    name: str = Form(),
    type: AssetType = Form(),  # noqa: A002
    slot: str = Form(),
    version: str = Form(),
    owner: str = Form(),
    tags: str = Form(default=""),
    thumbnail_url: str = Form(default=""),
) -> BrandAsset:
    """POST /api/assets — Upload a new brand asset.

    Stub: ignores the upload, returns the first fixture asset.
    """
    return fixtures.STUB_ASSETS[0]


@router.patch("/{asset_id}", response_model=BrandAsset)
async def update_asset(asset_id: str, body: BrandAssetUpdate) -> BrandAsset:
    """PATCH /api/assets/{id} — Partial update of a brand asset.

    Stub: ignores the body, returns the first fixture asset.
    """
    return fixtures.STUB_ASSETS[0]
