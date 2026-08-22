"""Drawing quality endpoint tests (spec v3 §7.2).

/api/drawings: POST /check, GET /{id}/quality, POST /{id}/request-reexport.
"""

from pathlib import Path
import uuid

from app.ingestion.quality_gate import VERDICT_LAYERED

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "samples"
    / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
)


def test_drawings_check_endpoint_layers_sample():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    with open(SAMPLE, "rb") as fh:
        resp = client.post(
            "/api/drawings/check",
            files={"file": ("sample.pdf", fh, "application/pdf")},
        )
    assert resp.status_code == 200
    assert resp.json()["verdict"] == VERDICT_LAYERED


def test_reexport_request_persists():
    from sqlalchemy import create_engine

    from app.db.base import Base
    from app.db.models.quality import ReexportRequest

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    # endpoint writes through get_engine(); exercise model layer directly here
    with __import__("sqlalchemy").orm.Session(engine) as session:
        req = ReexportRequest(message="re-export with layers")
        session.add(req)
        session.commit()
        assert req.id is not None


def test_request_reexport_endpoint_end_to_end(tmp_path, monkeypatch):
    """Full HTTP round-trip against a hermetic per-test DB.

    The endpoint resolves its session from ``app.drawings.router.get_engine``
    (module-level import), so patching that name routes the write-through to a
    private schema-initialized engine. This keeps the test independent of the
    process-global lru_cache state on app.db.session.get_engine, which other
    tests may legitimately mutate (see test_health_db).
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session as OrmSession

    from app.db.base import Base
    from app.db.models.project import Drawing, Project
    from app.main import app

    engine = create_engine(f"sqlite:///{(tmp_path / 'gate-e2e.db').as_posix()}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr("app.drawings.router.get_engine", lambda: engine)

    client = TestClient(app)
    with OrmSession(engine) as db:
        project = Project(name="gate-e2e-test")
        db.add(project)
        db.flush()
        drawing = Drawing(project_id=project.id, discipline="electrical")
        db.add(drawing)
        db.commit()
        did = str(drawing.id)

    resp = client.post(f"/api/drawings/{did}/request-reexport")
    assert resp.status_code == 200
    assert resp.json()["status"] == "recorded"

    # no assessment recorded yet for a fresh drawing ⇒ 404, not 500
    missing = client.get(f"/api/drawings/{uuid.uuid4()}/quality")
    assert missing.status_code == 404
