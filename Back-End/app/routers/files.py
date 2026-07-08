"""File-serving router — serves output PPTX and PDF for completed jobs.

Endpoint
--------
GET /api/jobs/{job_id}/files/{filename}
    Returns the file at out/{job_id}/{filename} as a download.
    404 if the job or file does not exist.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.exporter import OUT_ROOT

router = APIRouter(tags=["files"])


@router.get("/jobs/{job_id}/files/{filename}")
async def download_file(job_id: str, filename: str) -> FileResponse:
    """Serve an output file (output.pptx or output.pdf) for a completed job."""
    # Restrict to the two expected filenames to prevent path traversal
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
