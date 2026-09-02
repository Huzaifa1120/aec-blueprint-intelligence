"""HTTP integration tests for async E2E lighting endpoint (Task 2).

Tests the new async flow:
- POST /api/e2e/run → 202 + job_id (enqueue only, no pipeline execution)
- GET /api/jobs/{job_id} → status polling until done/failed

These tests are written RED first (TDD).
"""

import time
import uuid
from fastapi.testclient import TestClient


SAMPLE_PDF = (
    "C:/Users/saada/Desktop/H-new/aec-blueprint-intelligence/"
    "data/samples/MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
)


def _post_run(client: TestClient, *, persist: bool = False, project_id: str | None = None):
    """Helper to POST a PDF to /api/e2e/run."""
    with open(SAMPLE_PDF, "rb") as fh:
        files = {"file": ("sample.pdf", fh, "application/pdf")}
        params = {"persist": str(persist).lower()}
        if project_id:
            params["project_id"] = project_id
        return client.post("/api/e2e/run", files=files, params=params)


def test_post_e2e_run_returns_202_with_job_id():
    """POST /api/e2e/run returns 202 with job_id, status='queued', status_url, poll_after_ms=2000."""
    from app.main import app
    with TestClient(app) as client:
        resp = _post_run(client)
        assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "job_id" in body, "Response missing job_id"
        assert isinstance(body["job_id"], str) and len(body["job_id"]) >= 32
        assert body["status"] == "queued"
        assert "status_url" in body
        assert body["status_url"] == f"/api/jobs/{body['job_id']}"
        assert body["poll_after_ms"] == 2000


def test_get_job_returns_done_with_estimate_id():
    """GET /api/jobs/{job_id} polls to completion (up to 90s), asserts status='ok', scale present."""
    from app.main import app
    # Use TestClient as context manager to ensure lifespan startup runs
    with TestClient(app) as client:
        # Enqueue the job
        resp = _post_run(client, persist=True)
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]

        # Poll until done or failed (max 90s)
        deadline = time.time() + 90.0
        while time.time() < deadline:
            resp = client.get(f"/api/jobs/{job_id}")
            assert resp.status_code == 200, f"GET /api/jobs/{job_id} failed: {resp.text}"
            body = resp.json()
            if body["status"] in ("done", "failed"):
                break
            time.sleep(1.0)
        else:
            # Timeout - get final status for debugging
            resp = client.get(f"/api/jobs/{job_id}")
            body = resp.json()
            raise AssertionError(f"Job did not complete within 90s. Final status: {body}")

    assert body["status"] == "done", f"Job failed: {body.get('error')}"
    assert "result" in body and body["result"] is not None
    result = body["result"]
    assert result["status"] == "ok"
    assert "scale" in result
    assert "value" in result["scale"]
    assert "status" in result["scale"]
    # When persist=True, estimate_id should be present
    assert "estimate_id" in result


def test_get_job_returns_failed_with_real_error_message():
    """Inject failing runner, GET /api/jobs/{job_id} returns status='failed', error contains exception type."""
    from app.main import app
    from app.e2e.router import run_e2e_job
    from app.jobs.queue import get_job_queue

    def failing_runner(request: dict) -> dict:
        raise RuntimeError("deliberate test failure for Task 2")

    with TestClient(app) as client:
        # Set failing runner AFTER lifespan has run (inside context manager)
        queue = get_job_queue()
        queue.set_runner(failing_runner)

        try:
            # Enqueue a job
            resp = _post_run(client)
            assert resp.status_code == 202
            job_id = resp.json()["job_id"]

            # Poll until failed (should be fast)
            deadline = time.time() + 10.0
            while time.time() < deadline:
                resp = client.get(f"/api/jobs/{job_id}")
                assert resp.status_code == 200
                body = resp.json()
                if body["status"] == "failed":
                    break
                time.sleep(0.1)
            else:
                resp = client.get(f"/api/jobs/{job_id}")
                body = resp.json()
                raise AssertionError(f"Job did not fail within 10s. Status: {body}")

            assert body["status"] == "failed"
            assert body["error"] is not None
            assert "RuntimeError" in body["error"]
            assert "deliberate test failure" in body["error"]
        finally:
            # Restore real runner
            queue.set_runner(run_e2e_job)


def test_get_unknown_job_returns_404():
    """GET /api/jobs/{unknown} returns 404 with 'not found or expired'."""
    from app.main import app
    with TestClient(app) as client:
        unknown_id = str(uuid.uuid4())
        resp = client.get(f"/api/jobs/{unknown_id}")
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body
        assert "not found or expired" in body["detail"].lower()