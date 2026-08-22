"""Review-time instrumentation tests (spec §7.13/§15)."""


def test_session_lifecycle_and_metrics():
    from datetime import timedelta

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as OrmSession

    from app.db.base import Base
    from app.db.models.review import ReviewAction, ReviewSession

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with OrmSession(engine) as s:
        sess = ReviewSession(sheet_label="E-101")
        s.add(sess)
        s.flush()
        s.add(ReviewAction(session_id=sess.id, item_id="b1", action="accept", confidence_tier="MEASURED"))
        started = sess.started_at
        ended = started + timedelta(minutes=7)
        s.execute(
            ReviewSession.__table__.update()
            .where(ReviewSession.id == sess.id)
            .values(ended_at=ended)
        )
        s.commit()

    from app.review.router import compute_metrics

    metrics = compute_metrics(engine)
    assert metrics["sessions"] == 1
    assert abs(metrics["avg_minutes_per_sheet"] - 7.0) < 1e-6
    assert metrics["target_minutes"] > 0
    assert metrics["breaches_target"] is False


def test_empty_metrics_valid_payload():
    from sqlalchemy import create_engine

    from app.review.router import compute_metrics

    engine = create_engine("sqlite:///:memory:")
    from app.db.base import Base
    Base.metadata.create_all(engine)
    metrics = compute_metrics(engine)
    assert metrics == {
        "avg_minutes_per_sheet": None,
        "per_tier": {},
        "sessions": 0,
        "target_minutes": metrics["target_minutes"],
        "breaches_target": False,
    }


def test_review_endpoints_happy_path(tmp_path, monkeypatch):
    """HTTP round-trip against a hermetic per-test DB.

    The review endpoints resolve their session from ``app.review.router.get_engine``
    (module-level import), so patching that name routes the write-through to a
    private schema-initialized engine, independent of the process-global
    lru_cache state on app.db.session.get_engine.
    """
    from uuid import uuid4

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as OrmSession

    from app.db.base import Base
    from app.db.models.project import Project
    from app.main import app

    engine = create_engine(f"sqlite:///{(tmp_path / 'review-e2e.db').as_posix()}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.review.router.get_engine", lambda: engine)

    with OrmSession(engine) as db:
        project = Project(name="review-metrics-e2e")
        db.add(project)
        db.commit()
        pid = str(project.id)

    client = TestClient(app)

    created = client.post(
        "/api/review/sessions", json={"sheet_label": "E-101", "project_id": pid}
    )
    assert created.status_code == 200, created.text
    sid = created.json()["session_id"]

    action = client.post(
        f"/api/review/sessions/{sid}/actions",
        json={"item_id": "b1", "action": "accept", "confidence_tier": "MEASURED"},
    )
    assert action.status_code == 200, action.text

    closed = client.post(f"/api/review/sessions/{sid}/close")
    assert closed.status_code == 200, closed.text

    metrics = client.get(f"/api/projects/{pid}/review-metrics")
    assert metrics.status_code == 200, metrics.text
    body = metrics.json()
    assert body["sessions"] == 1
    assert body["target_minutes"] > 0
    assert body["breaches_target"] is False
    assert body["per_tier"] == {"MEASURED": body["avg_minutes_per_sheet"]}
    assert body["avg_minutes_per_sheet"] is not None

    # strict project_id filtering: an unrelated project sees zero sessions
    other = client.get(f"/api/projects/{uuid4()}/review-metrics")
    assert other.status_code == 200
    assert other.json()["sessions"] == 0

    # malformed ids are rejected, not 500s
    assert (
        client.post(
            "/api/review/sessions", json={"sheet_label": "X", "project_id": "not-a-uuid"}
        ).status_code
        == 400
    )
    assert client.get("/api/projects/nope/review-metrics").status_code == 400
