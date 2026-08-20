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
) -> Dict[str, Any]:
    boq = compute_boq_item(quantity, material_name, db)
    return {
        "assembly_type": assembly_type,
        "material_name": material_name,
        "quantity": round(quantity, 3),
        "unit_price": boq.get("unit_price"),
        "total_cost": boq.get("total_cost"),
        "unpriced": boq.get("unpriced", False),
        "confidence_status": confidence_status,
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
            for route in routes:
                assembly_type = layer_to_assembly(route.get("layer")) or route["type"]
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
                        )
                    )

            # Component BOQ: one assembly instance per counted symbol
            for comp in components:
                assembly_type = comp["assembly_type"]
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