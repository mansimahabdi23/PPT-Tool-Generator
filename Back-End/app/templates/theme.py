"""Brand theme injection.

Patches the slide-master's theme XML (fontScheme + clrScheme) in-place using lxml,
since python-pptx has no first-class API for modifying theme parts.

Public API
----------
apply_brand_theme(prs)   -- mutate an existing Presentation in-place
new_presentation()       -- return a blank, branded 16:9 Presentation
"""

from __future__ import annotations

from typing import Any

from lxml import etree  # type: ignore[import-untyped]
from pptx import Presentation
from pptx.util import Emu

from app import brand

# OOXML DrawingML namespace URI
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _clark(local: str) -> str:
    """Return the Clark-notation tag '{namespace}local' for a DrawingML element."""
    return f"{{{_A}}}{local}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _replace_child(parent: Any, new_xml: str) -> None:
    """Replace the first child element matching new_xml's tag with new_xml."""
    new_el = etree.fromstring(new_xml)
    tag = new_el.tag
    for old in parent.findall(tag):
        idx = list(parent).index(old)
        parent.remove(old)
        parent.insert(idx, new_el)
        return
    # Not found — append as fallback (handles malformed theme)
    parent.append(new_el)


def _font_scheme_xml() -> str:
    return f"""<a:fontScheme name="iMocha Brand" xmlns:a="{_A}">
  <a:majorFont>
    <a:latin typeface="{brand.PLAYFAIR}"/>
    <a:ea typeface=""/>
    <a:cs typeface=""/>
  </a:majorFont>
  <a:minorFont>
    <a:latin typeface="{brand.POPPINS}"/>
    <a:ea typeface=""/>
    <a:cs typeface=""/>
  </a:minorFont>
</a:fontScheme>"""


def _color_scheme_xml() -> str:
    b = brand
    return f"""<a:clrScheme name="iMocha 2024" xmlns:a="{_A}">
  <a:dk1><a:srgbClr val="{b.INK}"/></a:dk1>
  <a:lt1><a:srgbClr val="{b.WHITE}"/></a:lt1>
  <a:dk2><a:srgbClr val="{b.BRAND_PURPLE}"/></a:dk2>
  <a:lt2><a:srgbClr val="{b.SURFACE}"/></a:lt2>
  <a:accent1><a:srgbClr val="{b.BRAND_ORANGE}"/></a:accent1>
  <a:accent2><a:srgbClr val="{b.BRAND_ORANGE_DEEP}"/></a:accent2>
  <a:accent3><a:srgbClr val="{b.BRAND_PURPLE_BASE}"/></a:accent3>
  <a:accent4><a:srgbClr val="{b.BRAND_INDIGO}"/></a:accent4>
  <a:accent5><a:srgbClr val="{b.BADGE_FILL}"/></a:accent5>
  <a:accent6><a:srgbClr val="{b.BADGE_TEXT}"/></a:accent6>
  <a:hlink><a:srgbClr val="{b.BRAND_PURPLE}"/></a:hlink>
  <a:folHlink><a:srgbClr val="{b.BRAND_PURPLE_BASE}"/></a:folHlink>
</a:clrScheme>"""


def _patch_theme_part(theme_part: Any) -> None:
    root: Any = etree.fromstring(theme_part.blob)
    fmt_el = root.find(f".//{_clark('fmtScheme')}")
    parent = fmt_el.getparent() if fmt_el is not None else root

    _replace_child(parent, _font_scheme_xml())
    _replace_child(parent, _color_scheme_xml())

    theme_part._blob = etree.tostring(  # type: ignore[import-untyped]
        root, xml_declaration=True, encoding="UTF-8", standalone=True
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_brand_theme(prs: Any) -> None:
    """Inject iMocha brand fonts + color scheme into *prs* slide-master theme."""
    slide_master = prs.slide_master
    for rel in slide_master.part.rels.values():
        if "theme" in rel.reltype.lower():
            _patch_theme_part(rel.target_part)
            break


def new_presentation() -> Any:
    """Return a blank, 16:9 python-pptx Presentation with the iMocha brand theme applied."""
    prs: Any = Presentation()
    prs.slide_width = Emu(brand.SLIDE_WIDTH_EMU)
    prs.slide_height = Emu(brand.SLIDE_HEIGHT_EMU)
    apply_brand_theme(prs)
    return prs
