"""Data-quality counters (spec v3 conformance): nothing vanishes silently.

Every input that enters the e2e pipeline but silently vanishes — a route with
no applicable assembly, a symbol skipped in the count path, an unmapped
cluster, a degenerate polyline, a fixture outside the FU corridor, a failed
upload classification — must be tallied and surfaced in the response under
``data_quality``.
"""

from fastapi.testclient import TestClient

import app.e2e.router as er
from app.main import app
from app.parsing.fixture_units import accumulate_fixture_units
from app.parsing.routes import measure_routes


def _fake_parsed(**overrides):
    fake = dict(
        raw_drawings=[],
        raw_text_spans=[{"text": "nothing useful"}],
        clusters=[],
        components=[],
        annotations=[],
        schedule_rows=[],
        ocg_registry={},
    )
    fake.update(overrides)
    return fake


def _post_run(monkeypatch, parsed):
    monkeypatch.setattr(
        er,
        "classify_upload",
        lambda p: {"status": "vector", "source_quality": "layered_vector"},
    )
    monkeypatch.setattr(er, "parse_pdf", lambda p: parsed)
    client = TestClient(app)
    return client.post(
        "/api/e2e/run",
        files={"file": ("t.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )


def test_response_carries_data_quality_block(monkeypatch):
    resp = _post_run(monkeypatch, _fake_parsed())
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_quality"] == {
        "dropped_routes": 0,
        "dropped_symbols": 0,
        "unmapped_count": 0,
        "degenerate_skipped": 0,
        "fu_corridor_excluded": 0,
        "classifier_errors": 0,
        "title_block_excluded": 0,
        "legend_gate_excluded": 0,
    }


def test_dropped_routes_counted(monkeypatch):
    drawings = [
        {
            "id": "p1",
            "layer": "CABLE_TRAY",
            "bbox": [0.0, 0.0, 200.0, 4.0],
            "items": [("l", (0.0, 0.0), (200.0, 0.0))],
        }
    ]
    clusters = [
        {
            "cluster_id": 0,
            "centroid": None,
            "member_path_ids": ["p1"],
            "num_paths": 1,
            "bbox": (0.0, 0.0, 200.0, 4.0),
        }
    ]
    # Simulate YAML/code drift: no route-layer cluster resolves to a route
    # assembly any more, so the measured tray route must drop at gate 1.
    monkeypatch.setattr(er, "ROUTE_ASSEMBLIES", frozenset())
    resp = _post_run(monkeypatch, _fake_parsed(raw_drawings=drawings, clusters=clusters))
    assert resp.status_code == 200
    body = resp.json()
    assert body["routes_measured"] == 1
    assert body["data_quality"]["dropped_routes"] == 1


def test_dropped_symbols_counted(monkeypatch):
    ghost = {
        "assembly_type": "ghost_widget",
        "count": 1,
        "layer": "GHOST",
        "x": 10.0,
        "y": 10.0,
        "source_path_ids": ["p9"],
        "confidence_status": "MEASURED",
        "confidence_score": 1.0,
    }
    monkeypatch.setattr(er, "count_components", lambda *a, **k: [ghost])
    resp = _post_run(monkeypatch, _fake_parsed())
    assert resp.status_code == 200
    body = resp.json()
    assert body["components_found"] == 1
    assert body["boq_items"] == []
    assert body["data_quality"]["dropped_symbols"] == 1


def test_unmapped_count_tallied(monkeypatch):
    drawings = [
        {
            "id": "u1",
            "layer": "PSEUDO-GRID",
            "bbox": [100.0, 100.0, 104.0, 104.0],
        }
    ]
    resp = _post_run(
        monkeypatch,
        _fake_parsed(raw_drawings=drawings, ocg_registry={"PSEUDO-GRID": {}}),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_quality"]["unmapped_count"] == 1


def test_classifier_error_degrades_and_counts(monkeypatch):
    def boom(p):
        raise RuntimeError("classify exploded")

    monkeypatch.setattr(er, "classify_upload", boom)
    client = TestClient(app)
    resp = client.post(
        "/api/e2e/run",
        files={"file": ("t.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "raster"
    assert body["data_quality"]["classifier_errors"] == 1


def test_measure_routes_counts_degenerate_skipped():
    stats = {}
    routes = measure_routes(
        [{"member_path_ids": ["p1"]}],
        [{"id": "p1", "layer": "CABLE_TRAY", "items": [("l", (0.0, 0.0), (0.0, 0.0))]}],
        "1:100",
        stats=stats,
    )
    assert routes == []
    assert stats["degenerate_skipped"] == 1


def test_accumulate_fixture_units_counts_corridor_excluded():
    stats = {}
    total, breakdown = accumulate_fixture_units(
        [(0.0, 0.0), (100.0, 0.0)],
        [{"key": "w1", "component_type": "wc", "x": 500.0, "y": 500.0}],
        corridor_pt=24.0,
        stats=stats,
    )
    assert total == 0.0
    assert breakdown == []
    assert stats["fu_corridor_excluded"] == 1


def test_in_corridor_fixture_not_counted_as_excluded():
    stats = {}
    total, breakdown = accumulate_fixture_units(
        [(0.0, 0.0), (100.0, 0.0)],
        [{"key": "w1", "component_type": "wc", "x": 50.0, "y": 0.0}],
        corridor_pt=24.0,
        stats=stats,
    )
    assert total == 3.0
    assert len(breakdown) == 1
    assert stats.get("fu_corridor_excluded", 0) == 0
