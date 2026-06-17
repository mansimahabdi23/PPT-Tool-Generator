"""Asset-related Pydantic models — mirrors BrandAsset in types.ts."""


from .base import CamelModel
from .enums import AssetSlot, AssetStatus, AssetType


class BrandAsset(CamelModel):
    """Mirrors ``interface BrandAsset`` in types.ts."""

    id: str
    name: str
    type: AssetType
    slot: AssetSlot
    status: AssetStatus
    version: str
    owner: str
    expires_at: str | None = None  # ISO-8601 string
    tags: list[str]
    thumbnail_url: str


class BrandAssetUpdate(CamelModel):
    """Partial update body for ``PATCH /api/assets/{id}``."""

    name: str | None = None
    type: AssetType | None = None
    slot: AssetSlot | None = None
    status: AssetStatus | None = None
    version: str | None = None
    owner: str | None = None
    expires_at: str | None = None
    tags: list[str] | None = None
    thumbnail_url: str | None = None
