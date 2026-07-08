"""Parse the committed sample deck and print a structured summary.

Run from Back-End/:
    uv run python scripts/show_parser_output.py
"""

import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.parser import parse

SAMPLE = Path(__file__).parent.parent / "out" / "samples_imocha_template.pptx"


def _fmt_geom(g: dict) -> str:
    return (
        f"({g['left_pct']:.0%}, {g['top_pct']:.0%})"
        f" {g['width_pct']:.0%}w x {g['height_pct']:.0%}h"
    )


def main() -> None:
    if not SAMPLE.exists():
        print(f"[ERROR] Sample PPTX not found: {SAMPLE}", file=sys.stderr)
        sys.exit(1)

    deck = parse(SAMPLE, SAMPLE.name)
    print(f"Deck: {deck.name!r}   slides={deck.slide_count}")
    print("=" * 70)

    for slide in deck.slides:
        print(f"\nSlide {slide.index}  type={slide.slide_type.value!r}")
        print(f"  title      : {slide.title!r}")
        print(f"  body_items : {slide.body_items[:3]}"
              + (" ..." if len(slide.body_items) > 3 else ""))

        print(f"  text_blocks ({len(slide.text_blocks)}):")
        for b in slide.text_blocks:
            role_tag = f"[{b.shape_role}]"
            geom_tag = _fmt_geom(asdict(b.geometry))
            preview = b.full_text[:60].replace("\n", " | ")
            print(f"    {role_tag:8s} {geom_tag:28s} {preview!r}")

        if slide.tables:
            print(f"  tables ({len(slide.tables)}):")
            for tbl in slide.tables:
                print(f"    {tbl.row_count}x{tbl.col_count}  header={tbl.header_row}")

        if slide.images:
            print(f"  images ({len(slide.images)}):")
            for img in slide.images:
                bg = " [background]" if img.is_background else ""
                print(f"    {img.content_type}  {img.bytes_size:,}B{bg}")

        print(f"  claims ({len(slide.claims)}):")
        for claim in slide.claims:
            src = claim.source
            loc = f"s{src.slide_index}/shape{src.shape_id}"
            if src.row is not None:
                loc += f"/r{src.row}c{src.col}"
            elif src.paragraph_index is not None:
                loc += f"/p{src.paragraph_index}"
            preview = claim.text[:55]
            print(f"    [{claim.claim_type:12s}] {loc:22s} {preview!r}")

    print("\n" + "=" * 70)
    total_claims = sum(len(s.claims) for s in deck.slides)
    total_text   = sum(len(s.text_blocks) for s in deck.slides)
    total_images = sum(len(s.images) for s in deck.slides)
    total_tables = sum(len(s.tables) for s in deck.slides)
    print(f"Totals: {total_text} text_blocks  {total_tables} tables"
          f"  {total_images} images  {total_claims} claims")


if __name__ == "__main__":
    main()
