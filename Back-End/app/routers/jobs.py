"""Stub router for all /jobs endpoints (docs/architecture.md §8).

Every handler returns typed placeholder data from services/fixtures.py.
Path and query parameters are accepted and validated but not yet used.
"""

from fastapi import APIRouter, Form, Query, Response, UploadFile

from app.models.job import SlidePlan, TransformedSlide, TransformJob
from app.models.responses import JobCreatedResponse, JobResult
from app.services import fixtures

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobCreatedResponse, status_code=201)
async def create_job(
    file: UploadFile,
    allow_restructure: bool = Form(default=False),
) -> JobCreatedResponse:
    """POST /api/jobs — Accept a .pptx upload and return a job ID.

    Stub: ignores the file content, returns the fixture job ID.
    """
    return fixtures.STUB_JOB_CREATED


@router.get("", response_model=list[TransformJob])
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[TransformJob]:
    """GET /api/jobs — Return job history."""
    return fixtures.STUB_JOB_HISTORY


@router.get("/{job_id}", response_model=TransformJob)
async def get_job(job_id: str) -> TransformJob:
    """GET /api/jobs/{jobId} — Return a single job."""
    return fixtures.STUB_JOB


@router.get("/{job_id}/plan", response_model=list[SlidePlan])
async def get_plan(job_id: str) -> list[SlidePlan]:
    """GET /api/jobs/{jobId}/plan — Return the transformation plan."""
    return fixtures.STUB_PLAN


@router.post("/{job_id}/plan/approve", response_model=TransformJob, status_code=202)
async def approve_plan(job_id: str, response: Response) -> TransformJob:
    """POST /api/jobs/{jobId}/plan/approve — Approve the plan and resume the job.

    Stub: returns the fixture job (already at ``completed`` status).
    """
    response.status_code = 202
    return fixtures.STUB_JOB


@router.post(
    "/{job_id}/slides/{slide_id}/regenerate",
    response_model=TransformedSlide,
)
async def regenerate_slide(job_id: str, slide_id: str) -> TransformedSlide:
    """POST /api/jobs/{jobId}/slides/{slideId}/regenerate — Regenerate one slide."""
    return fixtures.STUB_SLIDES[0]


@router.get("/{job_id}/result", response_model=JobResult)
async def get_result(job_id: str) -> JobResult:
    """GET /api/jobs/{jobId}/result — Return download URLs + compliance metadata."""
    return fixtures.STUB_JOB_RESULT
