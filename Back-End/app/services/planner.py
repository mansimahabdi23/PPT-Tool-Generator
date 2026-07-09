"""Deterministic Analyze & Plan stand-in (sub-increment 1, LLM-free).

``build_plan`` converts a ``ParsedDeck`` into a ``list[SlidePlan]`` using only
the parser's slide-type heuristic and simple rules.

THIS IS A PLACEHOLDER.
In increment 2 this module is backed by an LLMProvider (StubProvider default,
Azure OpenAI when credentials are present). The function signature stays the
same so no callers change.
"""

from __future__ import annotations

import uuid

from app.models.enums import AssetType, SlideType
from app.models.job import SlidePlan
from app.services.parser import ParsedDeck

# ---------------------------------------------------------------------------
# Layout descriptions for each slide type (deterministic; overridden by LLM later)
# ---------------------------------------------------------------------------

_LAYOUT_MAP: dict[SlideType, str] = {
    SlideType.title: "Full-bleed cover with title, subtitle, and logo",
    SlideType.agenda: "Numbered agenda list with section highlights",
    SlideType.content: "Two-column or single-column content with icon accents",
    SlideType.data: "Chart or data table with supporting callout text",
    SlideType.divider: "Section divider with gradient background and section title",
    SlideType.closing: "Thank-you slide with CTA, logo, and contact details",
}

_ASSET_TYPE_MAP: dict[SlideType, list[AssetType]] = {
    SlideType.title: [AssetType.logo, AssetType.template],
    SlideType.agenda: [AssetType.icon, AssetType.template],
    SlideType.content: [AssetType.icon, AssetType.infographic],
    SlideType.data: [AssetType.chart, AssetType.template],
    SlideType.divider: [AssetType.template],
    SlideType.closing: [AssetType.logo, AssetType.template],
}


def build_plan(parsed: ParsedDeck, allow_restructure: bool) -> list[SlidePlan]:
    """Produce one SlidePlan per parsed slide.

    Parameters
    ----------
    parsed : ParsedDeck
        The structured model from ``parser.parse()``.
    allow_restructure : bool
        When True, the planner may (in the LLM increment) suggest slide
        reordering or consolidation. Here we just attach a note acknowledging
        the flag; no actual restructuring happens.

    Returns
    -------
    list[SlidePlan]
        One plan entry per slide, ordered by slide index.
    """
    plans: list[SlidePlan] = []

    for i, slide in enumerate(parsed.slides):
        slide_type = slide.slide_type
        planned_layout = _LAYOUT_MAP.get(slide_type, "Standard content layout")
        asset_types = _ASSET_TYPE_MAP.get(slide_type, [AssetType.template])

        note: str | None = None
        if allow_restructure:
            note = (
                "Restructuring enabled — the Analyze & Plan LLM may propose "
                "reordering or merging this slide in a future increment."
            )

        plans.append(SlidePlan(
            id=str(uuid.uuid4()),
            index=i,
            slide_type=slide_type,
            planned_layout=planned_layout,
            asset_types=asset_types,
            restructure_note=note,
        ))

    return plans
