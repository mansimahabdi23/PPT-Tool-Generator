"""Clone-and-fill composer for body-block slides (template slide 5).

Strategy
--------
1. Deep-copy all shapes from template slide 5 into a new blank slide.
2. Register image part relationships (logo, etc.) in the output package.
3. Replace the title run text in TextBox 5, preserving run formatting.
4. Inject a new body textbox inside Rounded Rectangle 1's bounding box.
5. Overflow: shrink 12 pt → 11 pt → 10 pt; flag if still overflowing.

Public API
----------
load_template(path)  -> Presentation
clone_body_block_slide(template_prs, out_prs, title, body_items, slide_number) -> bool
"""

from __future__ import annotations

import logging
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from lxml import etree  # type: ignore[import-untyped]
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from app import brand

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Template slide 5 → 0-based index 4 in the template PPTX
_TEMPLATE_SLIDE_IDX = 4

# OOXML namespace URIs
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Body box geometry: Rounded Rectangle 1 bounds with 0.2in (182 880 EMU) inset
#   Rounded Rectangle 1: x=407 306, y=976 393, cx=11 375 996, cy=5 131 799
_PAD = 182_880
_BODY_LEFT   = 407_306  + _PAD          #  590 186 EMU
_BODY_TOP    = 976_393  + _PAD          # 1 159 273 EMU
_BODY_WIDTH  = 11_375_996 - 2 * _PAD   # 11 010 236 EMU
_BODY_HEIGHT = 5_131_799  - 2 * _PAD   #  4 766 039 EMU

# Font-size cascade (pt) — try largest first; shrink if text overflows box
_FONT_CASCADE = (12, 11, 10)

# Overflow estimation parameters
_LINE_SPACING  = 1.35   # multiplier over font size
_PARA_SPACE_PT = 4.0    # space_before between bullets (pt)
_CHAR_W_RATIO  = 0.55   # avg Poppins char width = font_pt × ratio

# spTree structural tags — never copied or removed by mistake
_STRUCT_TAGS = {qn("p:nvGrpSpPr"), qn("p:grpSpPr")}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _next_shape_id(sp_tree: Any) -> int:
    """Return the next unused shape id (max existing + 1)."""
    ids = [int(el.get("id", 0)) for el in sp_tree.iter() if el.get("id") is not None]
    return (max(ids) if ids else 0) + 1


def _register_image_rels(src_slide: Any, target_slide: Any, tree_el: Any) -> None:
    """Rewrite r:embed / r:link attributes in *tree_el* to reference parts
    that exist in *target_slide*'s package.  Same two-pass strategy as merge.py."""
    embed_attr = f"{{{_R}}}embed"
    link_attr  = f"{{{_R}}}link"
    rId_map: dict[str, str] = {}

    for el in tree_el.iter():
        for attr in (embed_attr, link_attr):
            old = el.get(attr)
            if old and old not in rId_map:
                try:
                    rel = src_slide.part.rels[old]
                    rId_map[old] = target_slide.part.relate_to(rel.target_part, rel.reltype)
                except (KeyError, AttributeError):
                    pass  # unknown rel — PowerPoint will repair

    for el in tree_el.iter():
        for attr in (embed_attr, link_attr):
            old = el.get(attr)
            if old and old in rId_map:
                el.set(attr, rId_map[old])


def _replace_title(sp_tree: Any, new_title: str) -> bool:
    """Find 'TextBox 5' in *sp_tree* and replace its first run text.

    Edits the <a:r><a:t> node directly (not text_frame.text) so all run-level
    formatting (font, size, color) is preserved from the template.  Any extra
    runs in the same paragraph are removed to avoid leftover placeholder text.

    Returns True on success.
    """
    for sp in sp_tree.findall(f'.//{qn("p:sp")}'):
        cNvPr = sp.find(f'.//{qn("p:cNvPr")}')
        if cNvPr is None or cNvPr.get("name") != "TextBox 5":
            continue
        runs = sp.findall(f'.//{qn("a:r")}')
        if not runs:
            continue
        t_el = runs[0].find(qn("a:t"))
        if t_el is not None:
            t_el.text = new_title
        # Remove any extra runs in the same paragraph
        first_para = runs[0].getparent()
        for extra in runs[1:]:
            if extra.getparent() is first_para:
                first_para.remove(extra)
        return True
    return False


def _update_slide_number(sp_tree: Any, slide_number: int) -> None:
    """Update the cached display text of the <a:fld type="slidenum"> element."""
    for fld in sp_tree.findall(f'.//{qn("a:fld")}'):
        if fld.get("type") == "slidenum":
            t_el = fld.find(qn("a:t"))
            if t_el is not None:
                t_el.text = str(slide_number)
            return


