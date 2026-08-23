"""Estimates read API — BOQ rows and the replay determinism gate.

``GET /api/estimates/{id}/boq``
    Returns the persisted rows in the documented payload shape (identical to
    what ``app.exports.router`` adapts for downloads): ``estimate_id``,
    ``totals``, flat ``routes`` / ``materials`` line lists. Values are copied
    verbatim from persisted rows — no arithmetic happens at read time.

``GET /api/estimates/{id}/replay``
    Recomputes every stored BoqItem quantity from its recorded derivation
    and compares with the persisted quantity within ``1e-6 * max(1, qty)``:

    - ``formula``      -> evaluate_formula(formula, inputs) [* (1+waste)]
    - ``linear_per_m`` -> linear_per_m * length_m
    - ``gauge_lookup`` -> lookup_gauge(table, inputs) equals resolved value
    - anything else    -> skipped, counted unchecked

    Evaluation inputs reproduce ``apply_assembly``'s binding order exactly:
    the derivation's rule YAML ``defaults`` sit UNDER the recorded input
    snapshot (recorded values win), then derived variables such as
    ``max_mm`` are recomputed. A corrupt or non-dict ``derivation_json``
    fails honest as a mismatch — it can never hide as "unchecked".

    200 ``{checked, mismatches: []}`` when every checked item reproduces;
    409 ``{detail, mismatches: [boq_item_id, ...]}`` listing offenders when
    any recomputation diverges. A tampered database can never replay clean.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session as OrmSession

from app.assembly.formulas import (
    FormulaValidationError,
    evaluate_formula,
    lookup_gauge,
)
from app.assembly.rules import load_assembly_rule
from app.db.models.estimate import BoqItem, Estimate
from app.db.session import get_db

router = APIRouter(prefix="/api/estimates", tags=["estimates"])

_TOLERANCE = 1e-6

_RECOGNIZED_BRANCHES = ("formula", "linear_per_m", "gauge_lookup")


def _parse_json_object(raw: str | None) -> dict | None:
    """Tolerant parse for read paths; None on anything unparseable."""
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _load_derivation(raw: str | None) -> tuple[dict | None, bool]:
    """Strict parse for the replay gate.

    Returns ``(derivation, corrupt)`` where ``corrupt`` marks a payload that
    is present but unparseable or not a JSON object — those must fail honest
    as mismatches. A NULL/empty column means nothing was recorded and stays
    an unchecked skip.
    """
    if raw is None or raw == "":
        return None, False
    try:
        value = json.loads(raw)
    except ValueError:
        return None, True
    if not isinstance(value, dict):
        return None, True
    return value, False


def _material_name(derivation: dict, measurement: object) -> str:
    """Best-effort label; persistence stores the name in derivation_json."""
    for key in ("material_name", "rule_name"):
        value = derivation.get(key)
        if isinstance(value, str) and value:
            return value
    component = getattr(measurement, "component", None)
    component_type = getattr(component, "component_type", None)
    return component_type or getattr(measurement, "measurement_type", None) or "unnamed item"


def _payload_from_estimate(db: OrmSession, estimate: Estimate) -> dict:
    """Build the BOQ payload — same shape as app.exports.router adapts."""
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


@router.get("/{estimate_id}/boq", summary="Persisted BOQ rows for an estimate")
def get_estimate_boq(
    estimate_id: uuid.UUID,
    db: OrmSession = Depends(get_db),
) -> dict:
    estimate = db.get(Estimate, estimate_id)
    if estimate is None:
        raise HTTPException(status_code=404, detail="estimate not found")
    return _payload_from_estimate(db, estimate)


# ---------------------------------------------------------------------------
# Replay determinism gate
# ---------------------------------------------------------------------------
def _rule_defaults(rule_name: object) -> dict[str, float]:
    """Numeric ``defaults`` declared by the derivation's YAML rule."""
    if not isinstance(rule_name, str) or not rule_name:
        return {}
    rule = load_assembly_rule(rule_name) or {}
    defaults: dict[str, float] = {}
    for key, value in (rule.get("defaults") or {}).items():
        try:
            defaults[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return defaults


def _evaluation_inputs(derivation: dict) -> dict[str, float]:
    """Reproduce apply_assembly's binding: defaults < recorded < derived.

    The stored ``inputs`` snapshot holds only caller-supplied variables, but
    quantities were computed with the rule's YAML ``defaults`` underneath
    (rules.py ``_effective_variables``). Replay merges those defaults back
    under the snapshot — recorded values win — then re-derives variables
    such as ``max_mm`` to reproduce the exact evaluation context.
    """
    merged: dict[str, float] = {}
    for key, value in _rule_defaults(derivation.get("rule_name")).items():
        merged[key] = value
    for key, value in (derivation.get("inputs") or {}).items():
        try:
            merged[key] = float(value)
        except (TypeError, ValueError):
            continue
    if "max_mm" not in merged:
        candidates = [
            merged[source]
            for source in ("width_mm", "height_mm", "diameter_mm")
            if source in merged
        ]
        if candidates:
            merged["max_mm"] = max(candidates)
    return merged


def _replay_item(item: BoqItem, derivation: dict) -> bool:
    """Recompute one BoqItem's quantity from its recorded derivation."""
    tolerance = _TOLERANCE * max(1.0, float(item.quantity))

    def _matches(expected: float) -> bool:
        return abs(float(expected) - float(item.quantity)) <= tolerance

    inputs = _evaluation_inputs(derivation)
    try:
        if "formula" in derivation:
            expected = evaluate_formula(str(derivation["formula"]), inputs)
            waste = derivation.get("waste_factor")
            if waste is not None:
                expected *= 1.0 + float(waste)
            return _matches(expected)
        if "linear_per_m" in derivation:
            length_m = float(inputs.get("length_m", 0.0))
            return _matches(float(derivation["linear_per_m"]) * length_m)
        if "gauge_lookup" in derivation:
            resolved = lookup_gauge(derivation["gauge_lookup"], inputs)
            return resolved == derivation.get("resolved")
    except (FormulaValidationError, TypeError, ValueError):
        # Unbindable/corrupt record: fail honest as a mismatch, never pass.
        return False
    return True  # unrecognized branch: unchecked skip


@router.get(
    "/{estimate_id}/replay",
    summary="Recompute persisted quantities from their derivations",
)
def replay_estimate(
    estimate_id: uuid.UUID,
    db: OrmSession = Depends(get_db),
) -> Any:
    estimate = db.get(Estimate, estimate_id)
    if estimate is None:
        raise HTTPException(status_code=404, detail="estimate not found")

    mismatches: list[str] = []
    checked = 0
    unchecked = 0
    for item in estimate.boq_items:
        derivation, corrupt = _load_derivation(item.derivation_json)
        if corrupt:
            # Present-but-unparseable payload: fail honest, never hide as
            # unchecked (F2).
            checked += 1
            mismatches.append(str(item.id))
            continue
        recognized = bool(derivation) and any(key in derivation for key in _RECOGNIZED_BRANCHES)
        if not recognized:
            unchecked += 1
            continue
        checked += 1
        if not _replay_item(item, derivation):
            mismatches.append(str(item.id))

    if mismatches:
        return JSONResponse(
            status_code=409,
            content={
                "detail": (f"{len(mismatches)} BOQ item(s) failed the replay determinism check"),
                "checked": checked,
                "unchecked": unchecked,
                "mismatches": mismatches,
            },
        )
    return {
        "estimate_id": str(estimate.id),
        "checked": checked,
        "unchecked": unchecked,
        "mismatches": [],
    }
