"""In-memory FIFO job queue — PRD §6 async processing, single-tenant v2."""
from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from dataclasses import dataclass
from typing import Callable, Literal, Optional

logger = logging.getLogger(__name__)

JobStatus = Literal["queued", "running", "done", "failed"]
RunnerFn = Callable[[dict], dict]


@dataclass
class Job:
    id: str
    kind: Literal["e2e_run"]
    status: JobStatus
    created_at: float
    started_at: Optional[float]
    finished_at: Optional[float]
    request: dict
    result: Optional[dict] = None
    error: Optional[str] = None
    progress: str = ""


class InMemoryJobQueue:
    """Thread-safe in-memory FIFO queue with TTL + capacity bounds.

    Single daemon worker thread processes jobs in arrival order. The
    worker is started in __init__ and runs for the process lifetime.
    Queue is intentionally in-memory only — single-tenant v2 tool.
    """

    _MAX_JOBS = 100
    _JOB_TTL_SEC = 300  # 5 min after finished_at

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._runner: Optional[RunnerFn] = None
        self._stop = False
        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="job-worker")
        self._thread.start()

    def set_runner(self, fn: RunnerFn) -> None:
        """Inject the actual e2e_run body. Called once at app startup."""
        with self._lock:
            self._runner = fn

    def enqueue(self, kind: Literal["e2e_run"], request: dict) -> str:
        with self._cv:
            job_id = str(uuid.uuid4())
            self._jobs[job_id] = Job(
                id=job_id, kind=kind, status="queued",
                created_at=time.time(), started_at=None, finished_at=None,
                request=request, result=None, error=None, progress="queued",
            )
            self._evict_expired_locked()
            self._cv.notify()
            return job_id

    def get(self, job_id: str) -> Job:
        with self._lock:
            self._evict_expired_locked()
            if job_id not in self._jobs:
                raise KeyError(f"job not found or expired: {job_id}")
            return self._jobs[job_id]

    def _evict_expired_locked(self) -> None:
        """Called with the lock held. Evicts finished jobs past TTL,
        and oldest jobs if over capacity. Preserves queued/running."""
        now = time.time()
        # 1. evict finished+expired
        expired = [
            jid for jid, j in self._jobs.items()
            if j.finished_at is not None and (now - j.finished_at) > self._JOB_TTL_SEC
        ]
        for jid in expired:
            del self._jobs[jid]
        # 2. capacity: if still over _MAX_JOBS, evict oldest finished first
        if len(self._jobs) > self._MAX_JOBS:
            finished = sorted(
                [(j.finished_at or 0, jid) for jid, j in self._jobs.items()
                 if j.finished_at is not None]
            )
            while len(self._jobs) > self._MAX_JOBS and finished:
                _, jid = finished.pop(0)
                del self._jobs[jid]
        # 3. last resort: evict oldest queued
        if len(self._jobs) > self._MAX_JOBS:
            queued = sorted(
                [(j.created_at, jid) for jid, j in self._jobs.items()
                 if j.status == "queued"]
            )
            while len(self._jobs) > self._MAX_JOBS and queued:
                _, jid = queued.pop(0)
                del self._jobs[jid]

    def _worker_loop(self) -> None:
        while not self._stop:
            with self._cv:
                while not self._stop and not self._jobs:
                    self._cv.wait(timeout=1.0)
                if self._stop:
                    return
                # pick the oldest queued job
                queued = sorted(
                    [(j.created_at, jid) for jid, j in self._jobs.items()
                     if j.status == "queued"]
                )
                if not queued:
                    continue
                _, job_id = queued[0]
                job = self._jobs[job_id]
                job.status = "running"
                job.started_at = time.time()
                job.progress = "starting"
                runner = self._runner

            if runner is None:
                # No runner set — mark failed with explanation
                with self._lock:
                    job.status = "failed"
                    job.finished_at = time.time()
                    job.error = "no runner registered (set_runner() not called)"
                continue

            # Run outside the lock
            try:
                job.progress = "running"
                result = runner(job.request)
                with self._lock:
                    job.result = result
                    job.status = "done"
                    job.finished_at = time.time()
                    job.progress = "done"
            except Exception as exc:
                tb = traceback.format_exc().splitlines()
                short = f"{type(exc).__name__}: {exc} | " + (tb[-2] if len(tb) >= 2 else "")
                logger.exception("job %s failed", job_id)
                with self._lock:
                    job.status = "failed"
                    job.finished_at = time.time()
                    job.error = short
                    job.progress = "failed"


# Module-level singleton — wired up in app startup (Task 2)
_queue: Optional[InMemoryJobQueue] = None


def get_job_queue() -> InMemoryJobQueue:
    global _queue
    if _queue is None:
        _queue = InMemoryJobQueue()
    return _queue