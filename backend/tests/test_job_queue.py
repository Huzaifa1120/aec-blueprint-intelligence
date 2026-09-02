"""Tests for the in-memory job queue (PRD §6: 'Async processing — job queue')."""
import time
import threading
import pytest
from app.jobs.queue import InMemoryJobQueue


def test_enqueue_returns_job_id():
    q = InMemoryJobQueue()
    job_id = q.enqueue("e2e_run", {"file_path": "/tmp/x.pdf", "persist": False})
    assert isinstance(job_id, str) and len(job_id) >= 32


def test_get_returns_queued_job():
    q = InMemoryJobQueue()
    job_id = q.enqueue("e2e_run", {"file_path": "/tmp/x.pdf"})
    job = q.get(job_id)
    assert job.id == job_id
    assert job.status == "queued"
    assert job.result is None
    assert job.error is None


def test_worker_marks_status_running():
    q = InMemoryJobQueue()

    def run(req: dict) -> dict:
        # mark running via a hook by sleeping so the test can poll
        time.sleep(0.05)
        return {"status": "ok", "boq_items": []}

    q.set_runner(run)  # injected; see implementation note
    job_id = q.enqueue("e2e_run", {"file_path": "/tmp/x.pdf"})
    time.sleep(0.01)  # let worker transition to running
    job = q.get(job_id)
    assert job.status in ("running", "done")  # race-tolerant


def test_worker_marks_status_done_on_success():
    q = InMemoryJobQueue()

    def run(req: dict) -> dict:
        return {"status": "ok", "boq_items": [], "estimate_id": "abc"}

    q.set_runner(run)
    job_id = q.enqueue("e2e_run", {"file_path": "/tmp/x.pdf"})
    # Wait up to 2 s for completion
    deadline = time.time() + 2.0
    while time.time() < deadline:
        job = q.get(job_id)
        if job.status in ("done", "failed"):
            break
        time.sleep(0.05)
    assert job.status == "done"
    assert job.result == {"status": "ok", "boq_items": [], "estimate_id": "abc"}


def test_worker_marks_status_failed_on_exception():
    q = InMemoryJobQueue()

    def run(req: dict) -> dict:
        raise ValueError("deliberate test failure")

    q.set_runner(run)
    job_id = q.enqueue("e2e_run", {"file_path": "/tmp/x.pdf"})
    deadline = time.time() + 2.0
    while time.time() < deadline:
        job = q.get(job_id)
        if job.status in ("done", "failed"):
            break
        time.sleep(0.05)
    assert job.status == "failed"
    assert job.error is not None
    assert "ValueError" in job.error
    assert "deliberate test failure" in job.error


def test_job_ttl_expires_after_5_min():
    q = InMemoryJobQueue()
    # Patch TTL to 0.1 s for the test
    q._JOB_TTL_SEC = 0.1

    def run(req: dict) -> dict:
        return {"status": "ok"}

    q.set_runner(run)
    job_id = q.enqueue("e2e_run", {"file_path": "/tmp/x.pdf"})
    time.sleep(0.2)  # wait past TTL
    with pytest.raises(KeyError):
        q.get(job_id)


def test_queue_bounds_to_100_jobs():
    q = InMemoryJobQueue()
    q._MAX_JOBS = 5  # shrink for the test

    def run(req: dict) -> dict:
        return {"status": "ok"}

    q.set_runner(run)
    ids = [q.enqueue("e2e_run", {"file_path": f"/tmp/{i}.pdf"}) for i in range(10)]
    time.sleep(0.3)  # let workers drain
    # After eviction, only the newest 5 ids should be retrievable
    retrievable = [i for i in ids if _try_get(q, i)]
    assert len(retrievable) == 5
    assert retrievable == ids[-5:]


def test_concurrent_enqueue_is_thread_safe():
    """Tightened per F7: asserts capacity invariant + no duplicate IDs.

    Without these assertions, the test would pass even if locks were
    broken (the queue might exceed capacity or emit duplicate IDs).
    """
    q = InMemoryJobQueue()
    q._MAX_JOBS = 50  # shrink for the test

    def run(req: dict) -> dict:
        return {"status": "ok"}

    q.set_runner(run)

    enqueued_ids: list[str] = []
    enqueued_lock = threading.Lock()

    def worker(i: int) -> None:
        for _ in range(20):
            jid = q.enqueue("e2e_run", {"file_path": f"/tmp/{i}.pdf"})
            with enqueued_lock:
                enqueued_ids.append(jid)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    time.sleep(0.5)  # let workers drain

    # Capacity invariant: queue must never exceed _MAX_JOBS
    assert len(q._jobs) <= q._MAX_JOBS, (
        f"queue exceeded capacity: {len(q._jobs)} > {q._MAX_JOBS}"
    )

    # No duplicate IDs (enqueue must be atomic w.r.t. ID generation)
    assert len(enqueued_ids) == len(set(enqueued_ids)), "duplicate job IDs"

    # Each retrievable job has a consistent state
    for jid in enqueued_ids[-10:]:  # spot-check the most-recent 10
        try:
            job = q.get(jid)
            assert job.id == jid
            assert job.status in ("queued", "running", "done", "failed")
        except KeyError:
            pass  # OK if it was evicted by capacity/TTL

    # Queue is still functional after the storm
    jid = q.enqueue("e2e_run", {"file_path": "/tmp/x.pdf"})
    assert q.get(jid) is not None


def _try_get(q, jid):
    try:
        q.get(jid)
        return True
    except KeyError:
        return False