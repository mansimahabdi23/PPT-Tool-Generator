"""Asset library router — GET /api/assets, POST, PATCH.

Backed by the seeded InMemoryAssetStore (or PostgresAssetStore in production).
All retrieval goes through the deterministic filter + vector rank pipeline.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Form, Query, UploadFile

from app.models.asset import BrandAsset, BrandAssetUpdate
from app.models.enums import AssetSlot, AssetStatus, AssetType
from app.services.asset_store import AssetRecord, get_store

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[BrandAsset])
async def list_assets(
    type: AssetType | None = Query(default=None),  # noqa: A002
    status: AssetStatus | None = Query(default=None),
) -> list[BrandAsset]:
    """Return the full asset library, optionally filtered by type or status."""
    return get_store().list_all(type_filter=type, status_filter=status)


@router.post("", response_model=BrandAsset, status_code=201)
async def create_asset(
    file: UploadFile,
    name: str = Form(),
    type: AssetType = Form(),  # noqa: A002
    slot: AssetSlot = Form(),
    version: str = Form(default="v1.0"),
    owner: str = Form(default="Design"),
    tags: str = Form(default=""),
    thumbnail_url: str = Form(default=""),
) -> BrandAsset:
    """Upload a new brand asset and register it in the library.

    The asset file is accepted and discarded for now (storage is a Step 5+
    concern — S3 / blob storage). The metadata is indexed immediately.
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    record = AssetRecord.build(
        asset_id=str(uuid.uuid4()),
        name=name,
        type=type,
        slot=slot,
        status=AssetStatus.approved,
        version=version,
        owner=owner,
        tags=tag_list,
        thumbnail_url=thumbnail_url,
    )
    get_store().put(record)
    return BrandAsset(
        id=record.id,
        name=record.name,
        type=record.type,
        slot=record.slot,
        status=record.status,
        version=record.version,
        owner=record.owner,
        expires_at=record.expires_at,
        tags=record.tags,
        thumbnail_url=record.thumbnail_url,
    )


@router.patch("/{asset_id}", response_model=BrandAsset)
async def update_asset(asset_id: str, body: BrandAssetUpdate) -> BrandAsset:
    """Partial update of a brand asset (name, status, tags, version, etc.)."""
    store = get_store()
    try:
        updated = store.update(asset_id, body)
    except KeyError:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Asset {asset_id!r} not found")
    return BrandAsset(
        id=updated.id,
        name=updated.name,
        type=updated.type,
        slot=updated.slot,
        status=updated.status,
        version=updated.version,
        owner=updated.owner,
        expires_at=updated.expires_at,
        tags=updated.tags,
        thumbnail_url=updated.thumbnail_url,
    )
