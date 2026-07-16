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

from app.models.enums import AssetSlot, AssetStatus, AssetType, FragmentIntent
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


# Keyword vocabularies per icon category — makes the cosine embedding useful.
# Each category word alone is too thin; adding synonyms lets bullet text like
# "track hiring pipeline performance" surface "people" and "analytics" icons.
# Public so composer.py can import it for keyword-vote retrieval.
ICON_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "ai":        ["artificial", "intelligence", "machine", "learning", "automation",
                  "algorithm", "model", "predict", "generative", "llm"],
    "analytics": ["analytics", "data", "metrics", "report", "insights", "measurement",
                  "dashboard", "trend", "track", "statistics", "kpi"],
    "biz":       ["business", "strategy", "growth", "enterprise", "revenue", "roi",
                  "market", "company", "goal", "sales", "productivity"],
    "comm":      ["communication", "collaboration", "message", "connect", "engage",
                  "social", "notify", "share", "feedback", "interact"],
    "learn":     ["learning", "training", "education", "skills", "upskill", "course",
                  "reskill", "development", "knowledge", "certification"],
    "people":    ["people", "employee", "candidate", "talent", "workforce", "hiring",
                  "recruit", "user", "hr", "team", "onboard", "retention"],
    "score":     ["score", "assessment", "test", "evaluate", "rating", "benchmark",
                  "performance", "measure", "quiz", "rank", "accuracy"],
}


# ---------------------------------------------------------------------------
# Curated intent table — maps each fragment's PPTX stem to its structural intent.
#
# This is human-assigned, not inferred from keywords.  Intent is a HARD filter
# in retrieval: a sequential-process fragment must never be chosen for a slide
# whose content is unordered parallel features.
#
# Keys must match pptx_path.stem exactly (including em-dash and spaces).
# Fragments absent from this table get intent=None (no hard constraint applied).
# ---------------------------------------------------------------------------

_FRAGMENT_INTENT: dict[str, FragmentIntent] = {
    # ── single-stat ──────────────────────────────────────────────────────────
    "Bold Single Stat Slide – Progress Bar Callout 25% (Purple Solid)":
        FragmentIntent.single_stat,
    "Bold Single Stat Slide – Progress Bar Callout 79% (Orange Gradient)":
        FragmentIntent.single_stat,
    "People spotlight – single profile feature banner":
        FragmentIntent.single_stat,

    # ── data-chart ───────────────────────────────────────────────────────────
    "Dual Chart Analytics Panel – Pie + Grouped Bar (Orange)":
        FragmentIntent.data_chart,
    "Dual Chart Analytics Panel – Pie + Grouped Bar (Purple)":
        FragmentIntent.data_chart,
    "Triple Donut KPI Ring Set – 3 Percentage Metrics (Purple + Orange)":
        FragmentIntent.data_chart,
    "Donut Chart + 4-Row Icon List Dashboard (OrangePurple)":
        FragmentIntent.data_chart,
    "Proportional Bubble Cluster + Speedometer Arc – Investment Split Dashboard (Purple-Orange)":
        FragmentIntent.data_chart,
    "Staircase Bar Growth Chart – Digital Job Growth 2020-2025 with Category Breakdown":
        FragmentIntent.data_chart,

    # ── geographic ───────────────────────────────────────────────────────────
    "Dual World Map Panel – Connected Locations (Dark) + Subtle Outline (Gray)":
        FragmentIntent.geographic,

    # ── sequential-process ───────────────────────────────────────────────────
    "3-Column Stepped Workflow – Step 1 Active State":
        FragmentIntent.sequential_process,
    "3-Column Stepped Workflow – Step 2 Active State":
        FragmentIntent.sequential_process,
    "Dual-Style Vertical Process List – 3 Steps (Purple)":
        FragmentIntent.sequential_process,
    "Wave Arc Process Flow – 4 Stage Numbered S-Curve (Purple to Orange Gradient)":
        FragmentIntent.sequential_process,
    "Ascending Maturity Level Chart – 5 Stage Bar + Chevron Progression (GrayDark)":
        FragmentIntent.sequential_process,
    "Ascending Maturity Level Chart – 5 Stage Bar + Chevron Progression (Orange)":
        FragmentIntent.sequential_process,
    "Serpentine Journey Flow – 5 Stage Process (Orange)":
        FragmentIntent.sequential_process,
    "Serpentine journey flow – 5 stage process (purple)":
        FragmentIntent.sequential_process,
    "Wave Arc Process Flow – 5 Stage S-Curve (Purple to Orange Gradient)":
        FragmentIntent.sequential_process,

    # ── timeline ─────────────────────────────────────────────────────────────
    "Icon-Only Horizontal Timeline – 5 Milestones with Dotted Connector (Purple)":
        FragmentIntent.timeline,

    # ── parallel-features ────────────────────────────────────────────────────
    # NOTE: "Bookmark Card Process Flow" carries "Process Flow" in its name but
    # its visual design is 5 equal-weight side-by-side cards with no directional
    # arrow between them — suitable for unordered parallel features.
    # Correct to sequential-process if the design team considers it ordered.
    "Bookmark Card Process Flow – 5 Stage Fading Cards (Purple)":
        FragmentIntent.parallel_features,
    "4-Feature Hub-and-Spoke Diagram – Central Brand Icon (Purple)":
        FragmentIntent.parallel_features,
    "Customer Logo Wheel – Central Brand Hub with Satellite Use Cases":
        FragmentIntent.parallel_features,

    # ── hierarchy ────────────────────────────────────────────────────────────
    "Hierarchical Taxonomy Framework – 4-Level Classification with Examples":
        FragmentIntent.hierarchy,
    "Organizational Hierarchy Pyramid – 7 Level Structure (Orange)":
        FragmentIntent.hierarchy,
    "Organizational Hierarchy Pyramid – 7 Level Structure (Purple)":
        FragmentIntent.hierarchy,

    # ── roadmap ──────────────────────────────────────────────────────────────
    "Multi-Category Product Roadmap – Q4 Monthly Release Grid":
        FragmentIntent.roadmap,
}


