"""Deterministic distance-threshold connected-components clustering (spec v3 §7.4).

Replaces DBSCAN-style density clustering with an explicit, human-expressible
merge rule: "paths within N real-world millimeters of each other — the size of
the smallest legend symbol on this sheet." Deterministic: identical input ⇒
byte-identical grouping.

Geometry-type branching (spec v3 §7.4): symbol instances and routes/polylines
are different geometry classes handled by different engines. This module
clusters symbol-scale paths only. Paths whose bbox diagonal exceeds
``max_symbol_diagonal_px`` are route-scale geometry — they belong to route
tracing (``app.parsing.routes``) and are excluded from clustering entirely;
left in, their huge bboxes chain transitively via short-gap hops and swallow
symbol groups into mega-components.

The cutoff derives from the sheet's own scale, never an absolute constant:
cutoff = factor × merge threshold (same mm-derived basis as
``threshold_px``), so both scale together when the fallback threshold is
replaced by a legend-derived one. The factor is fixed by the migration parity
proof (see tests/test_phase2_5_clustering_migration.py).
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

PT_PER_INCH = 72.0
MM_PER_INCH = 25.4


class UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        root = i
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[i] != root:  # path compression
            self.parent[i], i = root, self.parent[i]
        return root

    def union(self, i: int, j: int) -> None:
        ri, rj = self.find(i), self.find(j)
        if ri != rj:
            self.parent[max(ri, rj)] = min(ri, rj)

    def groups(self) -> List[List[int]]:
        buckets: Dict[int, List[int]] = {}
        for i in range(len(self.parent)):
            buckets.setdefault(self.find(i), []).append(i)
        return sorted((sorted(g) for g in buckets.values()), key=lambda g: g[0])


def bbox_distance(
    a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]
) -> float:
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    return math.hypot(dx, dy)


def derive_threshold_px(
    threshold_mm: float | None, scale_denominator: float, fallback_px: float = 5.0
) -> float:
    if threshold_mm is None or scale_denominator <= 0:
        logger.warning("No legend-derived cluster threshold; using fallback %.1f pt", fallback_px)
        return fallback_px
    paper_mm = threshold_mm / scale_denominator
    return paper_mm / MM_PER_INCH * PT_PER_INCH


def cluster_paths_threshold(
    paths: List[dict],
    layer: str,
    threshold_px: float,
    max_symbol_diagonal_px: float | None = None,
) -> List[dict]:
    """Cluster symbol-scale paths of one layer by bbox gap ≤ threshold_px.

    When ``max_symbol_diagonal_px`` is set, paths whose bbox diagonal
    (``math.hypot(x1-x0, y1-y0)``) exceeds it are excluded from clustering
    entirely: per spec v3 §7.4 geometry-type branching they are route/polyline
    geometry and belong to route tracing, not symbol-instance clustering.
    Filtering is order-preserving, so the sorted deterministic grouping of the
    remaining paths is unchanged.

    Args:
        paths: DrawingPath dicts (bbox + layer keys required).
        layer: layer name to cluster (``"default"`` catches layer-less paths).
        threshold_px: merge threshold in points (mm-derived via
            :func:`derive_threshold_px`).
        max_symbol_diagonal_px: optional symbol-scale cutoff in points;
            larger paths are routed to route tracing instead.
    """
    selected = [
        p
        for p in paths
        if (p.get("layer") == layer or (p.get("layer") is None and layer == "default"))
        and (
            max_symbol_diagonal_px is None
            or math.hypot(p["bbox"][2] - p["bbox"][0], p["bbox"][3] - p["bbox"][1])
            <= max_symbol_diagonal_px
        )
    ]
    if not selected:
        return []

    centroids = np.array(
        [
            [(p["bbox"][0] + p["bbox"][2]) / 2.0, (p["bbox"][1] + p["bbox"][3]) / 2.0]
            for p in selected
        ]
    )

    # Grid bucketing: cell size = threshold ⇒ only 3×3 neighbour cells matter.
    cell = max(threshold_px, 1e-9)
    grid: Dict[Tuple[int, int], List[int]] = {}
    for idx, (cx, cy) in enumerate(centroids):
        grid.setdefault((int(cx // cell), int(cy // cell)), []).append(idx)

    uf = UnionFind(len(selected))
    offsets = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
    for (gx, gy), members in grid.items():
        for ox, oy in offsets:
            neighbours = grid.get((gx + ox, gy + oy), [])
            for i in members:
                for j in neighbours:
                    if (
                        j > i
                        and bbox_distance(selected[i]["bbox"], selected[j]["bbox"]) <= threshold_px
                    ):
                        uf.union(i, j)

    results: List[dict] = []
    for group_idx, group in enumerate(uf.groups()):
        bboxes = [selected[i]["bbox"] for i in group]
        envelope = (
            min(b[0] for b in bboxes),
            min(b[1] for b in bboxes),
            max(b[2] for b in bboxes),
            max(b[3] for b in bboxes),
        )
        cxs = centroids[group][:, 0]
        cys = centroids[group][:, 1]
        results.append(
            {
                "cluster_id": group_idx,
                "centroid": np.array([float(np.mean(cxs)), float(np.mean(cys))]),
                "member_path_ids": [selected[i]["id"] for i in group],
                "num_paths": len(group),
                "bbox": envelope,
            }
        )
    return results
