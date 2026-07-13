"""Branded deck composer — no AI.

Takes a ParsedDeck + an approved SlidePlan[] and builds a new iMocha-branded
python-pptx Presentation using the layout registry and slide builder from
app/templates/.

The plan drives layout selection: plan[i].layout_category picks the clone-and-fill
path (body-block for now) or falls back to plan[i].slide_type for the legacy
scratch-builder path.

Public API
----------
compose(parsed, plan, assets_root, template_prs=None) -> tuple[Presentation, set[int]]

The second return value is the set of slide indices whose body content overflowed
even at the minimum font size; the pipeline merges these into flagged_indices.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import settings
from app.models.job import SlidePlan
from app.services.parser import ParsedDeck
from app.templates.builder import SlideContent, add_slide
from app.templates.clone_fill import clone_body_block_slide, load_template
from app.templates.theme import new_presentation

logger = logging.getLogger(__name__)


def compose(
    parsed: ParsedDeck,
    plan: list[SlidePlan],
    assets_root: Path,
    template_prs: Any = None,
) -> tuple[Any, set[int]]:
    """Build and return a branded Presentation from *parsed* guided by *plan*.

    Parameters
    ----------
    parsed       : output of parser.parse()
    plan         : approved SlidePlan[] from the Analyze & Plan step.
    assets_root  : path to the monorepo assets/ directory (from settings)
    template_prs : pre-loaded iMocha template Presentation; loaded from
                   settings.template_pptx if None (pass a cached value to
                   avoid repeated I/O when compose is retried).

    Returns
    -------
    (prs, overflow_flagged)
        prs              : the built python-pptx Presentation
        overflow_flagged : set of 0-based slide indices whose content
                           overflowed even at 10 pt (should be flagged)
    """
    if template_prs is None:
        template_prs = load_template(settings.template_pptx)

    prs = new_presentation()
    plan_by_index = {p.index: p for p in plan}
    overflow_flagged: set[int] = set()

    for slide_num_1based, ps in enumerate(parsed.slides, start=1):
        plan_entry = plan_by_index.get(ps.index)

        if plan_entry is None:
            logger.warning(
                "No plan entry for slide %d — using parser heuristic (%s)",
                ps.index,
                ps.slide_type.value,
            )

        layout_category = plan_entry.layout_category if plan_entry else None

        if layout_category == "body-block":
            flagged = clone_body_block_slide(
                template_prs=template_prs,
                out_prs=prs,
                title=ps.title or "",
                body_items=ps.body_items or [],
                slide_number=slide_num_1based,
            )
            if flagged:
                overflow_flagged.add(ps.index)
        else:
            slide_type = plan_entry.slide_type if plan_entry else ps.slide_type
            content = SlideContent(
                title=ps.title,
                body_items=ps.body_items,
            )
            add_slide(prs, slide_type, content, assets_root)

    return prs, overflow_flagged
