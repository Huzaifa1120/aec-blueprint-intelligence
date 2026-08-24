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

    Phase 4 additionally verifies every ``fixture_units``-sourced route on
    the estimate for derivation coherence (Global Constraint refinement 2):
    the gauge table re-resolves ``fu_total`` to the recorded ``diameter_mm``,
    and the ``ref`` breakdown tokens must exist in the rule YAML and sum to
    the recorded total. Corrupt provenance fails honest; a tampered database
    can never replay clean.

    200 ``{checked, mismatches: []}`` when every checked item reproduces;
    409 ``{detail, mismatches: [boq_item_id | route:id, ...]}`` listing
    offenders when any recomputation diverges.
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
from app.db.models.project import Project
from app.db.session import get_db
from app.estimates.payload import payload_from_estimate
from app.parsing.fixture_units import (
    fixture_units_for_type,
    resolve_size_from_fixture_units,
)

router = APIRouter(prefix="/api/estimates", tags=["estimates"])


@router.get("", summary="List persisted estimates")
def list_estimates(db: OrmSession = Depends(get_db)) -> list[dict]:
    """Read-only listing for the frontend estimates index.

    Ordered by project name for stable display (Estimate carries no
    timestamp column; adding one would be a migration).
    """
    rows = (
        db.query(Estimate, Project)
        .join(Project, Estimate.project_id == Project.id)
        .all()
    )
    return [
        {
            "estimate_id": str(estimate.id),
            "project_name": project.name,
            "total_material_cost": estimate.total_material_cost,
            "total_labor_cost": estimate.total_labor_cost,
            "total_cost": estimate.total_cost,
        }
        for estimate, project in sorted(rows, key=lambda pair: pair[1].name)
    ]


_TOLERANCE = 1e-6

_RECOGNIZED_BRANCHES = ("formula", "linear_per_m", "gauge_lookup")


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


def _load_size_json(raw: str | None) -> dict | None:
    """Parse a persisted Route.size_json; None when absent/unparseable."""
    try:
        return json.loads(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _verify_fu_size(size: dict) -> bool:
    """Derivation coherence for one fixture_units-sourced route size.

    The gauge table must re-resolve the recorded fu_total to the recorded
    diameter_mm, and every ``type@key`` ref token's rule YAML fixture units
    must exist and sum to the recorded total (T7 writes both from the same
    accumulation, so a divergence means tampering or YAML drift).
    """
    gauge = (load_assembly_rule("water_supply") or {}).get("fixture_unit_gauge") or {}
    try:
        fu_total = float(size["fu_total"])
        diameter = float(size["diameter_mm"])
        breakdown = size["ref"]
    except (KeyError, TypeError, ValueError):
        return False
    if not isinstance(breakdown, list) or not breakdown:
        return False  # an FU-resolved size with no contributing fixtures is incoherent
    resolved = resolve_size_from_fixture_units(fu_total, gauge.get("rows") or {})
    if not resolved or abs(resolved["diameter_mm"] - diameter) > 1e-9:
        return False
    # Breakdown coherence: each "type@key" ref's rule YAML FU must exist,
    # and the recorded FUs must sum to the recorded total.
    total = 0.0
    for token in breakdown:
        ctype = str(token).split("@", 1)[0]
        fu = fixture_units_for_type(ctype)
        if fu <= 0.0:
            return False
        total += fu
    return abs(total - fu_total) <= 1e-6


@router.get("/{estimate_id}/boq", summary="Persisted BOQ rows for an estimate")
def get_estimate_boq(
    estimate_id: uuid.UUID,
    db: OrmSession = Depends(get_db),
) -> dict:
    estimate = db.get(Estimate, estimate_id)
    if estimate is None:
        raise HTTPException(status_code=404, detail="estimate not found")
    return payload_from_estimate(estimate)


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

    # Phase 4: fixture_units-sourced route sizes must stay coherent with
    # their recorded FU totals, breakdown refs, and the rule's gauge table.
    seen_route_ids: set[uuid.UUID] = set()
    for item in estimate.boq_items:
        route_row = getattr(getattr(item, "measurement", None), "route", None)
        if route_row is None or route_row.id in seen_route_ids:
            continue
        seen_route_ids.add(route_row.id)
        raw_size = route_row.size_json
        size = _load_size_json(raw_size)
        if raw_size and not isinstance(size, dict):
            # Present-but-corrupt provenance fails honest (mirrors the F2 rule).
            checked += 1
            mismatches.append(f"route:{route_row.id}")
            continue
        if not isinstance(size, dict) or size.get("source") != "fixture_units":
            continue
        checked += 1
        if not _verify_fu_size(size):
            mismatches.append(f"route:{route_row.id}")

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
