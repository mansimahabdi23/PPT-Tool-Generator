#!/usr/bin/env python
"""Emit one sample slide per iMocha layout and export to PPTX + PDF + PNGs.

Run from Back-End/:
    python scripts/emit_template_samples.py

What it produces
----------------
  out/samples_imocha_template.pptx   -- 6-slide deck, one slide per layout
  out/samples_imocha_template.pdf    -- PDF via LibreOffice headless
  out/slide_pngs/slide_*.png         -- one PNG per slide (LibreOffice headless)

The content/data slides have a real infographic fragment merged into their
region via XML shape-tree copy (merge.py) -- this proves the section 12/14 claim
that python-pptx deep-copy produces an editable, on-brand merged PPTX.

The PDF + PNG steps prove LibreOffice headless converts the deck correctly
(fonts Playfair Display + Poppins must be installed on the machine for crisp
output; LibreOffice will substitute if absent -- watch for visual regression).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# Allow running directly without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.models.enums import SlideType
from app.templates.builder import SlideContent, add_slide
from app.templates.merge import merge_fragment
from app.templates.theme import new_presentation

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ASSETS_ROOT: Path = settings.assets_root
OUT_DIR: Path = Path(__file__).parent.parent / "out"

# Infographic fragments: each assets/infographics/*.pptx exposes exactly 1 slide
# (index 0) -- the named infographic. Pick two visually distinct ones.
_INFOGRAPHICS: Path = ASSETS_ROOT / "infographics"
_ALL_FRAGS: list[Path] = sorted(_INFOGRAPHICS.glob("*.pptx"))

# Use first two fragments (if they exist) for content + data demo
CONTENT_FRAG: Path | None = _ALL_FRAGS[0] if len(_ALL_FRAGS) > 0 else None
DATA_FRAG: Path | None = _ALL_FRAGS[1] if len(_ALL_FRAGS) > 1 else None
FRAG_SLIDE_IDX: int = 0  # every fragment pptx exposes its infographic at slide 0

# ---------------------------------------------------------------------------
# Sample content
# ---------------------------------------------------------------------------

SAMPLE_CONTENT: dict[SlideType, SlideContent] = {
    SlideType.title: SlideContent(
        title="iMocha AI Presentation Studio",
        subtitle="Transform any deck into an on-brand iMocha presentation",
    ),
    SlideType.agenda: SlideContent(
        title="Agenda",
        body_items=[
            "01  Introduction & Context",
            "02  Key Findings",
            "03  Data & Insights",
            "04  Recommendations",
            "05  Next Steps",
        ],
    ),
    SlideType.content: SlideContent(
        title="Key Findings",
        body_items=[
            "Hiring quality improved 34% with structured assessment",
            "Time-to-hire reduced by 2.1 weeks on average",
            "Candidate experience scores increased to 4.6 / 5",
        ],
    ),
    SlideType.data: SlideContent(
        title="Assessment Performance Trends",
        caption="Source: iMocha platform data, Q1-Q3 2024  |  n = 12 400 candidates",
    ),
    SlideType.divider: SlideContent(
        title="Recommendations",
        kicker="Section 04",
    ),
    SlideType.closing: SlideContent(
        title="Thank You",
        subtitle="hello@imocha.co  |  www.imocha.co",
    ),
}

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pptx_path = OUT_DIR / "samples_imocha_template.pptx"

    print("Building branded presentation...")
    prs = new_presentation()

    slide_order = [
        SlideType.title,
        SlideType.agenda,
        SlideType.content,
        SlideType.data,
        SlideType.divider,
        SlideType.closing,
    ]

    slides: dict[SlideType, object] = {}
    for st in slide_order:
        slide = add_slide(prs, st, SAMPLE_CONTENT[st], ASSETS_ROOT)
        slides[st] = slide
        print(f"  [ok] {st.value} slide")

    # Merge real infographic fragments into content and data slides
    from app.templates.layouts import LAYOUTS

    print("\nMerging infographic fragments...")

    if CONTENT_FRAG is not None and CONTENT_FRAG.exists():
        content_slide = slides[SlideType.content]
        content_region = LAYOUTS[SlideType.content].infographic_region
        if content_region is not None:
            merge_fragment(content_slide, CONTENT_FRAG, FRAG_SLIDE_IDX, content_region)
            print(f"  [ok] content <- {CONTENT_FRAG.name}")
    else:
        print("  [warn] no infographic fragments found in assets/infographics/ -- skipping content merge")

    if DATA_FRAG is not None and DATA_FRAG.exists():
        data_slide = slides[SlideType.data]
        data_region = LAYOUTS[SlideType.data].infographic_region
        if data_region is not None:
            merge_fragment(data_slide, DATA_FRAG, FRAG_SLIDE_IDX, data_region)
            print(f"  [ok] data    <- {DATA_FRAG.name}")
    else:
        print("  [warn] no second infographic fragment -- skipping data merge")

    prs.save(str(pptx_path))
    print(f"\n[ok] PPTX saved -> {pptx_path}")

    # PDF + PNG via LibreOffice headless
    soffice = shutil.which("soffice")
    if soffice is None:
        print(
            "\n[warn] LibreOffice not found on PATH (soffice) -- skipping PDF/PNG export.\n"
            "   Install LibreOffice and ensure 'soffice' is on PATH to generate PDFs.\n"
            "   Also ensure Playfair Display + Poppins are installed system-wide for\n"
            "   correct font rendering (LibreOffice substitutes missing fonts)."
        )
        return

    print("\nConverting to PDF via LibreOffice headless...")
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(OUT_DIR), str(pptx_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        pdf_path = OUT_DIR / "samples_imocha_template.pdf"
        print(f"[ok] PDF saved -> {pdf_path}")
    else:
        print("[fail] LibreOffice PDF conversion failed:")
        print(result.stderr or result.stdout)
        sys.exit(1)

    print("\nConverting slides to PNG via LibreOffice headless...")
    png_dir = OUT_DIR / "slide_pngs"
    png_dir.mkdir(exist_ok=True)
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "png", "--outdir", str(png_dir), str(pptx_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        pngs = sorted(png_dir.glob("*.png"))
        print(f"[ok] {len(pngs)} PNG(s) saved -> {png_dir}/")
        for p in pngs:
            print(f"   {p.name}")
    else:
        print("[fail] LibreOffice PNG conversion failed:")
        print(result.stderr or result.stdout)
        sys.exit(1)


if __name__ == "__main__":
    main()
