"""GET /api/estimates — read-only listing for the frontend estimates index.

Gates:
- Returns one row per persisted estimate with project name + cost totals.
- Ordered by project name (Estimate has no timestamp column).
- Empty database yields [].
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


def test_list_estimates_empty(api):
    client, _ = api
    response = client.get("/api/estimates")
    assert response.status_code == 200
    assert response.json() == []


def test_list_estimates_returns_rows_ordered_by_project_name(api):
    client, session = api
    zeta = Project(name="Zeta Clinic")
    alpha = Project(name="Alpha Villa")
    session.add_all(
        [
            Estimate(project=zeta, total_material_cost=10.0, total_labor_cost=2.0, total_cost=12.0),
            Estimate(
                project=alpha, total_material_cost=100.0, total_labor_cost=20.0, total_cost=120.0
            ),
        ]
    )
    session.commit()

    response = client.get("/api/estimates")
    assert response.status_code == 200
    rows = response.json()
    assert [r["project_name"] for r in rows] == ["Alpha Villa", "Zeta Clinic"]
    assert rows[0]["total_cost"] == pytest.approx(120.0)
    assert set(rows[0].keys()) == {
        "estimate_id",
        "project_name",
        "total_material_cost",
        "total_labor_cost",
        "total_cost",
    }
