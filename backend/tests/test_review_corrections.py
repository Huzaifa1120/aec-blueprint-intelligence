"""Validated review actions + correction persistence (spec v3 §15).

The request contract is strict: ``action`` is a Literal of accept|reject|correct
and ``confidence_tier`` a Literal of MEASURED|DERIVED|ASSUMED|UNMAPPED — invalid
bodies get FastAPI's automatic 422 instead of being recorded verbatim.
"""


def _make_engine(tmp_path):
    from sqlalchemy import create_engine

    from app.db.base import Base

    engine = create_engine(f"sqlite:///{(tmp_path / 'review-corrections.db').as_posix()}")
    Base.metadata.create_all(engine)
    return engine


def _seed_review_session(client) -> str:
    created = client.post("/api/review/sessions", json={"sheet_label": "E-101"})
    assert created.status_code == 200, created.text
    return created.json()["session_id"]


def test_correct_action_persists_reason_value_and_boq_link(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as OrmSession

    from app.db.base import Base
    from app.db.models.estimate import BoqItem, Estimate, Measurement
    from app.db.models.project import Project
    from app.db.models.review import ReviewAction
    from app.main import app

    engine = create_engine(f"sqlite:///{(tmp_path / 'corrections-persist.db').as_posix()}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.review.router.get_engine", lambda: engine)

    with OrmSession(engine) as db:
        project = Project(name="corrections-persist")
        db.add(project)
        db.flush()
        estimate = Estimate(project_id=project.id)
        db.add(estimate)
        db.flush()
        measurement = Measurement(
            source_sheet="E-101",
            source_region="L2-CORRIDOR",
            measurement_type="length",
            raw_value=12.5,
            final_value=12.5,
        )
        db.add(measurement)
        db.flush()
        boq_item = BoqItem(
            measurement_id=measurement.id,
            estimate_id=estimate.id,
            quantity=12.5,
            unit_cost=3.0,
            total_cost=37.5,
        )
        db.add(boq_item)
        db.commit()
        boq_item_id = str(boq_item.id)

    client = TestClient(app)
    sid = _seed_review_session(client)

    resp = client.post(
        f"/api/review/sessions/{sid}/actions",
        json={
            "item_id": "row-7",
            "action": "correct",
            "confidence_tier": "MEASURED",
            "boq_item_id": boq_item_id,
            "reason": "Field measure overrides scaled length",
            "corrected_value": 14.2,
        },
    )
    assert resp.status_code == 200, resp.text

    with OrmSession(engine) as db:
        rows = db.query(ReviewAction).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.item_id == "row-7"
        assert row.action == "correct"
        assert row.confidence_tier == "MEASURED"
        assert str(row.boq_item_id) == boq_item_id
        assert row.reason == "Field measure overrides scaled length"
        assert abs(row.corrected_value - 14.2) < 1e-9


def test_accept_action_without_optionals_persists_nulls(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session as OrmSession

    from app.db.models.review import ReviewAction
    from app.main import app

    engine = _make_engine(tmp_path)
    monkeypatch.setattr("app.review.router.get_engine", lambda: engine)
    client = TestClient(app)
    sid = _seed_review_session(client)

    resp = client.post(
        f"/api/review/sessions/{sid}/actions",
        json={"item_id": "row-1", "action": "accept", "confidence_tier": "DERIVED"},
    )
    assert resp.status_code == 200, resp.text

    with OrmSession(engine) as db:
        row = db.query(ReviewAction).one()
        assert row.action == "accept"
        assert row.boq_item_id is None
        assert row.reason is None
        assert row.corrected_value is None


def test_invalid_confidence_tier_rejected_422(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.main import app

    engine = _make_engine(tmp_path)
    monkeypatch.setattr("app.review.router.get_engine", lambda: engine)
    client = TestClient(app)
    sid = _seed_review_session(client)

    resp = client.post(
        f"/api/review/sessions/{sid}/actions",
        json={"item_id": "row-1", "action": "accept", "confidence_tier": "HIGH"},
    )
    assert resp.status_code == 422


def test_legacy_free_string_action_rejected_422(tmp_path, monkeypatch):
    # contract change: spec conformance 2026-08-25 — free-string action values
    # that were previously recorded verbatim are now rejected at validation.
    from fastapi.testclient import TestClient

    from app.main import app

    engine = _make_engine(tmp_path)
    monkeypatch.setattr("app.review.router.get_engine", lambda: engine)
    client = TestClient(app)
    sid = _seed_review_session(client)

    resp = client.post(
        f"/api/review/sessions/{sid}/actions",
        json={"item_id": "row-1", "action": "flag-for-review", "confidence_tier": "MEASURED"},
    )
    assert resp.status_code == 422


def test_invalid_body_types_rejected_422(tmp_path, monkeypatch):
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from app.main import app

    engine = _make_engine(tmp_path)
    monkeypatch.setattr("app.review.router.get_engine", lambda: engine)
    client = TestClient(app)
    sid = _seed_review_session(client)

    resp = client.post(
        f"/api/review/sessions/{sid}/actions",
        json={
            "item_id": "row-1",
            "action": "correct",
            "confidence_tier": "ASSUMED",
            "boq_item_id": str(uuid4()),
            "corrected_value": "not-a-number",
        },
    )
    assert resp.status_code == 422
