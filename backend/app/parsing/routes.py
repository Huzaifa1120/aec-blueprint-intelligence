"""Route measurement — cable trunk / conduit lengths from vector coordinates, scaled.

Extracts ordered polylines from vector paths on the route layer,
measures lengths using the detected scale, and tracks waste factor.

Constraints:
- Lengths are deterministic calculations from real vector coordinates
- No LLM/vision model outputs final length directly
- Waste factor rule-driven (configurable per assembly rule set)
- All geometry traceable to source path IDs from get_drawings()
"""

from __future__ import annotations

import math
import uuid
from typing import List, Dict, Optional, Tuple, TypedDict


import numpy as np



# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class RouteGeo(TypedDict):
    id: str
    type: str  # "conduit", "cable_tray", "pipe"
    layer: str
    polyline: List[Tuple[float, float]]  # ordered vertices (scaled)
    length_m: float  # scaled length in real meters
    confidence_status: str  # "MEASURED"
    confidence_score: float  # 1.0 = measured directly from vector
    source_path_ids: List[str]
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1) around the polyline
    page: int  # 0-indexed source page of the first member path


# ---------------------------------------------------------------------------
# Route measurement functions
# ---------------------------------------------------------------------------


def compute_length_meters(
    polyline: List[Tuple[float, float]],
    scale: str,
) -> float:
    """Compute total length of an ordered polyline in real-world meters.

    Polyline coordinates are PDF user-space points (1/72 inch). The chain:
      paper-mm = points × 25.4/72
      real-mm  = paper-mm × scale_denominator   (e.g. 1:100 → ×100)
      real-m   = real-mm / 1000
    Net factor = denominator × 25.4 / (72 × 1000).

    Args:
        polyline: ordered list of (x, y) pairs in PDF user units (points)
        scale: scale string e.g. "1:100"

    Returns:
        Total length in real meters at the given drawing scale.
    """
    return round(_points_to_meters(_points_total_length(polyline), scale), 3)


def _points_total_length(polyline: List[Tuple[float, float]]) -> float:
    """Sum of Euclidean distances between consecutive points."""
    if len(polyline) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(polyline)):
        x0, y0 = polyline[i - 1]
        x1, y1 = polyline[i]
        total += np.hypot(x1 - x0, y1 - y0)
    return float(total)


def _points_to_meters(total_points: float, scale: str) -> float:
    """Convert a pt-length total to real meters at the given scale."""
    # Parse scale "1:100" → denominator = 100
    try:
        denominator = float(scale.split(":")[1])
    except (IndexError, ValueError):
        # Spec v3 §7.4: never assume 1:1. Unparseable == missing → 1:100,
        # and the pipeline stamps such runs scale_status="assumed".
        denominator = 100.0

    # corrected 2026-08-22: pt→paper-mm→real-m conversion
    # (was treating pt as meters; physically impossible outputs,
    # see tray-route-investigation.md)
    return total_points * denominator * 25.4 / (72.0 * 1000.0)


def extract_polyline_from_path(
    path_obj: object,
) -> List[Tuple[float, float]]:
    """Extract ordered vertex points from a PyMuPDF svg.path.Path object.

    svg.path objects support iteration (Move, Line, Cubic, etc.).
    We flatten to a simple polyline of centroids.
    """
    if path_obj is None:
        return []

    try:
        # svg.path.Path is iterable; each element is a Path.Command
        # We collect all points into a polyline
        points: List[Tuple[float, float]] = []
        for cmd in path_obj:
            if hasattr(cmd, "point"):
                # cmd.point is a complex number or tuple (x, y)
                p = cmd.point
                if isinstance(p, complex):
                    points.append((p.real, p.imag))
                elif isinstance(p, (list, tuple)) and len(p) == 2:
                    points.append((float(p[0]), float(p[1])))
            elif hasattr(cmd, "x"):
                points.append((float(cmd.x), float(cmd.y)))
        return points
    except Exception:
        # If we can't parse the path, return empty — caller handles
        return []


