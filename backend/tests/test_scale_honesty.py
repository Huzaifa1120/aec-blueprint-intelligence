"""Scale honesty end-to-end (spec v3 §7.4): unparseable scale == missing →
1:100 assumed, never 1:1; the e2e response carries an explicit scale block."""

from app.parsing.routes import compute_length_meters
from app.parsing.scale import resolve_scale


def test_unparseable_scale_no_longer_means_1_to_1():
    # 10pt at 1:100 = 0.353m (existing pinned truth). Garbage must equal missing.
    assert compute_length_meters([(0, 0), (10, 0)], "garbage") == compute_length_meters(
        [(0, 0), (10, 0)], "1:100"
    )


def test_resolver_flags_missing_scale_for_pipeline():
    assert resolve_scale([]).status == "assumed"


def test_run_response_carries_scale_block(monkeypatch):
    from fastapi.testclient import TestClient

    import app.e2e.router as er
    from app.main import app

    class FakeParsed(dict):
        pass

    fake = FakeParsed(
        raw_drawings=[],
        raw_text_spans=[{"text": "nothing useful"}],
        clusters=[],
        components=[],
        annotations=[],
        schedule_rows=[],
        ocg_registry={},
    )
    monkeypatch.setattr(
        er, "classify_upload", lambda p: {"status": "vector", "source_quality": "layered_vector"}
    )
    monkeypatch.setattr(er, "parse_pdf", lambda p: fake)

    client = TestClient(app)
    resp = client.post(
        "/api/e2e/run",
        files={"file": ("t.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scale"]["status"] == "assumed"
    assert body["scale"]["value"] == "1:100"
