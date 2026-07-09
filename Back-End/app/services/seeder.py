"""Asset library seeder — builds AssetRecord entries from the monorepo's asset folders.

Called once on application startup (lifespan) and in scripts/seed_assets.py.

Seeded asset types
------------------
infographic  27 PPTX fragments in assets/infographics/
icon         42 PNG icons in assets/icons/ (people/score/biz/comm/ai/analytics/learn)

For infographics, max_items and slot are inferred from the filename.
For icons, slot is always content, max_items is always 1.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.models.enums import AssetSlot, AssetStatus, AssetType
from app.services.asset_store import AssetRecord, InMemoryAssetStore

# ---------------------------------------------------------------------------
# Filename → metadata inference
# ---------------------------------------------------------------------------

_NUM_WORDS: dict[str, int] = {
    "single": 1, "one": 1,
    "dual": 2, "double": 2, "two": 2,
    "triple": 3, "three": 3,
    "quad": 4, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_QUANTIFIED_RE = re.compile(
    r"\b(\d+)[- ](columns?|stages?|steps?|milestones?|levels?|rows?|features?|points?|percentages?|kpis?|metrics?)\b",
    re.IGNORECASE,
)

_DATA_RE = re.compile(
    r"\b(chart|graph|stat|analytics|kpi|metric|pie|bar|donut|gauge|"
    r"speedometer|bubble|map|percentage|growth|data|dashboard)\b",
    re.IGNORECASE,
)

_STOPWORDS = {
    "the", "and", "for", "with", "into", "from", "over",
    "stage", "state", "type", "active", "style", "step", "arc",
}


def _infer_max_items(name: str) -> int | None:
    """Parse item capacity from patterns like '5 Stage', '3-Column', 'Dual'."""
    m = _QUANTIFIED_RE.search(name)
    if m:
        return int(m.group(1))
    lower = name.lower()
    for word, val in _NUM_WORDS.items():
        if re.search(rf"\b{word}\b", lower):
            return val
    return None


def _infer_slot(name: str) -> AssetSlot:
    """All infographics go in the content slot (data slides use the same infographic_region).

    The AssetSlot enum mirrors the TypeScript contract: cover|content|divider|closing.
    Chart/analytics infographics are still content-slot assets; the Analyze & Plan agent
    selects them by tags ("chart", "kpi") rather than by a separate "data" slot.
    """
    _ = name  # slot is always content for infographics; kept for future expansion
    return AssetSlot.content


def _infer_tags(name: str) -> list[str]:
    """Extract meaningful keyword tags from an infographic filename."""
    # Strip color/variant suffixes: "(Purple)", "[Orange]", "(GrayDark)"
    clean = re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", name)
    # Replace em-dashes with spaces
    clean = re.sub(r"[–—]", " ", clean)
    words = re.findall(r"\b[A-Za-z]{3,}\b", clean)
    tags = list(dict.fromkeys(
        w.lower() for w in words if w.lower() not in _STOPWORDS
    ))
    return tags[:8]


def _icon_category(stem: str) -> str:
    """'people_3' → 'people'."""
    parts = stem.rsplit("_", 1)
    return parts[0] if len(parts) == 2 else stem


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_infographics(assets_root: Path, store: InMemoryAssetStore) -> int:
    """Seed one AssetRecord per .pptx in assets/infographics/. Returns count."""
    folder = assets_root / "infographics"
    if not folder.exists():
        return 0
    count = 0
    for i, pptx_path in enumerate(sorted(folder.glob("*.pptx")), start=1):
        name = pptx_path.stem
        asset_id = f"infographic-{i:03d}"
        tags = _infer_tags(name)
        record = AssetRecord.build(
            asset_id=asset_id,
            name=name,
            type=AssetType.infographic,
            slot=_infer_slot(name),
            status=AssetStatus.approved,
            version="v1.0",
            owner="Design",
            tags=tags,
            thumbnail_url="",   # generated on demand via LibreOffice (Step 5+)
            max_items=_infer_max_items(name),
        )
        store.put(record)
        count += 1
    return count


def seed_icons(assets_root: Path, store: InMemoryAssetStore) -> int:
    """Seed one AssetRecord per .png in assets/icons/. Returns count."""
    folder = assets_root / "icons"
    if not folder.exists():
        return 0
    count = 0
    for png_path in sorted(folder.glob("*.png")):
        stem = png_path.stem
        category = _icon_category(stem)
        asset_id = f"icon-{stem}"
        variant = stem[len(category):].lstrip("_")
        display_name = f"{category.title()} Icon {variant}".strip()
        record = AssetRecord.build(
            asset_id=asset_id,
            name=display_name,
            type=AssetType.icon,
            slot=AssetSlot.content,
            status=AssetStatus.approved,
            version="v1.0",
            owner="Design",
            tags=[category, "icon"],
            thumbnail_url=f"/api/assets/{asset_id}/thumbnail",
            max_items=1,
        )
        store.put(record)
        count += 1
    return count


def seed_all(assets_root: Path, store: InMemoryAssetStore) -> int:
    """Seed infographics + icons. Returns total seeded count."""
    n = seed_infographics(assets_root, store)
    n += seed_icons(assets_root, store)
    return n
