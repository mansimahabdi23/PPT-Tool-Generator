"""Jobs router (docs/architecture.md §8).

Step 5 (sub-increment 1) — async engine + full state machine:
  POST /api/jobs                    — save upload → segment_a (background)
  GET  /api/jobs                    — real job history from store
  GET  /api/jobs/{id}               — real store lookup with full TransformJob
  GET  /api/jobs/{id}/plan          — stored SlidePlan[]
  POST /api/jobs/{id}/plan/approve  — guard + segment_b (background) → 202
  GET  /api/jobs/{id}/result        — real URLs + validator results
  POST /api/jobs/{id}/slides/{sid}/regenerate — stub (review-screen follow-up)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Form, HTTPException, Query, Response, UploadFile

from app.models.enums import ApprovalState, JobStatus
from app.models.job import SlidePlan, TransformedSlide, TransformJob
from app.models.responses import JobCreatedResponse, JobResult
from app.services import store as job_store
from app.services.exporter import OUT_ROOT
from app.services.job_engine import get_engine
from app.services.pipeline import run_segment_a, run_segment_b
from app.services.store import JobRecord

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# POST /api/jobs — upload + kick off segment A
# ---------------------------------------------------------------------------

@router.post("", response_model=JobCreatedResponse, status_code=201)
async def create_job(
    file: UploadFile,
    allow_restructure: bool = Form(default=False),
) -> JobCreatedResponse:
    """Upload a .pptx; return a job ID immediately and process in background.

    The pipeline runs asynchronously (engine thread). Poll ``GET /jobs/{id}``
    every ~700 ms to observe status transitions.
    """
    job_id = str(uuid.uuid4())
    deck_name = file.filename or "presentation.pptx"
    created_at = datetime.now(UTC).isoformat()

    # Save the uploaded bytes before entering the background thread.
    input_dir = OUT_ROOT / job_id
    input_dir.mkdir(parents=True, exist_ok=True)
    input_path = input_dir / "input.pptx"
    content = await file.read()
    input_path.write_bytes(content)

    # Create an initial record so GET /jobs/{id} never 404s immediately after POST.
    job_store.put(JobRecord(
        job_id=job_id,
        deck_name=deck_name,
        status=JobStatus.parsing,
        slide_count=0,
        created_at=created_at,
        allow_restructure=allow_restructure,
    ))

    # Kick off segment A — non-blocking.
    get_engine().submit(run_segment_a, job_id, input_path, deck_name, allow_restructure)
    logger.info("[%s] Job created; segment_a submitted", job_id)

    return JobCreatedResponse(job_id=job_id)


# ---------------------------------------------------------------------------
# GET /api/jobs — real job history
# ---------------------------------------------------------------------------

@router.get("", response_model=list[TransformJob])
async def list_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[TransformJob]:
    """Return all jobs, newest-first (in-memory; no real pagination yet)."""
    records = job_store.list_all()
    start = (page - 1) * page_size
    page_records = records[start : start + page_size]
    return [_record_to_job(r) for r in page_records]


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id} — real store lookup
# ---------------------------------------------------------------------------

@router.get("/{job_id}", response_model=TransformJob)
async def get_job(job_id: str) -> TransformJob:
    """Return the current state of a job."""
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _record_to_job(record)


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/plan — stored SlidePlan[]
# ---------------------------------------------------------------------------

@router.get("/{job_id}/plan", response_model=list[SlidePlan])
async def get_plan(job_id: str) -> list[SlidePlan]:
    """Return the plan produced by the Analyze&Plan step.

    Returns an empty list if the job exists but analysis has not completed yet.
    """
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return record.plan or []


# ---------------------------------------------------------------------------
# POST /api/jobs/{job_id}/plan/approve — resume with segment B
# ---------------------------------------------------------------------------

@router.post("/{job_id}/plan/approve", response_model=TransformJob, status_code=202)
async def approve_plan(job_id: str, response: Response) -> TransformJob:
    """Approve the plan and kick off the compose+export segment.

    Guards:
    - 404 if the job is unknown.
    - 409 if the job is not in ``plan_ready`` state (prevents double-approve
      or approving before the plan exists).
    """
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status != JobStatus.plan_ready:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve: job is in state '{record.status}', expected 'plan_ready'",
        )

    # Update status to retrieving BEFORE submitting to the engine.
    # In thread-pool mode this gives the frontend an immediate "working" state.
    # In inline (test) mode the submit() call runs synchronously and will
    # advance status through to completed — so the update must precede submit.
    job_store.update(job_id, status=JobStatus.retrieving)

    # Kick off segment B — non-blocking in thread-pool mode, synchronous in inline mode.
    get_engine().submit(run_segment_b, job_id)
    logger.info("[%s] Plan approved; segment_b submitted", job_id)

    response.status_code = 202
    record = job_store.get(job_id)
    assert record is not None
    return _record_to_job(record)


# ---------------------------------------------------------------------------
# POST /api/jobs/{job_id}/slides/{slide_id}/regenerate — stub
# ---------------------------------------------------------------------------

@router.post("/{job_id}/slides/{slide_id}/regenerate", response_model=TransformedSlide)
async def regenerate_slide(job_id: str, slide_id: str) -> TransformedSlide:
    """Regenerate a single slide and return the updated TransformedSlide.

    Current behaviour: resets the slide's approval to ``pending`` and bumps
    ``retryCount``.  The visual output (preview URL) is unchanged — actual
    per-slide LLM recompose is a follow-up task that requires single-slide
    compose + validate + LibreOffice render.

    Guards: 404 for unknown job or slide; 409 if the job is not yet completed.
    """
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status != JobStatus.completed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot regenerate: job is in state '{record.status}', expected 'completed'",
        )
    if not record.slides:
        raise HTTPException(status_code=409, detail="Job has no slides")

    target = next((s for s in record.slides if s.id == slide_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="Slide not found")

    updated = TransformedSlide(
        id=target.id,
        index=target.index,
        original_preview_url=target.original_preview_url,
        transformed_preview_url=target.transformed_preview_url,
        content_unchanged=target.content_unchanged,
        restructure_note=target.restructure_note,
        change_chips=sorted({*target.change_chips, "Regenerated"}),
        approval=ApprovalState.pending,
        retry_count=(target.retry_count or 0) + 1,
    )
    new_slides = [updated if s.id == slide_id else s for s in record.slides]
    job_store.update(job_id, slides=new_slides)
    logger.info("[%s] Slide %s regenerated (retryCount=%d)", job_id, slide_id, updated.retry_count or 0)
    return updated


# ---------------------------------------------------------------------------
# GET /api/jobs/{job_id}/result — real URLs + validator results
# ---------------------------------------------------------------------------

@router.get("/{job_id}/result", response_model=JobResult)
async def get_result(job_id: str) -> JobResult:
    """Return download URLs and validator results for a completed job."""
    record = job_store.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if record.status != JobStatus.completed:
        raise HTTPException(
            status_code=409,
            detail=f"Job is not completed (status: {record.status})",
        )

    pptx_url = f"/api/jobs/{job_id}/files/output.pptx"
    pdf_url = f"/api/jobs/{job_id}/files/output.pdf" if record.pdf_path else ""

    return JobResult(
        pptx_url=pptx_url,
        pdf_url=pdf_url,
        brand_compliance_passed=record.brand_compliance_passed if record.brand_compliance_passed is not None else False,
        content_fidelity=record.content_fidelity or "",
        processing_seconds=record.processing_seconds or 0,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record_to_job(record: JobRecord) -> TransformJob:
    """Map a JobRecord to the TransformJob wire model."""
    return TransformJob(
        id=record.job_id,
        deck_name=record.deck_name,
        status=record.status,
        allow_restructure=record.allow_restructure,
        slide_count=record.slide_count,
        created_at=record.created_at,
        plan=record.plan,
        slides=record.slides,
        processing_seconds=record.processing_seconds,
        brand_compliance_passed=record.brand_compliance_passed,
        content_fidelity=record.content_fidelity,
    )
