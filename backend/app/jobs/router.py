"""Job status polling endpoint — GET /api/jobs/{job_id}."""

from fastapi import APIRouter, HTTPException

from app.jobs.queue import get_job_queue

jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@jobs_router.get("/{job_id}")
def get_job(job_id: str) -> dict:
    """Return job status and result.

    Response shape:
    {
        "id": "...",
        "status": "queued|running|done|failed",
        "progress": "...",
        "created_at": ...,
        "started_at": ...,
        "finished_at": ...,
        "result": {...},
        "error": "..."
    }

    When status=done, result carries the SAME shape the synchronous
    e2e_run endpoint returned (so frontend redirect keeps working).
    """
    queue = get_job_queue()
    try:
        job = queue.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Job not found or expired")

    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "result": job.result,
        "error": job.error,
    }