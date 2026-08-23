"""E2E pipeline endpoint — PDF upload → BOQ.

Exposes ``POST /api/e2e/run`` which runs the full vector pipeline:

1. ``classify_upload`` → decides vector/raster
2. ``parse_pdf`` → extract drawings, text spans, build OCG registry
3. ``detect_scale`` → read scale from title block
4. ``measure_routes`` → CONDUIT / CABLE_TRAY lengths at detected scale
5. ``count_components`` → discrete symbols (lighting, switches, trays, …)
6. ``apply_assembly`` → per‑component BOM & labor hours from YAML rules
7. ``compute_boq_item`` → catalog price lookup, ``unpriced`` flag, total cost

Returns BOQ items with ``confidence_status`` (MEASURED/DERIVED/ASSUMED) and
``source_path_ids`` for frontend click‑through.

Trap compliance:
- No price is hardcoded in source. If the catalog has no price, the item is
  flagged ``unpriced`` (never $0 substitution) for human review.
- Layer→assembly resolution is YAML‑driven (``data/layer_mapping.yaml``).
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from typing import List, Dict, Any

from fastapi import APIRouter, File, UploadFile
from sqlalchemy.orm import Session as OrmSession

from app.db.session import get_engine
from app.e2e.extraction import (
    ComponentRow,
    LayerRow,
    RouteRow,
    SheetExtraction,
)
from app.e2e.persistence import persist_extraction
from app.ingestion.router import classify_upload
from app.ingestion.vector import parse_pdf
from app.parsing.scale import detect_scale
from app.parsing.routes import measure_routes
from app.parsing.sizes import detect_schedule_rows, resolve_route_size
from app.parsing.components import count_components
from app.parsing.layer_map import layer_to_assembly, route_layers
from app.assembly.rules import apply_assembly, load_assembly_rule
from app.catalog.prices import compute_boq_item


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/e2e", tags=["e2e"])

# Length-based assemblies: measured routes only (never point-based symbols).
ROUTE_ASSEMBLIES = {
    "cable_tray",
    "conduit",
    "duct_rectangular",
    "duct_round",
    "pipe_insulated",
}
# Mechanical route assemblies whose cross-section size drives the formulas.
SIZED_ASSEMBLIES = {"duct_rectangular", "duct_round", "pipe_insulated"}
# Assemblies counted from mechanical discipline symbols (metadata only,
# used to label persisted LayerRows with a classified_discipline).
MECHANICAL_ASSEMBLIES = {
    "duct_rectangular",
    "duct_round",
    "pipe_insulated",
    "hvac_equipment",
}


# ---------------------------------------------------------------------------
# Helper: compute BOQ line from a material + quantity
# ---------------------------------------------------------------------------
def _boq_line(
    assembly_type: str,
    material_name: str,
    quantity: float,
    confidence_status: str,
    source_path_ids: List[str],
    db: OrmSession,
    source_quality: str = "layered_vector",
    derivation: Any = None,
    size_source: str = None,
) -> Dict[str, Any]:
    from app.core.config import get_settings

    boq = compute_boq_item(quantity, material_name, db)
    base_score = (
        get_settings().degraded_confidence_multiplier
        if source_quality == "degraded_vector"
        else 1.0
    )
    return {
        "assembly_type": assembly_type,
        "material_name": material_name,
        "quantity": round(quantity, 3),
        "unit_price": boq.get("unit_price"),
        "total_cost": boq.get("total_cost"),
        "unpriced": boq.get("unpriced", False),
        "confidence_status": confidence_status,
        "confidence_score": base_score,
        "source_quality": source_quality,
        "source_path_ids": source_path_ids,
        "derivation": derivation,
        "size_source": size_source,
    }


def _adapt_spans_for_cascade(raw_text_spans: List[Dict]) -> List[Dict]:
    """Map PyMuPDF span dicts ({text, bbox}) to the cascade's x0..y1 shape."""
    adapted: List[Dict] = []
    for span in raw_text_spans:
        bbox = span.get("bbox")
        if not bbox or len(bbox) < 4:
            continue
        adapted.append({
            "text": span.get("text", ""),
            "x0": float(bbox[0]),
            "y0": float(bbox[1]),
            "x1": float(bbox[2]),
            "y1": float(bbox[3]),
        })
    return adapted


def _discipline_for_layer(layer: str) -> str:
    """Metadata-only discipline label for persisted LayerRows."""
    assembly = layer_to_assembly(layer)
    if assembly is None:
        return "unclassified"
    return "mechanical" if assembly in MECHANICAL_ASSEMBLIES else "electrical"