def extract_polyline_from_items(
    items: List[tuple],
) -> List[Tuple[float, float]]:
    """Extract ordered vertex points from PyMuPDF ``get_drawings()`` items.

    Item format (PyMuPDF ≥1.24): a tuple whose first element is the
    operation type, followed by the operand points:
      - ('l', p1, p2)          line segment
      - ('c', p1, p2, p3)      cubic Bézier (we sample the endpoints)
      - ('qu', p1, p2, p3)     quadratic Bézier (we sample the endpoints)
      - ('re', rect)           rectangle
      - ('qu', Quad)           filled quadrilateral (PyMuPDF ≥1.24.3 shape
                               items carry a ``Quad`` with ul/ur/lr/ll)

    Route tracing measures RUN-LENGTH CENTERLINES, never perimeters (a
    ribbon walked around both edges bills 2L+2W for an L-long run):
      - ('qu', Quad) / ('re', rect): emit the midpoint pair of the two
        SHORTER opposite sides — exact run length for rectangular ribbons
        (the CAD convention for tray/duct segments).
      - A CLOSED line loop (first point == last point) collapses to its
        bbox long-axis centerline: fittings/elbow pieces contribute their
        dominant crossing, not their outline.

    pymupdf ≥1.28 returns each stroked line as BOTH ('l', p1, p2) and
    ('l', p2, p1) items, so every segment would otherwise traverse twice
    (~2–3× inflated route lengths). A line item that is the exact reversal
    of the immediately preceding line item is skipped.
    """
    points: List[Tuple[float, float]] = []
    only_lines = True
    saw_item = False

    def _point(v) -> Optional[Tuple[float, float]]:
        if isinstance(v, complex):
            return (v.real, v.imag)
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return (float(v[0]), float(v[1]))
        # pymupdf.Point / Rect are iterable too
        try:
            xy = tuple(v)
            if len(xy) >= 2:
                return (float(xy[0]), float(xy[1]))
        except (TypeError, ValueError):
            return None
        return None

    def _quad_corners(v) -> Optional[List[Tuple[float, float]]]:
        """Cyclic corners (ul→ur→lr→ll) of a pymupdf.Quad-shaped operand."""
        attrs = []
        for name in ("ul", "ur", "lr", "ll"):
            corner = getattr(v, name, None)
            pt = _point(corner) if corner is not None else None
            if pt is None:
                return None
            attrs.append(pt)
        return attrs

    def _ribbon_centerline(corners: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Midpoint pair of the two SHORTER opposite sides (cyclic order)."""
        mids = [
            (
                (corners[i][0] + corners[(i + 1) % 4][0]) / 2.0,
                (corners[i][1] + corners[(i + 1) % 4][1]) / 2.0,
            )
            for i in range(4)
        ]
        side_len = [
            math.hypot(corners[(i + 1) % 4][0] - corners[i][0],
                       corners[(i + 1) % 4][1] - corners[i][1])
            for i in range(4)
        ]
        # Opposite side pairs under cyclic order: (0,2) and (1,3).
        pair_a = side_len[0] + side_len[2]
        pair_b = side_len[1] + side_len[3]
        if pair_a <= pair_b:
            return [mids[0], mids[2]]
        return [mids[1], mids[3]]

    prev_line: Optional[Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]] = None

    for item in items:
        if not isinstance(item, tuple) or not item:
            continue
        op = item[0]
        saw_item = True
        if op != "l":
            only_lines = False
        if op == "re":
            # Rectangle: bill its run, not its outline.
            rect = item[1]
            try:
                x0, y0, x1, y1 = tuple(rect)[:4]
            except (TypeError, ValueError):
                continue
            if abs(x1 - x0) >= abs(y1 - y0):
                yc = (y0 + y1) / 2.0
                points.extend([(float(x0), yc), (float(x1), yc)])
            else:
                xc = (x0 + x1) / 2.0
                points.extend([(xc, float(y0)), (xc, float(y1))])
            prev_line = None
        elif op == "qu" and len(item) == 2 and not isinstance(item[1], (int, float)):
            corners = _quad_corners(item[1])
            if corners is None:
                # Quadratic Bézier ('qu', p1, p2, p3): sample endpoints below.
                for operand in item[1:]:
                    pt = _point(operand)
                    if pt is not None:
                        points.append(pt)
            else:
                points.extend(_ribbon_centerline(corners))
            prev_line = None
        elif op == "l" and len(item) >= 3:
            p1, p2 = _point(item[1]), _point(item[2])
            if p1 is not None and p2 is not None:
                if prev_line is not None and prev_line == (p2, p1):
                    prev_line = None
                    continue
                prev_line = (p1, p2)
                points.append(p1)
                points.append(p2)
            else:
                for operand in item[1:]:
                    pt = _point(operand)
                    if pt is not None:
                        points.append(pt)
                prev_line = None
        else:
            prev_line = None
            for operand in item[1:]:
                pt = _point(operand)
                if pt is not None:
                    points.append(pt)

    # Closed line-only loop (fittings, elbow pieces): collapse to the bbox
    # long-axis centerline instead of billing the outline twice.
    if (
        saw_item
        and only_lines
        and len(points) >= 4
        and len(set(points)) >= 3
    ):
        perimeter = sum(
            math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
            for i in range(1, len(points))
        )
        closure_gap = math.hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1])
        if perimeter > 0 and closure_gap <= max(1e-6, 0.05 * perimeter):
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            if max(xs) - min(xs) >= max(ys) - min(ys):
                yc = (min(ys) + max(ys)) / 2.0
                points = [(min(xs), yc), (max(xs), yc)]
            else:
                xc = (min(xs) + max(xs)) / 2.0
                points = [(xc, min(ys)), (xc, max(ys))]

    return points


def deduplicate_routes(routes: List[RouteGeo]) -> List[RouteGeo]:
    """Deduplicate routes by source_path_ids.

    Keeps only one representative per unique source_path_ids subset,
    preserving order of first appearance.
    """
    seen: set = set()
    unique: List[RouteGeo] = []
    for route in routes:
        key = tuple(sorted(route.get("source_path_ids", [])))
        if key not in seen:
            seen.add(key)
            unique.append(route)
    return unique


def measure_routes(
    clusters: List[Dict],
    raw_drawings: List[Dict],
    scale: str,
    route_layer_names: Tuple[str, ...] = ("CONDUIT", "CABLE_TRAY", "PIPE"),
    stats: Optional[Dict[str, int]] = None,
) -> List[RouteGeo]:
    """Measure cable trunk / conduit lengths from clustered route-layer paths.

    Every cluster on a route layer — including singleton clusters — is a
    route candidate: with union-find clustering (spec v3 §7.4) there is no
    noise concept, and tray/conduit polylines legitimately form single-path
    clusters. Dedup by source_path_ids still applies downstream.

    Route candidates that cannot produce a measurable polyline (no
    extractable points, or fewer than 2 distinct points — e.g. a zero-length
    vent stub) are skipped and tallied in ``stats["degenerate_skipped"]``
    when a stats dict is supplied, so they never vanish silently.

    For each route-layer cluster, extract the paths' polyline,
    compute length using the detected scale, and return RouteGeo objects.

    Constraints enforced:
    - Lengths deterministic from vector coordinates
    - Scale supplied from detected scale (not assumed)
    - Source path IDs preserved for traceability
    - confidence_status default "MEASURED", score 1.0
    """
    if stats is None:
        stats = {}
    measured_routes: List[RouteGeo] = []

    # Build a lookup: path_id → drawing path dict
    path_lookup: Dict[str, Dict] = {
        p["id"]: p for p in raw_drawings
    }

    for cluster in clusters:
        member_ids = cluster.get("member_path_ids", [])

        # Determine the layer from the first member path
        member_path = path_lookup.get(member_ids[0], {})
        layer = member_path.get("layer", "")

        # Check if this cluster belongs to a route layer
        if layer not in route_layer_names:
            continue

        # Collect all path objects for this cluster. Each path contributes
        # its OWN geometry length; the cluster is a connected run network,
        # and member order is drawing order — chaining parts together and
        # walking the result would bill member-order hops between path ends
        # as tray length (a 114 pt zigzag on the MMC sheet). The chained
        # polyline below is still built for fitting derivation and
        # click-through provenance, but the LENGTH never crosses paths.
        total_points_length = 0.0
        polyline_parts: List[Tuple[float, float]] = []

        for mid in member_ids:
            path_dict = path_lookup.get(mid, {})
            items = path_dict.get("items")
            if items:
                part = extract_polyline_from_items(items)
            else:
                part = extract_polyline_from_path(path_dict.get("path"))
            if not part:
                continue
            total_points_length += _points_total_length(part)
            # Nearest-end continuation: keep each path's internal item order,
            # reversing the whole incoming path only when its far end sits
            # nearer to the chain's running endpoint than its near end.
            if polyline_parts:
                last_x, last_y = polyline_parts[-1]
                start_x, start_y = part[0]
                end_x, end_y = part[-1]
                d_start = np.hypot(start_x - last_x, start_y - last_y)
                d_end = np.hypot(end_x - last_x, end_y - last_y)
                if d_end < d_start:
                    part = list(reversed(part))
            for px, py in part:
                # Collapse consecutive duplicates (shared endpoints between
                # chained segments): a zero-length segment would otherwise
                # mask true corners from geometry-derived fitting counts.
                if not polyline_parts or (px, py) != polyline_parts[-1]:
                    polyline_parts.append((px, py))

        if len(polyline_parts) < 2:
            stats["degenerate_skipped"] = stats.get("degenerate_skipped", 0) + 1
            continue
        # Degenerate cluster (all points identical, e.g. a zero-length vent
        # stub): fewer than 2 DISTINCT points is no measurable route — skip
        # instead of emitting a qty-0 BOQ row.
        if len(set(polyline_parts)) < 2 or total_points_length <= 0.0:
            stats["degenerate_skipped"] = stats.get("degenerate_skipped", 0) + 1
            continue

        # No coordinate sorting here: a lexicographic (x, y) sort destroys
        # multi-segment continuity and yields zig-zag, non-path lengths.
        # The chained items-order sequence above IS the drawing order.
        length_m = round(_points_to_meters(total_points_length, scale), 3)

        xs = [pt[0] for pt in polyline_parts]
        ys = [pt[1] for pt in polyline_parts]

        route: RouteGeo = {
            "id": str(uuid.uuid4()),
            "type": layer.lower().replace(" ", "_"),
            "layer": layer,
            "polyline": polyline_parts,
            "length_m": length_m,
            "confidence_status": "MEASURED",
            "confidence_score": 1.0,
            "source_path_ids": member_ids,
            # Click-through provenance (spec v3 §7.12): region around the
            # measured run + the page it was drawn on (0-indexed).
            "bbox": (min(xs), min(ys), max(xs), max(ys)),
            "page": int(member_path.get("page_number") or 1) - 1,
        }

        measured_routes.append(route)

    # Deduplicate routes with identical source_path_ids
    measured_routes = deduplicate_routes(measured_routes)
    return measured_routes