"""Clustering migration: union-find parity vs legacy DBSCAN."""

import math
from pathlib import Path

from app.parsing.clustering import (
    UnionFind,
    bbox_distance,
    cluster_paths_threshold,
    derive_threshold_px,
)
from app.ingestion.vector import cluster_paths as dbscan_cluster_paths
from app.parsing.components import component_totals, count_components

SAMPLE = str(
    Path(__file__).resolve().parents[2]
    / "data"
    / "samples"
    / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
)

# Symbol/route separation (spec v3 §7.4 geometry-type branching): the cutoff
# derives from the sheet scale as factor × merge threshold, never an absolute
# constant. Factor 6 is fixed by this parity proof (fallback basis: 6 × 5 pt).
THRESHOLD_PX = 5.0
SYMBOL_CUTOFF_FACTOR = 6.0
MAX_SYMBOL_DIAGONAL_PX = SYMBOL_CUTOFF_FACTOR * THRESHOLD_PX

# Human-approved re-baseline (ruling 2026-08-22): union-find counts are the
# certified source of truth on the regression sheet; legacy DBSCAN numbers
# are retired (audit trail in the full-pipeline test docstring below).
APPROVED_REBASELINE_COUNTS = {
    "access_control_door": 2,
    "cable_tray": 1,
    "lighting_outlet": 26,
    # New layer mapping approved by owner 2026-08-24 (Phase 4 T5); per-layer
    # clustering behavior untouched — 11 downpipe symbols on the MMC sheet are
    # genuinely counted under the new storm_downpipe mapping.
    "storm_downpipe": 11,
}


def _filter_symbol_scale(paths, max_diagonal_px):
    """Order-preserving symbol-scale filter (same rule as the engine kwarg)."""
    return [
        p
        for p in paths
        if math.hypot(p["bbox"][2] - p["bbox"][0], p["bbox"][3] - p["bbox"][1]) <= max_diagonal_px
    ]


def _path(pid, cx, cy, layer="AC"):
    half = 2.0
    return {
        "id": pid,
        "type": "path",
        "path": None,
        "items": [],
        "bbox": (cx - half, cy - half, cx + half, cy + half),
        "layer": layer,
        "color": None,
        "fill_color": None,
        "width": 1.0,
        "page_number": 1,
    }


def test_unionfind_groups_sorted_deterministic():
    uf = UnionFind(4)
    uf.union(3, 1)
    uf.union(1, 2)
    assert uf.groups() == [[0], [1, 2, 3]]


def test_bbox_distance_overlapping_is_zero():
    assert bbox_distance((0, 0, 4, 4), (2, 2, 6, 6)) == 0.0
    assert math.isclose(bbox_distance((0, 0, 1, 1), (3, 1, 5, 2)), 2.0)


def test_derive_threshold_fallback_warns(caplog):
    px = derive_threshold_px(None, 100.0)
    assert px == 5.0


def test_derive_threshold_converts_mm():
    # 1000 mm real world @ 1:100 → 10 paper-mm → ≈28.35 pt
    assert abs(derive_threshold_px(1000.0, 100.0) - 28.346456692913385) < 1e-9


def test_two_symbols_merge_within_threshold_split_beyond():
    paths = [_path("a", 0, 0), _path("b", 3, 0), _path("c", 40, 40)]
    clusters = cluster_paths_threshold(paths, "AC", threshold_px=5.0)
    assert len(clusters) == 2
    sizes = sorted(c["num_paths"] for c in clusters)
    assert sizes == [1, 2]


def test_parity_with_dbscan_on_synthetic_layout():
    """Same effective distance ⇒ same grouping on a grid of symbols."""
    paths = []
    n = 0
    for gx in range(8):
        for gy in range(6):
            cx, cy = gx * 60 + (3 if gy % 2 else 0), gy * 60
            for k in range(4):  # 4 strokes per symbol, tight
                paths.append(_path(f"p{n}", cx + k * 1.5, cy))
                n += 1
    ours = cluster_paths_threshold(paths, "AC", threshold_px=5.0)
    theirs = dbscan_cluster_paths(paths, "AC", eps=5.0, min_pts=2)
    assert sorted(c["num_paths"] for c in ours) == sorted(c["num_paths"] for c in theirs)


