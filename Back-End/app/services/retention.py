"""Data-retention and purge logic.

``purge_job``         — delete one job's output files and mark it purged.
``purge_expired_jobs`` — scan all jobs and purge those older than the TTL.

These are called by the IT-admin endpoints (``POST /api/admin/purge``,
``DELETE /api/admin/jobs/{id}``) and can be wired to a Celery beat task
in production for automated nightly sweeps.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.models.enums import JobStatus
from app.services import store as job_store
from app.services.exporter import OUT_ROOT

logger = logging.getLogger(__name__)


@dataclass
class PurgeResult:
    purged: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def purge_job(job_id: str) -> bool:
    """Delete *job_id*'s output tree and mark it ``purged`` in the store.

    Returns True on success, False if the deletion raised an error.
    """
    job_dir = OUT_ROOT / job_id
    try:
        if job_dir.exists():
            shutil.rmtree(job_dir)
        job_store.update(job_id, status=JobStatus.purged)
        logger.info("RETENTION: purged job %s", job_id)
        return True
    except Exception as exc:
        logger.error("RETENTION: failed to purge job %s: %s", job_id, exc)
        return False


def purge_expired_jobs(retention_days: int = 30) -> PurgeResult:
    """Purge all jobs whose ``created_at`` is older than *retention_days*.

    Already-purged jobs are skipped. Parsing failures for ``created_at``
    are silently skipped (malformed records are not purged by default).
    """
    result = PurgeResult()
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    for record in job_store.list_all():
        if record.status == JobStatus.purged:
            continue
        try:
            created = datetime.fromisoformat(record.created_at)
            if created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
        except ValueError:
            continue  # skip records with malformed timestamps

        if created < cutoff:
            if purge_job(record.job_id):
                result.purged.append(record.job_id)
            else:
                result.errors.append(record.job_id)

    return result
