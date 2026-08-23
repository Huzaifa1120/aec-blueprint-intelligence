"""Exports API — download a persisted estimate's BOQ as JSON/XLSX/PDF (G7).

Loads ``Estimate -> BoqItem -> Measurement -> Route/Component`` via ORM and
adapts the rows into the documented ``GET /api/estimates/{id}/boq`` payload
shape, then hands that dict to the selected writer (``render(rows) -> bytes``).
Values are copied verbatim from persisted rows — no arithmetic happens here.
"""

from __future__ import annotations

import io
import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as OrmSession

from app.db.models.estimate import Estimate
from app.db.session import get_db
from app.exports import json_export, pdf_export, xlsx_export

router = APIRouter(prefix="/api/exports", tags=["exports"])

_WRITERS = {
    "json": (json_export.render, "application/json", "boq.json"),
    "xlsx": (
        xlsx_export.render,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "boq.xlsx",
    ),
    "pdf": (pdf_export.render, "application/pdf", "boq.pdf"),
}

Format = Literal["json", "xlsx", "pdf"]


def _parse_json_object(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _material_name(derivation: dict, measurement: object) -> str:
    """Best-effort label; persistence may store the name in derivation_json."""
    for key in ("material_name", "rule_name"):
        value = derivation.get(key)
        if isinstance(value, str) and value:
            return value
    component = getattr(measurement, "component", None)
    component_type = getattr(component, "component_type", None)
    return component_type or getattr(measurement, "measurement_type", None) or "unnamed item"


def _payload_from_estimate(db: OrmSession, estimate: Estimate) -> dict:
    """Build the BOQ payload (same shape as GET /api/estimates/{id}/boq)."""
    routes: list[dict] = []
    materials: list[dict] = []
    for item in estimate.boq_items:
        measurement = item.measurement
        derivation = _parse_json_object(item.derivation_json) or {}
        unpriced = bool(derivation.get("unpriced")) or item.unit_cost == 0.0
        entry: dict = {
            "material_name": _material_name(derivation, measurement),
            "quantity": item.quantity,
            "unit_cost": item.unit_cost,
            "total_cost": item.total_cost,
            "unpriced": unpriced,
            "confidence_status": getattr(measurement, "confidence_status", "MEASURED"),
            "size_source": item.size_source,
        }
        route = getattr(measurement, "route", None)
        if route is not None:
            routes.append(
                {
                    "route_type": route.route_type,
                    "length_m": route.length_m,
                    "size_json": _parse_json_object(route.size_json),
                    "confidence_status": route.confidence_status,
                    **entry,
                }
            )
        else:
            materials.append(entry)
    return {
        "estimate_id": str(estimate.id),
        "totals": {
            "materials": estimate.total_material_cost,
            "labor": estimate.total_labor_cost,
            "grand": estimate.total_cost,
        },
        "routes": routes,
        "materials": materials,
    }


@router.get(
    "/estimates/{estimate_id}/export",
    summary="Download a persisted estimate's BOQ as JSON, XLSX or PDF",
)
def export_estimate(
    estimate_id: uuid.UUID,
    format: Format = "json",
    db: OrmSession = Depends(get_db),
) -> StreamingResponse:
    estimate = db.get(Estimate, estimate_id)
    if estimate is None:
        raise HTTPException(status_code=404, detail="estimate not found")

    payload = _payload_from_estimate(db, estimate)
    render_fn, media_type, suffix = _WRITERS[format]
    data = render_fn(payload)
    filename = f"estimate-{estimate_id}-{suffix}"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
