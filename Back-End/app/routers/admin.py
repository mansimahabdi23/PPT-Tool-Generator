"""IT-admin management endpoints.

All routes require the ``it-admin`` role.

  GET  /api/admin/audit-log       — tail the audit log (last N events)
  POST /api/admin/purge           — run the retention sweep
  DELETE /api/admin/jobs/{id}     — force-delete one job immediately
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import settings
from app.models.auth import Role, UserIdentity
from app.services import store as job_store
from app.services.audit import get_audit_logger
from app.services.auth import require_roles
from app.services.retention import PurgeResult, purge_expired_jobs, purge_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# Typed alias — any endpoint that injects this requires the it-admin role.
ITAdmin = Annotated[UserIdentity, Depends(require_roles(Role.it_admin))]


@router.get("/audit-log")
async def get_audit_log(
    _user: ITAdmin,
    n: int = Query(default=100, ge=1, le=10_000),
) -> list[dict[str, Any]]:
    """Return the last *n* audit events (newest last)."""
    return get_audit_logger().tail(n)


@router.post("/purge")
async def run_purge(_user: ITAdmin) -> dict[str, Any]:
    """Run the retention sweep — purge all jobs older than the configured TTL."""
    result: PurgeResult = purge_expired_jobs(settings.data_retention_days)
    logger.info(
        "ADMIN purge: %d purged, %d errors",
        len(result.purged),
        len(result.errors),
    )
    return {"purged": result.purged, "errors": result.errors}


@router.delete("/jobs/{job_id}", status_code=204)
async def force_delete_job(job_id: str, _user: ITAdmin) -> None:
    """Immediately delete *job_id*'s output files, regardless of retention TTL."""
    if job_store.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    ok = purge_job(job_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to purge job — check server logs")
