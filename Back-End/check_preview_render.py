"""Smoke-test render_previews() on an existing completed job.

Usage (from Back-End/):
    python check_preview_render.py <job_id>
    python check_preview_render.py         # auto-picks the most recent job

Renders both "original" and "transformed" sides and reports what was produced.
Does NOT touch the pipeline, the job store, or the server -- safe to run while
the server is running.
"""

from __future__ import annotations

import io
import shutil
import sys
from pathlib import Path

# ASCII-only stdout to survive Windows cp1252/cp850 console codepages.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Ensure app/ is importable when run from Back-End/
sys.path.insert(0, str(Path(__file__).parent))

from app.services.exporter import OUT_ROOT, render_previews  # noqa: E402


# ---------------------------------------------------------------------------
# Tool pre-flight
# ---------------------------------------------------------------------------

def _check_tools() -> bool:
    ok = True
    for tool in ("pdftoppm", "soffice"):
        path = shutil.which(tool)
        if path:
            print(f"  [OK]      {tool} -> {path}")
        else:
            print(f"  [MISSING] {tool} -- not found on PATH")
            ok = False
    return ok


# ---------------------------------------------------------------------------
# Job selection
# ---------------------------------------------------------------------------

def _pick_job_id(arg: str | None) -> str | None:
    if arg:
        job_dir = OUT_ROOT / arg
        if not job_dir.exists():
            print(f"ERROR: out/{arg} does not exist")
            return None
        return arg

    # Auto-pick: newest directory that contains output.pptx
    candidates = sorted(
        (p for p in OUT_ROOT.iterdir() if p.is_dir() and (p / "output.pptx").exists()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        print("ERROR: no completed job directories found under out/")
        return None

    job_id = candidates[0].name
    print(f"Auto-selected job: {job_id}")
    return job_id


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== render_previews smoke test ===\n")

    print("Tool availability:")
    tools_ok = _check_tools()
    print()

    job_id = _pick_job_id(sys.argv[1] if len(sys.argv) > 1 else None)
    if job_id is None:
        sys.exit(1)

    job_dir = OUT_ROOT / job_id
    original_pptx    = job_dir / "input.pptx"
    transformed_pptx = job_dir / "output.pptx"
    existing_pdf     = job_dir / "output.pdf"

    print(f"Job directory : {job_dir}")
    print(f"input.pptx    : {'EXISTS' if original_pptx.exists() else 'MISSING'}")
    print(f"output.pptx   : {'EXISTS' if transformed_pptx.exists() else 'MISSING'}")
    print(f"output.pdf    : {'EXISTS (will reuse)' if existing_pdf.exists() else 'not found (will generate)'}")
    print()

    if not tools_ok:
        print("WARNING: one or more tools missing -- render will degrade gracefully.")
        print()

    for side, pptx_path, reuse_pdf in [
        ("original",    original_pptx,    None),
        ("transformed", transformed_pptx, existing_pdf if existing_pdf.exists() else None),
    ]:
        print(f"--- Rendering: {side} ---")
        preview_dir = OUT_ROOT / job_id / "previews" / side
        already_there = list(preview_dir.glob("slide-*.png")) if preview_dir.exists() else []
        if already_there:
            print(f"  Previews already exist ({len(already_there)} PNGs) -- idempotency will kick in.")

        pngs = render_previews(job_id, pptx_path, side, reuse_pdf=reuse_pdf)

        if pngs:
            print(f"  SUCCESS: {len(pngs)} PNG(s) produced")
            for p in pngs:
                size_kb = round(p.stat().st_size / 1024, 1)
                print(f"    {p.name}  ({size_kb} KB)")
        else:
            print("  DEGRADED: 0 PNGs produced (check warnings above for missing tool)")
        print()

    print("=== done ===")


if __name__ == "__main__":
    main()
