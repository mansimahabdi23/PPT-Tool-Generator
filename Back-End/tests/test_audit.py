"""Tests for app.services.audit — AuditEvent, AuditLogger, singleton."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.services.audit import AuditEvent, AuditLogger, get_audit_logger, init_audit_logger


# ---------------------------------------------------------------------------
# AuditLogger unit tests
# ---------------------------------------------------------------------------

class TestAuditLogger:
    def test_log_writes_json_line(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_file)

        logger.log(AuditEvent(
            action="job.created",
            resource_type="job",
            resource_id="job-1",
            user_id="user-abc",
            user_email="u@t.com",
            metadata={"deck_name": "test.pptx"},
        ))

        lines = log_file.read_text().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["action"] == "job.created"
        assert record["resource_id"] == "job-1"
        assert record["user_id"] == "user-abc"

    def test_log_sets_timestamp_if_empty(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_file)
        event = AuditEvent(
            action="job.created",
            resource_type="job",
            resource_id="j1",
            user_id="u",
            user_email="u@t.com",
        )
        assert event.timestamp == ""
        logger.log(event)
        assert event.timestamp != ""

    def test_log_preserves_existing_timestamp(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_file)
        event = AuditEvent(
            action="x",
            resource_type="y",
            resource_id="z",
            user_id="u",
            user_email="u@t.com",
            timestamp="2026-01-01T00:00:00+00:00",
        )
        logger.log(event)
        record = json.loads(log_file.read_text())
        assert record["timestamp"] == "2026-01-01T00:00:00+00:00"

    def test_multiple_events_produce_multiple_lines(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_file)
        for i in range(3):
            logger.log(AuditEvent(
                action=f"action.{i}",
                resource_type="job",
                resource_id=f"j{i}",
                user_id="u",
                user_email="u@t.com",
            ))
        lines = [l for l in log_file.read_text().splitlines() if l.strip()]
        assert len(lines) == 3

    def test_all_required_fields_present(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_file)
        logger.log(AuditEvent(
            action="slide.regenerated",
            resource_type="slide",
            resource_id="s1",
            user_id="uid",
            user_email="u@t.com",
            metadata={"job_id": "j1"},
        ))
        record = json.loads(log_file.read_text())
        for field in ("action", "resource_type", "resource_id", "user_id", "user_email", "timestamp"):
            assert field in record, f"missing field: {field}"

    def test_tail_returns_last_n_events(self, tmp_path: Path) -> None:
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_file)
        for i in range(10):
            logger.log(AuditEvent(
                action=f"a.{i}",
                resource_type="job",
                resource_id=f"j{i}",
                user_id="u",
                user_email="u@t.com",
            ))
        tail = logger.tail(3)
        assert len(tail) == 3
        assert tail[-1]["action"] == "a.9"

    def test_tail_on_missing_file_returns_empty_list(self, tmp_path: Path) -> None:
        logger = AuditLogger(tmp_path / "nonexistent.log")
        assert logger.tail() == []

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "audit.log"
        logger = AuditLogger(nested)
        logger.log(AuditEvent(
            action="x", resource_type="y", resource_id="z",
            user_id="u", user_email="u@t.com",
        ))
        assert nested.exists()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestAuditLoggerSingleton:
    def test_get_audit_logger_returns_instance(self) -> None:
        instance = get_audit_logger()
        assert isinstance(instance, AuditLogger)

    def test_init_audit_logger_replaces_instance(self, tmp_path: Path) -> None:
        custom = AuditLogger(tmp_path / "custom.log")
        init_audit_logger(custom)
        assert get_audit_logger() is custom
        # Restore a default so other tests don't use the custom path
        init_audit_logger()
