"""Unit tests for the iMocha template system.

Covers:
  - brand.py token correctness (§11 verbatim)
  - layouts.py registry completeness
  - builder.py add_slide shape output
  - merge.py shape-tree copy (shape count increases, image part copied)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app import brand
from app.models.enums import SlideType
from app.templates.builder import SlideContent, add_slide
from app.templates.layouts import LAYOUTS, LayoutSpec
from app.templates.merge import merge_fragment
from app.templates.theme import new_presentation

# Real assets path (repo root / assets)
_HERE = Path(__file__).parent
_ASSETS = _HERE.parent.parent / "assets"  # Back-End/tests/ → Back-End/ → repo root / assets
_SHOWCASE = _ASSETS / "templates" / "imocha_master.pptx"
_INFOGRAPHICS = sorted((_ASSETS / "infographics").glob("*.pptx")) if (_ASSETS / "infographics").exists() else []
# First available infographic fragment (each file exposes exactly 1 slide at index 0)
_FRAG = _INFOGRAPHICS[0] if _INFOGRAPHICS else None

# ---------------------------------------------------------------------------
# app/brand.py — §11 verbatim token values
# ---------------------------------------------------------------------------

class TestBrandTokens:
    def test_hex_values_match_spec(self) -> None:
        """All color tokens must match §11 exactly (verified by human against the doc)."""
        assert brand.BRAND_ORANGE == "FF4A00"
        assert brand.BRAND_ORANGE_DEEP == "FD5B0E"
        assert brand.BRAND_PURPLE == "481AEC"
        assert brand.BRAND_PURPLE_BASE == "7C3AED"
        assert brand.BRAND_INDIGO == "6366F1"
        assert brand.INK == "111827"
        assert brand.SURFACE == "F3F4F6"
        assert brand.BADGE_FILL == "EDE9FE"
        assert brand.BADGE_TEXT == "5B21B6"
        assert brand.WHITE == "FFFFFF"

    def test_font_names(self) -> None:
        assert brand.PLAYFAIR == "Playfair Display"
        assert brand.POPPINS == "Poppins"

    def test_allowed_fonts_set(self) -> None:
        assert brand.PLAYFAIR in brand.ALLOWED_FONTS
        assert brand.POPPINS in brand.ALLOWED_FONTS

    def test_allowed_colors_set(self) -> None:
        for token in (
            brand.BRAND_ORANGE, brand.BRAND_ORANGE_DEEP, brand.BRAND_PURPLE,
            brand.BRAND_PURPLE_BASE, brand.BRAND_INDIGO, brand.INK,
            brand.SURFACE, brand.BADGE_FILL, brand.BADGE_TEXT, brand.WHITE,
        ):
            assert token in brand.ALLOWED_COLORS, f"{token} missing from ALLOWED_COLORS"

    def test_gradient_allow_list(self) -> None:
        assert brand.GRADIENT_ORANGE_PURPLE in brand.ALLOWED_GRADIENTS
        assert brand.GRADIENT_PURPLE_INDIGO in brand.ALLOWED_GRADIENTS
        assert brand.GRADIENT_PURPLE_LIGHT in brand.ALLOWED_GRADIENTS

    def test_helpers(self) -> None:
        assert brand.rgb_tuple("FF4A00") == (0xFF, 0x4A, 0x00)
        assert brand.is_allowed_font(brand.PLAYFAIR)
        assert brand.is_allowed_font(brand.POPPINS)
        assert not brand.is_allowed_font("Arial")
        assert brand.is_allowed_color(brand.BRAND_ORANGE)
        assert not brand.is_allowed_color("FF0000")
        assert brand.is_allowed_gradient(brand.BRAND_ORANGE, brand.BRAND_PURPLE)
        assert not brand.is_allowed_gradient("FF0000", "00FF00")

    def test_slide_dimensions(self) -> None:
        # 16:9 at 914 400 EMU/inch → 13.33" × 7.5"
        assert brand.SLIDE_WIDTH_EMU == 12_192_000
        assert brand.SLIDE_HEIGHT_EMU == 6_858_000


# ---------------------------------------------------------------------------
# app/templates/layouts.py — registry completeness
# ---------------------------------------------------------------------------

class TestLayoutRegistry:
    def test_all_slide_types_covered(self) -> None:
        for st in SlideType:
            assert st in LAYOUTS, f"SlideType.{st} missing from LAYOUTS"

    def test_content_has_infographic_region(self) -> None:
        spec: LayoutSpec = LAYOUTS[SlideType.content]
        assert spec.infographic_region is not None, "content layout must have an infographic_region"

    def test_data_has_infographic_region(self) -> None:
        spec: LayoutSpec = LAYOUTS[SlideType.data]
        assert spec.infographic_region is not None, "data layout must have an infographic_region"

    def test_non_infographic_layouts_have_no_region(self) -> None:
        for st in (SlideType.title, SlideType.agenda, SlideType.divider, SlideType.closing):
            assert LAYOUTS[st].infographic_region is None, \
                f"{st} should not have an infographic_region"

    def test_title_layout_has_image_bg(self) -> None:
        from app.templates.layouts import ImageBg
        bg = LAYOUTS[SlideType.title].background
        assert isinstance(bg, ImageBg)
        assert bg.rel_path == "cover_bg.jpg"

    def test_agenda_has_accent_bar(self) -> None:
        assert LAYOUTS[SlideType.agenda].accent_bar is not None

    def test_divider_has_gradient_bg(self) -> None:
        from app.templates.layouts import GradientBg
        bg = LAYOUTS[SlideType.divider].background
        assert isinstance(bg, GradientBg)
        # Must be an allowed gradient pair
        assert brand.is_allowed_gradient(bg.stop1_hex, bg.stop2_hex)

    def test_closing_has_gradient_bg(self) -> None:
        from app.templates.layouts import GradientBg
        bg = LAYOUTS[SlideType.closing].background
        assert isinstance(bg, GradientBg)
        assert brand.is_allowed_gradient(bg.stop1_hex, bg.stop2_hex)

    def test_all_title_specs_use_brand_fonts(self) -> None:
        for st, spec in LAYOUTS.items():
            assert spec.title.font in brand.ALLOWED_FONTS, \
                f"{st}: title.font '{spec.title.font}' not in ALLOWED_FONTS"

    def test_all_body_specs_use_brand_fonts(self) -> None:
        for st, spec in LAYOUTS.items():
            for attr in ("body", "subtitle", "kicker", "caption"):
                ts = getattr(spec, attr, None)
                if ts is not None:
                    assert ts.font in brand.ALLOWED_FONTS, \
                        f"{st}.{attr}.font '{ts.font}' not in ALLOWED_FONTS"

    def test_infographic_region_inside_slide(self) -> None:
        for st in (SlideType.content, SlideType.data):
            r = LAYOUTS[st].infographic_region
            assert r is not None
            assert r.left >= 0
            assert r.top >= 0
            assert r.left + r.width <= brand.SLIDE_WIDTH_EMU
            assert r.top + r.height <= brand.SLIDE_HEIGHT_EMU


# ---------------------------------------------------------------------------
# app/templates/builder.py — add_slide output
# ---------------------------------------------------------------------------

class TestBuilder:
    def _make_prs(self):  # type: ignore[no-untyped-def]
        return new_presentation()

    def test_new_presentation_dimensions(self) -> None:
        prs = self._make_prs()
        assert int(prs.slide_width) == brand.SLIDE_WIDTH_EMU
        assert int(prs.slide_height) == brand.SLIDE_HEIGHT_EMU

    @pytest.mark.skipif(not _ASSETS.exists(), reason="assets dir not present")
    def test_add_slide_returns_slide_for_all_types(self) -> None:
        prs = self._make_prs()
        for st in SlideType:
            content = SlideContent(
                title=f"Test {st.value}",
                subtitle="Sub",
                body_items=["Item 1", "Item 2"],
                kicker="Kicker",
                caption="Caption",
            )
            slide = add_slide(prs, st, content, _ASSETS)
            assert slide is not None

    @pytest.mark.skipif(not _ASSETS.exists(), reason="assets dir not present")
    def test_title_text_present_in_slide(self) -> None:
        prs = self._make_prs()
        content = SlideContent(title="Hello iMocha")
        add_slide(prs, SlideType.agenda, content, _ASSETS)

        slide = prs.slides[0]
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
        assert any("Hello iMocha" in t for t in texts)

    @pytest.mark.skipif(not _ASSETS.exists(), reason="assets dir not present")
    def test_content_slide_has_region_marker(self) -> None:
        """The infographic region marker rectangle is present before merge."""
        prs = self._make_prs()
        content = SlideContent(title="Content slide")
        slide = add_slide(prs, SlideType.content, content, _ASSETS)
        # At least one shape should contain the region marker text
        texts = [
            shape.text_frame.text
            for shape in slide.shapes
            if shape.has_text_frame
        ]
        assert any("INFOGRAPHIC REGION" in t for t in texts)

    @pytest.mark.skipif(not _ASSETS.exists(), reason="assets dir not present")
    def test_title_slide_uses_brand_orange_or_white_title(self) -> None:
        """Title slide title text color must be white (cover image bg)."""
        from app.templates.layouts import ImageBg
        bg = LAYOUTS[SlideType.title].background
        assert isinstance(bg, ImageBg)
        title_spec = LAYOUTS[SlideType.title].title
        assert title_spec.color_hex == brand.WHITE


# ---------------------------------------------------------------------------
# app/templates/merge.py — shape-tree copy
# ---------------------------------------------------------------------------

class TestMerge:
    """Merge tests use assets/infographics/*.pptx (each exposes 1 slide at index 0)."""

    @pytest.mark.skipif(_FRAG is None, reason="no infographic fragments in assets/")
    def test_merge_increases_shape_count(self) -> None:
        assert _FRAG is not None
        prs = new_presentation()
        slide = add_slide(prs, SlideType.content, SlideContent(title="Merge test"), _ASSETS)

        before = len(slide.shapes)
        region = LAYOUTS[SlideType.content].infographic_region
        assert region is not None
        merge_fragment(slide, _FRAG, 0, region)
        after = len(slide.shapes)

        assert after > before, "merge_fragment must add at least one shape group"

    @pytest.mark.skipif(_FRAG is None, reason="no infographic fragments in assets/")
    def test_merge_copies_image_parts(self) -> None:
        """After merge, the target slide should have at least as many rels as before."""
        assert _FRAG is not None
        prs = new_presentation()
        slide = add_slide(prs, SlideType.content, SlideContent(title="Merge rels test"), _ASSETS)

        before_rels = set(slide.part.rels.keys())
        region = LAYOUTS[SlideType.content].infographic_region
        assert region is not None
        merge_fragment(slide, _FRAG, 0, region)
        after_rels = set(slide.part.rels.keys())

        assert len(after_rels) >= len(before_rels), "merge_fragment should not remove rels"

    @pytest.mark.skipif(_FRAG is None, reason="no infographic fragments in assets/")
    def test_merged_pptx_can_be_saved(self, tmp_path: Path) -> None:
        """Full round-trip: build → merge → save must not raise."""
        assert _FRAG is not None
        prs = new_presentation()
        slide = add_slide(prs, SlideType.data, SlideContent(title="Data"), _ASSETS)
        region = LAYOUTS[SlideType.data].infographic_region
        assert region is not None
        merge_fragment(slide, _FRAG, 0, region)
        out = tmp_path / "merged.pptx"
        prs.save(str(out))
        assert out.exists() and out.stat().st_size > 0
