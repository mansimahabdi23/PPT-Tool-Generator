"""Clone-and-fill composer for body-block slides (template slide 5).

Strategy
--------
1. Deep-copy all shapes from template slide 5 into a new blank slide.
2. Register image part relationships (logo, etc.) in the output package.
3. Replace the title run text in TextBox 5, preserving run formatting.
4. Inject a new body textbox inside Rounded Rectangle 1's bounding box.
5. Overflow: use normAutofit so PowerPoint/LibreOffice shrinks if needed;
   only flag slides that are genuinely extreme (> _EXTREME_OVERFLOW items).

Public API
----------
load_template(path)  -> Presentation
clone_body_block_slide(template_prs, out_prs, title, body_items, slide_number) -> bool
"""

from __future__ import annotations

import logging
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
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_R    = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Body box geometry: Rounded Rectangle 1 bounds with 0.2in (182 880 EMU) inset
#   Rounded Rectangle 1: x=407 306, y=976 393, cx=11 375 996, cy=5 131 799
_PAD = 182_880
_BODY_LEFT   = 407_306  + _PAD          #  590 186 EMU
_BODY_TOP    = 976_393  + _PAD          # 1 159 273 EMU
_BODY_WIDTH  = 11_375_996 - 2 * _PAD   # 11 010 236 EMU
_BODY_HEIGHT = 5_131_799  - 2 * _PAD   #  4 766 039 EMU

# Body font: fixed 12 pt Poppins; normAutofit handles any real overflow in PowerPoint.
_BODY_FONT_PT = 12

# Spacing: 140 % line spacing; 8 pt space_before between bullets.
_LINE_SPACING_PCT = 140_000   # OOXML spcPct val: 140 000 = 140%
_PARA_SPACE_PT    = 8

# Flag slides only when content is genuinely extreme (no layout can hold it).
# Matches _OVERFLOW_FLAG_THRESHOLD in layout_catalog.py.
_EXTREME_OVERFLOW = 12

# Text-body insets (EMU): 0.1 in on all sides; combined with the 0.2 in box
# padding this gives the text ~0.3 in clearance from the rounded-rect edge.
_INSET_EMU = 91_440   # 0.1 in = 91 440 EMU

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


def _style_body_frame(tf: Any) -> None:
    """Apply vertical centering, insets, and normAutofit to a text frame.

    normAutofit tells PowerPoint to shrink the font automatically if the text
    exceeds the box — a reliable native behaviour that replaces the previous
    Python estimation cascade.  The box size stays fixed so the layout is
    always preserved.
    """
    txBody = tf._txBody
    bodyPr = txBody.find(qn("a:bodyPr"))
    if bodyPr is None:
        bodyPr = etree.SubElement(txBody, qn("a:bodyPr"))

    # Vertical centering — text floats in the middle of the 5.21" tall box
    bodyPr.set("anchor", "ctr")
    # Fixed insets (0.1 in all sides; combined with 0.2 in box padding = 0.3 in clearance)
    bodyPr.set("lIns", str(_INSET_EMU))
    bodyPr.set("rIns", str(_INSET_EMU))
    bodyPr.set("tIns", str(_INSET_EMU))
    bodyPr.set("bIns", str(_INSET_EMU))

    # Replace any existing autofit element with normAutofit so PowerPoint
    # shrinks the font natively when the text genuinely overflows the box.
    for tag in (qn("a:noAutofit"), qn("a:normAutofit"), qn("a:spAutoFit")):
        for el in bodyPr.findall(tag):
            bodyPr.remove(el)
    bodyPr.append(
        etree.fromstring(
            f'<a:normAutofit xmlns:a="{_A_NS}"/>'
        )
    )


def _set_para_spacing(para: Any, is_first: bool) -> None:
    """Set 140 % line spacing and paragraph space_before on *para*."""
    para.space_before = Pt(0) if is_first else Pt(_PARA_SPACE_PT)

    pPr = para._p.get_or_add_pPr()
    for old in pPr.findall(qn("a:lnSpc")):
        pPr.remove(old)
    pPr.append(
        etree.fromstring(
            f'<a:lnSpc xmlns:a="{_A_NS}">'
            f'<a:spcPct val="{_LINE_SPACING_PCT}"/>'
            f"</a:lnSpc>"
        )
    )


def _inject_body(slide: Any, body_items: list[str]) -> bool:
    """Add a body textbox to *slide* at the body-box geometry.

    Uses a fixed 12 pt Poppins font with normAutofit so PowerPoint/LibreOffice
    shrinks the text automatically if it genuinely overflows.  Only flags a
    slide when the item count is extreme (> _EXTREME_OVERFLOW), matching the
    plan-stage threshold so the signal is coherent end-to-end.

    Returns True when the slide is flagged for human review.
    """
    overflow_flagged = len(body_items) > _EXTREME_OVERFLOW
    if overflow_flagged:
        logger.warning(
            "clone_body_block: %d items exceeds threshold %d — slide flagged",
            len(body_items), _EXTREME_OVERFLOW,
        )

    txBox = slide.shapes.add_textbox(
        Emu(_BODY_LEFT), Emu(_BODY_TOP), Emu(_BODY_WIDTH), Emu(_BODY_HEIGHT)
    )
    tf = txBox.text_frame
    tf.word_wrap = True
    _style_body_frame(tf)

    for i, item in enumerate(body_items):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        _set_para_spacing(para, is_first=(i == 0))
        run = para.add_run()
        run.text = item
        run.font.name  = brand.POPPINS
        run.font.size  = Pt(_BODY_FONT_PT)
        run.font.color.rgb = RGBColor(0x11, 0x18, 0x27)

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
