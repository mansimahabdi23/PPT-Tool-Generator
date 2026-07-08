"""File exporter — saves branded PPTX and attempts LibreOffice PDF conversion.

Public API
----------
OUT_ROOT : Path  — Back-End/out/ (also used by routers/files.py)
export(job_id, prs) -> tuple[Path, Path | None]
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Back-End/out/  (two parents up from app/services/)
OUT_ROOT: Path = Path(__file__).parent.parent.parent / "out"


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
