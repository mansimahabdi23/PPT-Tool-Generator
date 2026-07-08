"""Deterministic PPTX parser — no AI.

Extracts title + body text from each slide and assigns a SlideType via a
simple heuristic. The AI Analyze & Plan agent (Step 5) will replace the
heuristic with genuine understanding; this code only needs to work well
enough for the walking skeleton.

Public API
----------
ParsedSlide  -- per-slide extracted data
ParsedDeck   -- collection of ParsedSlide + deck metadata
parse(pptx_path, deck_name) -> ParsedDeck
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pptx import Presentation
from pptx.util import Pt

from app.models.enums import SlideType


@dataclass
class ParsedSlide:
    index: int               # 0-based
    title: str
    body_items: list[str]
    slide_type: SlideType


@dataclass
class ParsedDeck:
    name: str                # original filename (used as deck display name)
    slides: list[ParsedSlide] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_title(slide: object) -> str:
    """Return the title placeholder text, or the first large-font text found."""
    # Try the named title placeholder first (idx 0)
    for shape in slide.shapes:  # type: ignore[attr-defined]
        if shape.has_text_frame and shape.is_placeholder:
            try:
                if shape.placeholder_format.idx == 0:
                    return shape.text_frame.text.strip()
            except (ValueError, AttributeError):
                pass

    # Fallback: largest font size text block
    best_text = ""
    best_size = 0.0
    for shape in slide.shapes:  # type: ignore[attr-defined]
        if not shape.has_text_frame:
            continue
        text = shape.text_frame.text.strip()
        if not text:
            continue
        # Estimate size from first run
        try:
            size = shape.text_frame.paragraphs[0].runs[0].font.size or Pt(0)
            size_pt = size.pt
        except (IndexError, AttributeError):
            size_pt = 0.0
        if size_pt > best_size:
            best_size = size_pt
            best_text = text
    return best_text


def _extract_body(slide: object, title_text: str) -> list[str]:
    """Return non-empty paragraph texts, excluding the title block."""
    body_items: list[str] = []
    for shape in slide.shapes:  # type: ignore[attr-defined]
        if not shape.has_text_frame:
            continue
        block_text = shape.text_frame.text.strip()
        if not block_text or block_text == title_text:
            continue
        for para in shape.text_frame.paragraphs:
            line = para.text.strip()
            if line:
                body_items.append(line)
    return body_items


def _assign_type(
    index: int,
    last_index: int,
    title: str,
    body_items: list[str],
) -> SlideType:
    """Heuristic slide-type assignment — deterministic, no AI."""
    if index == 0:
        return SlideType.title
    if index == last_index:
        return SlideType.closing
    if "agenda" in title.lower():
        return SlideType.agenda
    if not body_items:
        return SlideType.divider
    return SlideType.content


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(pptx_path: Path, deck_name: str) -> ParsedDeck:
    """Open *pptx_path* with python-pptx and return a ParsedDeck.

    Parameters
    ----------
    pptx_path : path to the source .pptx file
    deck_name : display name for the deck (typically the original filename)
    """
    prs = Presentation(str(pptx_path))
    slides = prs.slides
    last = len(slides) - 1

    parsed_slides: list[ParsedSlide] = []
    for i, slide in enumerate(slides):
        title = _extract_title(slide)
        body = _extract_body(slide, title)
        slide_type = _assign_type(i, last, title, body)
        parsed_slides.append(ParsedSlide(index=i, title=title, body_items=body, slide_type=slide_type))

    return ParsedDeck(name=deck_name, slides=parsed_slides)
