"""Route tracing measures run-length CENTERLINES — never perimeters.

Bug (2026-08-25 owner report): MMC cable tray BOQ showed 0.752 m for a run
that visibly spans most of Basement 2 (~18 m). Evidence-probed root causes:

1. The three main tray legs are drawn as single ``('qu', Quad)`` items —
   filled ribbon quadrilaterals (111.1 / 168.8 / 218.2 pt long axes ≈ 498 pt
   ≈ 17.6 m at 1:100). ``extract_polyline_from_items`` had no ``qu`` branch,
   so the legs yielded ZERO points and silently vanished.
2. Even when parseable, paths whose bbox diagonal exceeds the symbol cutoff
   (6 × merge threshold = 30 pt) are excluded from symbol clustering
   (spec v3 §7.4 geometry branching) — and ``measure_routes`` only iterates
   clusters, so route-scale geometry was unreachable by construction.
3. The one measured fragment (a closed 10-segment loop at the corridor
   junction) was PERIMETER-walked: 21.3 pt billed for a ~6.1 pt crossing.

Fix contract pinned here:
- Ribbon quads / rects / closed line-loops reduce to their centerline
  (short-side-midpoint pair / bbox long axis); open polylines unchanged.
- The e2e router clusters ROUTE layers WITHOUT the symbol cutoff and feeds
  those clusters to ``measure_routes`` (helper mirrors
  ``_unmapped_layer_clusters``); symbol clustering + certified count
  baselines stay byte-identical.
"""

import math
from pathlib import Path

import pytest

from app.parsing.routes import (
    compute_length_meters,
    extract_polyline_from_items,
    measure_routes,
)

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "samples"
    / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
)


class _Q:
    """Minimal pymupdf.Quad stand-in (attrs ul/ur/ll/lr, cyclic ul→ur→lr→ll)."""

    def __init__(self, ul, ur, lr, ll):
        self.ul, self.ur, self.lr, self.ll = ul, ur, lr, ll


def _len(pts):
    return sum(
        math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]) for i in range(1, len(pts))
    )


# ---------------------------------------------------------------------------
# Unit: primitive extraction
# ---------------------------------------------------------------------------


def test_quad_ribbon_horizontal_yields_exact_centerline():
    # Horizontal ribbon 111.12 pt × 3.6 pt (real MMC leg-1 geometry)
    quad = _Q((346.56, 480.72), (235.44, 480.72), (235.44, 484.32), (346.56, 484.32))
    pts = extract_polyline_from_items([("qu", quad)])
    assert len(pts) == 2
    assert _len(pts) == pytest.approx(111.12, abs=1e-6)


def test_quad_ribbon_vertical_yields_exact_centerline():
    # Vertical ribbon 168.84 pt × 3.48 pt (real MMC leg-2 geometry)
    quad = _Q((347.88, 310.56), (351.36, 310.56), (351.36, 479.40), (347.88, 479.40))
    pts = extract_polyline_from_items([("qu", quad)])
    assert _len(pts) == pytest.approx(168.84, abs=1e-6)


def test_rect_item_yields_centerline_not_perimeter():
    rect = (100.0, 200.0, 300.0, 203.0)  # 200 × 3
    pts = extract_polyline_from_items([("re", rect)])
    assert _len(pts) == pytest.approx(200.0, abs=1e-6)


def test_closed_line_loop_yields_long_axis_not_perimeter():
    # Closed square-ish loop 6.12 × 4.92 pt (MMC junction fitting shape)
    loop = []
    ring = [(0.0, 0.0), (6.12, 0.0), (6.12, 4.92), (0.0, 4.92)]
    for i in range(len(ring)):
        a, b = ring[i], ring[(i + 1) % len(ring)]
        loop.append(("l", a, b))
    pts = extract_polyline_from_items(loop)
    assert _len(pts) == pytest.approx(6.12, abs=1e-6)


def test_open_chain_unchanged():
    # Pinned contract (tests/test_phase4_fixture_pdf.py): consecutive shared
    # endpoints stay in the raw extraction; measure_routes collapses them
    # during chaining.
    a, b, c = (0.0, 0.0), (10.0, 0.0), (10.0, 5.0)
    assert extract_polyline_from_items([("l", a, b), ("l", b, c)]) == [a, b, b, c]


# ---------------------------------------------------------------------------
# Integration: MMC cable-tray route reaches drawn truth
# ---------------------------------------------------------------------------


