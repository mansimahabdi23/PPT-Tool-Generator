"""Tests for app.services.retention — purge_job and purge_expired_jobs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models.enums import JobStatus
from app.services import store as job_store
from app.services.exporter import OUT_ROOT
from app.services.retention import PurgeResult, purge_expired_jobs, purge_job
from app.services.store import JobRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _put_job(job_id: str, created_at: str, status: JobStatus = JobStatus.completed) -> JobRecord:
    record = JobRecord(
        job_id=job_id,
        deck_name="test.pptx",
        status=status,
        slide_count=1,
        created_at=created_at,
    )
    job_store.put(record)
    return record


def _make_job_dir(job_id: str) -> Path:
    job_dir = OUT_ROOT / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "output.pptx").write_bytes(b"fake pptx")
    return job_dir


def _ts(days_ago: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


# ---------------------------------------------------------------------------
# purge_job
# ---------------------------------------------------------------------------

class TestPurgeJob:
    def test_removes_output_directory(self) -> None:
        job_id = "purge-test-dir-001"
        _put_job(job_id, _ts(1))
        job_dir = _make_job_dir(job_id)

        result = purge_job(job_id)

        assert result is True
        assert not job_dir.exists()

    def test_sets_status_to_purged(self) -> None:
        job_id = "purge-test-status-001"
        _put_job(job_id, _ts(1))

        purge_job(job_id)

        record = job_store.get(job_id)
        assert record is not None
        assert record.status == JobStatus.purged

    def test_succeeds_when_directory_does_not_exist(self) -> None:
        job_id = "purge-test-nodir-001"
        _put_job(job_id, _ts(1))
        # No directory created — purge_job should still succeed
        result = purge_job(job_id)
        assert result is True


# ---------------------------------------------------------------------------
# purge_expired_jobs
# ---------------------------------------------------------------------------

class TestPurgeExpiredJobs:
    def test_purges_old_jobs(self) -> None:
        old_id = "expire-old-001"
        _put_job(old_id, _ts(40))  # 40 days old, past the 30-day default

        result = purge_expired_jobs(retention_days=30)

        assert old_id in result.purged
        record = job_store.get(old_id)
        assert record is not None
        assert record.status == JobStatus.purged

    def test_skips_recent_jobs(self) -> None:
        new_id = "expire-new-001"
        _put_job(new_id, _ts(5))  # only 5 days old

        result = purge_expired_jobs(retention_days=30)

        assert new_id not in result.purged
        record = job_store.get(new_id)
        assert record is not None
        assert record.status != JobStatus.purged

    def test_skips_already_purged_jobs(self) -> None:
        purged_id = "expire-already-purged-001"
        _put_job(purged_id, _ts(60), status=JobStatus.purged)

        result = purge_expired_jobs(retention_days=30)

        # Should not appear in the purged list again
        assert purged_id not in result.purged

    def test_returns_purge_result_type(self) -> None:
        result = purge_expired_jobs(retention_days=30)
        assert isinstance(result, PurgeResult)
        assert isinstance(result.purged, list)
        assert isinstance(result.errors, list)
