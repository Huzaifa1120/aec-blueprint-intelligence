"""Text–layer association walker (spec v3, G5 part 1).

Pure deterministic geometry join: each cascade-shaped text span
(``{text,x0,y0,x1,y1}``) attaches to its nearest component centroid or route
polyline within ``threshold_pt``; unattached spans are dropped (schedule text
is covered by the schedule parser). No LLM/vision output ever becomes a final
quantity here — this only labels which annotation belongs to which target.

``probe_span_ocgs`` is a best-effort probe of PyMuPDF's per-span optional
content group membership; it degrades to ``{}`` on any engine that does not
expose the field. When no span-level data is available it falls back to a
content-stream walk (spec v3 §4.6(2)): ``extract_span_ocgs_from_contents``
replays ``/OC /Name BDC … EMC`` marked-content nesting in lockstep with the
flattened span order, returning ``{}`` on any structural doubt.
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
    installed PyMuPDF does not expose per-span OCG membership; if the direct
    span data yields nothing, the content-stream fallback tier runs (spec v3
    §4.6(2)). A partial direct map is never merged with fallback output.
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
    if out:
        return out
    return extract_span_ocgs_from_contents(page)


_TEXT_SHOW_OPS = frozenset({"Tj", "TJ", "'", '"'})


def _tokenize_contents(raw: bytes) -> list[str]:
    """Whitespace tokenizer that keeps PDF string literals and hex strings
    intact so their contents can never be mistaken for operators."""
    try:
        text = raw.decode("latin-1")
    except Exception:
        return []
    tokens: list[str] = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "(":
            depth, parts, j = 1, [], i + 1
            while j < n and depth:
                c = text[j]
                if c == "\\" and j + 1 < n:
                    parts.append(text[j : j + 2])
                    j += 2
                    continue
                parts.append(c)
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                j += 1
            tokens.append("(" + "".join(parts))
            i = j
            continue
        if ch == "<":
            end = text.find(">", i + 1)
            j = n if end == -1 else end + 1
            tokens.append(text[i:j])
            i = j
            continue
        j = i
        while j < n and not text[j].isspace():
            j += 1
        tokens.append(text[i:j])
        i = j
    return tokens


def _scan_marked_content_ops(tokens: list[str]) -> list[str | None] | None:
    """One innermost OC name (or None) per text-showing op, in stream order.

    Returns None when the marked-content structure is unbalanced — a stray
    ``EMC`` with an empty stack or an unclosed ``BDC`` at end of stream means
    guessing would be dishonest.
    """
    stack: list[str] = []
    prev2: str | None = None
    prev1: str | None = None
    ops: list[str | None] = []
    in_image_data = False
    for tok in tokens:
        if in_image_data:
            if tok == "EI":
                in_image_data = False
            continue
        if tok == "BDC":
            if prev2 == "/OC" and prev1 is not None and prev1.startswith("/"):
                stack.append(prev1[1:])
        elif tok == "EMC":
            if not stack:
                return None
            stack.pop()
        elif tok in _TEXT_SHOW_OPS:
            ops.append(stack[-1] if stack else None)
        elif tok == "ID":
            in_image_data = True
        prev2, prev1 = prev1, tok
    if stack:
        return None
    return ops


def extract_span_ocgs_from_contents(page) -> dict[int, str]:
    """Content-stream BDC/EMC fallback (spec v3 §4.6(2)).

    Tokenizes ``page.read_contents()`` and replays the marked-content stack
    (``/OC /Name BDC`` pushes, ``EMC`` pops) in lockstep with the flattened
    span order of ``page.get_text("dict")``: every span must correspond to
    exactly one text-showing operation. Any count mismatch or unbalanced
    marked content returns {} (honest degradation), never a partial guess.
    """
    try:
        raw = page.read_contents()
    except Exception:
        return {}
    if isinstance(raw, list):
        raw = b"".join(raw)
    if not raw:
        return {}
    try:
        info = page.get_text("dict")
    except Exception:
        return {}
    span_count = sum(
        len(line.get("spans", []))
        for block in info.get("blocks", [])
        for line in block.get("lines", [])
    )
    ops = _scan_marked_content_ops(_tokenize_contents(raw))
    if ops is None or len(ops) != span_count:
        return {}
    return {i: name for i, name in enumerate(ops) if name}
