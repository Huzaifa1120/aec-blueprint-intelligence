"""XLSX BOQ export via openpyxl (spec v3 §7.14).

One deterministic sheet: header row, one row per BOQ line (routes then
materials), then a verbatim totals block. Every line carries material,
quantity, unit, confidence_status, size_source and the unpriced flag;
unpriced lines show the review label in both cost cells — never $0.
"""

from __future__ import annotations

import io

from openpyxl import Workbook

from app.exports import UNPRICED_LABEL

SHEET_NAME = "BOQ"

HEADERS = [
    "Material",
    "Quantity",
    "Unit",
    "Unit Cost",
    "Total Cost",
    "Unpriced",
    "Confidence Status",
    "Size Source",
]

# Column indexes (1-based).
COL_MATERIAL = 1
COL_QUANTITY = 2
COL_UNIT = 3
COL_UNIT_COST = 4
COL_TOTAL_COST = 5
COL_UNPRICED = 6
COL_CONFIDENCE = 7
COL_SIZE_SOURCE = 8


def _line_cells(line: dict) -> list:
    unpriced = bool(line.get("unpriced"))
    if unpriced:
        unit_cost: object = UNPRICED_LABEL
        total_cost: object = UNPRICED_LABEL
    else:
        unit_cost = line.get("unit_cost")
        total_cost = line.get("total_cost")
    return [
        line.get("material_name"),
        line.get("quantity"),
        line.get("unit"),
        unit_cost,
        total_cost,
        unpriced,
        line.get("confidence_status"),
        line.get("size_source"),
    ]


def render(rows: dict) -> bytes:
    """Render the BOQ payload to XLSX bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME
    ws.append(HEADERS)
    for section in ("routes", "materials"):
        for line in rows.get(section) or []:
            ws.append(_line_cells(line))
    totals = rows.get("totals") or {}
    if totals:
        ws.append([])
        for label, key in (
            ("Materials Total", "materials"),
            ("Labor Total", "labor"),
            ("Grand Total", "grand"),
        ):
            if key in totals:
                ws.append([label, None, None, None, totals[key], None, None, None])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
