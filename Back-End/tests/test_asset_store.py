"""Tests for the asset library: InMemoryAssetStore, seeder, and API routes.

Coverage
--------
Embedding             _embed produces fixed-dim deterministic vectors
Cosine similarity     _cosine correct for known cases
Filter: slot          assets in wrong slot excluded
Filter: approved      pending/deprecated excluded from retrieve()
Filter: max_items     assets with insufficient capacity excluded
Filter: type          optional asset_type filter respected
Vector rank           query text moves relevant asset to front
list_all              type/status filters work; all assets returned unfiltered
PATCH update          status change persisted; embedding re-computed on name change
Seeder                infographics + icons seeded with correct metadata
Seeder inference      _infer_max_items, _infer_slot, _infer_tags correct
API: list             GET /api/assets returns seeded assets
API: create           POST /api/assets adds a new record
API: patch            PATCH /api/assets/{id} updates status
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.models.asset import BrandAssetUpdate
from app.models.enums import AssetSlot, AssetStatus, AssetType
from app.services.asset_store import (
    EMBED_DIM,
    AssetRecord,
    InMemoryAssetStore,
    _cosine,
    _embed,
    get_store,
    init_store,
)
from app.services.seeder import (
    _infer_max_items,
    _infer_slot,
    _infer_tags,
    seed_all,
    seed_icons,
    seed_infographics,
)

ASSETS_ROOT = Path(__file__).parent.parent.parent.parent / "assets"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_store(*records: AssetRecord) -> InMemoryAssetStore:
    store = InMemoryAssetStore()
    for r in records:
        store.put(r)
    return store


def _infographic(
    name: str = "Workflow",
    slot: AssetSlot = AssetSlot.content,
    status: AssetStatus = AssetStatus.approved,
    max_items: int | None = None,
    asset_id: str | None = None,
    tags: list[str] | None = None,
) -> AssetRecord:
    return AssetRecord.build(
        name=name,
        type=AssetType.infographic,
        slot=slot,
        status=status,
        max_items=max_items,
        tags=tags or ["workflow"],
        asset_id=asset_id,
    )


# ---------------------------------------------------------------------------
# 1. Embedding
# ---------------------------------------------------------------------------

def test_embed_fixed_dimension() -> None:
    v = _embed("process workflow talent")
    assert len(v) == EMBED_DIM


def test_embed_normalized() -> None:
    v = _embed("hiring quality assessment")
    norm = math.sqrt(sum(x * x for x in v))
    assert abs(norm - 1.0) < 1e-9, f"vector not normalized: norm={norm}"


def test_embed_deterministic() -> None:
    a = _embed("skill assessment icon")
    b = _embed("skill assessment icon")
    assert a == b


def test_embed_empty_returns_zeros() -> None:
    v = _embed("")
    assert all(x == 0.0 for x in v)
    assert len(v) == EMBED_DIM


# ---------------------------------------------------------------------------
# 2. Cosine similarity
# ---------------------------------------------------------------------------

def test_cosine_identical_vectors() -> None:
    v = _embed("hiring workflow")
    assert abs(_cosine(v, v) - 1.0) < 1e-9


def test_cosine_zero_vector() -> None:
    zero = [0.0] * EMBED_DIM
    v = _embed("talent analytics")
    assert _cosine(zero, v) == 0.0


def test_cosine_similar_beats_dissimilar() -> None:
    """'chart analytics kpi' is closer to 'chart data' than 'workflow process' is."""
    q = _embed("chart data")
    similar = _cosine(q, _embed("chart analytics kpi"))
    dissimilar = _cosine(q, _embed("workflow process steps"))
    assert similar > dissimilar


# ---------------------------------------------------------------------------
# 3. Filter: slot
# ---------------------------------------------------------------------------

def test_filter_excludes_wrong_slot() -> None:
    store = _make_store(
        _infographic("Content Graphic", slot=AssetSlot.content),
        _infographic("Divider Graphic", slot=AssetSlot.divider),
    )
    results = store.retrieve(slot=AssetSlot.content)
    assert len(results) == 1
    assert results[0].name == "Content Graphic"


# ---------------------------------------------------------------------------
# 4. Filter: approved only
# ---------------------------------------------------------------------------

def test_filter_excludes_pending() -> None:
    store = _make_store(
        _infographic("Good Asset", status=AssetStatus.approved),
        _infographic("Pending Asset", status=AssetStatus.pending),
    )
    results = store.retrieve(slot=AssetSlot.content)
    names = {r.name for r in results}
    assert "Good Asset" in names
    assert "Pending Asset" not in names


def test_filter_excludes_deprecated() -> None:
    store = _make_store(
        _infographic("Current", status=AssetStatus.approved),
        _infographic("Old", status=AssetStatus.deprecated),
    )
    results = store.retrieve(slot=AssetSlot.content)
    assert all(r.name != "Old" for r in results)


def test_retrieve_empty_when_none_approved() -> None:
    store = _make_store(
        _infographic("Draft", status=AssetStatus.pending),
    )
    results = store.retrieve(slot=AssetSlot.content)
    assert results == []


# ---------------------------------------------------------------------------
# 5. Filter: max_items
# ---------------------------------------------------------------------------

def test_filter_max_items_fits() -> None:
    store = _make_store(
        _infographic("3-Step", max_items=3),
        _infographic("5-Step", max_items=5),
    )
    # Requesting item_count=4 — only the 5-step fits
    results = store.retrieve(slot=AssetSlot.content, item_count=4)
    assert len(results) == 1
    assert results[0].name == "5-Step"


def test_filter_max_items_none_means_unlimited() -> None:
    store = _make_store(
        _infographic("Fixed-3", max_items=3),
        _infographic("Unlimited", max_items=None),
    )
    # item_count=10 — Fixed-3 excluded, Unlimited always fits
    results = store.retrieve(slot=AssetSlot.content, item_count=10)
    assert len(results) == 1
    assert results[0].name == "Unlimited"


# ---------------------------------------------------------------------------
# 6. Filter: asset_type
# ---------------------------------------------------------------------------

def test_filter_asset_type() -> None:
    store = _make_store(
        _infographic("Infographic A"),
        AssetRecord.build(
            name="Chart B",
            type=AssetType.chart,
            slot=AssetSlot.content,
        ),
    )
    results = store.retrieve(slot=AssetSlot.content, asset_type=AssetType.infographic)
    assert len(results) == 1
    assert results[0].name == "Infographic A"


# ---------------------------------------------------------------------------
# 7. Vector rank
# ---------------------------------------------------------------------------

def test_vector_rank_orders_by_relevance() -> None:
    store = _make_store(
        _infographic("Timeline Milestones Journey", tags=["timeline", "milestones"]),
        _infographic("Chart KPI Dashboard Analytics", tags=["chart", "kpi", "analytics"]),
    )
    # Query about analytics → chart/kpi should rank first
    results = store.retrieve(slot=AssetSlot.content, query_text="analytics dashboard kpi metrics")
    assert len(results) == 2
    assert "Chart" in results[0].name


def test_vector_rank_top_k() -> None:
    store = _make_store(*[_infographic(f"Asset {i}") for i in range(10)])
    results = store.retrieve(slot=AssetSlot.content, k=3)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# 8. list_all
# ---------------------------------------------------------------------------

def test_list_all_no_filter() -> None:
    store = _make_store(
        _infographic("A", status=AssetStatus.approved),
        _infographic("B", status=AssetStatus.pending),
        _infographic("C", status=AssetStatus.deprecated),
    )
    results = store.list_all()
    assert len(results) == 3


def test_list_all_status_filter() -> None:
    store = _make_store(
        _infographic("A", status=AssetStatus.approved),
        _infographic("B", status=AssetStatus.pending),
    )
    approved = store.list_all(status_filter=AssetStatus.approved)
    assert len(approved) == 1
    assert approved[0].name == "A"


def test_list_all_type_filter() -> None:
    store = _make_store(
        _infographic("Infographic"),
        AssetRecord.build(name="Icon", type=AssetType.icon, slot=AssetSlot.content),
    )
    icons = store.list_all(type_filter=AssetType.icon)
    assert len(icons) == 1
    assert icons[0].name == "Icon"


# ---------------------------------------------------------------------------
# 9. PATCH update
# ---------------------------------------------------------------------------

def test_update_status() -> None:
    record = _infographic("Draft", status=AssetStatus.pending, asset_id="test-id")
    store = _make_store(record)
    patch = BrandAssetUpdate(status=AssetStatus.approved)
    updated = store.update("test-id", patch)
    assert updated.status == AssetStatus.approved


def test_update_recomputes_embedding_on_name_change() -> None:
    record = _infographic("Old Name", asset_id="emb-id")
    old_embedding = list(record.embedding)
    store = _make_store(record)
    store.update("emb-id", BrandAssetUpdate(name="New Different Name"))
    updated = store.get("emb-id")
    assert updated is not None
    assert updated.embedding != old_embedding


def test_update_unknown_id_raises() -> None:
    store = InMemoryAssetStore()
    with pytest.raises(KeyError):
        store.update("nonexistent", BrandAssetUpdate(status=AssetStatus.deprecated))


# ---------------------------------------------------------------------------
# 10. Seeder — inference helpers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("3-Column Stepped Workflow", 3),
    ("5 Stage Process", 5),
    ("4-Feature Hub-and-Spoke Diagram", 4),
    ("Icon-Only Horizontal Timeline – 5 Milestones", 5),
    ("Dual Chart Analytics Panel", 2),
    ("Triple Donut KPI Ring Set", 3),
    ("Bold Single Stat Slide", 1),
    ("Organizational Hierarchy Pyramid", None),   # no count pattern
])
def test_infer_max_items(name: str, expected: int | None) -> None:
    assert _infer_max_items(name) == expected


@pytest.mark.parametrize("name,expected_slot", [
    # All infographics are content-slot assets (AssetSlot has no "data" value).
    # The AI Analyze & Plan agent selects chart/kpi assets by tags, not by slot.
    ("Dual Chart Analytics Panel", AssetSlot.content),
    ("Ascending Maturity Level Chart", AssetSlot.content),
    ("Bold Single Stat Slide", AssetSlot.content),
    ("Serpentine Journey Flow", AssetSlot.content),
    ("3-Column Stepped Workflow", AssetSlot.content),
    ("Organizational Hierarchy Pyramid", AssetSlot.content),
])
def test_infer_slot(name: str, expected_slot: AssetSlot) -> None:
    assert _infer_slot(name) == expected_slot


def test_infer_tags_strips_color_variants() -> None:
    tags = _infer_tags("Dual Chart Analytics Panel – Pie + Grouped Bar (Orange)")
    assert "orange" not in tags
    assert any(t in tags for t in ["dual", "chart", "analytics", "pie", "grouped", "bar"])


# ---------------------------------------------------------------------------
# 11. Seeder — seed from real assets folder
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not ASSETS_ROOT.exists(), reason="assets/ folder not found")
def test_seed_infographics_count() -> None:
    store = InMemoryAssetStore()
    n = seed_infographics(ASSETS_ROOT, store)
    assert n == 27, f"Expected 27 infographics, got {n}"
    assert store.count() == 27


@pytest.mark.skipif(not ASSETS_ROOT.exists(), reason="assets/ folder not found")
def test_seed_icons_count() -> None:
    store = InMemoryAssetStore()
    n = seed_icons(ASSETS_ROOT, store)
    assert n == 42, f"Expected 42 icons, got {n}"


@pytest.mark.skipif(not ASSETS_ROOT.exists(), reason="assets/ folder not found")
def test_seed_all_total() -> None:
    store = InMemoryAssetStore()
    n = seed_all(ASSETS_ROOT, store)
    assert n == 69  # 27 infographics + 42 icons


@pytest.mark.skipif(not ASSETS_ROOT.exists(), reason="assets/ folder not found")
def test_seeded_infographics_are_approved() -> None:
    store = InMemoryAssetStore()
    seed_infographics(ASSETS_ROOT, store)
    assets = store.list_all(type_filter=AssetType.infographic)
    assert all(a.status == AssetStatus.approved for a in assets)


@pytest.mark.skipif(not ASSETS_ROOT.exists(), reason="assets/ folder not found")
def test_retrieve_from_seeded_store() -> None:
    store = InMemoryAssetStore()
    seed_infographics(ASSETS_ROOT, store)
    results = store.retrieve(slot=AssetSlot.content, query_text="workflow process steps")
    assert len(results) > 0
    assert all(r.type == AssetType.infographic for r in results)


@pytest.mark.skipif(not ASSETS_ROOT.exists(), reason="assets/ folder not found")
def test_retrieve_chart_assets_by_tag_from_seeded_store() -> None:
    """Chart/analytics infographics land in content slot; tags drive selection."""
    store = InMemoryAssetStore()
    seed_infographics(ASSETS_ROOT, store)
    results = store.retrieve(slot=AssetSlot.content, query_text="analytics chart kpi")
    assert len(results) > 0


# ---------------------------------------------------------------------------
# 12. API routes (with lifespan that seeds the store)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_client() -> TestClient:
    from app.main import app
    with TestClient(app) as client:
        yield client


def test_api_list_assets_returns_data(api_client: TestClient) -> None:
    resp = api_client.get("/api/assets")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_api_list_assets_type_filter(api_client: TestClient) -> None:
    resp = api_client.get("/api/assets?type=infographic")
    assert resp.status_code == 200
    data = resp.json()
    assert all(a["type"] == "infographic" for a in data)


def test_api_list_assets_status_filter(api_client: TestClient) -> None:
    resp = api_client.get("/api/assets?status=approved")
    assert resp.status_code == 200
    data = resp.json()
    assert all(a["status"] == "approved" for a in data)


def test_api_create_asset(api_client: TestClient) -> None:
    resp = api_client.post(
        "/api/assets",
        data={
            "name": "Test Infographic",
            "type": "infographic",
            "slot": "content",
            "version": "v1.0",
            "owner": "Test",
            "tags": "test,unit",
        },
        files={"file": ("test.pptx", b"dummy", "application/octet-stream")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test Infographic"
    assert data["status"] == "approved"
    assert "id" in data


def test_api_patch_asset_status(api_client: TestClient) -> None:
    # First find an existing asset
    assets = api_client.get("/api/assets").json()
    asset_id = assets[0]["id"]

    resp = api_client.patch(
        f"/api/assets/{asset_id}",
        json={"status": "deprecated"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "deprecated"


def test_api_patch_unknown_asset(api_client: TestClient) -> None:
    resp = api_client.patch("/api/assets/does-not-exist", json={"status": "deprecated"})
    assert resp.status_code == 404
