"""Export slide PNGs using the project's render_previews pipeline."""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from app.services.exporter import OUT_ROOT, render_previews

job_id = "icon_test"
pptx_path = OUT_ROOT / job_id / "output.pptx"

# Clear any cached previews so we get fresh output
preview_dir = OUT_ROOT / job_id / "previews" / "transformed"
if preview_dir.exists():
    import shutil
    shutil.rmtree(preview_dir)

pngs = render_previews(job_id, pptx_path, "transformed")
print(f"Rendered {len(pngs)} preview PNGs:")
for p in pngs:
    print(f"  {p}")
