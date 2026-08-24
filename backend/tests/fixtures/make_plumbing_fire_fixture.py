"""Generate a synthetic layer-rich plumbing + fire-protection drawing PDF.

Test scaffolding ONLY (spec §7.3) — production code must never import this.
Everything is deterministic: fixed coordinates on an A3 landscape sheet at
scale 1:100 (title-block text ``SCALE 1:100`` so ``detect_scale`` finds it).

Document creation, OCG registration, segmented tagged strokes and text
insertion mirror ``tests/fixtures/make_hvac_fixture.py`` — the reviewed
precedent for building OCG-tagged PDFs with pymupdf. Runs are SEGMENTED like
real CAD exports for the same reason as the HVAC fixture: ~4pt collinear
strokes guarantee the approved centroid-grid clusterer proposes every
consecutive pair, so polyline legs union into full-run routes while segment
lengths sum to the exact ground-truth totals below.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Tuple

import pymupdf

_SCALE_DENOM = 100

SEGMENT_PT = 4.0

Point = Tuple[float, float]


def _segment_chain(p0: Point, p1: Point) -> List[Tuple[Point, Point]]:
    """Split the straight run p0->p1 into collinear segments of ~SEGMENT_PT."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = (dx * dx + dy * dy) ** 0.5
    n = max(2, int(length / SEGMENT_PT) + 1)
    pts = [(p0[0] + dx * i / n, p0[1] + dy * i / n) for i in range(n + 1)]
    return [((pts[i][0], pts[i][1]), (pts[i + 1][0], pts[i + 1][1])) for i in range(n)]


def _polyline_segments(points: List[Point]) -> List[Tuple[Point, Point]]:
    strokes: List[Tuple[Point, Point]] = []
    for a, b in zip(points, points[1:]):
        strokes.extend(_segment_chain(a, b))
    return strokes


def polyline_length_pt(points: List[Point]) -> float:
    """Ground-truth drawn length in pt = sum of Euclidean segment lengths."""
    total = 0.0
    for i in range(1, len(points)):
        total += math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1])
    return total


# Fixed geometry (PDF points, top-left origin page coords). Every number here
# is ground truth; EXPECTED below is the contract Task 7 codes against.
SANITARY_MAIN_PTS = [(100.0, 700.0), (400.0, 700.0), (400.0, 550.0)]
# Lower endpoint of the branch lies ON the main's first-segment interior -> 1 tee.
SANITARY_BRANCH_PTS = [(250.0, 700.0), (250.0, 600.0)]
# One true elbow at (500,400); deliberately NO size label -> forces FU sizing tier.
COLD_MAIN_PTS = [(100.0, 400.0), (500.0, 400.0), (560.0, 340.0)]
SPRINKLER_BRANCH_PTS = [(700.0, 700.0), (950.0, 700.0), (950.0, 600.0)]
STANDPIPE_PTS = [(1100.0, 750.0), (1100.0, 300.0)]  # zero bends
# Degenerate single-point path: must produce no route and no phantom BOQ row.
VENT_STUB_PT = (450.0, 550.0)

# CW fixtures inside the stated y=410..430 band, spread x=120..480. Every
# fixture CENTROID stays within the 24pt FU corridor of the cold-water main
# (WC centers 10pt, lavatory centers 21pt below it) so all 30 are counted.
# Same-layer symbol bboxes stay >5pt apart (the fallback cluster threshold):
# a single WC row keeps 20 symbols ~15pt apart, and the lavatory row sits
# 6.5pt below them — nothing merges into the route cluster and no two
# fixtures collapse into one component.
_WC_ROW_PITCH = 360.0 / 19.0
WC_RECTS = [(120.0 + k * _WC_ROW_PITCH, 408.0, 124.0 + k * _WC_ROW_PITCH, 412.0) for k in range(20)]
LAVATORY_CIRCLES = [((150.0 + 33.0 * m, 421.0), 2.5) for m in range(10)]
# One WC far outside the corridor — must be excluded from FU accumulation.
EXTRA_WC_RECT = (800.0, 650.0, 804.0, 654.0)

# Sprinkler heads along y=690 above their own branch; >=24pt away from every
# OTHER discipline's polylines (nearest foreign line: standpipe x=1100 -> 185pt).
SPRINKLER_HEADS = [((715.0 + 40.0 * k, 690.0), 3.0) for k in range(6)]

# FA devices clustered legend-style at (80..140, 120..220); shapes are kept
# >=8pt apart bbox-to-bbox so each resolves to its own component cluster.
FA_DETECTOR_RECTS = [
    (85.0, 125.0, 91.0, 131.0),
    (85.0, 140.0, 91.0, 146.0),
    (85.0, 155.0, 91.0, 161.0),
    (85.0, 170.0, 91.0, 176.0),
]
FA_CALLPOINT_RECTS = [(105.0, 125.0, 111.0, 133.0), (105.0, 140.0, 111.0, 148.0)]
FA_SOUNDER_CIRCLES = [((127.0, 129.0), 4.0), ((127.0, 145.0), 4.0)]
FA_FACP_RECT = (95.0, 190.0, 113.0, 202.0)

