"""Branded deck composer — no AI.

Takes a ParsedDeck + an approved SlidePlan[] and builds a new iMocha-branded
python-pptx Presentation using the layout registry and slide builder from
app/templates/.

Layout selection for body-block slides
---------------------------------------
1. Short-label guard: all body_items ≤ 6 words → infographic eligible.
2. Asset store query: exact item_count match on approved infographic fragments.
3. Dispatch: the highest-cosine fragment whose name is in _FRAGMENT_DISPATCH
   gets cloned; fall back to body-block if none match.

Add entries to _FRAGMENT_DISPATCH as more fragment fill implementations are
completed.  Slides with long sentences always go directly to body-block.

Public API
----------
compose(parsed, plan, assets_root, template_prs=None) -> tuple[Presentation, set[int], set[int]]

The second return value is the set of slide indices whose body content overflowed;
the third is the set of slide indices rendered as infographics.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from app.config import settings
from app.models.enums import AssetSlot, AssetType, FragmentIntent, SlideType
from app.models.job import SlidePlan
from app.services.asset_store import get_store
from app.services.parser import ParsedDeck
from app.services.seeder import ICON_CATEGORY_KEYWORDS
from app.templates.builder import SlideContent, add_slide
from app.templates.clone_fill import (
    clone_body_block_slide,
    clone_cover_slide,
    clone_closing_slide,
    clone_hub_spoke_slide,
    clone_infographic_slide,
    load_template,
)
from app.templates.layout_catalog import SHORT_LABEL_MAX_WORDS
from app.templates.theme import new_presentation
from app.theme import get_palette

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Infographic auto-selection
# ---------------------------------------------------------------------------

# SHORT_LABEL_MAX_WORDS is imported from layout_catalog — single source of truth
# shared with select_catalog_entry()'s cards guard so both systems stay in sync.

# Maps infographic asset name (= PPTX stem from the filename) → clone function.
# Add entries here as more fragment fill implementations are completed.
# Slides whose top-ranked fragment is NOT in this table fall back to body-block.
_FRAGMENT_DISPATCH: dict[str, Any] = {
    "Bookmark Card Process Flow – 5 Stage Fading Cards (Purple)": clone_infographic_slide,
    "4-Feature Hub-and-Spoke Diagram – Central Brand Icon (Purple)": clone_hub_spoke_slide,
}


def _all_short_labels(items: list[str]) -> bool:
    """True when every item is ≤ SHORT_LABEL_MAX_WORDS words (card/infographic-suitable).

    Uses the same threshold as layout_catalog.select_catalog_entry() so the
    two systems agree on what counts as a short parallel label.
    """
    return bool(items) and all(
        len(item.split()) <= SHORT_LABEL_MAX_WORDS for item in items
    )


def _try_infographic(
    template_prs: Any,
    out_prs: Any,
    ps: Any,
    slide_num_1based: int,
    assets_root: Path,
    intent_filter: "FragmentIntent | None" = None,
) -> bool:
    """Query the asset store for an exact-count, matching-intent infographic and clone it.

    Filters on:
      · slot == content
      · max_items == len(body_items)  (exact slot count)
      · intent == intent_filter        (hard constraint; skipped when None)

    Returns True when a fragment was applied to *out_prs*.
    Returns False when no fragment with a fill implementation matched (slot count,
    intent, or dispatch table) so the caller falls back to body-block — content
    is never silently dropped.
    """
    body_items = ps.body_items or []
    if not body_items:
        return False

    item_count = len(body_items)
    logger.info(
        "slide %d: _try_infographic  count=%d  intent_filter=%s",
        slide_num_1based, item_count,
        intent_filter.value if intent_filter else "None",
    )

    query_text = " ".join(filter(None, [ps.title] + body_items))
    candidates = get_store().retrieve(
        slot=AssetSlot.content,
        item_count=item_count,
        query_text=query_text,
        asset_type=AssetType.infographic,
        k=5,
        item_count_exact=True,
        intent_filter=intent_filter,
    )

    if not candidates:
        logger.info(
            "slide %d: 0 candidates after slot+count+intent filter "
            "(intent=%s, count=%d) → body-block",
            slide_num_1based,
            intent_filter.value if intent_filter else "None",
            item_count,
        )
        return False

    for candidate in candidates:
        clone_fn = _FRAGMENT_DISPATCH.get(candidate.name)
        if clone_fn is None:
            logger.debug(
                "slide %d: fragment %r has no fill implementation — skipping",
                slide_num_1based, candidate.name,
            )
            continue
        applied = clone_fn(
            template_prs=template_prs,
            out_prs=out_prs,
            title=ps.title or "",
            body_items=body_items,
            slide_number=slide_num_1based,
            assets_root=assets_root,
        )
        if applied:
            logger.info(
                "slide %d: auto-selected infographic %r (intent=%s, %d items)",
                slide_num_1based, candidate.name,
                intent_filter.value if intent_filter else "None",
                item_count,
            )
            return True

    logger.info(
        "slide %d: all %d candidates lack a fill implementation → body-block",
        slide_num_1based, len(candidates),
    )
    return False


# Topic categories ranked above 'people': a slide is usually ABOUT a topic,
# not about the actors mentioned in the bullet text.
_ICON_CATEGORY_PRIORITY = ["analytics", "score", "learn", "ai", "biz", "comm", "people"]


def _vote_icon_category(query_text: str) -> tuple[str | None, dict[str, int]]:
    """Keyword-vote: count per-category hits in query, return (winner, tally).

    Returns (None, tally) when no category has any keyword match so the
    caller can fall back to cosine similarity over all icons.
    """
    words = set(re.findall(r"\w+", query_text.lower()))
    tally: dict[str, int] = {
        cat: sum(1 for kw in keywords if kw in words)
        for cat, keywords in ICON_CATEGORY_KEYWORDS.items()
    }
    max_votes = max(tally.values(), default=0)
    if max_votes == 0:
        return None, tally
    winner = max(
        tally,
        key=lambda c: (
            tally[c],
            # tie-break: lower priority-list index = higher priority
            -(
                _ICON_CATEGORY_PRIORITY.index(c)
                if c in _ICON_CATEGORY_PRIORITY
                else len(_ICON_CATEGORY_PRIORITY)
            ),
        ),
    )
    return winner, tally


def _resolve_icon(
    ps: Any,
    slide_num: int,
    assets_root: Path,
) -> "Path | None":
    """Return the best-matching icon path for *ps*, or None."""
    query_text = " ".join(filter(None, [ps.title] + (ps.body_items or [])))
    if not query_text.strip():
        return None
    winner, tally = _vote_icon_category(query_text)
    tally_str = "  ".join(
        f"{c}={tally[c]}" for c in _ICON_CATEGORY_PRIORITY
    )
    logger.info(
        "slide %d icon-vote: [%s]  -> winner=%s",
        slide_num, tally_str, winner or "cosine-fallback",
    )
    hits = get_store().retrieve(
        slot=AssetSlot.content,
        item_count=1,
        query_text=query_text,
        asset_type=AssetType.icon,
        tags_include=[winner] if winner else None,
        k=1,
    )
    if not hits:
        return None
    stem = hits[0].id[len("icon-"):]
    candidate = assets_root / "icons" / f"{stem}.png"
    if candidate.is_file():
        logger.info("slide %d: icon=%s", slide_num, stem)
        return candidate
    return None


def compose(
    parsed: ParsedDeck,
    plan: list[SlidePlan],
    assets_root: Path,
    template_prs: Any = None,
    slide_themes: dict[int, str] | None = None,
) -> tuple[Any, set[int], set[int]]:
    """Build and return a branded Presentation from *parsed* guided by *plan*.

    Parameters
    ----------
    parsed       : output of parser.parse()
    plan         : approved SlidePlan[] from the Analyze & Plan step.
    assets_root  : path to the monorepo assets/ directory (from settings)
    template_prs : pre-loaded iMocha template Presentation; loaded from
                   settings.template_pptx if None (pass a cached value to
                   avoid repeated I/O when compose is retried).
    slide_themes : mapping of 0-based slide index → "light"/"dark"; defaults
                   to "light" for any slide not present in the map.

    Returns
    -------
    (prs, overflow_flagged, infographic_indices)
        prs                  : the built python-pptx Presentation
        overflow_flagged     : 0-based slide indices whose content overflowed
        infographic_indices  : 0-based slide indices rendered as infographics
                               (theme toggle is disabled for those slides)
    """
    if template_prs is None:
        template_prs = load_template(settings.template_pptx)

    prs = new_presentation()
    plan_by_index = {p.index: p for p in plan}
    overflow_flagged: set[int] = set()
    infographic_indices: set[int] = set()
    themes = slide_themes or {}

    for slide_num_1based, ps in enumerate(parsed.slides, start=1):
        plan_entry = plan_by_index.get(ps.index)

        if plan_entry is None:
            logger.warning(
                "No plan entry for slide %d — using parser heuristic (%s)",
                ps.index,
                ps.slide_type.value,
            )

        layout_category = plan_entry.layout_category if plan_entry else None
        slide_type = plan_entry.slide_type if plan_entry else ps.slide_type
        palette = get_palette(themes.get(ps.index, "light"))

        if layout_category == "cover" or slide_type == SlideType.title:
            # Clone template slide 1 — preserves photo/overlay/logo; fills text slots.
            clone_cover_slide(
                template_prs=template_prs,
                out_prs=prs,
                title=ps.title or "",
                body_items=ps.body_items or [],
            )

        elif layout_category == "closing" or slide_type == SlideType.closing:
            # The source's closing-tagged slide is rendered as a body-block so its
            # content is preserved.  The real brand closing is appended after the loop.
            icon_path = _resolve_icon(ps, slide_num_1based, assets_root)
            flagged = clone_body_block_slide(
                template_prs=template_prs,
                out_prs=prs,
                title=ps.title or "",
                body_items=ps.body_items or [],
                slide_number=slide_num_1based,
                icon_path=icon_path,
                theme=palette,
                assets_root=assets_root,
            )
            if flagged:
                overflow_flagged.add(ps.index)

        else:
            # All content layout_categories ('body-block', 'cards', 'body-image',
            # 'body-subheading', or any future category) go through the same path:
            # try infographic first; fall back to body-block so no content is dropped.
            body_items = ps.body_items or []
            intent_filter = plan_entry.required_intent if plan_entry else None
            applied = False
            if _all_short_labels(body_items):
                applied = _try_infographic(
                    template_prs, prs, ps, slide_num_1based, assets_root,
                    intent_filter=intent_filter,
                )
                if applied:
                    infographic_indices.add(ps.index)
            if not applied:
                icon_path = _resolve_icon(ps, slide_num_1based, assets_root)
                flagged = clone_body_block_slide(
                    template_prs=template_prs,
                    out_prs=prs,
                    title=ps.title or "",
                    body_items=body_items,
                    slide_number=slide_num_1based,
                    icon_path=icon_path,
                    theme=palette,
                    assets_root=assets_root,
                )
                if flagged:
                    overflow_flagged.add(ps.index)

    # Append the brand closing slide (template slide 20) as the final slide.
    # This is always additive — source slide count grows by 1.
    clone_closing_slide(template_prs=template_prs, out_prs=prs)

    return prs, overflow_flagged, infographic_indices


def compose_single_slide(
    parsed_slide: Any,
    plan_entry: SlidePlan | None,
    assets_root: Path,
    template_prs: Any,
    theme_str: str = "light",
) -> tuple[Any, bool]:
    """Build a 1-slide Presentation for *parsed_slide* with the given theme.

    Used by the per-slide theme toggle endpoint to re-render a single slide
    without recomposing the whole deck.

    Parameters
    ----------
    parsed_slide : ParsedSlide from parsed.slides
    plan_entry   : SlidePlan for this slide (None → fall back to slide type)
    assets_root  : path to the monorepo assets/ directory
    template_prs : pre-loaded iMocha template Presentation
    theme_str    : "light" or "dark"

    Returns
    -------
    (prs, is_infographic)
        prs            : 1-slide python-pptx Presentation
        is_infographic : True when an infographic fragment was applied
                         (theme toggle is disabled for those slides)
    """
    prs = new_presentation()
    palette = get_palette(theme_str)
    ps = parsed_slide
    layout_category = plan_entry.layout_category if plan_entry else None
    slide_type = plan_entry.slide_type if plan_entry else ps.slide_type
    slide_num = 1

    if layout_category == "cover" or slide_type == SlideType.title:
        clone_cover_slide(
            template_prs=template_prs, out_prs=prs,
            title=ps.title or "", body_items=ps.body_items or [],
        )
        return prs, False

    elif layout_category == "closing" or slide_type == SlideType.closing:
        icon_path = _resolve_icon(ps, slide_num, assets_root)
        clone_body_block_slide(
            template_prs=template_prs, out_prs=prs, title=ps.title or "",
            body_items=ps.body_items or [], slide_number=slide_num,
            icon_path=icon_path, theme=palette, assets_root=assets_root,
        )
        return prs, False

    else:
        # All content layout_categories — same infographic-attempt path.
        body_items = ps.body_items or []
        intent_filter = plan_entry.required_intent if plan_entry else None
        applied = False
        if _all_short_labels(body_items):
            applied = _try_infographic(
                template_prs, prs, ps, slide_num, assets_root,
                intent_filter=intent_filter,
            )
        if not applied:
            icon_path = _resolve_icon(ps, slide_num, assets_root)
            clone_body_block_slide(
                template_prs=template_prs, out_prs=prs, title=ps.title or "",
                body_items=body_items, slide_number=slide_num,
                icon_path=icon_path, theme=palette, assets_root=assets_root,
            )
        return prs, applied
