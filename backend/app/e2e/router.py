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

import os
import tempfile
from typing import List, Dict, Any

from fastapi import APIRouter, File, UploadFile
from sqlalchemy.orm import Session as OrmSession

from app.db.session import get_engine
from app.ingestion.router import classify_upload
from app.ingestion.vector import parse_pdf
from app.parsing.scale import detect_scale
from app.parsing.routes import measure_routes
from app.parsing.components import count_components
from app.parsing.layer_map import layer_to_assembly, route_layers
from app.assembly.rules import apply_assembly
from app.catalog.prices import compute_boq_item


router = APIRouter(prefix="/api/e2e", tags=["e2e"])


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
    }


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
) -> Dict[str, Any]:
    """Run the complete PDF → BOQ pipeline and return BOQ items."""

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

        # 3️⃣ Measure routes (length-based assemblies: cable tray, conduit)
        route_layer_names = tuple(route_layers())
        routes = measure_routes(clusters, raw_drawings, scale, route_layer_names)

        # 4️⃣ Count discrete components (symbol-based assemblies)
        components = count_components(clusters, raw_drawings)

        # 5️⃣ Apply assembly rules & compute BOQ
        boq_items: List[Dict[str, Any]] = []
        with OrmSession(get_engine()) as db:
            # Route BOQ: quantity scales with measured length
            # Routes must ONLY evaluate against route-based assembly rules
            # Strict filter: route geometries must only map to route-based assemblies
            # (cable_tray, conduit) and never to point-based assemblies (lighting, switches, etc.)
            for route in routes:
                layer = route.get("layer", "")
                resolved_assembly = layer_to_assembly(layer)
                # Use resolved layer assembly if available, fall back to route type
                assembly_type = resolved_assembly if resolved_assembly else route.get("type", "")
                # Enforce: routes must only use route-based assembly rules
                # Point-based assemblies (lighting, switch, socket, etc.) are strictly excluded
                if assembly_type not in {"cable_tray", "conduit"}:
                    continue
                applied = apply_assembly(assembly_type)
                for mat in applied.get("materials", []):
                    quantity = mat["quantity"] * route["length_m"]
                    boq_items.append(
                        _boq_line(
                            assembly_type,
                            mat["material_name"],
                            quantity,
                            route.get("confidence_status", "MEASURED"),
                            route.get("source_path_ids", []),
                            db,
                            source_quality=source_quality,
                        )
                    )

            # Component BOQ: one assembly instance per counted symbol
            # Enforce strict 1-to-1 layer-to-assembly matching
            # Before applying any rule, verify the component's resolved type
            # exactly matches the rule name. This prevents access_control_door
            # components from yielding lighting_outlet, cable_tray, or other
            # unrelated assemblies.
            for comp in components:
                resolved_type = comp.get("assembly_type")

                # Load available assembly rules from the rules engine
                from app.assembly.rules import load_assembly_rule as _load_rule
                rule = _load_rule(resolved_type)
                if rule is None or resolved_type != rule.get("name", resolved_type):
                    # STRICT SKIP: Do not apply lighting_outlet to access_control_door
                    continue

                assembly_type = resolved_type
                applied = apply_assembly(assembly_type)
                for mat in applied.get("materials", []):
                    quantity = mat["quantity"] * comp["count"]
                    boq_items.append(
                        _boq_line(
                            assembly_type,
                            mat["material_name"],
                            quantity,
                            comp.get("confidence_status", "MEASURED"),
                            comp.get("source_path_ids", []),
                            db,
                            source_quality=source_quality,
                        )
                    )

        return {
            "status": "ok",
            "scale": scale,
            "routes_measured": len(routes),
            "components_found": len(components),
            "boq_items": boq_items,
        }

    finally:
        # Clean up the temporary PDF file – runs even if we returned early.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass