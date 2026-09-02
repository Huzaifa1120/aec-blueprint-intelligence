"""Helper: poll an async e2e_run job to completion in tests."""
import os
import time
from fastapi.testclient import TestClient


def post_and_wait(
    client: TestClient, file_path: str, persist: bool = False, timeout: float = 90.0
) -> dict:
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        r = client.post(
            f"/api/e2e/run?persist={str(persist).lower()}",
            files={"file": (filename, f, "application/pdf")},
        )
    assert r.status_code == 202, f"enqueue failed: {r.status_code} {r.text}"
    job_id = r.json()["job_id"]
    deadline = time.time() + timeout
    body = None
    while time.time() < deadline:
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] in ("done", "failed"):
            break
        time.sleep(0.5)
    assert body is not None and body["status"] == "done", f"job did not finish: {body}"
    return body