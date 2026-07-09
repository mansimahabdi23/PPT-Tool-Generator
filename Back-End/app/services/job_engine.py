"""Swappable job-engine seam.

The ``JobEngine`` protocol has a single method:
    submit(fn, *args) -> None   # fire-and-forget; exceptions are captured, not re-raised

``InProcessJobEngine`` is the default implementation:
  - Uses ``concurrent.futures.ThreadPoolExecutor`` to keep blocking I/O (python-pptx,
    LibreOffice subprocess) off the asyncio event loop.
  - ``inline=True`` runs the callable *synchronously* in the calling thread — this is
    the test hook that makes ``TestClient`` tests deterministic without sleeps.

Prod upgrade path (documented, NOT built yet):
  A ``CeleryJobEngine`` or ``RQJobEngine`` that satisfies the same protocol can be
  activated by changing ``settings.job_engine`` and calling ``init_engine()`` from
  ``lifespan()``. No caller changes needed — they all go through ``get_engine()``.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol — the stable seam
# ---------------------------------------------------------------------------


@runtime_checkable
class JobEngine(Protocol):
    """Submit a callable for background execution.

    Implementations must be fire-and-forget: ``submit`` returns immediately
    and captures any exception from *fn* (logs it; never raises into the caller).
    """

    def submit(self, fn: Callable[..., Any], *args: Any) -> None:  # noqa: D102
        ...

    def shutdown(self, wait: bool = True) -> None:  # noqa: D102
        """Release resources. Called from the application lifespan on shutdown."""
        ...


# ---------------------------------------------------------------------------
# InProcessJobEngine
# ---------------------------------------------------------------------------


class InProcessJobEngine:
    """ThreadPoolExecutor-backed engine with an optional synchronous test mode.

    Parameters
    ----------
    max_workers : int
        Thread-pool size for production use. Ignored when ``inline=True``.
    inline : bool
        When True, ``submit`` runs *fn* synchronously (blocks the caller).
        Use this in tests to avoid timing-dependent polling.
    """

    def __init__(self, max_workers: int = 2, inline: bool = False) -> None:
        self._inline = inline
        self._executor: ThreadPoolExecutor | None = None
        if not inline:
            self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="job-engine")

    def submit(self, fn: Callable[..., Any], *args: Any) -> None:
        """Schedule *fn*(*args) for background execution.

        Exceptions from *fn* are caught and logged; they are NOT propagated to
        the caller (fire-and-forget contract).
        """
        if self._inline:
            # Synchronous mode for tests — run immediately in the calling thread.
            try:
                fn(*args)
            except Exception:
                logger.exception("InProcessJobEngine (inline): job fn raised")
            return

        assert self._executor is not None

        def _wrapper() -> None:
            try:
                fn(*args)
            except Exception:
                logger.exception("InProcessJobEngine: job fn raised")

        future: Future[None] = self._executor.submit(_wrapper)
        # Log top-level executor errors (e.g. if the pool itself dies).
        future.add_done_callback(
            lambda f: f.exception() and logger.error("InProcessJobEngine: future raised %s", f.exception())
        )

    def shutdown(self, wait: bool = True) -> None:
        """Gracefully drain the thread pool."""
        if self._executor is not None:
            self._executor.shutdown(wait=wait)
            self._executor = None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_ENGINE: JobEngine | None = None


def init_engine(engine: JobEngine) -> None:
    """Set the module-level engine. Called once from ``app.main.lifespan``."""
    global _ENGINE
    _ENGINE = engine


def get_engine() -> JobEngine:
    """Return the active engine. Raises if ``init_engine`` has not been called."""
    if _ENGINE is None:
        raise RuntimeError("JobEngine not initialised — call init_engine() first.")
    return _ENGINE