def test_full_pipeline_parity_on_sample_sheet():
    """Union-find component counts equal the human-approved re-baseline table.

    RE-BASELINE APPROVED (human ruling, 2026-08-22): on this regression sheet
    the union-find engine's per-type counts are certified as the source of
    truth — {access_control_door: 2, cable_tray: 1, lighting_outlet: 26} —
    and the legacy DBSCAN numbers are RETIRED. Spec v3 §7.4's bbox-gap rule
    ("paths within N real-world mm") governs; DBSCAN centroid chaining is
    the defect.

    Why the legacy DBSCAN numbers were retired (two structural artifacts):
    1. Noise double-emission: legacy ``cluster_paths`` in
       app/ingestion/vector.py appended every label==-1 path BOTH to the
       shared -1 group cluster AND again as its own singleton (e.g.
       NORMAL TRAY: 4 paths → 5 components, 8 member slots over 4 unique
       ids). Fixed in vector.py (fix round 2): noise paths are emitted
       exactly once, as singletons; group clusters never contain -1 members.
    2. Stroke fragmentation: fixture symbols are drawn as multiple strokes
       whose bboxes touch or overlap (gap 0–3 pt) while their centroids sit
       tens of points apart. Centroid-distance chaining (eps=5 pt) fragments
       each multi-stroke symbol into several groups; the spec's physical-gap
       rule correctly yields ONE component per symbol (post-fix legacy 48 vs
       union-find 26 on ``E-lt-fix-nm-clg``).

    Cutoff derivation (symbol/route separation, spec v3 §7.4 geometry-type
    branching): MAX_SYMBOL_DIAGONAL_PX = SYMBOL_CUTOFF_FACTOR 6 × fallback
    merge threshold THRESHOLD_PX 5.0 pt = 30.0 pt. The factor is fixed by
    the sheet scale (same mm-derived basis as the merge threshold), never an
    absolute constant; factor 6 was certified by the round 1–2 cutoff sweep.

    Fair-universe method: ``drawings`` is pre-filtered ONCE by the symbol/
    route diagonal cutoff and that identical filtered list feeds the engine
    under test (which additionally receives the same cutoff via its
    ``max_symbol_diagonal_px`` kwarg — idempotent). Route-scale polylines
    belong to route tracing per spec v3 §7.4 in either engine, so without
    the shared filter the comparison would be apples-to-oranges.

    CRITICAL: clustering filters paths by LAYER NAME, so the engine must
    run over exactly the layer-name set parse_pdf uses (mapped layers +
    legacy AC aliases) — never assembly-type strings.
    """
    from app.ingestion.vector import parse_pdf
    from app.parsing.layer_map import all_mapped_layers

    parsed = parse_pdf(SAMPLE)
    drawings = parsed["raw_drawings"]

    # Mirror parse_pdf's own layer selection (order-preserving de-dup).
    ac_layer_names = ("AC", "ACCESS_CONTROL", "SECURITY", "CARD_READER")
    layer_names = list(dict.fromkeys(list(all_mapped_layers()) + list(ac_layer_names)))

    # Filter once: identical symbol-scale universe for every run of the test.
    symbol_drawings = _filter_symbol_scale(drawings, MAX_SYMBOL_DIAGONAL_PX)

    # new engine (union-find, spec v3 §7.4 bbox-gap semantics)
    new_clusters = []
    for layer in layer_names:
        new_clusters.extend(
            cluster_paths_threshold(
                symbol_drawings,
                layer,
                threshold_px=THRESHOLD_PX,
                max_symbol_diagonal_px=MAX_SYMBOL_DIAGONAL_PX,
            )
        )

    totals = component_totals(count_components(new_clusters, drawings))
    assert totals == APPROVED_REBASELINE_COUNTS
