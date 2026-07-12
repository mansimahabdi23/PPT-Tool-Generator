"""File-serving router — serves output PPTX, PDF, and per-slide preview PNGs.

Endpoints
---------
GET /api/jobs/{job_id}/files/{filename}
    Returns output.pptx or output.pdf for a completed job.

GET /api/jobs/{job_id}/previews/{side}/{filename}
    Returns a per-slide preview PNG (slide-N.png) rendered by render_previews().
    side ∈ {"original", "transformed"}; filename must match ^slide-\\d+\\.png$.

Both endpoints require authentication (CurrentUser).  With AUTH_DEV_BYPASS=true
(local dev), get_current_user returns a synthetic identity without checking
headers, so <img> tags load preview PNGs in dev without extra configuration.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.models.auth import UserIdentity
from app.services.auth import get_current_user
from app.services.exporter import OUT_ROOT

CurrentUser = Annotated[UserIdentity, Depends(get_current_user)]

router = APIRouter(tags=["files"])

_PREVIEW_FILENAME = re.compile(r"^slide-\d+\.png$")


@router.get("/jobs/{job_id}/files/{filename}")
async def download_file(job_id: str, filename: str, _user: CurrentUser) -> FileResponse:
    """Serve an output file (output.pptx or output.pdf) for a completed job."""
    if filename not in ("output.pptx", "output.pdf"):
        raise HTTPException(status_code=404, detail="File not found")

    path = OUT_ROOT / job_id / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    media_type = (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if filename.endswith(".pptx")
        else "application/pdf"
    )
    return FileResponse(str(path), media_type=media_type, filename=filename)


@router.get("/jobs/{job_id}/previews/{side}/{filename}")
async def get_slide_preview(
    job_id: str,
    side: str,
    filename: str,
    _user: CurrentUser,
) -> FileResponse:
    """Serve a per-slide preview PNG for a job.

    Guards
    ------
    - side must be exactly "original" or "transformed".
    - filename must match ^slide-\\d+\\.png$ (no path separators, no traversal).
    - Resolved path must stay within out/{job_id}/previews/ (defense in depth).
    """
    if side not in ("original", "transformed"):
        raise HTTPException(status_code=404, detail="Not found")
    if not _PREVIEW_FILENAME.fullmatch(filename):
        raise HTTPException(status_code=404, detail="Not found")

    # Resolve both paths and confirm containment (defense in depth).
    preview_root = (OUT_ROOT / job_id / "previews").resolve()
    path = (OUT_ROOT / job_id / "previews" / side / filename).resolve()
    try:
        path.relative_to(preview_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="Not found")

    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")

    return FileResponse(str(path), media_type="image/png")