def _build_sheet_extraction(
    sheet_name: str | None,
    scale: Any,
    source_quality: str,
    routes: List[Dict],
    route_sizes: List[Dict | None],
    components: List[Dict],
) -> SheetExtraction:
    """Project the pipeline's route/component lists into a SheetExtraction.

    Minimal A1 slice: geometry rows only — persistence.py re-derives the
    BOQ from the same deterministic YAML rules, never from these lists.
    """
    layer_names: List[str] = []
    for route in routes:
        name = route.get("layer", "")
        if name and name not in layer_names:
            layer_names.append(name)
    for comp in components:
        name = comp.get("layer", "")
        if name and name not in layer_names:
            layer_names.append(name)

    return SheetExtraction(
        sheet_name=sheet_name,
        page_number=None,
        scale=str(scale) if scale else None,
        discipline=None,
        source_quality=source_quality,
        layers=[LayerRow(n, _discipline_for_layer(n)) for n in layer_names],
        routes=[
            RouteRow(
                route_type=str(route.get("type") or ""),
                layer_ocg=route.get("layer", ""),
                length_m=float(route.get("length_m") or 0.0),
                confidence_status=route.get("confidence_status", "MEASURED"),
                confidence_score=float(route.get("confidence_score", 1.0)),
                size_json=route_sizes[index],
            )
            for index, route in enumerate(routes)
        ],
        components=[
            ComponentRow(
                component_type=comp.get("assembly_type"),
                layer_ocg=comp.get("layer", ""),
                x=float(comp.get("x", 0.0)),
                y=float(comp.get("y", 0.0)),
                confidence_status=comp.get("confidence_status", "MEASURED"),
                confidence_score=float(comp.get("confidence_score", 1.0)),
                source_path_ids=list(comp.get("source_path_ids", [])),
            )
            for comp in components
        ],
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@router.post(
    "/run",
    summary="Run the full E2E vector pipeline on an uploaded PDF",
)
def e2e_run(
    file: UploadFile = File(...,
        description="PDF file to process (vector preferred)."),
    persist: bool = False,
    project_id: uuid.UUID | None = None,
) -> Dict[str, Any]:
    """Run the complete PDF → BOQ pipeline and return BOQ items.

    When ``persist`` is true the extraction is written to the database
    (idempotently replacing any prior rows for the same sheet under the
    project) and the response gains an ``estimate_id``.
    """

    # Save the uploaded PDF to a temporary file so that the path‑based
    # helpers (classify_upload, parse_pdf) can receive a real file path.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    try:
        # 1️⃣ Classify
        try:
            classify_result = classify_upload(tmp_path)
        except Exception:
            classify_result = {"status": "raster"}

        if classify_result.get("status") != "vector":
            return {
                "status": "raster",
                "detail": "PDF classified as raster; vector pipeline skipped.",
            }

        source_quality = classify_result.get("source_quality", "layered_vector")

        # 2️⃣ Parse PDF
        parsed = parse_pdf(tmp_path)
        scale = detect_scale(parsed.get("raw_text_spans", []))
        clusters = parsed.get("clusters", [])
        raw_drawings = parsed.get("raw_drawings", [])
        cascade_spans = _adapt_spans_for_cascade(parsed.get("raw_text_spans", []))
        schedule_rows = detect_schedule_rows(cascade_spans)

        # 3️⃣ Measure routes (length-based assemblies: tray, conduit, ducts, pipes)
        route_layer_names = tuple(route_layers())
        routes = measure_routes(clusters, raw_drawings, scale, route_layer_names)
        # Resolved cross-section sizes aligned with `routes` by index —
        # reused when projecting a SheetExtraction for persistence.
        route_sizes: List[Dict | None] = [None] * len(routes)

        # 4️⃣ Count discrete components (symbol-based assemblies)
        components = count_components(clusters, raw_drawings)

        # 5️⃣ Apply assembly rules & compute BOQ
        boq_items: List[Dict[str, Any]] = []
        with OrmSession(get_engine()) as db:
            # Route BOQ: quantity scales with measured length
            # Routes must ONLY evaluate against route-based assembly rules
            for route_index, route in enumerate(routes):
                layer = route.get("layer", "")
                resolved_assembly = layer_to_assembly(layer)
                # Use resolved layer assembly if available, fall back to route type
                assembly_type = resolved_assembly if resolved_assembly else route.get("type", "")
                if assembly_type not in ROUTE_ASSEMBLIES:
                    continue

                variables = None
                size_source = None
                if assembly_type in SIZED_ASSEMBLIES:
                    mech_rule = load_assembly_rule(assembly_type) or {}
                    size = resolve_route_size(
                        route,
                        cascade_spans,
                        scale,
                        schedule_rows=schedule_rows,
                        default_size=mech_rule.get("defaults") or None,
                    )
                    if size is None:
                        logger.warning(
                            "dropping %s route (%.3f m): no resolvable "
                            "cross-section size and no configured default",
                            assembly_type,
                            route["length_m"],
                        )
                        continue
                    size_source = size.get("source")
                    route_sizes[route_index] = size
                    # A cascade source above 'assumed' only holds if the
                    # resolved size actually covers the rule's required size
                    # variables; when defaults filled the gap the row must be
                    # labelled ASSUMED (fail-honest provenance, spec §4).
                    required_size_vars = set(mech_rule.get("variables") or []) - {
                        "length_m",
                        "max_mm",
                    }
                    if any(var not in size for var in required_size_vars):
                        size_source = "assumed"
                    variables = {"length_m": route["length_m"], **{
                        k: v for k, v in size.items()
                        if k in ("width_mm", "height_mm", "diameter_mm")
                    }}
                    # max_mm is derived inside rules.py from the bound
                    # width/height/diameter — no manual duplication here.

                applied = apply_assembly(assembly_type, variables=variables)
                for mat in applied.get("materials", []):
                    quantity = mat["quantity"]
                    # Legacy electrical path (variables=None): constants are
                    # per-unit-length multipliers scaled here. Mechanical
                    # rules with bound variables already scale their constant
                    # lines by length_m inside rules.py — scaling again would
                    # square every fitting length (0.2 * L^2).
                    if variables is None and "formula" not in (
                        mat.get("derivation") or {}
                    ):
                        quantity *= route["length_m"]
                    boq_items.append(
                        _boq_line(
                            assembly_type,
                            mat["material_name"],
                            quantity,
                            route.get("confidence_status", "MEASURED"),
                            route.get("source_path_ids", []),
                            db,
                            source_quality=source_quality,
                            derivation=mat.get("derivation"),
                            size_source=size_source,
                        )
                    )

            # Component BOQ: one assembly instance per counted symbol
            # Enforce strict 1-to-1 layer-to-assembly matching (Phase 2 rule).
            for comp in components:
                resolved_type = comp.get("assembly_type")

                # Sized route assemblies are quantified by the ROUTE loop
                # (formula needs per-route size variables); a duct/pipe
                # cluster surfacing here is geometry, not a countable symbol.
                if resolved_type in SIZED_ASSEMBLIES:
                    continue

                rule = load_assembly_rule(resolved_type)
                if rule is None or resolved_type != rule.get("name", resolved_type):
                    # STRICT SKIP: never apply an unrelated rule to a component
                    continue

                applied = apply_assembly(resolved_type)
                for mat in applied.get("materials", []):
                    quantity = mat["quantity"] * comp["count"]
                    boq_items.append(
                        _boq_line(
                            resolved_type,
                            mat["material_name"],
                            quantity,
                            comp.get("confidence_status", "MEASURED"),
                            comp.get("source_path_ids", []),
                            db,
                            source_quality=source_quality,
                            derivation=mat.get("derivation"),
                            size_source=None,
                        )
                    )

            # Optional A1 persistence slice (default-off): project the
            # measured geometry into a SheetExtraction and write it through
            # the persistence spine inside this same session.
            estimate_id: uuid.UUID | None = None
            if persist:
                filename = file.filename or ""
                sheet_name = os.path.splitext(filename)[0] or None
                extraction = _build_sheet_extraction(
                    sheet_name=sheet_name,
                    scale=scale,
                    source_quality=source_quality,
                    routes=routes,
                    route_sizes=route_sizes,
                    components=components,
                )
                estimate_id = persist_extraction(db, project_id, extraction)

        response: Dict[str, Any] = {
            "status": "ok",
            "scale": scale,
            "routes_measured": len(routes),
            "components_found": len(components),
            "boq_items": boq_items,
        }
        if persist and estimate_id is not None:
            response["estimate_id"] = str(estimate_id)
        return response

    finally:
        # Clean up the temporary PDF file – runs even if we returned early.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass