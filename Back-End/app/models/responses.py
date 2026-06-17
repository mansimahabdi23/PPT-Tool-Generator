"""Envelope response models for endpoints that don't return a domain model directly."""

from .base import CamelModel


class JobCreatedResponse(CamelModel):
    """Response for ``POST /api/jobs``. Frontend reads ``{ jobId }``."""

    job_id: str


class JobResult(CamelModel):
    """Response for ``GET /api/jobs/{jobId}/result`` (§8).

    Note: the frontend API client currently reads only ``pptxUrl`` and ``pdfUrl``;
    the extra fields are specified in docs/architecture.md §8 and are included here
    per the docs-win rule in CLAUDE.md. The client silently ignores the extras.
    """

    pptx_url: str
    pdf_url: str
    brand_compliance_passed: bool
    content_fidelity: str
    processing_seconds: int
