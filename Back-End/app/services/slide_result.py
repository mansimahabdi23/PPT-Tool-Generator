"""Build TransformedSlide[] from pipeline results.

Converts the structured parser/validator output into the wire model that the
frontend's review screen displays per slide.

Preview URLs are populated by the caller (pipeline.py) after render_previews()
runs.  An empty string means the PNG was not rendered (tools unavailable);
the frontend shows "preview unavailable" in that case.
"""

from __future__ import annotations

import uuid

from app.models.enums import ApprovalState, SlideTheme
from app.models.job import SlidePlan, TransformedSlide
from app.services.content_diff import ContentDiffResult
from app.services.parser import ParsedDeck


def build_slides(
    parsed: ParsedDeck,
    plan: list[SlidePlan],
    content_result: ContentDiffResult,
    original_preview_urls: list[str] | None = None,
    transformed_preview_urls: list[str] | None = None,
    flagged_indices: set[int] | None = None,
    retry_count: int = 0,
    infographic_indices: set[int] | None = None,
    slide_themes: dict[int, str] | None = None,
) -> list[TransformedSlide]:
    """Build one TransformedSlide per parsed slide.

    Parameters
    ----------
    parsed : ParsedDeck
        The source deck model (one entry per original slide).
    plan : list[SlidePlan]
        The approved plan — used to surface restructure_note and to detect
        when the LLM reclassified a slide (Reclassified chip).
    content_result : ContentDiffResult
        Result of content_diff.diff() — used to determine per-slide claim
        preservation.
    original_preview_urls : list[str] | None
        Per-slide preview URLs for the original deck, indexed by slide
        position.  Empty string means the PNG was not rendered.
    transformed_preview_urls : list[str] | None
        Per-slide preview URLs for the transformed deck, indexed by slide
        position.  Empty string means the PNG was not rendered.
    flagged_indices : set[int] | None
        Slide indices that the validate gate could not fix after max retries.
        Those slides get ``approval = "flagged"``.
    retry_count : int
        Number of compose→validate cycles executed (0 = passed first try).
    """
    flagged = flagged_indices or set()
    infographics = infographic_indices or set()
    themes = slide_themes or {}
    global_content_ok = content_result.passed

    plan_by_index = {p.index: p for p in plan}

    slides: list[TransformedSlide] = []

    for i, ps in enumerate(parsed.slides):
        plan_entry = plan_by_index.get(i)

        chips: list[str] = ["Rebranded", "Reformatted"]

        if plan_entry is not None and plan_entry.slide_type != ps.slide_type:
            chips.append("Reclassified")

        if not global_content_ok:
            chips.append("Content check failed")

        approval: ApprovalState = (
            ApprovalState.flagged if i in flagged else ApprovalState.pending
        )

        orig_url = (
            original_preview_urls[i]
            if original_preview_urls and i < len(original_preview_urls)
            else ""
        )
        trans_url = (
            transformed_preview_urls[i]
            if transformed_preview_urls and i < len(transformed_preview_urls)
            else ""
        )

        # Theme toggle is available only on body-block non-infographic slides.
        # Cover (title type) and infographic slides are always rendered from their
        # fixed template/fragment layouts so the toggle is disabled for them.
        layout_category = plan_entry.layout_category if plan_entry else None
        slide_type_val = plan_entry.slide_type if plan_entry else ps.slide_type
        from app.models.enums import SlideType
        theme_toggleable = (
            layout_category == "body-block"
            and i not in infographics
            and slide_type_val != SlideType.title
        )

        theme_str = themes.get(i, "light")
        slide_theme = SlideTheme.dark if theme_str == "dark" else SlideTheme.light

        slides.append(TransformedSlide(
            id=str(uuid.uuid4()),
            index=i,
            original_preview_url=orig_url,
            transformed_preview_url=trans_url,
            content_unchanged=global_content_ok,
            restructure_note=plan_entry.restructure_note if plan_entry else None,
            change_chips=chips,
            approval=approval,
            retry_count=retry_count,
            theme=slide_theme,
            theme_toggleable=theme_toggleable,
        ))

    return slides