def test_mmc_tray_route_length_matches_drawn_truth(tmp_path, monkeypatch):
    """Drawn truth: legs 111.12+168.84+218.16 pt + ~6.12 pt junction crossing
    ≈ 504.2 pt ⇒ ×(100×25.4/(72×1000)) ≈ 17.79 m at 1:100. The old pipeline
    billed 0.752 m (one sub-cutoff junction fragment, perimeter-walked)."""
    from sqlalchemy import create_engine

    from app.db.base import Base
    from app.main import app
    from fastapi.testclient import TestClient

    db_path = tmp_path / "test_tray.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setattr(
        "app.e2e.router.get_engine",
        lambda: create_engine(f"sqlite:///{db_path}"),
    )
    with open(SAMPLE, "rb") as fh:
        resp = TestClient(app).post(
            "/api/e2e/run",
            files={"file": ("sample.pdf", fh, "application/pdf")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # The legacy linear route rule bills BOM constants × length_m, so the
    # cable_tray_section row's quantity equals the measured run length.
    lengths = [
        item["quantity"]
        for item in body["boq_items"]
        if "tray" in str(item.get("material_name", "")).lower()
    ]
    assert lengths, f"no cable tray rows in BOQ: {body['boq_items'][:5]}"
    assert max(lengths) == pytest.approx(17.79, rel=0.02)


def test_mmc_tray_scale_math_is_dimensionally_sound():
    """Sanity on the conversion itself: 10 pt at 1:100 MUST be 0.353 m
    (pinned truth from test_phase2_regression) — the failure was geometry
    reach, never this factor."""
    assert compute_length_meters([(0.0, 0.0), (10.0, 0.0)], "1:100") == pytest.approx(
        0.353, abs=5e-4
    )


# ---------------------------------------------------------------------------
# Unit: route-scale paths reach measure_routes (uncapped clustering)
# ---------------------------------------------------------------------------


def test_measure_routes_sees_long_paths_via_uncapped_cluster_helper():
    """A >30 pt-diagonal path on a route layer must be measurable — the old
    pipeline dropped it between symbol clustering and route tracing."""
    from app.e2e.router import _route_layer_clusters

    long_leg = {
        "id": "leg1",
        "layer": "CABLE_TRAY",
        "bbox": [0.0, 0.0, 200.0, 4.0],
        "page_number": 1,
        "items": [("l", (0.0, 0.0), (200.0, 0.0))],
    }
    clusters = _route_layer_clusters([long_leg], "1:100")
    assert clusters, "route-scale path must cluster when the cutoff is lifted"
    routes = measure_routes(clusters, [long_leg], "1:100", ("CABLE_TRAY",))
    assert len(routes) == 1
    # 200 pt at 1:100 = 7.056 m
    assert routes[0]["length_m"] == pytest.approx(7.056, abs=5e-3)


def test_cluster_length_never_bills_inter_path_hops():
    """Two disjoint strips in one cluster: total = sum of each strip's own
    length. The chained-walk implementation billed the member-order jump
    between them (a zigzag across the sheet) as tray length."""
    from app.e2e.router import _route_layer_clusters

    def strip(pid, y):
        return {
            "id": pid,
            "layer": "NORMAL TRAY",
            "bbox": [0.0, y, 100.0, y + 3.0],
            "page_number": 1,
            "items": [("l", (0.0, y + 1.5), (100.0, y + 1.5))],
        }

    # Same layer, ends >threshold apart ⇒ one merged network is impossible,
    # so force membership via a bridging third strip (bbox chain).
    paths = [
        strip("a", 0.0),
        {  # bridge: vertical strip joining a and b top-to-top
            "id": "bridge",
            "layer": "NORMAL TRAY",
            "bbox": [99.0, 0.0, 102.0, 30.0],
            "page_number": 1,
            "items": [("l", (100.5, 1.5), (100.5, 28.5))],
        },
        strip("b", 30.0),
    ]
    clusters = _route_layer_clusters(paths, "1:100")
    assert len(clusters) == 1
    routes = measure_routes(clusters, paths, "1:100", ("NORMAL TRAY",))
    assert len(routes) == 1
    # Σ own geometry: 100 + 27 + 100 pt — the walk from strip-a's tail to the
    # bridge and onward adds nothing.
    expected_pt = 100.0 + 27.0 + 100.0
    assert routes[0]["length_m"] == pytest.approx(expected_pt * 100 * 25.4 / (72 * 1000), abs=5e-3)


def test_elongated_route_paths_merge_despite_distant_centroids():
    """Two 111 pt strips whose ENDS touch (centroids ~111 pt apart) form ONE
    run. Centroid-grid bucketing (symbol mode) can never compare them; route
    clustering must bucket by enlarged bboxes instead."""
    from app.e2e.router import _route_layer_clusters

    def strip(pid, x0, x1):
        return {
            "id": pid,
            "layer": "NORMAL TRAY",
            "bbox": [x0, 480.7, x1, 484.3],
            "page_number": 1,
            "items": [("l", (x0, 482.5), (x1, 482.5))],
        }

    paths = [strip("s1", 235.44, 346.56), strip("s2", 346.56, 457.68)]
    clusters = _route_layer_clusters(paths, "1:100")
    assert len(clusters) == 1, [c["member_path_ids"] for c in clusters]
    routes = measure_routes(clusters, paths, "1:100", ("NORMAL TRAY",))
    assert len(routes) == 1
    # (111.12 + 111.12) pt at 1:100
    assert routes[0]["length_m"] == pytest.approx(222.24 * 100 * 25.4 / (72 * 1000), abs=5e-3)
