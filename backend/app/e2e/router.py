"""E2E pipeline endpoint — PDF upload → BOQ.

Exposes ``POST /api/e2e/run`` which runs the full vector pipeline:

1. ``classify_upload`` → decides vector/raster
2. ``parse_pdf`` → extract drawings, text spans, build OCG registry
3. ``detect_scale`` → read scale from title block
4. ``measure_routes`` → CONDUIT / CABLE_TRAY lengths at detected scale
5. ``apply_assembly`` → per‑component BOM & labor hours from YAML rules
6. ``compute_boq_item`` → catalog price lookup, ``unpriced`` flag, total cost

Returns BOQ items with ``confidence_status`` (MEASURED/DERIVED/ASSUMED) and
``source_path_ids`` for frontend click‑through.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, File, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_engine, get_db, Session as OrmSession
from app.ingestion.router import classify_upload
from app.ingestion.vector import parse_pdf
from app.parsing.scale import detect_scale
from app.parsing.routes import measure_routes
from app.assembly.rules import load_assembly_rule, apply_assembly
from app.catalog.prices import compute_boq_item, ingest_material_price
from app.db.base import Base


router = APIRouter(prefix="/api/e2e", tags=["e2e"])


# ---------------------------------------------------------------------------
# Helper: seed a minimal catalog if none exists
# ---------------------------------------------------------------------------
def _seed_catalog(db: OrmSession) -> None:
    """Ensure at least one material price exists so BOQ computation does not
    always return *unpriced*.  This is purely for the integration demo; in
    production the catalog would be populated by the spreadsheet‑import
    endpoint."""
    from app.db.models.catalog import Material, Price
    mat = db.query(Material).first()
    if not mat:
        mat = Material(name="Conduit", unit="m", category="electrical")
        db.add(mat)
        db.commit()
    latest = db.query(Price).filter(Price.material_id == mat.id).order_by(
        Price.effective_from.desc()
    ).first()
    if not latest:
        latest = Price(material_id=mat.id, unit_price=2.50, currency="USD",
                       effective_from=None)
        db.add(latest)
        db.commit()


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

        # 3️⃣ Measure routes
        routes = measure_routes(
            parsed.get("clusters", []),
            parsed.get("raw_drawings", []),
            scale,
            ("CONDUIT", "CABLE_TRAY"),
        )

        # 4️⃣ Apply assembly rules & compute BOQ
        boq_items: List[Dict[str, Any]] = []
        with OrmSession(get_engine()) as db:
            _seed_catalog(db)
            for route in routes:
                assembly_type = route["type"]
                applied = apply_assembly(assembly_type)
                for mat in applied.get("materials", []):
                    boq = compute_boq_item(
                        mat["quantity"],
                        mat["material_name"],
                        db,
                    )
                    boq_items.append(
                        {
                            "type": assembly_type,
                            "material_name": mat["material_name"],
                            "quantity": mat["quantity"],
                            "unit_price": boq.get("unit_price"),
                            "total_cost": boq.get("total_cost"),
                            "unpriced": boq.get("unpriced", False),
                            "confidence_status": boq.get("confidence_status", "MEASURED"),
                            "source_path_ids": route.get("source_path_ids"),
                        }
                    )

        return {
            "status": "ok",
            "scale": scale,
            "routes_measured": len(routes),
            "boq_items": boq_items,
        }

    finally:
        # Clean up the temporary PDF file – runs even if we returned early.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass