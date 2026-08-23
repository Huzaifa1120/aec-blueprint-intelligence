"""Shared BOQ payload builder — one source of truth for reads and downloads.

``payload_from_estimate`` loads ``Estimate -> BoqItem -> Measurement ->
Route/Component`` via ORM into the documented ``GET /api/estimates/{id}/boq``
row shape (``estimate_id`` / ``totals`` / flat ``routes`` / ``materials``
lists). The estimates, exports and narration routers all consume this builder
so a JSON export is byte-for-value equal to the /boq response.

Values are copied verbatim from persisted rows — no arithmetic happens at
read time (trap compliance: the flag ``unpriced``, never a substituted $0
price, reports a missing catalog price).
"""

from __future__ import annotations

import json

from app.db.models.estimate import Estimate


def parse_json_object(raw: str | None) -> dict | None:
    """Tolerant parse for read paths; None on anything unparseable."""
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def material_name(derivation: dict, measurement: object) -> str:
    """Best-effort label; persistence stores the name in derivation_json."""
    for key in ("material_name", "rule_name"):
        value = derivation.get(key)
        if isinstance(value, str) and value:
            return value
    component = getattr(measurement, "component", None)
    component_type = getattr(component, "component_type", None)
    return component_type or getattr(measurement, "measurement_type", None) or "unnamed item"


def payload_from_estimate(estimate: Estimate) -> dict:
    """Build the BOQ payload — same shape for /boq, exports and narration."""
    routes: list[dict] = []
    materials: list[dict] = []
    for item in estimate.boq_items:
        measurement = item.measurement
        derivation = parse_json_object(item.derivation_json) or {}
        unpriced = bool(derivation.get("unpriced")) or item.unit_cost == 0.0
        entry: dict = {
            "material_name": material_name(derivation, measurement),
            "quantity": item.quantity,
            "unit_cost": item.unit_cost,
            # None when unpriced: the flag, never a fabricated $0, is truth.
            "unit_price": None if unpriced else item.unit_cost,
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
                    "size_json": parse_json_object(route.size_json),
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
