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

# Fixed geometry (PDF points, top-left origin page coords)
RECT_DUCT_PTS = [(200, 300), (483.465, 300), (483.465, 317.008), (200, 317.008), (200, 300)]
ROUND_DUCT_PTS = [(200, 500), (454.863, 500)]
PIPE_PTS = [(200, 650), (339.912, 650)]
EQUIPMENT_RECTS = [(600, 280, 660, 320), (600, 480, 660, 520)]  # 2 units

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
    shape.draw_polyline(RECT_DUCT_PTS)
    shape.finish(color=(0, 0, 1), width=1, oc=ocg["M-DUCT"])
    shape.draw_polyline(ROUND_DUCT_PTS)
    shape.finish(color=(0, 0, 1), width=1, oc=ocg["M-DUCT-RND"])
    shape.draw_polyline(PIPE_PTS)
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
    page.insert_text((300, 490), "DN250", fontsize=8)            # round label
    page.insert_text((240, 640), "DN150", fontsize=8)            # pipe label
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
