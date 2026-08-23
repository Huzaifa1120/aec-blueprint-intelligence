"""Generate a synthetic layer-rich HVAC drawing PDF for e2e ground truth.

Test scaffolding ONLY (spec §7.3) — production code must never import this.
Everything is deterministic: fixed coordinates at scale 1:100, so expected
real lengths derive from the documented pt→paper-mm→real-m chain:
    real_m = points * denominator * 25.4 / (72 * 1000)
"""

from __future__ import annotations

from typing import Dict

import pymupdf

_SCALE_DENOM = 100
_PT_TO_M = _SCALE_DENOM * 25.4 / (72.0 * 1000.0)

# Fixed geometry (PDF points, top-left origin page coords).
# Runs are SEGMENTED like real CAD exports. Segment length 4pt guarantees the
# approved centroid-grid clusterer proposes every consecutive pair (centroid
# delta 4pt crosses at most one 5pt cell boundary), so collinear strokes union
# into full-run routes. Known contract gap logged for human review: bbox-
# touching paths whose centroids sit further apart are never compared by the
# approved clusterer (see ledger / Memory open items). Collinear segmentation
# preserves totals exactly under _real_length.
SEGMENT_PT = 4.0

RECT_TOP_Y, RECT_BOT_Y = 300.0, 317.008          # 17.008pt apart = 600mm duct
RECT_X0, RECT_X1 = 200.0, 483.465                # 283.465pt run = 10 m