# Sheet furniture (border/title block) — unlayered decoration mirroring the
# HVAC fixture's convention; never touches any measured run above.
_BORDER_RECTS = [(20, 20, 1171, 822), (35, 35, 1156, 807)]
_TITLE_BLOCK_H = [(35, 750), (1156, 750)]
_TITLE_BLOCK_V_XS = [300, 550, 800, 1000]

EXPECTED = {
    "scale": "1:100",
    "sanitary_main": {"length_pt": 450.0, "size_label": "DN150", "elbows": 1},
    "cold_main": {"length_pt": 484.85, "fu_expected": 70.0, "excluded_fixtures": 1},
    "sprinkler_branch": {"length_pt": 350.0, "size_label": "Ø50", "elbows": 1},
    "standpipe": {"length_pt": 450.0, "size_label": "DN100"},
    "heads": 6,
    "fixtures_in_corridor": {"wc": 20, "lavatory": 10},
    "fa_devices": {"smoke_detector": 4, "call_point": 2, "sounder": 2, "facp": 1},
}


def build_plumbing_fire_fixture(path: str) -> Dict:
    doc = pymupdf.open()
    page = doc.new_page(width=1191, height=842)  # A3 landscape

    ocg = {
        name: doc.add_ocg(name, on=True)
        for name in (
            "P-SAN-MAIN",
            "P-SAN-BRANCH",
            "P-DOM-CW",
            "P-VENT",
            "FP-SPRK-BRANCH",
            "FP-SPRK-HEADS",
            "FP-STANDPIPE",
            "FA-DETECTOR",
            "FA-CALLPOINT",
            "FA-SOUNDER",
            "FA-FACP",
        )
    }

    def draw_polyline(shape, points, layer):
        for seg in _polyline_segments(points):
            shape.draw_line(*seg)
            shape.finish(color=(0, 0, 1), width=1, oc=ocg[layer])

    shape = page.new_shape()
    draw_polyline(shape, SANITARY_MAIN_PTS, "P-SAN-MAIN")
    draw_polyline(shape, SANITARY_BRANCH_PTS, "P-SAN-BRANCH")
    draw_polyline(shape, COLD_MAIN_PTS, "P-DOM-CW")
    draw_polyline(shape, SPRINKLER_BRANCH_PTS, "FP-SPRK-BRANCH")
    draw_polyline(shape, STANDPIPE_PTS, "FP-STANDPIPE")
    # Degenerate vent stub: a single 1-point path (zero-length stroke).
    shape.draw_line(VENT_STUB_PT, VENT_STUB_PT)
    shape.finish(color=(0, 0, 1), width=1, oc=ocg["P-VENT"])
    for rect in WC_RECTS + [EXTRA_WC_RECT]:
        shape.draw_rect(pymupdf.Rect(rect))
        shape.finish(color=(1, 0, 0), width=1, oc=ocg["P-DOM-CW"])
    for center, r in LAVATORY_CIRCLES:
        shape.draw_circle(center, r)
        shape.finish(color=(1, 0, 0), width=1, oc=ocg["P-DOM-CW"])
    for center, r in SPRINKLER_HEADS:
        shape.draw_circle(center, r)
        shape.finish(color=(1, 0, 0), width=1, oc=ocg["FP-SPRK-HEADS"])
    for rect in FA_DETECTOR_RECTS:
        shape.draw_rect(pymupdf.Rect(rect))
        shape.finish(color=(0, 0.5, 0), width=1, oc=ocg["FA-DETECTOR"])
    for rect in FA_CALLPOINT_RECTS:
        shape.draw_rect(pymupdf.Rect(rect))
        shape.finish(color=(0, 0.5, 0), width=1, oc=ocg["FA-CALLPOINT"])
    for center, r in FA_SOUNDER_CIRCLES:
        shape.draw_circle(center, r)
        shape.finish(color=(0, 0.5, 0), width=1, oc=ocg["FA-SOUNDER"])
    shape.draw_rect(pymupdf.Rect(FA_FACP_RECT))
    shape.finish(color=(0, 0.5, 0), width=1, oc=ocg["FA-FACP"])
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
    deco.commit()

    page.insert_text((180, 694), "DN150", fontsize=8)  # sanitary main label
    # Cold-water main intentionally has NO size label (forces FU tier).
    page.insert_text((760, 694), "Ø50", fontsize=8)  # sprinkler label
    page.insert_text((1090, 520), "DN100", fontsize=8)  # standpipe label
    page.insert_text((100, 100), "SCALE 1:100", fontsize=8)  # scale detect

    doc.set_metadata(
        {
            "title": "Plumbing & Fire Protection Fixture (synthetic)",
            "producer": "aec-blueprint-intelligence test fixture",
            "creator": "make_plumbing_fire_fixture.py",
        }
    )
    # no_new_id=True: pymupdf otherwise stamps a random /ID per save;
    # suppressing it keeps the bytes identical across regeneration runs.
    doc.save(path, no_new_id=True)
    doc.close()

    return dict(EXPECTED)


def main() -> None:
    out_path = Path(__file__).resolve().parent / "out" / "plumbing_fire_fixture.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    expected = build_plumbing_fire_fixture(str(out_path))
    print(f"wrote {out_path}")
    print(expected)


if __name__ == "__main__":
    main()  # writes tests/fixtures/out/plumbing_fire_fixture.pdf
