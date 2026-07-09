"""Structured audit log — one JSON line per event, written to out/audit.log.

Events are also emitted to the Python logger at INFO so they appear in server
logs immediately. The log file can be shipped to a SIEM (Splunk, Sentinel, etc.)
as a follow-up without changing this interface.

Usage::

    from app.services.audit import AuditEvent, get_audit_logger

    get_audit_logger().log(AuditEvent(
        action="job.created",
        resource_type="job",
        resource_id=job_id,
        user_id=user.user_id,
        user_email=user.email,
        metadata={"deck_name": deck_name},
    ))
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.services.exporter import OUT_ROOT

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH: Path = OUT_ROOT / "audit.log"

_INSTANCE: AuditLogger | None = None
_INIT_LOCK = threading.Lock()


@dataclass
class AuditEvent:
    """A single auditable action."""

    action: str                    # e.g. "job.created", "slide.regenerated"
    resource_type: str             # e.g. "job", "slide", "asset"
    resource_id: str               # primary key of the resource
    user_id: str
    user_email: str
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""            # filled in by AuditLogger.log() if empty


class AuditLogger:
    """Thread-safe JSON-lines audit logger."""

    def __init__(self, log_path: Path = AUDIT_LOG_PATH) -> None:
        self._path = log_path
        self._lock = threading.Lock()
        # Ensure the parent directory exists (OUT_ROOT/audit.log).
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: AuditEvent) -> None:
        """Append *event* to the audit log file as a JSON line."""
        if not event.timestamp:
            event.timestamp = datetime.now(UTC).isoformat()
        record = asdict(event)
        line = json.dumps(record, default=str)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        logger.info(
            "AUDIT %s %s/%s user=%s",
            event.action,
            event.resource_type,
            event.resource_id,
            event.user_id,
        )

    def tail(self, n: int = 100) -> list[dict[str, Any]]:
        """Return the last *n* audit events as dicts (newest last)."""
        if not self._path.exists():
            return []
        with self._lock:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-n:] if line.strip()]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def init_audit_logger(audit_logger: AuditLogger | None = None) -> None:
    """Initialise the module-level AuditLogger singleton.

    Called from ``app.main.lifespan``. Safe to call multiple times
    (last call wins). If never called, ``get_audit_logger()`` creates a
    default instance on first use.
    """
    global _INSTANCE
    _INSTANCE = audit_logger or AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Return the AuditLogger singleton, creating a default one if needed."""
    global _INSTANCE
    if _INSTANCE is None:
        with _INIT_LOCK:
            if _INSTANCE is None:
                _INSTANCE = AuditLogger()
    return _INSTANCE
