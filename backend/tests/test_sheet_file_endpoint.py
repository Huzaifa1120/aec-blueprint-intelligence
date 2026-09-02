"""Task 9: store the uploaded drawing per estimate + serve it back.

Runs the synthetic HVAC fixture through POST /api/e2e/run?persist=true
(the integration-test pattern from tests/test_v3_integration.py) and verifies:

- GET /api/estimates/{id}/file returns 200 ``application/pdf`` whose bytes
  match the uploaded document exactly;
- the persisted Estimate.source_pdf_path points at backend/data/uploads/;
- a legacy estimate (source_pdf_path NULL) 404s cleanly — the frontend PDF
  viewer must never get a broken response for pre-Task-9 estimates;
- an unknown estimate id 404s.
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.db.models.estimate import Estimate
from app.db.models.project import Project
from app.db.session import get_engine
from tests.fixtures.make_hvac_fixture import build_hvac_fixture
from tests._e2e_async import post_and_wait


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def stored_run(client, tmp_path_factory):
    """Persist-run on the synthetic fixture with known upload bytes."""
    pdf_dir = tmp_path_factory.mktemp("sheet_file")
    pdf_path = str(pdf_dir / "hvac_sheet_file.pdf")
    build_hvac_fixture(pdf_path)
    with open(pdf_path, "rb") as f:
        upload_bytes = f.read()
    body = post_and_wait(client, pdf_path, persist=True)
    result = body["result"]
    assert result["status"] == "ok", result
    assert "estimate_id" in result
    return result, upload_bytes


# ---------------------------------------------------------------------------
# Stored file round trip
# ---------------------------------------------------------------------------
class TestSheetFileEndpoint:
    def test_stored_file_round_trips_bytes(self, client, stored_run):
        body, upload_bytes = stored_run
        estimate_id = body["estimate_id"]
        response = client.get(f"/api/estimates/{estimate_id}/file")
        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        assert response.content == upload_bytes

    def test_estimate_records_stored_path(self, stored_run):
        body, _ = stored_run
        with OrmSession(get_engine()) as db:
            estimate = db.get(Estimate, uuid.UUID(body["estimate_id"]))
            assert estimate is not None
            assert estimate.source_pdf_path
            assert estimate.source_pdf_path.endswith(f"{body['estimate_id']}.pdf")
            assert os.path.isfile(estimate.source_pdf_path)


# ---------------------------------------------------------------------------
# Legacy tolerance + unknown ids
# ---------------------------------------------------------------------------
def test_legacy_estimate_without_stored_file_404s(client):
    with OrmSession(get_engine()) as db:
        project = db.query(Project).first()
        assert project is not None
        legacy = Estimate(project_id=project.id)
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        legacy_id = str(legacy.id)
    response = client.get(f"/api/estimates/{legacy_id}/file")
    assert response.status_code == 404
    assert response.json()["detail"] == "Source file not stored for this estimate"


def test_unknown_estimate_404s(client):
    response = client.get(f"/api/estimates/{uuid.uuid4()}/file")
    assert response.status_code == 404
