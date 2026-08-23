"""PDF BOQ export via reportlab (spec v3 §7.14).

Single landscape-A4 document: title, one table row per BOQ line with the
same provenance columns as the XLSX writer (material, quantity, unit,
confidence_status, size_source, unpriced flag), then a verbatim totals
block. Unpriced lines carry the review-required label instead of a price.
"""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.exports import UNPRICED_LABEL

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

# Sum ≈ 710pt against ~752pt usable width on landscape A4 with 15mm margins.
_COL_WIDTHS = [210, 50, 35, 80, 105, 55, 95, 80]
_GREY = colors.Color(0.85, 0.85, 0.85)


def _format_number(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return str(value)


def _line_cells(line: dict) -> list[str]:
    unpriced = bool(line.get("unpriced"))
    if unpriced:
        unit_cost: object = UNPRICED_LABEL
        total_cost: object = UNPRICED_LABEL
    else:
        unit_cost = _format_number(line.get("unit_cost"))
        total_cost = _format_number(line.get("total_cost"))
    size_source = line.get("size_source")
    unit = line.get("unit")
    return [
        str(line.get("material_name")),
        _format_number(line.get("quantity")),
        "" if unit is None else str(unit),
        str(unit_cost),
        str(total_cost),
        "YES" if unpriced else "NO",
        str(line.get("confidence_status") or ""),
        "" if size_source is None else str(size_source),
    ]


def render(rows: dict) -> bytes:
    """Render the BOQ payload to PDF bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title="Bill of Quantities",
    )
    styles = getSampleStyleSheet()
    story: list = [
        Paragraph("Bill of Quantities", styles["Title"]),
        Spacer(1, 6),
    ]
    estimate_id = rows.get("estimate_id")
    if estimate_id:
        story.append(Paragraph(f"Estimate {estimate_id}", styles["Normal"]))
        story.append(Spacer(1, 8))

    data: list[list] = [HEADERS]
    for section in ("routes", "materials"):
        for line in rows.get(section) or []:
            data.append(_line_cells(line))
    table = Table(data, colWidths=_COL_WIDTHS, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("BACKGROUND", (0, 0), (-1, 0), _GREY),
                ("GRID", (0, 0), (-1, -1), 0.25, _GREY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(table)

    totals = rows.get("totals") or {}
    total_rows = [
        [label.replace(" Total", " total"), _format_number(totals[key])]
        for label, key in (
            ("Materials Total", "materials"),
            ("Labor Total", "labor"),
            ("Grand Total", "grand"),
        )
        if key in totals
    ]
    if total_rows:
        story.append(Spacer(1, 10))
        totals_table = Table(total_rows, colWidths=[140, 100], hAlign="RIGHT")
        totals_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -2), "Helvetica"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LINEABOVE", (0, -1), (-1, -1), 0.5, _GREY),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(totals_table)

    doc.build(story)
    return buffer.getvalue()
