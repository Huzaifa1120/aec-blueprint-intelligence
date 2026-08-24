"""Fixture-unit accumulation and code-table pipe sizing (Phase 4 spec §5).

Classic plumbing-code sizing scoped honestly to plan-view geometry: fixtures
near a water-supply route contribute their YAML-declared fixture units; the
total resolves a diameter through an owner-editable gauge table. Pure
deterministic logic — no LLM/vision output ever becomes a quantity.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.assembly.rules import load_assembly_rule


def fixture_units_for_type(component_type: str) -> float:
    """YAML-declared fixture units for a counted component type (0 if none)."""
    rule = load_assembly_rule(component_type)
    if not rule:
        return 0.0
    try:
        return float(rule.get("fixture_units") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _point_to_polyline_distance(
    px: float, py: float, points: List[Tuple[float, float]]
) -> float:
    if len(points) < 2:
        return math.inf
    best = math.inf
    for i in range(1, len(points)):
        ax, ay = points[i - 1]
        bx, by = points[i]
        dx, dy = bx - ax, by - ay
        seg_sq = dx * dx + dy * dy
        if seg_sq == 0.0:
            continue
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_sq))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


def accumulate_fixture_units(
    route_polyline: List[Tuple[float, float]],
    components: List[Dict],
    corridor_pt: float = 24.0,
) -> Tuple[float, List[Dict]]:
    """Sum fixture units of components within corridor_pt of the polyline."""
    total = 0.0
    breakdown: List[Dict] = []
    for comp in components:
        d = _point_to_polyline_distance(float(comp["x"]), float(comp["y"]), route_polyline)
        if d > corridor_pt:
            continue
        fu = fixture_units_for_type(str(comp.get("component_type") or ""))
        if fu <= 0.0:
            continue
        total += fu
        breakdown.append({
            "key": comp.get("key"),
            "component_type": comp.get("component_type"),
            "fu": fu,
        })
    return total, breakdown


def resolve_size_from_fixture_units(
    fu_total: float, rows: Dict[str, str]
) -> Optional[Dict]:
    """First threshold >= fu_total wins (mirrors lookup_gauge semantics)."""
    for key in sorted(rows, key=float):
        if float(key) >= fu_total:
            return {"diameter_mm": float(rows[key]), "shape": "round"}
    return None
