"""Geometry-derived pipe fittings from route polylines (Phase 4 spec §4).

Tiny drawn fitting symbols are unreliable to cluster; instead, elbows and
tees derive deterministically from the ordered polylines measure_routes
already produces. Pure geometry — no LLM/vision output ever becomes a count.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

Point = Tuple[float, float]


def _unit(v: Tuple[float, float]) -> Optional[Tuple[float, float]]:
    norm = math.hypot(*v)
    if norm == 0.0:
        return None
    return (v[0] / norm, v[1] / norm)


def _angle_between(v1: Point, v2: Point) -> float:
    u1, u2 = _unit(v1), _unit(v2)
    if u1 is None or u2 is None:
        return 0.0
    dot = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
    return math.degrees(math.acos(dot))


def derive_fittings(
    route: Dict,
    other_routes: Optional[List[Dict]] = None,
    *,
    bend_angle_deg: float = 30.0,
    min_segment_pt: float = 2.0,
    junction_tol_pt: float = 6.0,
) -> Dict:
    """Count elbows/tees for one route from its own and foreign vertices."""
    polyline: List[Point] = [(float(x), float(y)) for x, y in route.get("polyline") or []]
    elbows = 0
    provenance: List[Dict[str, str]] = []

    for i in range(1, len(polyline) - 1):
        prev, cur, nxt = polyline[i - 1], polyline[i], polyline[i + 1]
        seg_in = (cur[0] - prev[0], cur[1] - prev[1])
        seg_out = (nxt[0] - cur[0], nxt[1] - cur[1])
        if math.hypot(*seg_in) < min_segment_pt or math.hypot(*seg_out) < min_segment_pt:
            continue
        if _angle_between(seg_in, seg_out) >= bend_angle_deg:
            elbows += 1
            provenance.append({
                "kind": "geometry_fittings:elbow",
                "ref": f"{cur[0]:.1f},{cur[1]:.1f}",
            })

    tees = 0
    for other in other_routes or []:
        if other is route:
            continue
        for qx, qy in (other.get("polyline") or []):
            if _distance_to_polyline_interior((qx, qy), polyline, junction_tol_pt):
                tees += 1
                provenance.append({
                    "kind": "geometry_fittings:tee",
                    "ref": f"{qx:.1f},{qy:.1f}",
                })
                break  # one foreign route contributes at most one tee here

    return {"elbows_90": elbows, "tees": tees, "provenance": provenance}


def _distance_to_polyline_interior(
    point: Point, polyline: List[Point], tol: float
) -> bool:
    """True if point lies within tol of the polyline body strictly between
    its two open endpoints. A branch meeting an open end is a collinear
    continuation (or elbow), never a tee; only interior junctions count."""
    if len(polyline) < 2:
        return False
    px, py = point
    best = math.inf
    for j in range(len(polyline) - 1):
        ax, ay = polyline[j]
        bx, by = polyline[j + 1]
        dx, dy = bx - ax, by - ay
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq == 0.0:
            continue
        t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
        t = max(0.0, min(1.0, t))
        dist = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        if dist < best:
            best = dist
    if best > tol:
        return False
    # Reject touches at either open end of the target route.
    first, last = polyline[0], polyline[-1]
    if math.hypot(px - first[0], py - first[1]) <= tol:
        return False
    if math.hypot(px - last[0], py - last[1]) <= tol:
        return False
    return True
