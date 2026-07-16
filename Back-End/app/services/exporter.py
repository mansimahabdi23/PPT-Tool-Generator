"""File exporter — saves branded PPTX, PDF, and per-slide preview PNGs.

Public API
----------
OUT_ROOT        : Path  — Back-End/out/ (shared by routers/files.py)
export(job_id, prs) -> tuple[Path, Path | None]
render_previews(job_id, pptx_path, side, reuse_pdf) -> list[Path]
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Back-End/out/  (two parents up from app/services/)
OUT_ROOT: Path = Path(__file__).parent.parent.parent / "out"

# Matches the predictable names we write after renaming pdftoppm output.
_SLIDE_PNG = re.compile(r"^slide-(\d+)\.png$")


def export(job_id: str, prs: Any) -> tuple[Path, Path | None]:
    """Save *prs* as PPTX and attempt PDF conversion.

    Returns
    -------
    (pptx_path, pdf_path)  — pdf_path is None when LibreOffice is not available.
    """
    job_dir = OUT_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    pptx_path = job_dir / "output.pptx"
    prs.save(str(pptx_path))
    logger.info("PPTX saved: %s", pptx_path)

    pdf_path = _try_libreoffice_pdf(pptx_path, job_dir)
    return pptx_path, pdf_path


def render_previews(
    job_id: str,
    pptx_path: Path,
    side: str,
    reuse_pdf: Path | None = None,
) -> list[Path]:
    """Render per-slide PNGs for *side* ("original" or "transformed").

    Flow: PPTX → PDF (via LibreOffice; reuses *reuse_pdf* if it exists) →
    per-page PNGs (via pdftoppm from poppler-utils).

    Idempotent — if slide-*.png files already exist in the preview directory
    they are returned without re-rendering.

    Never raises.  Returns [] if pdftoppm or LibreOffice is unavailable so
    that a render failure does not flip the job to 'failed'.

    Output files are named slide-1.png, slide-2.png, … (1-indexed, no
    zero-padding) regardless of the raw pdftoppm output format.
    """
    preview_dir = OUT_ROOT / job_id / "previews" / side

    # Idempotency: if PNGs already exist, return them without re-rendering.
    existing = _sorted_pngs(preview_dir)
    if existing:
        logger.debug(
            "render_previews: reusing %d existing PNGs for %s/%s",
            len(existing), job_id, side,
        )
        return existing

    try:
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm is None:
            logger.warning(
                "pdftoppm not found on PATH — slide preview PNGs skipped for %s/%s. "
                "Install poppler-utils to enable per-slide preview images.",
                job_id, side,
            )
            return []

        pdf_path = _get_or_create_pdf(pptx_path, reuse_pdf, job_id, side)
        if pdf_path is None:
            return []

        preview_dir.mkdir(parents=True, exist_ok=True)
        prefix = str(preview_dir / "slide")
        result = subprocess.run(
            [pdftoppm, "-r", "150", "-png", str(pdf_path), prefix],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error(
                "pdftoppm failed for %s/%s: %s",
                job_id, side, result.stderr or result.stdout,
            )
            return []

        # pdftoppm names files slide-1.png / slide-01.png / slide-001.png
        # depending on total page count.  Rename to predictable slide-N.png.
        raw = _sorted_pngs(preview_dir)
        renamed: list[Path] = []
        for i, p in enumerate(raw, 1):
            dest = preview_dir / f"slide-{i}.png"
            if p != dest:
                p.rename(dest)
            renamed.append(preview_dir / f"slide-{i}.png")

        logger.info("Rendered %d preview PNGs for %s/%s", len(renamed), job_id, side)
        return renamed

    except Exception:
        logger.exception(
            "render_previews failed for %s/%s — previews skipped", job_id, side
        )
        return []


def render_single_slide_png(pptx_path: Path, output_png: Path) -> bool:
    """Render the first (only) slide of *pptx_path* to *output_png*.

    Overwrites *output_png* when it already exists.  Returns True on success.
    Non-fatal: logs and returns False when LibreOffice or pdftoppm are
    unavailable, leaving the previous PNG in place.
    """
    try:
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm is None:
            logger.warning("pdftoppm not found — single-slide re-render skipped")
            return False

        # Render via a temp PDF in the same directory as the pptx
        pdf = _try_libreoffice_pdf(pptx_path, pptx_path.parent)
        if pdf is None:
            return False

        output_png.parent.mkdir(parents=True, exist_ok=True)
        prefix = str(output_png.with_suffix(""))
        result = subprocess.run(
            [pdftoppm, "-r", "150", "-png", "-l", "1", str(pdf), prefix],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            logger.error("pdftoppm failed for single slide: %s", result.stderr or result.stdout)
            return False

        # pdftoppm writes <prefix>-1.png / <prefix>-01.png / <prefix>-001.png
        stem = output_png.stem
        for candidate in [
            output_png.with_name(f"{stem}-1.png"),
            output_png.with_name(f"{stem}-01.png"),
            output_png.with_name(f"{stem}-001.png"),
        ]:
            if candidate.exists():
                if candidate != output_png:
                    candidate.replace(output_png)
                return True

        logger.warning("render_single_slide_png: output PNG not found after pdftoppm run")
        return False

    except Exception:
        logger.exception("render_single_slide_png failed for %s", pptx_path)
        return False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sorted_pngs(directory: Path) -> list[Path]:
    """Return slide-N.png files from *directory* sorted by numeric suffix."""
    if not directory.exists():
        return []
    files: list[tuple[int, Path]] = []
    for p in directory.glob("slide-*.png"):
        m = _SLIDE_PNG.match(p.name)
        if m:
            files.append((int(m.group(1)), p))
    return [p for _, p in sorted(files)]


def _get_or_create_pdf(
    pptx_path: Path,
    reuse_pdf: Path | None,
    job_id: str,
    side: str,
) -> Path | None:
    """Return a PDF for *pptx_path*, reusing *reuse_pdf* when it exists."""
    if reuse_pdf is not None and reuse_pdf.exists():
        return reuse_pdf
    # No existing PDF — create one via LibreOffice (non-fatal if unavailable).
    pdf = _try_libreoffice_pdf(pptx_path, pptx_path.parent)
    if pdf is None:
        logger.warning(
            "Cannot generate PDF for %s/%s previews — LibreOffice unavailable",
            job_id, side,
        )
    return pdf


def _try_libreoffice_pdf(pptx_path: Path, out_dir: Path) -> Path | None:
    """Convert *pptx_path* to PDF with LibreOffice headless.

    Returns the PDF path on success, None if LibreOffice is unavailable or
    conversion fails (non-fatal — the skeleton works without PDF).
    """
    soffice = shutil.which("soffice")
    if soffice is None:
        logger.warning(
            "LibreOffice (soffice) not found on PATH — PDF export skipped. "
            "Install LibreOffice and ensure Playfair Display + Poppins fonts are "
            "available system-wide before enabling PDF export."
        )
        return None

    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(pptx_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error("LibreOffice PDF conversion failed: %s", result.stderr or result.stdout)
        return None

    pdf_path = out_dir / (pptx_path.stem + ".pdf")
    if pdf_path.exists():
        logger.info("PDF saved: %s", pdf_path)
        return pdf_path

    return None
