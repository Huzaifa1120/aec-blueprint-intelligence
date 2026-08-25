"""Persistence spine — SheetExtraction → relational rows → replayable BOQ (G1).

Writes the unified conformance schema (spec v3 §8): Project/Drawing/Sheet,
layers, routes, components, schedule blocks, text annotations, then derives
Measurements + BoqItems from the SAME deterministic YAML rules the e2e
pipeline uses. No quantity is invented here: every stored number traces to
``apply_assembly`` / ``evaluate_formula`` and is replayable via
``GET /api/estimates/{id}/replay``.

Idempotency: a Sheet with the same name under the same project is replaced —
its measurements, boq_items and cascade children are deleted before
re-insertion, so re-running a sheet never duplicates rows.

Trap compliance:
- Geometry calculates, rules derive: this module only persists what the
  frozen extraction dataclasses and YAML rules produce.
- Unpriced materials keep ``unpriced: true`` in derivation_json; cost columns
  store 0.0 only because the schema is non-nullable — the flag, never a $0
  price, is the reported truth.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session as OrmSession

from app.assembly.formulas import FormulaValidationError
from app.assembly.rules import apply_assembly, load_assembly_rule
from app.catalog.prices import compute_boq_item
from app.core.config import get_settings
from app.db.models.estimate import BoqItem, Estimate, Measurement
from app.db.models.extraction import Layer, ScheduleBlock, TextAnnotation
from app.db.models.geometry import Component, Route
from app.db.models.project import Drawing, Project, Sheet
from app.e2e.extraction import ROUTE_ASSEMBLIES, SIZED_ASSEMBLIES, SheetExtraction
from app.parsing.confidence_tiering import confidence_score
from app.parsing.layer_map import layer_to_assembly

logger = logging.getLogger(__name__)


def live_confidence_tier(
    *,
    size_source: str | None,
    scale_assumed: bool,
    source_quality: str,
    rule_version: str | None,
) -> tuple[str, float]:
    """The single live-tier rule for priced BOQ lines (T3-review ruling).

    Shared by the e2e response builder (``app.e2e.router._boq_line``) and this
    persistence spine so a replayed estimate reads exactly the tiers a fresh
    run carried — never the row-level MEASURED status. ASSUMED wins over
    DERIVED; degraded input quality multiplies the score.
    """
    if size_source == "assumed" or scale_assumed:
        tier = "ASSUMED"
        score = 0.3
    else:
        tier = "DERIVED"
        score = confidence_score("DERIVED", {"rule_version": rule_version or "1.0.0"})
    if source_quality == "degraded_vector":
        score = round(score * get_settings().degraded_confidence_multiplier, 4)
    return tier, score


def _source_region(page: int | None, bbox: Any) -> dict | None:
    """Normalized click-through region ``{"page", "bbox"}``; None when absent.

    Same shape the live response carries in each BOQ row's ``source`` block,
    so payload round-trips are value-identical.
    """
    if not bbox:
        return None
    try:
        corners = [float(v) for v in bbox]
    except (TypeError, ValueError):
        return None
    if len(corners) < 4:
        return None
    return {"page": int(page or 0), "bbox": corners}


def _resolve_project(db: OrmSession, project_id: uuid.UUID | None) -> Project:
    if project_id is not None:
        project = db.get(Project, project_id)
        if project is None:
            raise ValueError(f"project {project_id} not found")
        return project
    project = db.query(Project).filter_by(name="Default Project").first()
    if project is None:
        project = Project(name="Default Project")
        db.add(project)
        db.flush()
    return project


def _find_sheet(db: OrmSession, project_id: uuid.UUID, sheet_name: str | None) -> Sheet | None:
    query = (
        db.query(Sheet)
        .join(Drawing, Sheet.drawing_id == Drawing.id)
        .filter(Drawing.project_id == project_id)
    )
    if sheet_name is None:
        query = query.filter(Sheet.name.is_(None))
    else:
        query = query.filter(Sheet.name == sheet_name)
    return query.first()


def _replace_sheet(db: OrmSession, sheet: Sheet) -> Drawing:
    """Delete a sheet's measurements/boq_items/cascade children.

    Returns the drawing to reuse for re-insertion.
    """
    drawing = sheet.drawing

    # Leaf extraction tables have no ORM relationship from Sheet — bulk
    # delete them first (they also FK-reference routes/components, so they
    # must go before the cascade removes those).
    (
        db.query(TextAnnotation)
        .filter(TextAnnotation.sheet_id == sheet.id)
        .delete(synchronize_session=False)
    )
    (
        db.query(ScheduleBlock)
        .filter(ScheduleBlock.sheet_id == sheet.id)
        .delete(synchronize_session=False)
    )
    (db.query(Layer).filter(Layer.sheet_id == sheet.id).delete(synchronize_session=False))

    # Deleting the sheet cascades delete-orphan through routes/components/
    # spaces → measurements → boq_items in one unit-of-work pass.
    db.delete(sheet)
    db.flush()
    return drawing


def _size_variables(size_json: dict | None) -> dict[str, float]:
    size = size_json or {}
    out = {
        k: float(size[k])
        for k in ("width_mm", "height_mm", "diameter_mm", "elbows_90", "tees")
        if k in size
    }
    return out


def _derivation_payload(
    material: dict,
    assembly: str,
    rule_version: str,
    rule_bom: dict | None,
    rule_waste_default: float,
) -> dict:
    """Build the replayable derivation record for one material line."""
    derivation = material.get("derivation") or {}
    payload: dict = {"material_name": material["material_name"]}
    # spec v3 §4.8: exported lines carry material/quantity/unit — stash the
    # rule-inferred unit so payload/exports can surface it (fix-wave F3).
    if material.get("unit"):
        payload["unit"] = material["unit"]
    if "formula" in derivation:
        entry = (rule_bom or {}).get(material["material_name"])
        waste = rule_waste_default
        if isinstance(entry, dict) and "waste_factor" in entry:
            waste = float(entry["waste_factor"])
        payload.update(
            {
                "formula": derivation["formula"],
                "inputs": derivation.get("inputs") or {},
                "waste_factor": waste,
                "rule_name": assembly,
                "rule_version": rule_version,
            }
        )
    elif "gauge_lookup" in derivation:
        payload.update(
            {
                "gauge_lookup": derivation["gauge_lookup"],
                "inputs": derivation.get("inputs") or {},
                "resolved": material["material_name"],
                "rule_name": assembly,
                "rule_version": rule_version,
            }
        )
    return payload


def _persist_route_boq(
    db: OrmSession,
    estimate: Estimate,
    route_row: Route,
    length_m: float,
    confidence_status: str,
    source_quality: str,
    size_json: dict | None,
    rule_version: str,
    size_source: str | None,
    layer_ocg: str,
    *,
    scale_status: str | None = None,
    source: dict | None = None,
) -> None:
    """Derive and persist the material lines for one measured route."""
    assembly = layer_to_assembly(layer_ocg) or route_row.route_type
    if assembly not in ROUTE_ASSEMBLIES:
        return

    sized = assembly in SIZED_ASSEMBLIES
    variables: dict[str, float] | None = None
    if sized:
        variables = {"length_m": length_m, **_size_variables(size_json)}

    try:
        applied = apply_assembly(assembly, variables=variables)
        materials = applied.get("materials", [])
    except FormulaValidationError as exc:
        logger.warning(
            "persist: dropping %s route (%.3f m): unresolvable size variables (%s)",
            assembly,
            length_m,
            exc,
        )
        return

    # Live tier exactly as the response carried it (T3 ruling) — same inputs,
    # same rule as app.e2e.router._boq_line via the shared helper.
    tier, score = live_confidence_tier(
        size_source=size_source,
        scale_assumed=(scale_status == "assumed"),
        source_quality=source_quality,
        rule_version=applied.get("rule_version"),
    )

    rule_dict = load_assembly_rule(assembly) or {}
    rule_bom = rule_dict.get("bom")
    rule_waste_default = float(rule_dict.get("waste_factor", 0.10))

    measurement = Measurement(
        route_id=route_row.id,
        source_sheet=route_row.sheet.name or "",
        source_region="",
        measurement_type="length",
        raw_value=length_m,
        final_value=length_m,
        confidence_status=confidence_status,
        calculation_method="vector_route_measure",
        rule_version=rule_version,
    )
    db.add(measurement)
    db.flush()

    for mat in materials:
        quantity = mat["quantity"]
        payload = _derivation_payload(
            mat,
            assembly,
            applied.get("rule_version", rule_version),
            rule_bom,
            rule_waste_default,
        )
        if "formula" not in payload and "gauge_lookup" not in payload:
            # Derivation-less constant line on a route. Sized rules already
            # scaled it by length_m inside rules.py; legacy electrical
            # constants are per-unit-length multipliers scaled here — exactly
            # as app.e2e.router does. Either way the line is replayable as
            # qty == linear_per_m * length_m.
            if variables is not None:
                base = quantity / length_m if length_m > 0 else None
            else:
                base = quantity
                quantity = base * length_m
            if base is not None:
                payload["linear_per_m"] = base
                payload["inputs"] = {"length_m": length_m}
        _add_boq_item(
            db,
            estimate,
            measurement,
            mat["material_name"],
            quantity,
            payload,
            source_quality,
            size_source,
            source=source,
            confidence_status=tier,
            confidence_score=score,
        )


def _persist_component_boq(
    db: OrmSession,
    estimate: Estimate,
    component_row: Component,
    count: int,
    confidence_status: str,
    source_quality: str,
    rule_version: str,
    *,
    source: dict | None = None,
) -> None:
    """Derive and persist the material lines for one counted symbol type."""
    resolved_type = component_row.component_type
    if resolved_type is None or resolved_type == "UNMAPPED":
        # UNMAPPED symbols are surfaced and persisted, never priced (D9):
        # rows arrive with component_type coerced to the string "UNMAPPED",
        # so the guard must match that literal too — rule availability must
        # never decide whether an unmapped symbol gets priced (F2).
        return
    if resolved_type in SIZED_ASSEMBLIES:
        # Sized assemblies are quantified by routes only (same rule as the
        # e2e pipeline): a duct/pipe cluster here is geometry, not a symbol.
        return
    # STRICT SKIP, mirroring app.e2e.router: when the rule is missing or its
    # declared name does not match the resolved type, never apply an
    # unrelated rule — persisted BOQ must equal response math (fix-wave L1).
    rule = load_assembly_rule(resolved_type)
    if rule is None or resolved_type != rule.get("name", resolved_type):
        return
    applied = apply_assembly(resolved_type)
    materials = applied.get("materials", [])
    if not materials:
        return

    # Live tier exactly as the response carried it (T3 ruling). T3 carve-out:
    # component quantities are count × rule multiplier — scale-independent by
    # construction — so counted lines never take the assumed-scale downgrade
    # (neither does the live response's component call site).
    tier, score = live_confidence_tier(
        size_source=None,
        scale_assumed=False,
        source_quality=source_quality,
        rule_version=applied.get("rule_version"),
    )

    measurement = Measurement(
        component_id=component_row.id,
        source_sheet=component_row.sheet.name or "",
        source_region="",
        measurement_type="count",
        raw_value=float(count),
        final_value=float(count),
        confidence_status=confidence_status,
        calculation_method="symbol_cluster_count",
        rule_version=rule_version,
    )
    db.add(measurement)
    db.flush()

    for mat in materials:
        quantity = mat["quantity"] * count
        payload = _derivation_payload(
            mat,
            resolved_type,
            applied.get("rule_version", rule_version),
            (load_assembly_rule(resolved_type) or {}).get("bom"),
            float((load_assembly_rule(resolved_type) or {}).get("waste_factor", 0.10)),
        )
        _add_boq_item(
            db,
            estimate,
            measurement,
            mat["material_name"],
            quantity,
            payload,
            source_quality,
            None,
            source=source,
            confidence_status=tier,
            confidence_score=score,
        )


def _add_boq_item(
    db: OrmSession,
    estimate: Estimate,
    measurement: Measurement,
    material_name: str,
    quantity: float,
    payload: dict,
    source_quality: str,
    size_source: str | None,
    *,
    source: dict | None = None,
    confidence_status: str | None = None,
    confidence_score: float | None = None,
) -> None:
    boq = compute_boq_item(quantity, material_name, db)
    if boq.get("unpriced"):
        payload["unpriced"] = True
    item = BoqItem(
        measurement_id=measurement.id,
        estimate_id=estimate.id,
        quantity=quantity,
        unit_cost=float(boq.get("unit_price") or 0.0),
        total_cost=float(boq.get("total_cost") or 0.0),
        derivation_json=json.dumps(payload),
        size_source=size_source,
        # Click-through region + live tier, mirroring the API response
        # (T3-review ruling): a replayed estimate reads the same tiers a
        # fresh run showed, never the row-level MEASURED status.
        source_bbox_json=(json.dumps(source) if source else None),
        confidence_status=confidence_status,
        confidence_score=confidence_score,
    )
    db.add(item)


def persist_extraction(
    db: OrmSession,
    project_id: uuid.UUID | None,
    extraction: SheetExtraction,
) -> uuid.UUID:
    """Persist one sheet extraction; returns the new estimate id.

    Replace strategy: an existing Sheet with the same name under the project
    has its measurements/boq_items/cascade children deleted before the fresh
    rows are inserted. Creates ``Project(name="Default Project")`` when
    ``project_id`` is None.
    """
    project = _resolve_project(db, project_id)

    existing_sheet = _find_sheet(db, project.id, extraction.sheet_name)
    if existing_sheet is not None:
        drawing = _replace_sheet(db, existing_sheet)
    else:
        drawing = Drawing(discipline=extraction.discipline)
        project.drawings.append(drawing)
        db.flush()

    sheet = Sheet(
        drawing_id=drawing.id,
        name=extraction.sheet_name,
        page_number=extraction.page_number,
        scale=extraction.scale[:20] if extraction.scale else None,
        source_quality=extraction.source_quality,
    )
    db.add(sheet)
    db.flush()

    layer_ids: dict[str, uuid.UUID] = {}
    for row in extraction.layers:
        layer = Layer(
            sheet_id=sheet.id,
            ocg_name=row.ocg_name[:100],
            classified_discipline=row.classified_discipline[:50],
        )
        db.add(layer)
        db.flush()
        layer_ids[row.ocg_name] = layer.id

    route_rows: list[Route] = []
    for row in extraction.routes:
        route = Route(
            sheet_id=sheet.id,
            route_type=row.route_type[:100] or "unclassified",
            length_m=row.length_m,
            confidence_status=row.confidence_status,
            confidence_score=row.confidence_score,
            layer_id=layer_ids.get(row.layer_ocg),
            source_quality=extraction.source_quality,
            size_json=(json.dumps(row.size_json) if row.size_json else None),
        )
        db.add(route)
        route_rows.append(route)

    component_rows: list[Component] = []
    for row in extraction.components:
        component = Component(
            sheet_id=sheet.id,
            component_type=(row.component_type or "UNMAPPED")[:100],
            source_layer=row.layer_ocg[:100] or None,
            x=row.x,
            y=row.y,
            # component_type=None ⇒ UNMAPPED tier, whatever the caller sent.
            confidence_status=(
                row.confidence_status if row.component_type else "UNMAPPED"
            ),
            confidence_score=row.confidence_score,
            layer_id=layer_ids.get(row.layer_ocg),
            source_quality=extraction.source_quality,
        )
        db.add(component)
        component_rows.append(component)

    for row in extraction.schedule_blocks:
        db.add(
            ScheduleBlock(
                sheet_id=sheet.id,
                block_type=row.block_type[:30],
                page_region_json=json.dumps(row.page_region)[:500],
                entries_json=json.dumps(row.entries),
                source_quality=extraction.source_quality,
            )
        )

    annotations: list[TextAnnotation] = []
    for row in extraction.text_annotations:
        annotation = TextAnnotation(
            sheet_id=sheet.id,
            text=row.text,
            bbox_json=json.dumps(list(row.bbox))[:200],
            ocg_layer=row.ocg_layer[:100] if row.ocg_layer else None,
        )
        db.add(annotation)
        annotations.append(annotation)

    db.flush()  # assign route/component ids before measurements reference them

    # Estimate-level provenance (spec v3 conformance): how the scale was
    # obtained + the run's DataQuality counters with the resolved scale_str
    # folded into the same JSON document.
    estimate = Estimate(
        project_id=project.id,
        scale_status=extraction.scale_status,
        data_quality_json=json.dumps(
            {"scale_str": extraction.scale_str, **(extraction.data_quality or {})}
        ),
    )
    db.add(estimate)
    db.flush()

    for row, route_row in zip(extraction.routes, route_rows):
        _persist_route_boq(
            db,
            estimate,
            route_row,
            row.length_m,
            row.confidence_status,
            extraction.source_quality,
            row.size_json,
            extraction.rule_version,
            (row.size_json or {}).get("source"),
            row.layer_ocg,
            scale_status=extraction.scale_status,
            source=_source_region(row.page, row.bbox),
        )

    counts: dict[str | None, int] = {}
    order: list[str | None] = []
    for row in extraction.components:
        key = row.component_type
        if key not in counts:
            counts[key] = 0
            order.append(key)
        counts[key] += 1
    consumed: dict[str | None, int] = {key: 0 for key in order}
    for row, component_row in zip(extraction.components, component_rows):
        key = row.component_type
        if consumed[key] == 0:
            _persist_component_boq(
                db,
                estimate,
                component_row,
                counts[key],
                row.confidence_status,
                extraction.source_quality,
                extraction.rule_version,
                source=_source_region(row.page, row.bbox),
            )
        consumed[key] += 1

    for row, annotation in zip(extraction.text_annotations, annotations):
        if row.component_index is not None and row.component_index < len(component_rows):
            annotation.component_id = component_rows[row.component_index].id
        if row.route_index is not None and row.route_index < len(route_rows):
            annotation.route_id = route_rows[row.route_index].id
    db.flush()

    total_material = (
        db.query(BoqItem)
        .filter(BoqItem.estimate_id == estimate.id)
        .with_entities(BoqItem.total_cost)
        .all()
    )
    estimate.total_material_cost = round(sum(float(t[0] or 0.0) for t in total_material), 2)
    estimate.total_labor_cost = 0.0
    estimate.total_cost = estimate.total_material_cost
    db.commit()
    return estimate.id
