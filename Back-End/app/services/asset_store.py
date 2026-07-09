"""In-memory asset store with deterministic filter + vector rank retrieval.

Architecture (docs §9)
----------------------
Retrieval = deterministic filter (approved + correct slot + fits item-count)
THEN vector rank on the survivors. Only approved assets are ever indexed,
so "approved-only" is a structural guarantee, not a runtime check that
could be bypassed.

This implementation stores records in-memory (seeded from disk on startup).
`asset_store_pg.py` provides the production PostgreSQL + pgvector backend
with the identical interface — swap by changing `get_store()`.

Public API
----------
AssetRecord      — full internal record (includes retrieval metadata)
InMemoryAssetStore
get_store()      — returns the module-level singleton
init_store(s)    — replaces the singleton (used in lifespan + tests)
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass, replace
from typing import Any

from app.models.asset import BrandAsset, BrandAssetUpdate
from app.models.enums import AssetSlot, AssetStatus, AssetType

# ---------------------------------------------------------------------------
# Embedding — hash-trick bag-of-words, 64 dims, deterministic, no ML deps
#
# Produces fixed-dimension vectors suitable for cosine similarity and for
# the vector(64) column in the PostgreSQL schema. Swap for a real embedding
# model (e.g. Azure OpenAI text-embedding-3-small) when the LLM provider is
# wired in Step 5.
# ---------------------------------------------------------------------------

EMBED_DIM = 64


def _embed(text: str, dim: int = EMBED_DIM) -> list[float]:
    """Hash-trick bag-of-words embedding at fixed dimension.

    Deterministic across platforms (uses MD5, not Python's hash()).
    """
    words = re.findall(r"\w+", text.lower())
    vec = [0.0] * dim
    for word in words:
        idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm > 0 else vec


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b) if norm_a > 0 and norm_b > 0 else 0.0


# ---------------------------------------------------------------------------
# AssetRecord — internal representation (superset of BrandAsset)
# ---------------------------------------------------------------------------

@dataclass
class AssetRecord:
    """Full internal asset record, including retrieval metadata.

    Fields beyond BrandAsset (not exposed in API responses):
      max_items   — maximum content items the infographic supports (None = any)
      width_emu   — safe render width in EMU (None = not constrained)
      height_emu  — safe render height in EMU (None = not constrained)
      embedding   — fixed-dim vector for cosine ranking
    """

    id: str
    name: str
    type: AssetType
    slot: AssetSlot
    status: AssetStatus
    version: str
    owner: str
    expires_at: str | None
    tags: list[str]
    thumbnail_url: str
    max_items: int | None        # infographic capacity; None = no limit
    width_emu: int | None
    height_emu: int | None
    embedding: list[float]

    @classmethod
    def build(
        cls,
        *,
        name: str,
        type: AssetType,
        slot: AssetSlot,
        status: AssetStatus = AssetStatus.approved,
        version: str = "v1.0",
        owner: str = "Design",
        expires_at: str | None = None,
        tags: list[str] | None = None,
        thumbnail_url: str = "",
        max_items: int | None = None,
        width_emu: int | None = None,
        height_emu: int | None = None,
        asset_id: str | None = None,
    ) -> "AssetRecord":
        """Convenience constructor — computes embedding from name + tags."""
        effective_tags = tags or []
        embed_text = f"{name} {' '.join(effective_tags)}"
        return cls(
            id=asset_id or str(uuid.uuid4()),
            name=name,
            type=type,
            slot=slot,
            status=status,
            version=version,
            owner=owner,
            expires_at=expires_at,
            tags=effective_tags,
            thumbnail_url=thumbnail_url,
            max_items=max_items,
            width_emu=width_emu,
            height_emu=height_emu,
            embedding=_embed(embed_text),
        )


def _to_brand_asset(r: AssetRecord) -> BrandAsset:
    return BrandAsset(
        id=r.id,
        name=r.name,
        type=r.type,
        slot=r.slot,
        status=r.status,
        version=r.version,
        owner=r.owner,
        expires_at=r.expires_at,
        tags=r.tags,
        thumbnail_url=r.thumbnail_url,
    )


# ---------------------------------------------------------------------------
# InMemoryAssetStore
# ---------------------------------------------------------------------------

class InMemoryAssetStore:
    """Thread-safe-enough for single-process FastAPI dev/test use.

    Production backend: see asset_store_pg.PostgresAssetStore (pgvector).
    """

    def __init__(self) -> None:
        self._records: dict[str, AssetRecord] = {}

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def put(self, record: AssetRecord) -> None:
        """Insert or replace an asset record."""
        self._records[record.id] = record

    def get(self, asset_id: str) -> AssetRecord | None:
        return self._records.get(asset_id)

    def update(self, asset_id: str, patch: BrandAssetUpdate) -> AssetRecord:
        record = self._records.get(asset_id)
        if record is None:
            raise KeyError(f"Asset {asset_id!r} not found")
        changes: dict[str, Any] = {
            k: v for k, v in patch.model_dump().items() if v is not None
        }
        # Re-compute embedding if name or tags changed
        if "name" in changes or "tags" in changes:
            new_name = changes.get("name", record.name)
            new_tags = changes.get("tags", record.tags)
            changes["embedding"] = _embed(f"{new_name} {' '.join(new_tags)}")
        updated = replace(record, **changes)
        self._records[asset_id] = updated
        return updated

    def count(self) -> int:
        return len(self._records)

    # ------------------------------------------------------------------
    # Read: list (for GET /assets)
    # ------------------------------------------------------------------

    def list_all(
        self,
        type_filter: AssetType | None = None,
        status_filter: AssetStatus | None = None,
    ) -> list[BrandAsset]:
        records = [
            r for r in self._records.values()
            if (type_filter is None or r.type == type_filter)
            and (status_filter is None or r.status == status_filter)
        ]
        return [_to_brand_asset(r) for r in records]

    # ------------------------------------------------------------------
    # Read: retrieve (the actual retrieval pipeline)
    # ------------------------------------------------------------------

    def retrieve(
        self,
        slot: AssetSlot,
        item_count: int | None = None,
        query_text: str = "",
        asset_type: AssetType | None = None,
        k: int = 5,
    ) -> list[BrandAsset]:
        """Return up to k approved assets that fit the slot and item_count.

        Step 1 — deterministic filter (structural guarantee):
          · status == approved       (only approved ever returned)
          · slot == requested slot
          · max_items is None OR max_items >= item_count
          · type matches if provided

        Step 2 — vector rank on survivors:
          · cosine similarity between query_text embedding and asset embedding
          · highest similarity first
        """
        # Step 1: deterministic filter
        candidates = [
            r for r in self._records.values()
            if r.status == AssetStatus.approved
            and r.slot == slot
            and (item_count is None or r.max_items is None or r.max_items >= item_count)
            and (asset_type is None or r.type == asset_type)
        ]

        if not candidates:
            return []

        # Step 2: vector rank
        if query_text.strip():
            q_vec = _embed(query_text)
            candidates.sort(key=lambda r: -_cosine(q_vec, r.embedding))

        return [_to_brand_asset(r) for r in candidates[:k]]


# ---------------------------------------------------------------------------
# Module-level singleton — replaced by lifespan on startup
# ---------------------------------------------------------------------------

_STORE: InMemoryAssetStore = InMemoryAssetStore()


def get_store() -> InMemoryAssetStore:
    """Return the active asset store (in-memory by default)."""
    return _STORE


def init_store(store: InMemoryAssetStore) -> None:
    """Replace the module-level singleton (called from lifespan + tests)."""
    global _STORE
    _STORE = store
