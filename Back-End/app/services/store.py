"""In-memory job store for the walking skeleton.

A module-level dict keyed by job_id. No persistence — a future step replaces
this with PostgreSQL. All reads/writes happen on the same process so no locking
is needed for the synchronous skeleton.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.models.enums import JobStatus


@dataclass
class JobRecord:
    job_id: str
    deck_name: str
    status: JobStatus
    slide_count: int
    created_at: str          # ISO-8601 string
    pptx_path: Path | None = None
    pdf_path: Path | None = None
    processing_seconds: int | None = None
    error: str | None = None


_STORE: dict[str, JobRecord] = {}


def put(record: JobRecord) -> None:
    _STORE[record.job_id] = record


def get(job_id: str) -> JobRecord | None:
    return _STORE.get(job_id)