# ---------------------------------------------------------------------------
# Description-capability table — fragments where EACH item slot has BOTH a
# short headline text area AND a longer prose body text area.
#
# Fragments absent from this set are label-only (one short text per slot, or
# text embedded in chart/image shapes that the fill code cannot replace).
#
# Keys must match pptx_path.stem exactly.
# ---------------------------------------------------------------------------

_FRAGMENT_HAS_DESCRIPTION: frozenset[str] = frozenset({
    # 3 slots — step label + headline + body (two body areas each)
    "3-Column Stepped Workflow – Step 1 Active State",
    "3-Column Stepped Workflow – Step 2 Active State",
    # 3 slots — process label + description sentence
    "Dual-Style Vertical Process List – 3 Steps (Purple)",
    # 4 slots — headline + body per icon-list row (beside donut chart)
    "Donut Chart + 4-Row Icon List Dashboard (OrangePurple)",
    # 4 slots — number + headline + body
    "Wave Arc Process Flow – 4 Stage Numbered S-Curve (Purple to Orange Gradient)",
    # 5 slots — level label + description (bar height grows with content)
    "Ascending Maturity Level Chart – 5 Stage Bar + Chevron Progression (GrayDark)",
    "Ascending Maturity Level Chart – 5 Stage Bar + Chevron Progression (Orange)",
    # 5 slots — number + headline + body (parallel-features capable)
    "Bookmark Card Process Flow – 5 Stage Fading Cards (Purple)",
    # 5 slots named / 6 headline+body pairs in shape tree (see inventory note)
    "Serpentine Journey Flow – 5 Stage Process (Orange)",
    "Serpentine journey flow – 5 stage process (purple)",
    # 5 slots — number + headline + body
    "Wave Arc Process Flow – 5 Stage S-Curve (Purple to Orange Gradient)",
})


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
            intent=_FRAGMENT_INTENT.get(name),
            has_description=name in _FRAGMENT_HAS_DESCRIPTION,
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
        tags = [category, "icon"] + ICON_CATEGORY_KEYWORDS.get(category, [])
        record = AssetRecord.build(
            asset_id=asset_id,
            name=display_name,
            type=AssetType.icon,
            slot=AssetSlot.content,
            status=AssetStatus.approved,
            version="v1.0",
            owner="Design",
            tags=tags,
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
