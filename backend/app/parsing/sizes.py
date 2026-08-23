"""Size-resolution cascade for duct/pipe routes (Phase 3, spec §4).

Priority: schedule table > text label > measured geometry > ASSUMED default.
Every resolution records {value..., source, ref} so downstream BOQ rows can
state exactly where each size came from. Pure geometry/text logic — no LLM.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

SIZE_SOURCE_ORDER = ("schedule", "label", "geometry", "assumed")

# pt -> real-mm at scale denominator D: pt * D * 25.4/72
_PT_TO_REAL_MM = 25.4 / 72.0

# Both bbox sides must exceed this for the route to count as a double-line duct
# (a bare polyline line is degenerate: one side collapses to ~0 pt)
MIN_SIDE_PT = 2.0

_RECT_RE = re.compile(r"(\d{3,4})\s*[xX×]\s*(\d{3,4})")
_DN_RE = re.compile(r"\bDN\s?(\d{2,4})\b", re.IGNORECASE)
_DIAM_RE = re.compile(r"[ØøD]\s?(\d{2,4})\b")
_INCH_RE = re.compile(r'(\d{1,2})\s?(?:in\b|")', re.IGNORECASE)


def parse_size_label(text: str) -> Optional[Dict]:
    """Parse a size label into normalized mm dimensions. None if no match."""
    if not text:
        return None
    m = _RECT_RE.search(text)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w != h:  # 600x600 is ambiguous rect/round; treat as rect
            return {"width_mm": float(w), "height_mm": float(h), "shape": "rect"}
    m = _DN_RE.search(text)
    if m:
        return {"diameter_mm": float(m.group(1)), "shape": "round"}
    m = _DIAM_RE.search(text)
    if m:
        return {"diameter_mm": float(m.group(1)), "shape": "round"}
    m = _INCH_RE.search(text)
    if m:
        return {"diameter_mm": round(float(m.group(1)) * 25.4, 1), "shape": "round"}
    return None


def _span_center(span: Dict) -> tuple:
    return ((span["x0"] + span["x1"]) / 2.0, (span["y0"] + span["y1"]) / 2.0)


def _route_bbox(polyline: List) -> Optional[tuple]:
    if len(polyline) < 2:
        return None
    xs = [p[0] for p in polyline]
    ys = [p[1] for p in polyline]
    return (min(xs), min(ys), max(xs), max(ys))


def _label_near_route(label: Dict, route: Dict, proximity_pt: float) -> bool:
    """True if label center sits within proximity_pt of the route bbox.

    Entries without x0/y0/x1/y1 (e.g. hand-fed schedule rows) are treated as
    position-independent and match any route.
    """
    if any(k not in label for k in ("x0", "y0", "x1", "y1")):
        return True
    bbox = _route_bbox(route["polyline"])
    if bbox is None:
        return False
    cx, cy = _span_center(label)
    x0, y0, x1, y1 = bbox
    dx = max(x0 - cx, 0.0, cx - x1)
    dy = max(y0 - cy, 0.0, cy - y1)
    return (dx * dx + dy * dy) ** 0.5 <= proximity_pt


def _size_matches_route_shape(size: Dict, layer: str) -> bool:
    """A round size only fits a round-route layer and vice versa."""
    layer_upper = (layer or "").upper()
    round_layer = "RND" in layer_upper or "ROUND" in layer_upper
    round_size = size.get("shape") == "round"
    return round_layer == round_size


def measure_rect_width_mm(
    route: Dict, scale: str, aspect_ratio: float = 2.0
) -> Optional[Dict]:
    """Measure duct width from the route's own double-line geometry.

    Width = longer bbox side converted pt -> real mm via scale; height from
    the declared aspect ratio. Returns None when the bbox is degenerate —
    both sides must exceed MIN_SIDE_PT (2.0 pt); a bare polyline line has a
    collapsed side and is not a double-line duct.
    """
    bbox = _route_bbox(route["polyline"])
    if bbox is None:
        return None
    try:
        denominator = float(scale.split(":")[1])
    except (IndexError, ValueError):
        return None
    w_pt = bbox[2] - bbox[0]
    h_pt = bbox[3] - bbox[1]
    if min(w_pt, h_pt) <= MIN_SIDE_PT:  # bare line / zero-thickness, not a duct
        return None
    width_mm = max(w_pt, h_pt) * denominator * _PT_TO_REAL_MM
    return {
        "width_mm": round(width_mm, 1),
        "height_mm": round(width_mm / aspect_ratio, 1),
        "shape": "rect",
    }


def resolve_route_size(
    route: Dict,
    text_spans: List[Dict],
    scale: str,
    schedule_rows: Optional[List[Dict]] = None,
    default_size: Optional[Dict] = None,
    label_proximity_pt: float = 25.0,
) -> Optional[Dict]:
    """Resolve a route's cross-section size via the cascade (spec §4).

    Returns {"width_mm","height_mm"|"diameter_mm", "source", "ref"} or None.
    """
    # 1. Schedule table wins
    for row in schedule_rows or []:
        if _label_near_route(row, route, label_proximity_pt * 4):
            out = {k: v for k, v in row.items() if k != "ref"}
            out["source"] = "schedule"
            out["ref"] = row.get("ref", "schedule_row")
            return out

    # 2. Text label near the route
    for span in text_spans:
        if not _label_near_route(span, route, label_proximity_pt):
            continue
        size = parse_size_label(span.get("text", ""))
        if size and _size_matches_route_shape(size, route.get("layer", "")):
            out = {k: v for k, v in size.items() if k != "shape"}
            out["source"] = "label"
            out["ref"] = f"text_span:{span.get('text', '')}"
            return out

    # 3. Measured geometry (double-line rectangular ducts)
    measured = measure_rect_width_mm(route, scale)
    if measured:
        out = {k: v for k, v in measured.items() if k != "shape"}
        out["source"] = "geometry"
        out["ref"] = "route_polyline_bbox"
        return out

    # 4. ASSUMED default — flagged, never silent
    if default_size:
        out = dict(default_size)
        out["source"] = "assumed"
        out["ref"] = "configured_default"
        return out

    return None
