"""In-memory job store (concurrency-safe for engine threads).

A module-level dict protected by a ``threading.Lock``. Engine threads write
while request handlers read — the lock prevents torn reads / lost updates.

A future step replaces this with a PostgreSQL-backed store behind the same
``put`` / ``get`` / ``update`` / ``list_all`` API.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.models.enums import JobStatus
from app.models.job import SlidePlan, TransformedSlide


@dataclass
class JobRecord:
    # Core identity
    job_id: str
    deck_name: str
    status: JobStatus
    slide_count: int
    created_at: str          # ISO-8601 string

    # Settings carried from the upload request
    allow_restructure: bool = False

    # Output paths (set after exporting)
    pptx_path: Path | None = None
    pdf_path: Path | None = None

    # Timing
    processing_seconds: int | None = None

    # Failure reason
    error: str | None = None

    # Plan produced by Analyze&Plan step — exposed via GET /jobs/{id}/plan
    plan: list[SlidePlan] | None = None

    # Slide-level results built after compose + validate
    slides: list[TransformedSlide] | None = None

    # Validator results
    brand_compliance_passed: bool | None = None
    content_fidelity: str | None = None   # e.g. "43/45 claims preserved"

    # In-memory cache of the ParsedDeck so segment_b doesn't re-parse.
    # NOT serialised to the wire (internal only).
    _parsed: Any = field(default=None, compare=False, repr=False)


_STORE: dict[str, JobRecord] = {}
_LOCK = threading.Lock()


def put(record: JobRecord) -> None:
    """Insert or fully replace a record."""
    with _LOCK:
        _STORE[record.job_id] = record


def get(job_id: str) -> JobRecord | None:
    """Return the record for *job_id*, or None."""
    with _LOCK:
        return _STORE.get(job_id)


def update(job_id: str, **changes: Any) -> JobRecord | None:
    """Atomically update named fields on an existing record.

    Returns the (mutated) record, or None if the job_id is unknown.
    Unrecognised field names raise AttributeError — this is intentional
    so caller bugs surface immediately rather than being silently ignored.
    """
    with _LOCK:
        record = _STORE.get(job_id)
        if record is None:
            return None
        for key, value in changes.items():
            setattr(record, key, value)
        return record


def list_all() -> list[JobRecord]:
    """Return all records, newest-first (by ``created_at`` string sort)."""
    with _LOCK:
        records = list(_STORE.values())
    records.sort(key=lambda r: r.created_at, reverse=True)
    return records
