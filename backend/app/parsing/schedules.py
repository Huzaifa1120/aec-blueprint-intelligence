"""Generic legend & schedule-block detector (spec v3 §7.5, G4 part 1).

Pure text/geometry heuristics over cascade-shaped spans
(``{text,x0,y0,x1,y1}``) — deterministic, no model involved, and no output
here is ever a final quantity: blocks are candidate regions surfaced for the
human-verified pipeline downstream.

Heuristics:
1. A row whose joined cell text carries header keywords classifies a block:
   ``SYMBOL``+``DESCRIPTION`` ⇒ legend; ``DUCT SIZE`` or ``SIZE`` with
   ``THICK``|``GAUGE`` ⇒ attribute_schedule.
2. Spans group into visual rows by y-centerline tolerance
   (≤ max span height × 0.6); rows join a block only while they overlap the
   header's x-extent.
3. ≥2 aligned rows required (header + at least one data row), else no block.
Block bbox = union of member spans; multiple blocks per sheet supported;
garbage input yields [].
"""

from __future__ import annotations

from app.e2e.extraction import ScheduleBlockRow

_ROW_TOLERANCE_FACTOR = 0.6


def _centerline(span: dict) -> float:
    return (span["y0"] + span["y1"]) / 2.0


def _group_rows(spans: list[dict]) -> list[list[dict]]:
    """Cluster spans into visual rows by y-centerline tolerance.

    The tolerance anchor is each row's first member centerline, so grouping
    stays deterministic regardless of span order.
    """
    tol = max(s["y1"] - s["y0"] for s in spans) * _ROW_TOLERANCE_FACTOR
    ordered = sorted(spans, key=lambda s: (_centerline(s), s["x0"]))
    rows: list[list[dict]] = []
    for span in ordered:
        if rows and abs(_centerline(span) - _centerline(rows[-1][0])) <= tol:
            rows[-1].append(span)
        else:
            rows.append([span])
    return [sorted(row, key=lambda s: s["x0"]) for row in rows]


def _row_text(row: list[dict]) -> str:
    return " ".join(span.get("text", "") for span in row).upper()


def _classify_header(text: str) -> str | None:
    if "SYMBOL" in text and "DESCRIPTION" in text:
        return "legend"
    if "DUCT SIZE" in text or ("SIZE" in text and ("THICK" in text or "GAUGE" in text)):
        return "attribute_schedule"
    return None


def _x_extent(row: list[dict]) -> tuple[float, float]:
    return min(s["x0"] for s in row), max(s["x1"] for s in row)


def detect_blocks(spans: list[dict]) -> list[ScheduleBlockRow]:
    """Detect legend / schedule blocks from cascade-shaped text spans."""
    if not spans:
        return []
    rows = _group_rows(spans)
    blocks: list[ScheduleBlockRow] = []
    i = 0
    while i < len(rows):
        header_type = _classify_header(_row_text(rows[i]))
        if header_type is None:
            i += 1
            continue
        hx0, hx1 = _x_extent(rows[i])
        members = [rows[i]]
        j = i + 1
        while j < len(rows):
            nx0, nx1 = _x_extent(rows[j])
            if nx1 < hx0 or nx0 > hx1 or _classify_header(_row_text(rows[j])) is not None:
                break
            members.append(rows[j])
            j += 1
        if len(members) >= 2:  # header + at least one aligned data row
            entries = [{"cells": [s.get("text", "") for s in row]} for row in members[1:]]
            region = {
                "x0": min(s["x0"] for row in members for s in row),
                "y0": min(s["y0"] for row in members for s in row),
                "x1": max(s["x1"] for row in members for s in row),
                "y1": max(s["y1"] for row in members for s in row),
            }
            blocks.append(
                ScheduleBlockRow(
                    block_type=header_type,
                    page_region=region,
                    entries=entries,
                )
            )
        i = j
    return blocks