def _overflows(items: list[str], font_pt: float) -> bool:
    """Estimate whether *items* exceed the body box at *font_pt*."""
    width_pt  = _BODY_WIDTH  / 12_700   # EMU → pt (12 700 EMU = 1 pt)
    height_pt = _BODY_HEIGHT / 12_700

    chars_per_line = max(1.0, width_pt / (font_pt * _CHAR_W_RATIO))
    line_ht_pt     = font_pt * _LINE_SPACING
    lines_avail    = height_pt / line_ht_pt

    lines_used = 0.0
    for i, item in enumerate(items):
        lines_used += max(1.0, math.ceil(len(item) / chars_per_line))
        if i > 0:
            lines_used += _PARA_SPACE_PT / line_ht_pt

    return lines_used > lines_avail


def _inject_body(slide: Any, body_items: list[str]) -> bool:
    """Add a body textbox to *slide* at the body-box geometry.

    Tries each font size in _FONT_CASCADE (12 → 11 → 10 pt).  If even 10 pt
    overflows, renders at 10 pt and returns True (overflow_flagged).
    """
    chosen_pt = _FONT_CASCADE[-1]  # default to minimum if nothing fits
    overflow_flagged = True

    for pt in _FONT_CASCADE:
        if not _overflows(body_items, float(pt)):
            chosen_pt = pt
            overflow_flagged = False
            break

    txBox = slide.shapes.add_textbox(
        Emu(_BODY_LEFT), Emu(_BODY_TOP), Emu(_BODY_WIDTH), Emu(_BODY_HEIGHT)
    )
    tf = txBox.text_frame
    tf.word_wrap = True

    for i, item in enumerate(body_items):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.space_before = Pt(0) if i == 0 else Pt(4)
        run = para.add_run()
        run.text = item
        run.font.name  = brand.POPPINS
        run.font.size  = Pt(chosen_pt)
        run.font.color.rgb = RGBColor(0x11, 0x18, 0x27)

    if overflow_flagged:
        logger.warning(
            "clone_body_block: %d items overflow at %d pt — slide flagged",
            len(body_items), _FONT_CASCADE[-1],
        )

    return overflow_flagged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_template(path: Path) -> Any:
    """Open the iMocha template PPTX and return a python-pptx Presentation.

    Call once per compose run and pass the result to clone_body_block_slide
    for every body-block slide to avoid repeated file I/O.
    """
    return Presentation(str(path))


def clone_body_block_slide(
    template_prs: Any,
    out_prs: Any,
    title: str,
    body_items: list[str],
    slide_number: int,
) -> bool:
    """Clone template slide 5 into *out_prs* and fill with content.

    Parameters
    ----------
    template_prs : Presentation loaded by load_template()
    out_prs      : output Presentation to append the cloned slide to
    title        : slide title (replaces '<Slide Title>' in TextBox 5)
    body_items   : bullet / body lines to inject inside the content box
    slide_number : 1-based output slide number (updates slidenum field)

    Returns
    -------
    bool — True when content still overflows at minimum font size (10 pt);
            the slide is rendered at 10 pt and should be flagged for review.
    """
    tmpl_slide: Any = template_prs.slides[_TEMPLATE_SLIDE_IDX]

    # ---- add a blank slide ----
    blank_layout = out_prs.slide_layouts[6]
    new_slide: Any = out_prs.slides.add_slide(blank_layout)

    src_cSld   = tmpl_slide.element.find(qn("p:cSld"))
    src_spTree = src_cSld.find(qn("p:spTree"))
    tgt_spTree = new_slide.shapes._spTree

    # Clear any shapes the blank layout inserted (keep structural nvGrpSpPr / grpSpPr)
    for child in list(tgt_spTree):
        if child.tag not in _STRUCT_TAGS:
            tgt_spTree.remove(child)

    # ---- deep-copy template shapes ----
    # Renumber ids while copying to guarantee uniqueness in the output package.
    start_id = _next_shape_id(tgt_spTree)
    counter  = start_id
    for child in src_spTree:
        if child.tag in _STRUCT_TAGS:
            continue
        copied = deepcopy(child)
        for el in copied.iter():
            if el.get("id") is not None:
                el.set("id", str(counter))
                counter += 1
        tgt_spTree.append(copied)

    # ---- register image relationships (logo, etc.) ----
    _register_image_rels(tmpl_slide, new_slide, tgt_spTree)

    # ---- fill title (preserves run formatting from template) ----
    if not _replace_title(tgt_spTree, title):
        logger.warning("clone_body_block: TextBox 5 not found — title not set")

    # ---- update cached page-number display ----
    _update_slide_number(tgt_spTree, slide_number)

    # ---- inject body textbox with overflow handling ----
    return _inject_body(new_slide, body_items)
