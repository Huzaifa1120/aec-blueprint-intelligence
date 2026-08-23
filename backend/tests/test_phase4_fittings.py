"""Golden tests for geometry-derived fittings (Phase 4 spec §4)."""

from app.parsing.fittings import derive_fittings


def _route(pts):
    return {"polyline": [(float(x), float(y)) for x, y in pts], "layer": "P-SAN-MAIN"}


def test_right_angle_bends_count_as_elbows():
    # Two 90-degree corners; all segments long enough
    r = _route([(0, 0), (100, 0), (100, 80), (40, 80)])
    out = derive_fittings(r)
    assert out["elbows_90"] == 2
    assert out["tees"] == 0


def test_shallow_bend_below_threshold_is_not_elbow():
    # 15-degree direction change < 30-degree default threshold
    import math
    p0 = (0.0, 0.0)
    p1 = (100.0, 0.0)
    ang = math.radians(15.0)
    p2 = (p1[0] + 100.0 * math.cos(ang), p1[1] + 100.0 * math.sin(ang))
    out = derive_fittings(_route([p0, p1, p2]))
    assert out["elbows_90"] == 0


def test_tiny_segment_vertex_is_skipped():
    # Collinear long segments joined by a sub-threshold jog vertex
    r = _route([(0, 0), (100, 0), (100, 1.0), (200, 1.0)])
    out = derive_fittings(r, min_segment_pt=2.0)
    # The 1-pt segment is below min length; neither adjacent vertex counts
    assert out["elbows_90"] == 0


def test_tee_when_foreign_vertex_hits_interior():
    target = _route([(0, 0), (200, 0)])          # horizontal main
    branch = _route([(100, 0), (100, 80)])       # branch endpoint ON main interior
    out = derive_fittings(target, [branch])
    assert out["tees"] == 1


def test_endpoint_touch_is_not_tee_on_interior_route():
    # Branch tip meets main's ENDPOINT -> collinear continuation, no tee
    target = _route([(0, 0), (100, 0)])
    other = _route([(100, 0), (100, 80)])
    out = derive_fittings(target, [other])
    assert out["tees"] == 0


def test_junction_tolerance_edge():
    target = _route([(0, 0), (200, 0)])
    near = _route([(100.0, 5.9), (100.0, 80.0)])   # within 6pt tol
    far = _route([(100.0, 6.1), (100.0, 80.0)])    # outside tol
    assert derive_fittings(target, [near], junction_tol_pt=6.0)["tees"] == 1
    assert derive_fittings(target, [far], junction_tol_pt=6.0)["tees"] == 0


def test_provenance_records_kind_and_ref():
    r = _route([(0, 0), (100, 0), (100, 80)])
    out = derive_fittings(r)
    kinds = [p["kind"] for p in out["provenance"]]
    assert kinds == ["geometry_fittings:elbow"]
    assert "100.0,0.0" in out["provenance"][0]["ref"]
