"""Layout catalog — maps template slide indices to catalog entries.

Each entry describes one slide from iMocha_PPT_Template_New__2026_.pptx that
the Analyze-and-Plan agent can select.  Step 2 (clone-and-fill) will clone
the chosen template slide and fill it with real content.

Edit CATALOG to adjust the mapping — this is the single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.services.parser import ParsedSlide

LayoutCategory = Literal[
    "cover",
    "closing",
    "cards",
    "body-image",
    "body-block",
    "body-subheading",
]

# Shared short-label threshold — used by BOTH the catalog (Rule 3 cards guard)
# and the composer (_all_short_labels / _try_infographic).  Kept in one place so
# the two systems can never diverge again.  Items with ≤ SHORT_LABEL_MAX_WORDS
# words are noun-phrase labels suitable for card/infographic layouts; items with
# more words are full sentences that belong in body-block text.
SHORT_LABEL_MAX_WORDS = 6

# body-subheading: first item must be at most this many words (short subtitle/tagline)
_SUBTITLE_MAX_WORDS = 4
# body-subheading: remaining items must average MORE than this many words (actual body text)
_SUBTITLE_BODY_MIN_AVG_WORDS = 6

# Items beyond this count → slide is too dense for any layout → overflow_flagged
_OVERFLOW_FLAG_THRESHOLD = 12


@dataclass(frozen=True)
class CatalogEntry:
    """One template slide that the planner can pick."""

    template_slide_index: int        # 1-based index into the template PPTX
    category: LayoutCategory
    max_items: int | None = None     # card/list capacity; None = no hard cap
    has_image_slot: bool = False
    wanted_asset_types: tuple[str, ...] = field(default_factory=tuple)
    # ^ plain strings (not bound to AssetType enum) — includes "image" for future use


# ---------------------------------------------------------------------------
# Catalog — adjust slide indices here when the template changes
# ---------------------------------------------------------------------------

CATALOG: list[CatalogEntry] = [
    CatalogEntry(
        template_slide_index=1,
        category="cover",
        wanted_asset_types=("logo",),
    ),
    CatalogEntry(
        template_slide_index=20,
        category="closing",
        wanted_asset_types=("logo",),
    ),
    CatalogEntry(
        template_slide_index=5,
        category="body-block",
        max_items=6,
    ),
    CatalogEntry(
        template_slide_index=4,
        category="body-subheading",
    ),
    CatalogEntry(
        template_slide_index=14,
        category="body-image",
        has_image_slot=True,
        wanted_asset_types=("image",),
    ),
    CatalogEntry(
        template_slide_index=17,
        category="cards",
        max_items=3,
        wanted_asset_types=("icon",),
    ),
    CatalogEntry(
        template_slide_index=18,
        category="cards",
        max_items=4,
        wanted_asset_types=("icon",),
    ),
    CatalogEntry(
        template_slide_index=15,
        category="cards",
        max_items=5,
        wanted_asset_types=("icon",),
    ),
]

# ---------------------------------------------------------------------------
# Derived lookups — built once at import time
# ---------------------------------------------------------------------------

_COVER = next(e for e in CATALOG if e.category == "cover")
_CLOSING = next(e for e in CATALOG if e.category == "closing")
_BODY_BLOCK = next(e for e in CATALOG if e.category == "body-block")
_BODY_SUBHEADING = next(e for e in CATALOG if e.category == "body-subheading")
_BODY_IMAGE = next(e for e in CATALOG if e.category == "body-image")
_CARDS_BY_COUNT: dict[int, CatalogEntry] = {
    e.max_items: e
    for e in CATALOG
    if e.category == "cards" and e.max_items is not None
}


# ---------------------------------------------------------------------------
# Selection — deterministic priority ladder
# ---------------------------------------------------------------------------


def select_catalog_entry(
    slide: ParsedSlide,
    is_first: bool,
    is_last: bool,
) -> tuple[CatalogEntry, bool]:
    """Pick the best catalog entry for *slide* using the priority ladder.

    Returns ``(entry, overflow_flagged)``.

    ``overflow_flagged = True`` when item count exceeds ``_OVERFLOW_FLAG_THRESHOLD``;
    the slide is then too dense for any layout and should be queued for human review.

    Priority ladder
    ---------------
    1. Position anchors   — first slide → cover, last → closing.
    2. (Divider detection — future step; not implemented here.)
    3. 3–5 short parallel items → cards entry matching the count.
    4. Non-background image present → body-image.
    5. First item looks like a subtitle → body-subheading; else body-block.

    Item-overflow rule
    ------------------
    Slides with > 5 items fall through rule 3 and land on body-block, which
    renders them as a text list without dropping any content.  Only when count
    exceeds ``_OVERFLOW_FLAG_THRESHOLD`` is the slide flagged for human review.
    Nothing is ever silently truncated.
    """
    if is_first:
        return _COVER, False
    if is_last:
        return _CLOSING, False

    items: list[str] = slide.body_items or []
    count = len(items)
    has_non_bg_image = any(not img.is_background for img in slide.images)

    # Rule 3: 3–5 short parallel items → cards
    # "Short" = every item is a noun-phrase label, not a full sentence.
    # Guard: ALL items must have ≤ _MAX_WORDS_PER_CARD_ITEM words.
    if 3 <= count <= 5:
        if all(len(item.split()) <= SHORT_LABEL_MAX_WORDS for item in items):
            card = _CARDS_BY_COUNT.get(count)
            if card is not None:
                return card, False

    # Rule 4: non-background image → body-image
    if has_non_bg_image:
        return _BODY_IMAGE, False

    # Rule 5: body-block or body-subheading
    overflow_flagged = count > _OVERFLOW_FLAG_THRESHOLD

    # body-subheading: first item is a very short subtitle/tagline (≤ _SUBTITLE_MAX_WORDS)
    # AND the rest of the content is noticeably longer (avg > _SUBTITLE_BODY_MIN_AVG_WORDS).
    # This rejects slides where all bullets are similar length — those are body-block.
    if count >= 2:
        first_wc = len(items[0].split())
        rest_avg_wc = sum(len(i.split()) for i in items[1:]) / (count - 1)
        if first_wc <= _SUBTITLE_MAX_WORDS and rest_avg_wc > _SUBTITLE_BODY_MIN_AVG_WORDS:
            return _BODY_SUBHEADING, overflow_flagged

    return _BODY_BLOCK, overflow_flagged
