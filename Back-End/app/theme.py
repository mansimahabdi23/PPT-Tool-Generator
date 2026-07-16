"""Per-slide light/dark theme palettes.

Two palettes — LIGHT (default) and DARK — match the color mapping in the
iMocha About_Us reference slides.

Both palettes preserve:
  - Title orange  #FF4A00  (inherited from template run formatting)
  - Logo images              (unchanged template assets)
  - Cover / closing slides   (always rendered from their dark template slides)

Use get_palette(theme_str) to resolve "light"/"dark" → ThemePalette.
"""

from __future__ import annotations

from dataclasses import dataclass

from app import brand


@dataclass(frozen=True)
class ThemePalette:
    """Color tokens applied per-slide during clone-and-fill rendering."""

    bg: str          # slide background (hex6, no #)
    body_text: str   # body bullet text color
    icon_tile: str   # backing rounded-rect color behind icon PNG
    panel_fill: str  # content-area rounded-rect (body panel) fill


# LIGHT — white background, dark text, light-purple content panel
LIGHT = ThemePalette(
    bg=brand.WHITE,        # FFFFFF
    body_text=brand.INK,   # 111827
    icon_tile=brand.WHITE, # FFFFFF — white tile so icon reads on white bg
    panel_fill="EAE7F2",   # light lavender panel (About_Us light reference)
)

# DARK — deep brand-purple background, near-white text, darker panel
DARK = ThemePalette(
    bg="1E0B2E",           # deep purple-blue (#210032 family)
    body_text="E7E1F6",    # near-white lavender
    icon_tile="2D0F4E",    # dark-purple tile — icon readable on dark bg
    panel_fill="2D0F4E",   # dark translucent-purple content panel
)


def get_palette(theme: str) -> ThemePalette:
    """Return DARK for 'dark', LIGHT for everything else."""
    return DARK if theme == "dark" else LIGHT
