"""Narration API — narrated scope of work for a persisted estimate (G8).

Loads the persisted BOQ via ORM (Estimate -> BoqItem -> Measurement ->
Route/Component) into the same row shape as ``GET /api/estimates/{id}/boq``
(``routes`` / ``materials`` / ``totals``), then hands it to a narrator
provider. Template fallback fires on ANY provider exception, logged once.

The router only formats structured numbers verbatim downstream: it copies
values from the ORM rows without arithmetic.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as OrmSession

from app.db.models.estimate import Estimate
from app.db.session import get_db
from app.narration.providers import (
    NarrationResult,
    TemplateNarrator,
    get_provider,
    verify_no_invented_numbers,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/narration", tags=["narration"])

_fallback_logged = False


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


@router.get("/estimates/{estimate_id}", summary="Narrated scope of work for an estimate")
def narrate_estimate(estimate_id: uuid.UUID, db: OrmSession = Depends(get_db)) -> dict:
    estimate = db.get(Estimate, estimate_id)
    if estimate is None:
        raise HTTPException(status_code=404, detail="estimate not found")

    payload = _payload_from_estimate(db, estimate)

    global _fallback_logged
    provider = get_provider()
    try:
        result: NarrationResult = provider.narrate(payload)
        # Runtime numeric enforcement — prompt compliance is never trusted.
        verify_no_invented_numbers(result["narrative"], payload)
    except Exception:
        if not _fallback_logged:
            logger.warning(
                "narration provider %s failed verbatimism gate; falling back to template",
                getattr(provider, "name", "?"),
                exc_info=True,
            )
            _fallback_logged = True
        result = TemplateNarrator().narrate(payload)

    return {
        "estimate_id": str(estimate.id),
        "provider": result["provider"],
        "narrative": result["narrative"],
    }
