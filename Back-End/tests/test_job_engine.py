"""Unit tests for InProcessJobEngine."""

from __future__ import annotations

import threading
import time

import pytest

from app.services.job_engine import InProcessJobEngine, get_engine, init_engine


class TestInlineMode:
    def test_runs_synchronously(self) -> None:
        """inline=True: fn must complete before submit() returns."""
        engine = InProcessJobEngine(inline=True)
        result: list[int] = []

        engine.submit(result.append, 42)

        assert result == [42]

    def test_exception_does_not_propagate(self) -> None:
        """inline=True: exceptions from fn are swallowed (fire-and-forget)."""
        engine = InProcessJobEngine(inline=True)

        def boom() -> None:
            raise ValueError("oops")

        # Must not raise
        engine.submit(boom)

    def test_multiple_submits(self) -> None:
        engine = InProcessJobEngine(inline=True)
        calls: list[str] = []

        engine.submit(calls.append, "a")
        engine.submit(calls.append, "b")
        engine.submit(calls.append, "c")

        assert calls == ["a", "b", "c"]

    def test_shutdown_noop(self) -> None:
        """Shutdown on inline engine is a no-op and must not raise."""
        engine = InProcessJobEngine(inline=True)
        engine.shutdown(wait=True)


class TestThreadPoolMode:
    def test_runs_in_background(self) -> None:
        """Thread-pool mode: fn is executed (eventually) in a worker thread."""
        engine = InProcessJobEngine(max_workers=1)
        event = threading.Event()

        engine.submit(event.set)

        assert event.wait(timeout=5), "fn was not called within 5 seconds"
        engine.shutdown(wait=True)

    def test_exception_does_not_propagate(self) -> None:
        """Thread-pool mode: exceptions from fn must not crash the pool."""
        engine = InProcessJobEngine(max_workers=1)
        done = threading.Event()

        def boom_then_signal() -> None:
            try:
                raise RuntimeError("expected test error")
            finally:
                done.set()

        engine.submit(boom_then_signal)
        assert done.wait(timeout=5)
        # Pool should still be alive — submit another task.
        after = threading.Event()
        engine.submit(after.set)
        assert after.wait(timeout=5)
        engine.shutdown(wait=True)

    def test_shutdown_drains(self) -> None:
        """shutdown(wait=True) blocks until the running fn finishes."""
        engine = InProcessJobEngine(max_workers=1)
        results: list[int] = []
        ready = threading.Event()

        def slow_append() -> None:
            ready.wait()
            results.append(1)

        engine.submit(slow_append)
        # Let it start before signalling
        time.sleep(0.05)
        ready.set()
        engine.shutdown(wait=True)
        assert results == [1]


class TestSingleton:
    def test_init_and_get_roundtrip(self) -> None:
        engine = InProcessJobEngine(inline=True)
        init_engine(engine)
        assert get_engine() is engine

    def test_get_without_init_raises(self) -> None:
        """If we reset the singleton, get_engine should raise."""
        import app.services.job_engine as je
        original = je._ENGINE
        je._ENGINE = None
        try:
            with pytest.raises(RuntimeError, match="not initialised"):
                get_engine()
        finally:
            je._ENGINE = original