def _segment_chain(p0, p1):
    """Split the straight run p0->p1 into collinear segments of ~SEGMENT_PT."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = (dx * dx + dy * dy) ** 0.5
    n = max(2, int(length / SEGMENT_PT) + 1)
    pts = [(p0[0] + dx * i / n, p0[1] + dy * i / n) for i in range(n + 1)]
    return [((pts[i][0], pts[i][1]), (pts[i + 1][0], pts[i + 1][1]))
            for i in range(n)]


def _continuous_loop(p0, p1, p2, p3):
    """Closed loop p0->p1->p2->p3->p0 as consecutive ~SEGMENT_PT strokes.

    Strokes are emitted in continuous drawing order (each starts where the
    previous ended), so measure_routes' nearest-end chaining follows the loop
    exactly and the measured length equals the perimeter.
    """
    corners = [p0, p1, p2, p3, p0]
    strokes = []
    for a, b in zip(corners, corners[1:]):
        strokes.extend(_segment_chain(a, b))
    return strokes


RECT_DUCT_SEGMENTS = _continuous_loop(
    (RECT_X0, RECT_TOP_Y), (RECT_X1, RECT_TOP_Y),
    (RECT_X1, RECT_BOT_Y), (RECT_X0, RECT_BOT_Y),
)
ROUND_DUCT_SEGMENTS = _segment_chain((200.0, 500.0), (454.863, 500.0))
PIPE_SEGMENTS = _segment_chain((200.0, 650.0), (339.912, 650.0))

# Closed-loop polylines for expectation math only (lengths identical to the
# segmented strokes above; rect length is the loop perimeter by definition).
RECT_DUCT_PTS = [(200, 300), (483.465, 300), (483.465, 317.008), (200, 317.008), (200, 300)]
ROUND_DUCT_PTS = [(200, 500), (454.863, 500)]
PIPE_PTS = [(200, 650), (339.912, 650)]

# Symbol-scale equipment: bbox diagonals ~14-15pt (< 30pt cutoff). At 1:100 a
# 12x8pt unit is 1.2m x 0.8m — FCU/terminal-unit scale.
EQUIPMENT_RECTS = [(600, 280, 612, 288), (600, 480, 612, 488)]  # 2 units

# Sheet furniture (borders/title block/grid/symbols) — unlayered decoration that
# pads get_drawings() past the >20 vector-path contract without touching any
# measured run above.
_BORDER_RECTS = [(20, 20, 1171, 822), (35, 35, 1156, 807)]
_TITLE_BLOCK_H = [(35, 750), (1156, 750)]
_TITLE_BLOCK_V_XS = [300, 550, 800, 1000]
_GRID_TICK_TOP_XS = list(range(150, 1051, 100))
_GRID_TICK_LEFT_YS = list(range(150, 751, 100))
_SYMBOL_CIRCLES = [((900, 200), 15), ((950, 260), 15)]


def _real_length(points) -> float:
    total = 0.0
    for i in range(1, len(points)):
        total += ((points[i][0] - points[i - 1][0]) ** 2
                  + (points[i][1] - points[i - 1][1]) ** 2) ** 0.5
    return round(total * _PT_TO_M, 3)


def build_hvac_fixture(path: str) -> Dict:
    doc = pymupdf.open()
    page = doc.new_page(width=1191, height=842)  # A3 landscape

    ocg = {name: doc.add_ocg(name, on=True)
           for name in ("M-DUCT", "M-DUCT-RND", "M-PIPE", "M-EQPT-NEW")}

    shape = page.new_shape()
    for seg in RECT_DUCT_SEGMENTS:
        shape.draw_line(*seg)
        shape.finish(color=(0, 0, 1), width=1, oc=ocg["M-DUCT"])
    for seg in ROUND_DUCT_SEGMENTS:
        shape.draw_line(*seg)
        shape.finish(color=(0, 0, 1), width=1, oc=ocg["M-DUCT-RND"])
    for seg in PIPE_SEGMENTS:
        shape.draw_line(*seg)
        shape.finish(color=(0, 0, 1), width=1, oc=ocg["M-PIPE"])
    for rect in EQUIPMENT_RECTS:
        shape.draw_rect(pymupdf.Rect(rect))
        shape.finish(color=(1, 0, 0), width=1, oc=ocg["M-EQPT-NEW"])
    shape.commit()

    deco = page.new_shape()
    for rect in _BORDER_RECTS:
        deco.draw_rect(pymupdf.Rect(rect))
        deco.finish(color=(0.5, 0.5, 0.5), width=0.75)
    deco.draw_line(*_TITLE_BLOCK_H)
    deco.finish(color=(0.5, 0.5, 0.5), width=0.75)
    for x in _TITLE_BLOCK_V_XS:
        deco.draw_line((x, 750), (x, 807))
        deco.finish(color=(0.5, 0.5, 0.5), width=0.75)
    for x in _GRID_TICK_TOP_XS:
        deco.draw_line((x, 20), (x, 50))
        deco.finish(color=(0.7, 0.7, 0.7), width=0.5)
    for y in _GRID_TICK_LEFT_YS:
        deco.draw_line((20, y), (50, y))
        deco.finish(color=(0.7, 0.7, 0.7), width=0.5)
    for (cx, cy), r in _SYMBOL_CIRCLES:
        deco.draw_circle((cx, cy), r)
        deco.finish(color=(0, 0.5, 0), width=0.75)
        deco.draw_line((cx - 2 * r, cy), (cx + 2 * r, cy))
        deco.finish(color=(0, 0.5, 0), width=0.5)
        deco.draw_line((cx, cy - 2 * r), (cx, cy + 2 * r))
        deco.finish(color=(0, 0.5, 0), width=0.5)
    deco.commit()

    page.insert_text((300, 290), "600x400", fontsize=8)          # rect label
    # Real HVAC sheets repeat size labels along runs; repeating them here
    # lets every segment-cluster of a run resolve its size by proximity
    # instead of falling through to the geometry/ASSUMED cascade steps.
    x = 210.0
    while x < RECT_X1:
        page.insert_text((x, 292), "600x400", fontsize=8)        # above top edge
        page.insert_text((x, 332), "600x400", fontsize=8)        # below bottom edge
        x += 40.0
    xr = 205.0
    while xr < 455.0:
        page.insert_text((xr, 494), "DN250", fontsize=8)         # along round run
        xr += 40.0
    xp = 205.0
    while xp < 340.0:
        page.insert_text((xp, 644), "DN150", fontsize=8)         # along pipe run
        xp += 40.0
    page.insert_text((610, 275), "AHU-01", fontsize=8)           # equipment tags
    page.insert_text((610, 475), "FCU-02", fontsize=8)
    page.insert_text((100, 100), "DUCT SIZE", fontsize=10)       # mini schedule
    page.insert_text((100, 120), "600x400", fontsize=8)
    page.insert_text((100, 140), "SCALE 1:100", fontsize=8)      # scale detect

    doc.save(path)
    doc.close()

    return {
        "scale": "1:100",
        "rect_duct": {"length_m": _real_length(RECT_DUCT_PTS),
                      "width_mm": 600, "height_mm": 400},
        "round_duct": {"length_m": _real_length(ROUND_DUCT_PTS),
                       "diameter_mm": 250},
        "pipe": {"length_m": _real_length(PIPE_PTS), "diameter_mm": 150},
        "equipment_count": len(EQUIPMENT_RECTS),
    }
