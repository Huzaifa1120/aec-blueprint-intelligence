"""Text–layer association walker (spec v3, G5 part 1).

Pure deterministic geometry join: each cascade-shaped text span
(``{text,x0,y0,x1,y1}``) attaches to its nearest component centroid or route
polyline within ``threshold_pt``; unattached spans are dropped (schedule text
is covered by the schedule parser). No LLM/vision output ever becomes a final
quantity here — this only labels which annotation belongs to which target.

``probe_span_ocgs`` is a best-effort probe of PyMuPDF's per-span optional
content group membership; it degrades to ``{}`` on any engine that does not
expose the field.
"""

from __future__ import annotations

import math

from app.e2e.extraction import TextAnnotationRow


def _span_center(span: dict) -> tuple[float, float]:
    return ((span["x0"] + span["x1"]) / 2.0, (span["y0"] + span["y1"]) / 2.0)


def _segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx = bx - ax
    dy = by - ay
    if dx == 0.0 and dy == 0.0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _polyline_distance(px: float, py: float, points: list[tuple[float, float]]) -> float:
    if not points:
        return float("inf")
    if len(points) == 1:
        return math.hypot(px - points[0][0], py - points[0][1])
    best = float("inf")
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        d = _segment_distance(px, py, ax, ay, bx, by)
        if d < best:
            best = d
    return best


def associate_text(
    spans: list[dict],
    components: list[tuple[float, float]],
    routes: list[list[tuple[float, float]]],
    ocg_by_span: dict[int, str] | None = None,
    threshold_pt: float = 18.0,
) -> list[TextAnnotationRow]:
    """Attach each span to its nearest component centroid or route polyline.

    Distance is point-to-centroid for components and min point-to-segment for
    routes. The closest overall target within ``threshold_pt`` wins (earlier
    index wins ties); spans with no target in range are dropped.
    """
    rows: list[TextAnnotationRow] = []
    ocg_map = ocg_by_span or {}
    for i, span in enumerate(spans):
        px, py = _span_center(span)
        best = float("inf")
        comp_idx: int | None = None
        route_idx: int | None = None
        for ci, (cx, cy) in enumerate(components):
            d = math.hypot(px - cx, py - cy)
            if d < best:
                best = d
                comp_idx, route_idx = ci, None
        for ri, pts in enumerate(routes):
            d = _polyline_distance(px, py, pts)
            if d < best:
                best = d
                comp_idx, route_idx = None, ri
        if best > threshold_pt:
            continue
        rows.append(
            TextAnnotationRow(
                text=span.get("text", ""),
                bbox=(span["x0"], span["y0"], span["x1"], span["y1"]),
                ocg_layer=ocg_map.get(i),
                component_index=comp_idx,
                route_index=route_idx,
            )
        )
    return rows


def probe_span_ocgs(page) -> dict[int, str]:
    """Best-effort span-index → OCG name map from ``page.get_text("dict")``.

    Span indices follow sequential flattening of all text lines/spans across
    blocks (image blocks skipped). Returns {} on any failure or when the
    installed PyMuPDF does not expose per-span OCG membership.
    """
    try:
        info = page.get_text("dict")
    except Exception:
        return {}
    xref_names: dict[int, str] = {}
    try:
        for xref, meta in (page.parent.get_ocgs() or {}).items():
            name = meta.get("name")
            if name:
                xref_names[xref] = name
    except Exception:
        xref_names = {}
    out: dict[int, str] = {}
    idx = 0
    for block in info.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                xref = span.get("ocg")
                if xref is not None and xref in xref_names:
                    out[idx] = xref_names[xref]
                idx += 1
    return out
