"""Brand tokens — the §11 allow-list.

Single source of truth shared by:
  - app/templates/*  (slide construction)
  - app/services/brand_lint.py  (future deterministic linter)

Pure Python — no presentation-framework imports. Keep it that way.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Slide canvas (16:9, 13.33" × 7.5" at 914 400 EMU/inch)
# ---------------------------------------------------------------------------
SLIDE_WIDTH_EMU: int = 12_192_000
SLIDE_HEIGHT_EMU: int = 6_858_000

# ---------------------------------------------------------------------------
# Typography (§11)
# ---------------------------------------------------------------------------
PLAYFAIR: str = "Playfair Display"  # titles: 30–34 pt, brand-orange, regular weight
POPPINS: str = "Poppins"  # body: 10–12 pt, ink

TITLE_PT: int = 32  # nominal title (layouts may use 30–34; override where needed)
BODY_PT: int = 11  # nominal body  (layouts may use 10–12; override where needed)

# ---------------------------------------------------------------------------
# Color tokens — 6-char UPPERCASE hex, no "#" (§11 verbatim)
# ---------------------------------------------------------------------------
BRAND_ORANGE: str = "FF4A00"  # primary accent, titles
BRAND_ORANGE_DEEP: str = "FD5B0E"  # CTAs, highlights
BRAND_PURPLE: str = "481AEC"  # secondary accent, diagrams
BRAND_PURPLE_BASE: str = "7C3AED"  # secondary surfaces
BRAND_PURPLE_LIGHT: str = "826FFF"  # template decorative fill (rounded rectangle at 10% opacity)
BRAND_INDIGO: str = "6366F1"  # gradient partner
INK: str = "111827"  # text, dark surfaces
SURFACE: str = "F3F4F6"  # light surfaces
BADGE_FILL: str = "EDE9FE"  # pills/badges fill
BADGE_TEXT: str = "5B21B6"  # pills/badges text
WHITE: str = "FFFFFF"  # base background

ALLOWED_FONTS: frozenset[str] = frozenset({PLAYFAIR, POPPINS})

ALLOWED_COLORS: frozenset[str] = frozenset(
    {
        BRAND_ORANGE,
        BRAND_ORANGE_DEEP,
        BRAND_PURPLE,
        BRAND_PURPLE_BASE,
        BRAND_PURPLE_LIGHT,
        BRAND_INDIGO,
        INK,
        SURFACE,
        BADGE_FILL,
        BADGE_TEXT,
        WHITE,
    }
)

# ---------------------------------------------------------------------------
# Gradient allow-list (§11) — (stop1, stop2) pairs only; no neon/rainbow
# ---------------------------------------------------------------------------
GRADIENT_ORANGE_PURPLE: tuple[str, str] = (BRAND_ORANGE, BRAND_PURPLE)
GRADIENT_PURPLE_INDIGO: tuple[str, str] = (BRAND_PURPLE, BRAND_INDIGO)
GRADIENT_PURPLE_LIGHT: tuple[str, str] = (BRAND_PURPLE, BRAND_PURPLE_BASE)

ALLOWED_GRADIENTS: frozenset[tuple[str, str]] = frozenset(
    {
        GRADIENT_ORANGE_PURPLE,
        GRADIENT_PURPLE_INDIGO,
        GRADIENT_PURPLE_LIGHT,
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def rgb_tuple(hex6: str) -> tuple[int, int, int]:
    """6-char hex string (no "#") → (R, G, B) integers."""
    h = hex6.lstrip("#").upper()
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def is_allowed_font(name: str) -> bool:
    return name in ALLOWED_FONTS


def is_allowed_color(hex6: str) -> bool:
    return hex6.upper().lstrip("#") in {c.upper() for c in ALLOWED_COLORS}


def is_allowed_gradient(stop1: str, stop2: str) -> bool:
    s1 = stop1.upper().lstrip("#")
    s2 = stop2.upper().lstrip("#")
    normalized = {(a.upper(), b.upper()) for a, b in ALLOWED_GRADIENTS}
    return (s1, s2) in normalized
