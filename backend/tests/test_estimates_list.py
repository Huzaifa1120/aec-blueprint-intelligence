"""GET /api/estimates — paginated read-only listing for the frontend index.

Gates:
- Envelope shape {items, total, page, per_page}; defaults page=1 per_page=20.
- Ordered by project name then estimate id (stable paging; Estimate has no
  timestamp column).
- Slicing: page beyond range yields empty items with real total.
- Validation: page/per_page out of bounds → 422.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models.estimate import Estimate
from app.db.models.project import Project
from app.db.session import get_db
from app.estimates.router import router as estimates_router


@pytest.fixture()
def api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    app = FastAPI()
    app.include_router(estimates_router)
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app), session
    session.close()


def test_list_estimates_empty_defaults(api):
    client, _ = api
    response = client.get("/api/estimates")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "per_page": 20}


def test_list_estimates_envelope_order_and_paging(api):
    client, session = api
    zeta = Project(name="Zeta Clinic")
    alpha = Project(name="Alpha Villa")
    mid = Project(name="Mid Office")
    session.add_all(
        [
            Estimate(project=zeta, total_cost=12.0),
            Estimate(project=alpha, total_cost=120.0),
            Estimate(project=mid, total_cost=60.0),
        ]
    )
    session.commit()

    first = client.get("/api/estimates", params={"page": 1, "per_page": 2}).json()
    assert first["total"] == 3
    assert first["page"] == 1
    assert first["per_page"] == 2
    assert [i["project_name"] for i in first["items"]] == ["Alpha Villa", "Mid Office"]
    assert first["items"][0]["total_cost"] == pytest.approx(120.0)
    assert set(first["items"][0].keys()) == {
        "estimate_id",
        "project_name",
        "total_material_cost",
        "total_labor_cost",
        "total_cost",
    }

    second = client.get("/api/estimates", params={"page": 2, "per_page": 2}).json()
    assert [i["project_name"] for i in second["items"]] == ["Zeta Clinic"]

    beyond = client.get("/api/estimates", params={"page": 9, "per_page": 2}).json()
    assert beyond["items"] == []
    assert beyond["total"] == 3


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page": -1}, {"per_page": 0}, {"per_page": 101}],
)
def test_list_estimates_rejects_out_of_bounds_params(api, params):
    client, _ = api
    response = client.get("/api/estimates", params=params)
    assert response.status_code == 422
