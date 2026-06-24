"""Layout registry — code-defined specs for every iMocha slide type.

Each LayoutSpec describes geometry, typography, background, logo placement, and
(for content/data layouts) the infographic merge region that merge.py targets.
Geometry is in EMU; fonts/colors reference app.brand constants.

All six SlideType values are covered:
  title · agenda · content · data · divider · closing
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app import brand
from app.models.enums import SlideType

# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Rect:
    """An axis-aligned rectangle in EMU coordinates."""

    left: int
    top: int
    width: int
    height: int


# ---------------------------------------------------------------------------
# Background variants
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SolidBg:
    kind: Literal["solid"] = "solid"
    color_hex: str = brand.WHITE


@dataclass(frozen=True)
class GradientBg:
    """Linear two-stop gradient.

    ``angle`` is OOXML lin angle in 1/60 000 degrees:
      0         = horizontal, left → right
      5 400 000 = vertical,   top → bottom  (90°)
    """

    kind: Literal["gradient"] = "gradient"
    stop1_hex: str = brand.BRAND_PURPLE
    stop2_hex: str = brand.BRAND_INDIGO
    angle: int = 0  # horizontal


@dataclass(frozen=True)
class ImageBg:
    """Full-bleed raster image stretched to slide size."""

    kind: Literal["image"] = "image"
    rel_path: str = ""  # relative to assets_root


Background = SolidBg | GradientBg | ImageBg

# ---------------------------------------------------------------------------
# Text region
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TextSpec:
    rect: Rect
    font: str
    size_pt: int
    color_hex: str
    bold: bool = False


# ---------------------------------------------------------------------------
# Layout specification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LayoutSpec:
    """Complete visual spec for one slide type.

    Fields
    ------
    background       : how to fill the slide canvas
    title            : primary heading text region
    body             : optional multi-line body / bullet text region
    subtitle         : optional secondary line below title (title layout)
    kicker           : optional superscript-style label (divider layout)
    caption          : optional small note below infographic (data layout)
    accent_bar       : optional solid orange bar (agenda layout)
    logo_rel_path    : rel_path from assets_root; "" = no logo
    logo_rect        : bounding rect for the logo picture
    infographic_region : EMU rect that merge.py deep-copies fragments into;
                         None for layouts that don't host infographics
    """

    background: Background
    title: TextSpec
    body: TextSpec | None = None
    subtitle: TextSpec | None = None
    kicker: TextSpec | None = None
    caption: TextSpec | None = None
    accent_bar: Rect | None = None
    logo_rel_path: str = ""
    logo_rect: Rect | None = None
    infographic_region: Rect | None = None


# ---------------------------------------------------------------------------
# Shared constants  (EMU unless noted)
# ---------------------------------------------------------------------------
W = brand.SLIDE_WIDTH_EMU   # 12 192 000
H = brand.SLIDE_HEIGHT_EMU  # 6 858 000

_MARGIN = 457_200            # 0.5"
_TITLE_H = 685_800           # 0.75"
_LOGO_H = 342_900            # 0.375"
_FOOTER_TOP = H - _LOGO_H - _MARGIN // 2   # bottom strip baseline
_BODY_TOP = _MARGIN + _TITLE_H + 114_300   # just below title
_BODY_H = H - _BODY_TOP - _LOGO_H - _MARGIN

# ---------------------------------------------------------------------------
# The six layouts
# ---------------------------------------------------------------------------

def _layouts() -> dict[SlideType, LayoutSpec]:  # noqa: PLR0914  (complex but readable)
    # ------------------------------------------------------------------
    # 1. TITLE — full-bleed cover image, Playfair title, Poppins subtitle
    # ------------------------------------------------------------------
    title_layout = LayoutSpec(
        background=ImageBg(rel_path="cover_bg.jpg"),
        title=TextSpec(
            rect=Rect(left=1_143_000, top=2_400_300, width=9_906_000, height=1_371_600),
            font=brand.PLAYFAIR,
            size_pt=34,
            color_hex=brand.WHITE,
        ),
        subtitle=TextSpec(
            rect=Rect(left=1_143_000, top=3_885_900, width=9_906_000, height=685_800),
            font=brand.POPPINS,
            size_pt=18,
            color_hex=brand.WHITE,
        ),
        logo_rel_path="logo/logo_white.png",
        logo_rect=Rect(left=_MARGIN, top=H - _LOGO_H - _MARGIN, width=0, height=_LOGO_H),
    )

    # ------------------------------------------------------------------
    # 2. AGENDA — white bg, orange accent bar, numbered list
    # ------------------------------------------------------------------
    agenda_layout = LayoutSpec(
        background=SolidBg(color_hex=brand.WHITE),
        title=TextSpec(
            rect=Rect(left=685_800, top=_MARGIN, width=10_963_200, height=_TITLE_H),
            font=brand.PLAYFAIR,
            size_pt=32,
            color_hex=brand.BRAND_ORANGE,
        ),
        body=TextSpec(
            rect=Rect(left=685_800, top=_BODY_TOP, width=10_963_200, height=_BODY_H),
            font=brand.POPPINS,
            size_pt=12,
            color_hex=brand.INK,
        ),
        accent_bar=Rect(left=0, top=0, width=228_600, height=H),
        logo_rel_path="logo_footer.png",
        logo_rect=Rect(left=_MARGIN, top=_FOOTER_TOP, width=0, height=_LOGO_H),
    )

    # ------------------------------------------------------------------
    # 3. CONTENT — left text column, right infographic region
    # ------------------------------------------------------------------
    _content_col_w = (W - _MARGIN * 3) // 2   # ~5 638 800 EMU each side

    content_layout = LayoutSpec(
        background=SolidBg(color_hex=brand.WHITE),
        title=TextSpec(
            rect=Rect(left=_MARGIN, top=228_600, width=W - _MARGIN * 2, height=_TITLE_H),
            font=brand.PLAYFAIR,
            size_pt=30,
            color_hex=brand.INK,
        ),
        body=TextSpec(
            rect=Rect(left=_MARGIN, top=_BODY_TOP, width=_content_col_w, height=_BODY_H),
            font=brand.POPPINS,
            size_pt=11,
            color_hex=brand.INK,
        ),
        logo_rel_path="logo_footer.png",
        logo_rect=Rect(left=_MARGIN, top=_FOOTER_TOP, width=0, height=_LOGO_H),
        infographic_region=Rect(
            left=_MARGIN * 2 + _content_col_w,
            top=_BODY_TOP,
            width=_content_col_w,
            height=_BODY_H,
        ),
    )

    # ------------------------------------------------------------------
    # 4. DATA — surface background, large infographic region, caption
    # ------------------------------------------------------------------
    _data_infographic_h = H - _BODY_TOP - _LOGO_H - _MARGIN * 2 - 457_200

    data_layout = LayoutSpec(
        background=SolidBg(color_hex=brand.SURFACE),
        title=TextSpec(
            rect=Rect(left=_MARGIN, top=228_600, width=W - _MARGIN * 2, height=_TITLE_H),
            font=brand.PLAYFAIR,
            size_pt=30,
            color_hex=brand.BRAND_ORANGE,
        ),
        caption=TextSpec(
            rect=Rect(
                left=_MARGIN,
                top=_BODY_TOP + _data_infographic_h + _MARGIN // 2,
                width=W - _MARGIN * 2,
                height=_LOGO_H,
            ),
            font=brand.POPPINS,
            size_pt=10,
            color_hex=brand.INK,
        ),
        logo_rel_path="logo_footer.png",
        logo_rect=Rect(left=_MARGIN, top=_FOOTER_TOP, width=0, height=_LOGO_H),
        infographic_region=Rect(
            left=_MARGIN,
            top=_BODY_TOP,
            width=W - _MARGIN * 2,
            height=_data_infographic_h,
        ),
    )

    # ------------------------------------------------------------------
    # 5. DIVIDER — purple→indigo gradient, centered section title + kicker
    # ------------------------------------------------------------------
    divider_layout = LayoutSpec(
        background=GradientBg(
            stop1_hex=brand.BRAND_PURPLE,
            stop2_hex=brand.BRAND_INDIGO,
            angle=0,  # horizontal L→R
        ),
        title=TextSpec(
            rect=Rect(left=1_143_000, top=2_286_000, width=9_906_000, height=1_371_600),
            font=brand.PLAYFAIR,
            size_pt=34,
            color_hex=brand.WHITE,
        ),
        kicker=TextSpec(
            rect=Rect(left=1_143_000, top=3_771_900, width=9_906_000, height=685_800),
            font=brand.POPPINS,
            size_pt=16,
            color_hex=brand.WHITE,
        ),
        logo_rel_path="logo/logo_white.png",
        logo_rect=Rect(left=_MARGIN, top=H - _LOGO_H - _MARGIN, width=0, height=_LOGO_H),
    )

    # ------------------------------------------------------------------
    # 6. CLOSING — orange→purple gradient, Thank you + contact
    # ------------------------------------------------------------------
    closing_layout = LayoutSpec(
        background=GradientBg(
            stop1_hex=brand.BRAND_ORANGE,
            stop2_hex=brand.BRAND_PURPLE,
            angle=5_400_000,  # vertical top→bottom
        ),
        title=TextSpec(
            rect=Rect(left=1_143_000, top=2_057_400, width=9_906_000, height=1_371_600),
            font=brand.PLAYFAIR,
            size_pt=34,
            color_hex=brand.WHITE,
        ),
        subtitle=TextSpec(
            rect=Rect(left=1_143_000, top=3_542_700, width=9_906_000, height=685_800),
            font=brand.POPPINS,
            size_pt=14,
            color_hex=brand.WHITE,
        ),
        logo_rel_path="logo/logo_white.png",
        logo_rect=Rect(left=_MARGIN, top=H - _LOGO_H - _MARGIN, width=0, height=_LOGO_H),
    )

    return {
        SlideType.title: title_layout,
        SlideType.agenda: agenda_layout,
        SlideType.content: content_layout,
        SlideType.data: data_layout,
        SlideType.divider: divider_layout,
        SlideType.closing: closing_layout,
    }


LAYOUTS: dict[SlideType, LayoutSpec] = _layouts()
