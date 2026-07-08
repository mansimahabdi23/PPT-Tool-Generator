"""Jobs router (docs/architecture.md §8).

Walking skeleton (Step 3):
  POST /api/jobs          — REAL: parse → compose → export; stores job in memory
  GET  /api/jobs/{id}     — REAL: reads from in-memory store
  GET  /api/jobs/{id}/result — REAL: returns real file URLs

All other endpoints remain stubs returning fixture data.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Form, HTTPException, Query, Response, UploadFile

from app.config import settings
from app.models.enums import JobStatus
from app.models.job import SlidePlan, TransformedSlide, TransformJob
from app.models.responses import JobCreatedResponse, JobResult
from app.services import fixtures
from app.services import store as job_store
from app.services.composer import compose
from app.services.exporter import OUT_ROOT, export
from app.services.parser import parse
from app.services.store import JobRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# POST /api/jobs — real pipeline
# ---------------------------------------------------------------------------

@router.post("", response_model=JobCreatedResponse, status_code=201)
async def create_job(
    file: UploadFile,
    allow_restructure: bool = Form(default=False),
) -> JobCreatedResponse:
    """Upload a .pptx, run parse→compose→export, return a job ID.

    The pipeline runs synchronously for the skeleton (no Celery worker yet).
    On any error the job is stored as failed so the frontend can poll for it.
    """
    job_id = str(uuid.uuid4())
    deck_name = file.filename or "presentation.pptx"
    created_at = datetime.now(timezone.utc).isoformat()

    # Optimistically store a 'parsing' record so GET /jobs/{id} never 404s
    job_store.put(JobRecord(
        job_id=job_id,
        deck_name=deck_name,
        status=JobStatus.parsing,
        slide_count=0,
        created_at=created_at,
    ))

    try:
        t0 = time.perf_counter()

        # 1. Save uploaded file
        input_dir = OUT_ROOT / job_id
        input_dir.mkdir(parents=True, exist_ok=True)
        input_path = input_dir / "input.pptx"
        content = await file.read()
        input_path.write_bytes(content)

        # 2. Parse
        parsed = parse(input_path, deck_name)

        # 3. Compose branded deck
        prs = compose(parsed, settings.assets_root)

        # 4. Export PPTX (+ optional PDF)
        pptx_path, pdf_path = export(job_id, prs)

        elapsed = int(time.perf_counter() - t0)

        job_store.put(JobRecord(
            job_id=job_id,
            deck_name=deck_name,
            status=JobStatus.completed,
            slide_count=len(parsed.slides),
            created_at=created_at,
            pptx_path=pptx_path,
            pdf_path=pdf_path,
            processing_seconds=elapsed,
        ))
        logger.info("Job %s completed in %ds (%d slides)", job_id, elapsed, len(parsed.slides))

    except Exception as exc:
        logger.exception("Job %s failed: %s", job_id, exc)
        record = job_store.get(job_id)
        if record:
            record.status = JobStatus.failed
            record.error = str(exc)

    return JobCreatedResponse(job_id=job_id)


# ---------------------------------------------------------------------------
# GET /api/jobs — stub history
# ---------------------------------------------------------------------------

@router.get("", response_model=list[TransformJob])
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[TransformJob]:
    """GET /api/jobs — Return job history (stub)."""
    return fixtures.STUB_JOB_HISTORY


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id} — real store lookup
# ---------------------------------------------------------------------------

@router.get("/{job_id}", response_model=TransformJob)
async def get_job(job_id: str) -> TransformJob:
    """GET /api/jobs/{jobId} — Return job status from store."""
    record = job_store.get(job_id)
    if record is None:
        # Fall back to fixture for stub job IDs (keeps history page working)
        if job_id == fixtures.STUB_JOB.id:
            return fixtures.STUB_JOB
        raise HTTPException(status_code=404, detail="Job not found")

    return TransformJob(
        id=record.job_id,
        deck_name=record.deck_name,
        status=record.status,
        allow_restructure=False,
        slide_count=record.slide_count,
        created_at=record.created_at,
        processing_seconds=record.processing_seconds,
        brand_compliance_passed=(record.status == JobStatus.completed) or None,
        content_fidelity="claimed" if record.status == JobStatus.completed else None,
    )


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/plan — stub
# ---------------------------------------------------------------------------

@router.get("/{job_id}/plan", response_model=list[SlidePlan])
async def get_plan(job_id: str) -> list[SlidePlan]:
    """GET /api/jobs/{jobId}/plan — stub."""
    return fixtures.STUB_PLAN


# ---------------------------------------------------------------------------
# POST /api/jobs/{job_id}/plan/approve — stub
# ---------------------------------------------------------------------------

@router.post("/{job_id}/plan/approve", response_model=TransformJob, status_code=202)
async def approve_plan(job_id: str, response: Response) -> TransformJob:
    """POST /api/jobs/{jobId}/plan/approve — stub."""
    response.status_code = 202
    return fixtures.STUB_JOB


# ---------------------------------------------------------------------------
# POST /api/jobs/{job_id}/slides/{slide_id}/regenerate — stub
# ---------------------------------------------------------------------------

@router.post("/{job_id}/slides/{slide_id}/regenerate", response_model=TransformedSlide)
async def regenerate_slide(job_id: str, slide_id: str) -> TransformedSlide:
    """POST /api/jobs/{jobId}/slides/{slideId}/regenerate — stub."""
    return fixtures.STUB_SLIDES[0]


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/result — real file URLs
# ---------------------------------------------------------------------------

@router.get("/{job_id}/result", response_model=JobResult)
async def get_result(job_id: str) -> JobResult:
    """GET /api/jobs/{jobId}/result — return real download URLs."""
    record = job_store.get(job_id)
    if record is None:
        # Fall back to fixture for stub job IDs
        if job_id == fixtures.STUB_JOB.id:
            return fixtures.STUB_JOB_RESULT
        raise HTTPException(status_code=404, detail="Job not found")

    if record.status != JobStatus.completed:
        raise HTTPException(status_code=409, detail=f"Job is not completed (status: {record.status})")

    pptx_url = f"/api/jobs/{job_id}/files/output.pptx"
    pdf_url = f"/api/jobs/{job_id}/files/output.pdf" if record.pdf_path else ""

    return JobResult(
        pptx_url=pptx_url,
        pdf_url=pdf_url,
        brand_compliance_passed=True,
        content_fidelity="claimed",
        processing_seconds=record.processing_seconds or 0,
    )
