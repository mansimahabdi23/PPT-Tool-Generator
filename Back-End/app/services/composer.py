"""Branded deck composer — no AI.

Takes a ParsedDeck and builds a new iMocha-branded python-pptx Presentation
using the layout registry and slide builder from app/templates/.

Public API
----------
compose(parsed, assets_root) -> Presentation
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.parser import ParsedDeck
from app.templates.builder import SlideContent, add_slide
from app.templates.theme import new_presentation


def compose(parsed: ParsedDeck, assets_root: Path) -> Any:
    """Build and return a branded Presentation from *parsed*.

    Parameters
    ----------
    parsed      : output of parser.parse()
    assets_root : path to the monorepo assets/ directory (from settings)
    """
    prs = new_presentation()

    for ps in parsed.slides:
        content = SlideContent(
            title=ps.title,
            body_items=ps.body_items,
        )
        add_slide(prs, ps.slide_type, content, assets_root)

    return prs
