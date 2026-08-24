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
    if len(polyline) < 2:
        return 0.0

    # Measure sum of Euclidean distances between consecutive points
    total_points = 0.0
    for i in range(1, len(polyline)):
        x0, y0 = polyline[i - 1]
        x1, y1 = polyline[i]
        segment = np.hypot(x1 - x0, y1 - y0)
        total_points += segment

    # Parse scale "1:100" → denominator = 100
    try:
        denominator = float(scale.split(":")[1])
    except (IndexError, ValueError):
        denominator = 1.0  # fallback: assume 1:1

    # corrected 2026-08-22: pt→paper-mm→real-m conversion
    # (was treating pt as meters; physically impossible outputs,
    # see tray-route-investigation.md)
    real_length = total_points * denominator * 25.4 / (72.0 * 1000.0)

    return round(real_length, 3)


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

    We flatten to a simple ordered polyline for length measurement.

    pymupdf ≥1.28 returns each stroked line as BOTH ('l', p1, p2) and
    ('l', p2, p1) items, so every segment would otherwise traverse twice
    (~2–3× inflated route lengths). A line item that is the exact reversal
    of the immediately preceding line item is skipped.
    """
    points: List[Tuple[float, float]] = []

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

    prev_line: Optional[Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]] = None

    for item in items:
        if not isinstance(item, tuple) or not item:
            continue
        op = item[0]
        if op == "re":
            # Rectangle: emit the four corners
            rect = item[1]
            try:
                x0, y0, x1, y1 = tuple(rect)[:4]
            except (TypeError, ValueError):
                continue
            points.extend([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
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
) -> List[RouteGeo]:
    """Measure cable trunk / conduit lengths from clustered route-layer paths.

    Every cluster on a route layer — including singleton clusters — is a
    route candidate: with union-find clustering (spec v3 §7.4) there is no
    noise concept, and tray/conduit polylines legitimately form single-path
    clusters. Dedup by source_path_ids still applies downstream.

    For each route-layer cluster, extract the paths' polyline,
    compute length using the detected scale, and return RouteGeo objects.

    Constraints enforced:
    - Lengths deterministic from vector coordinates
    - Scale supplied from detected scale (not assumed)
    - Source path IDs preserved for traceability
    - confidence_status default "MEASURED", score 1.0
    """
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

        # Collect all path objects for this cluster
        polyline_parts: List[Tuple[float, float]] = []

        for mid in member_ids:
            path_dict = path_lookup.get(mid, {})
            path_obj = path_dict.get("path")
            items = path_dict.get("items")
            if items:
                part = extract_polyline_from_items(items)
            else:
                part = extract_polyline_from_path(path_obj)
            if not part:
                continue
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
            continue
        # Degenerate cluster (all points identical, e.g. a zero-length vent
        # stub): fewer than 2 DISTINCT points is no measurable route — skip
        # instead of emitting a qty-0 BOQ row.
        if len(set(polyline_parts)) < 2:
            continue

        # No coordinate sorting here: a lexicographic (x, y) sort destroys
        # multi-segment continuity and yields zig-zag, non-path lengths.
        # The chained items-order sequence above IS the drawing order.
        length_m = compute_length_meters(polyline_parts, scale)

        route: RouteGeo = {
            "id": str(uuid.uuid4()),
            "type": layer.lower().replace(" ", "_"),
            "layer": layer,
            "polyline": polyline_parts,
            "length_m": length_m,
            "confidence_status": "MEASURED",
            "confidence_score": 1.0,
            "source_path_ids": member_ids,
        }

        measured_routes.append(route)

    # Deduplicate routes with identical source_path_ids
    measured_routes = deduplicate_routes(measured_routes)
    return measured_routes