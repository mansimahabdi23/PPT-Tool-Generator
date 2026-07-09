"""Branded deck composer — no AI.

Takes a ParsedDeck + an approved SlidePlan[] and builds a new iMocha-branded
python-pptx Presentation using the layout registry and slide builder from
app/templates/.

The plan drives layout selection: plan[i].slide_type (the LLM's classification)
overrides the parser's heuristic so every slide is placed on the correct template.

Public API
----------
compose(parsed, plan, assets_root) -> Presentation
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.models.job import SlidePlan
from app.services.parser import ParsedDeck
from app.templates.builder import SlideContent, add_slide
from app.templates.theme import new_presentation

logger = logging.getLogger(__name__)


def compose(parsed: ParsedDeck, plan: list[SlidePlan], assets_root: Path) -> Any:
    """Build and return a branded Presentation from *parsed* guided by *plan*.

    Parameters
    ----------
    parsed      : output of parser.parse()
    plan        : approved SlidePlan[] from the Analyze & Plan step.
                  plan[i].slide_type drives layout selection for slide i,
                  overriding the parser's heuristic.
    assets_root : path to the monorepo assets/ directory (from settings)
    """
    prs = new_presentation()

    # Build a plan index for fast lookup; fall back to parser heuristic if the
    # plan is shorter than the deck (shouldn't happen post-approval, but defensive).
    plan_by_index = {p.index: p for p in plan}

    for ps in parsed.slides:
        plan_entry = plan_by_index.get(ps.index)
        if plan_entry is None:
            logger.warning(
                "No plan entry for slide %d — using parser heuristic (%s)",
                ps.index,
                ps.slide_type.value,
            )
            slide_type = ps.slide_type
        else:
            slide_type = plan_entry.slide_type

        content = SlideContent(
            title=ps.title,
            body_items=ps.body_items,
        )
        add_slide(prs, slide_type, content, assets_root)

    return prs
