"""Build TransformedSlide[] from pipeline results.

Converts the structured parser/validator output into the wire model that the
frontend's review screen displays per slide.

Preview URLs are placeholders in this increment. Real per-slide PNGs require
LibreOffice PDF→PNG splitting, which is a follow-up task.
"""

from __future__ import annotations

import uuid

from app.models.enums import ApprovalState
from app.models.job import TransformedSlide
from app.services.content_diff import ContentDiffResult
from app.services.parser import ParsedDeck


def build_slides(
    parsed: ParsedDeck,
    content_result: ContentDiffResult,
    flagged_indices: set[int] | None = None,
    retry_count: int = 0,
) -> list[TransformedSlide]:
    """Build one TransformedSlide per parsed slide.

    Parameters
    ----------
    parsed : ParsedDeck
        The source deck model (one entry per original slide).
    content_result : ContentDiffResult
        Result of content_diff.diff() — used to determine per-slide claim
        preservation. We approximate: if a slide's claims are all in the global
        preserved set we mark it unchanged, otherwise not.
    flagged_indices : set[int] | None
        Slide indices that the validate gate could not fix after max retries.
        Those slides get ``approval = "flagged"``.
    retry_count : int
        The number of compose→validate cycles that were executed (0 = passed
        on first try).

    Returns
    -------
    list[TransformedSlide]
        One entry per source slide, ordered by index.

    Notes
    -----
    Per-slide claim fidelity is approximated at a global level this increment
    (the content_diff computes a single blob, not per-slide fidelity).
    Per-slide analysis is a follow-up when the LLM Compose stage lands.
    """
    flagged = flagged_indices or set()
    # Approximate: if overall content passed, all slides are unchanged.
    global_content_ok = content_result.passed

    slides: list[TransformedSlide] = []

    for i, ps in enumerate(parsed.slides):
        # Derive change chips from what the builder does deterministically.
        chips: list[str] = ["Rebranded", "Reformatted"]
        if not global_content_ok:
            chips.append("Content check failed")

        approval: ApprovalState
        if i in flagged:
            approval = ApprovalState.flagged
        else:
            approval = ApprovalState.pending

        # Placeholder preview URLs — real LibreOffice rendering is a follow-up.
        placeholder_base = "https://placehold.co/640x360/481aec/ffffff"
        slide_label = f"Slide {i + 1}"
        preview_url = f"{placeholder_base}?text={slide_label}&font=poppins"

        slides.append(TransformedSlide(
            id=str(uuid.uuid4()),
            index=i,
            original_preview_url=preview_url,
            transformed_preview_url=preview_url,
            content_unchanged=global_content_ok,
            restructure_note=None,
            change_chips=chips,
            approval=approval,
            retry_count=retry_count,
        ))

    return slides
