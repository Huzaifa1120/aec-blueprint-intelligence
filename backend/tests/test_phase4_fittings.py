"""Golden tests for geometry-derived fittings (Phase 4 spec §4)."""

from app.core.config import get_settings
from app.e2e.router import resolve_route_context
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


# ---------------------------------------------------------------------------
# Tee discipline restriction (final-review F1): sibling candidates in
# resolve_route_context must classify into the target route's discipline.
# Size resolves via the sanitary_drainage YAML default (diameter_mm 100).
# ---------------------------------------------------------------------------


def _ctx_with_sibling(sibling_layer: str):
    target = {
        "polyline": [(0.0, 0.0), (200.0, 0.0)],
        "layer": "P-SAN-MAIN",
        "length_m": 5.0,
        "type": "sanitary_drainage",
    }
    sibling = {
        "polyline": [(100.0, 0.0), (100.0, 80.0)],
        "layer": sibling_layer,
        "length_m": 2.0,
        "type": "cable_tray",
    }
    all_routes = [target, sibling]
    return resolve_route_context(
        "sanitary_drainage",
        all_routes[0],
        [],  # cascade_spans
        "1:100",  # scale
        [],  # schedule_rows
        [],  # components
        all_routes,
        0,
        settings=get_settings(),
    )


def test_foreign_discipline_crossing_yields_no_tee():
    ctx = _ctx_with_sibling("NORMAL TRAY")  # classifies electrical
    assert ctx is not None
    variables, _, size = ctx
    assert float(variables["tees"]) == 0.0
    assert float(size["tees"]) == 0.0


def test_same_discipline_crossing_yields_one_tee():
    ctx = _ctx_with_sibling("P-SAN-BRANCH")  # classifies plumbing
    assert ctx is not None
    variables, _, size = ctx
    assert float(variables["tees"]) == 1.0
    assert float(size["tees"]) == 1.0
