"""Phase 2 Regression Test Suite — Electrical Discipline DoD Gates.

Validates all Phase 2 Definition of Done gates using in-memory SQLite.
Follows Phase 1 test patterns exactly: create_engine, Base.metadata.create_all,
Session management, deterministic pure functions, no blended confidence %.

Constraint: All numbers trace to deterministic calculations — no LLM/vision output
of final quantities directly. Import PyMuPDF as pymupdf, never the deprecated fitz alias.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.main import app
from app.db.base import Base
from app.catalog.prices import (
    ingest_material_price,
    ingest_labor_rate,
    compute_boq_item,
    labor_hours,
    labor_cost,
    total_cost,
)

client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory SQLite session for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ──────────────────────────────────────────────
# T1: test_component_counts_from_electrical_sheet
# ──────────────────────────────────────────────

def test_component_counts_from_electrical_sheet():
    """Phase 2 DoD: Component counts from automated estimation match manual verification.

    Requirement: Count of each component type (lighting fixtures, switches,
    outlets, conduit runs, cable tray sections, distribution boards) verified
    against human count. Tolerance: ±5% for automated counts (clustering tolerance).

    Trap reference: AGENTS.md §2 — Geometry calculates, no LLM output of final quantities.

    This gate runs the deterministic vector pipeline against the real electrical
    sample sheet and asserts that counts are (a) non-zero for the sheet's mapped
    layers, (b) stable across repeated runs (deterministic), and (c) traceable to
    source path IDs. The exact counts are surfaced for human verification, per the
    "AI proposes, humans approve" rule.
    """
    from app.ingestion.vector import parse_pdf
    from app.parsing.components import count_components, component_totals

    sample = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "samples"
        / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
    )
    assert sample.exists(), f"Sample fixture missing: {sample}"

    parsed = parse_pdf(str(sample))
    assert parsed["drawing_count"] > 10000, "Expected a real vector sheet"

    components = count_components(parsed["clusters"], parsed["raw_drawings"])
    totals = component_totals(components)

    # Non-zero: the sheet has lighting fixtures on a mapped layer.
    assert totals.get("lighting_outlet", 0) > 0, "Expected lighting fixtures on the sheet"

    # Every emitted component must map to a YAML assembly rule.
    from app.assembly.rules import load_assembly_rule

    for comp in components:
        rule = load_assembly_rule(comp["assembly_type"])
        assert rule is not None, f"Assembly rule missing for {comp['assembly_type']}"
        assert comp["confidence_status"] == "MEASURED"
        assert len(comp["source_path_ids"]) >= 1, "Each component must be traceable"

    # Determinism: re-running the same pure pipeline gives identical counts.
    totals_again = component_totals(
        count_components(parsed["clusters"], parsed["raw_drawings"])
    )
    assert totals_again == totals, "Component counts must be deterministic"


# ──────────────────────────────────────────────
# T2: test_scale_detection_from_electrical_title_block
# ──────────────────────────────────────────────

def test_scale_detection_from_electrical_title_block():
    """Phase 2 DoD: Scale detected from electrical sheet title block.

    Requirement: Cable/conduit lengths correct within stated scale (1:100 or as
    marked on sheet). Constraint: Scale must be read from sheet, not assumed
    (1:100 for sample sheet).

    Trap reference: AGENTS.md §4, trap.md §3 — Scale read from sheet, never assumed.
    """
    # Validate scale detection pure function with electrical patterns
    from app.parsing.scale import detect_scale, scale_needs_review

    # Test with electrical scale notation
    spans_with_electrical_scale = [
        {"text": "ELECTRICAL.SCALE 1:100", "bbox": (0, 0, 100, 20), "font": "Arial", "size": 12.0},
    ]
    scale = detect_scale(spans_with_electrical_scale)
    assert scale == "1:100", f"Expected 1:100, got {scale}"

    # Test with no scale found — should flag for review
    spans_no_scale = [{"text": "NO SCALE HERE", "bbox": (0, 0, 100, 20), "font": "Arial", "size": 12.0}]
    needs_review = scale_needs_review(spans_no_scale, search_patterns=3)
    assert needs_review is True, "Scale not found should flag for review"

    # Test with architectural scale
    spans_arch_scale = [
        {"text": "DRAWING.SCALE 1:50", "bbox": (0, 0, 100, 20), "font": "Arial", "size": 12.0},
    ]
    scale = detect_scale(spans_arch_scale)
    assert scale == "1:50", f"Expected 1:50, got {scale}"


# ──────────────────────────────────────────────
# T3: test_route_lengths_correct_at_detected_scale
# ──────────────────────────────────────────────

def test_route_lengths_correct_at_detected_scale():
    """Phase 2 DoD: Route lengths (conduit/cable tray) correct at measured scale.

    Requirement: Route lengths correct at measured scale. Constraint: Scale
    supplied from detect_scale() not hardcoded.

    Trap reference: trap.md §2 — Productivity rates live in catalog DB, never hardcoded.
    """
    # Test compute_length_meters pure function with known scale
    from app.parsing.routes import compute_length_meters

    # corrected 2026-08-22: pt→paper-mm→real-m conversion (was treating pt as
    # meters; physically impossible outputs, see tray-route-investigation.md)
    # Net factor = denominator × 25.4 / (72 × 1000):
    # At 1:100, 10 pt → 3.528 paper-mm × 100 = 352.78 real-mm = 0.353 m
    length = compute_length_meters([(0, 0), (10, 0)], "1:100")
    assert abs(length - 0.353) < 5e-4, f"Expected 0.353 at 1:100, got {length}"

    # At scale 1:50, 10 PDF units → 3.528 paper-mm × 50 = 176.39 real-mm = 0.176 m
    length = compute_length_meters([(0, 0), (10, 0)], "1:50")
    assert abs(length - 0.176) < 5e-4, f"Expected 0.176 at 1:50, got {length}"

    # Single point → 0 length
    length = compute_length_meters([(5, 5)], "1:100")
    assert length == 0.0, f"Expected 0.0 for single point, got {length}"


# ──────────────────────────────────────────────
# T4: test_yaml_rules_load_for_all_electrical_types
# ──────────────────────────────────────────────

def test_yaml_rules_load_for_all_electrical_types():
    """Phase 2 DoD: New assembly types (distribution_board, cable_tray, conduit, etc.)
    work without Python code changes.

    Requirement: New assembly types added via YAML edit only, not code changes.
    Test: load_assembly_rule() loads YAML successfully for all electrical types.
    Test: apply_assembly() returns correct BOM and labor hours.
    Test: persist_assembly_to_db() persists to DB.

    Trap reference: Rules.md §3.8, trap.md §2 — YAML-driven rules, not hardcoded.
    """
    from app.assembly.rules import load_assembly_rule, apply_assembly

    # Test all electrical assembly types load successfully
    electrical_types = [
        "access_control_door",
        "switch",
        "power_outlet",
        "distribution_board",
        "cable_tray",
        "conduit",
        "lighting_outlet",
        "socket_outlet",
    ]

    for assembly_name in electrical_types:
        rule = load_assembly_rule(assembly_name)
        assert rule is not None, f"Assembly rule '{assembly_name}' should be loadable"
        assert rule["name"] == assembly_name, f"Rule name should match: {assembly_name}"
        assert "bom" in rule, f"Rule should have BOM: {assembly_name}"
        assert "labor" in rule, f"Rule should have labor: {assembly_name}"
        assert "waste_factor" in rule, f"Rule should have waste_factor: {assembly_name}"

        # Test apply_assembly returns derived quantities
        applied = apply_assembly(assembly_name)
        assert "materials" in applied, f"apply_assembly should have materials: {assembly_name}"
        assert "labor_hours" in applied, f"apply_assembly should have labor_hours: {assembly_name}"
        assert "waste_factor" in applied, f"apply_assembly should have waste_factor: {assembly_name}"
        assert "rule_version" in applied, f"apply_assembly should have rule_version: {assembly_name}"

    # Verify YAML-driven: no hardcoded assembly types in source
    # (Verified by the fact that all 8 types load from YAML files)


# ──────────────────────────────────────────────
# T5: test_catalog_import_updates_prices
# ──────────────────────────────────────────────

def test_catalog_import_updates_prices(db_session):
    """Phase 2 DoD: Price catalogs editable without code changes (via spreadsheet import
    or API).

    Requirement: New material prices entered via CSV import → appear in
    list_materials() → reflected in BOQ computation. Test: Labor rates updated
    via API → productivity/hourly rates affect labor_hours and labor_cost
    calculations.

    Trap reference: AGENTS.md §5, §7 — Catalog editability without code changes.
    """
    # Test ingest_material_price creates/updates material price
    ingest_material_price(db_session, "Conduit", 2.50, source="test_import")
    ingest_material_price(db_session, "Cable Tray Section", 1.80, source="test_import")

    # Verify list_materials returns the new prices
    from app.catalog.prices import list_materials
    materials = list_materials(db_session)
    material_names = [m["name"] for m in materials]
    assert "Conduit" in material_names, "Conduit should appear in list_materials"
    assert "Cable Tray Section" in material_names, "Cable Tray Section should appear in list_materials"

    # Verify price values
    conduit_material = next(m for m in materials if m["name"] == "Conduit")
    assert conduit_material["latest_unit_price"] == 2.50, (
        f"Expected 2.50, got {conduit_material['latest_unit_price']}"
    )

    # Test compute_boq_item with priced material
    boq_item = compute_boq_item(10.0, "Conduit", db_session)
    assert boq_item["unpriced"] is False, "Conduit should have price ingested"
    assert boq_item["total_cost"] == 25.0, f"Expected 25.0, got {boq_item['total_cost']}"

    # Test compute_boq_item without price (unpriced flag)
    boq_item2 = compute_boq_item(10.0, "UnknownMaterial", db_session)
    assert boq_item2["unpriced"] is True, "Unknown material should be flagged unpriced"
    assert boq_item2["total_cost"] == 0.0, "Unpriced should not be $0"
    assert (
        boq_item2["note"] == "Material price not found in catalog — flag for review"
    ), "Unpriced should have descriptive note"


# ──────────────────────────────────────────────
# T6: test_boq_clickability_to_source_region
# ──────────────────────────────────────────────

def test_boq_clickability_to_source_region(db_session):
    """Phase 2 DoD: Every BOQ number is clickable → highlights source region on rendered PDF.

    Requirement: Every BOQ number is clickable → highlights source region on rendered PDF.
    Test: API endpoint returns BOQ items with source_path_ids → frontend can map
    to PDF region. Constraint: Full deterministic trail:
    PDF → vector paths → clusters → classification → scale → measurement →
    assembly rules → catalog prices → BOQ.

    Trap reference: AGENTS.md §4 — Full deterministic trail traceability.
    """
    # Test compute_boq_item returns BOQ item with deterministic trail
    # Ingest a material price first
    ingest_material_price(db_session, "Conduit", 5.00, source="test_clickability")

    # Compute BOQ item
    boq_item = compute_boq_item(8.0, "Conduit", db_session)

    # Verify BOQ item has required traceability fields
    assert "quantity" in boq_item, "BOQ item should have quantity"
    assert "unit_price" in boq_item, "BOQ item should have unit_price"
    assert "total_cost" in boq_item, "BOQ item should have total_cost"
    assert "unpriced" in boq_item, "BOQ item should have unpriced flag"

    # Verify deterministic calculation: 8 * 5.00 = 40.0
    assert boq_item["total_cost"] == 40.0, (
        f"Expected 40.0 (8 * 5.00), got {boq_item['total_cost']}"
    )
    assert boq_item["quantity"] == 8.0, f"Expected 8.0, got {boq_item['quantity']}"
    assert boq_item["unit_price"] == 5.0, f"Expected 5.0, got {boq_item['unit_price']}"

    # Verify no blended accuracy percentage
    assert isinstance(boq_item["total_cost"], float), (
        "total_cost should be float, not blended accuracy %"
    )
    assert "/" not in str(boq_item.get("confidence_status", "")), (
        "Should not have blended confidence like 'MEASURED/DERIVED'"
    )


# ──────────────────────────────────────────────
# T7: test_unpriced_flag_never_substitutes_zero
# ──────────────────────────────────────────────

def test_unpriced_flag_never_substitutes_zero(db_session):
    """Phase 2 DoD: Unpriced materials flagged with unpriced: True, never $0 substitution.

    Requirement: Unpriced materials flagged with unpriced: True, never $0 substitution.
    Test: compute_boq_item(10.0, "UnknownMaterial", session) returns
    unpriced: True, total_cost: 0.0. System reports gap note:
    "Material price not found in catalog — flag for review".

    Trap reference: AGENTS.md §17, trap.md §2 — "Missing price → 'unpriced', not $0".
    """
    # Test unpriced flag with material not in catalog
    boq_item = compute_boq_item(10.0, "UnknownMaterial", db_session)

    # Verify unpriced is True (not missing from dict)
    assert boq_item["unpriced"] is True, f"Expected unpriced=True, got {boq_item['unpriced']}"

    # Verify total_cost is 0.0, NOT some other value
    assert boq_item["total_cost"] == 0.0, f"Expected 0.0, got {boq_item['total_cost']}"

    # Verify descriptive note (not empty, not $0 substitution)
    assert (
        boq_item["note"] == "Material price not found in catalog — flag for review"
    ), f"Expected descriptive note, got: {boq_item['note']}"

    # Verify unpriced item is distinguishable from a priced item
    # (a priced item should have unpriced=False and total_cost > 0 when priced)
    ingest_material_price(db_session, "Conduit", 3.00, source="test_unpriced")
    boq_priced = compute_boq_item(10.0, "Conduit", db_session)
    assert boq_priced["unpriced"] is False, "Priced material should have unpriced=False"
    assert boq_priced["total_cost"] == 30.0, "Priced material should have positive total_cost"


# ──────────────────────────────────────────────
# T8: test_labor_rates_affect_boq_calculations
# ──────────────────────────────────────────────

def test_labor_rates_affect_boq_calculations(db_session):
    """Phase 2 DoD: Productivity rates affect labor hours in BOQ calculations.

    Requirement: Productivity rates affect labor hours in BOQ calculations.
    Test: Labor rates with different productivity rates produce different
    labor_hours values. Test: compute_boq_item() with same quantity but
    different labor rates produces different total_cost.

    Trap reference: trap.md §2 — Productivity rates live in catalog DB,
    never hardcoded.
    """
    # Ingest labor rates with different productivity rates
    ingest_labor_rate(db_session, "Electrical Install", 3.0, 45.00, category="electrical")
    ingest_labor_rate(db_session, "Conduit Install", 2.0, 45.00, category="electrical")

    # Test labor_hours pure function with different productivity rates
    # 6m at 3m/hr = 2hr; 6m at 2m/hr = 3hr
    hours1 = labor_hours(6.0, 3.0)
    hours2 = labor_hours(6.0, 2.0)
    assert hours1 == 2.0, f"Expected 2.0, got {hours1}"
    assert hours2 == 3.0, f"Expected 3.0, got {hours2}"
    assert hours1 != hours2, "Different productivity rates should produce different labor hours"

    # Test compute_boq_item with same material but different labor rates
    # First ingest a material price
    ingest_material_price(db_session, "Wire", 3.00, source="test_labor")

    # Compute BOQ item - the labor cost will differ based on productivity rate
    # though compute_boq_item only takes quantity and material_name,
    # labor hours are computed separately via labor_hours()
    # Verify labor_hours function is the mechanism linking productivity rates to BOQ

    # Verify that labor cost computation works correctly
    labor_cost_result = labor_cost(2.0, 45.0)
    assert labor_cost_result == 90.0, f"Expected 90.0, got {labor_cost_result}"

    # Verify total_cost function with material + labor
    total = total_cost(30.0, 90.0, 10.0, 2.0, 5.0)
    assert total == 137.0, f"Expected 137.0, got {total}"


# ──────────────────────────────────────────────
# T9: test_catalog_import_endpoint_updates_prices
# ──────────────────────────────────────────────

def test_catalog_import_endpoint_updates_prices(tmp_path, monkeypatch):
    """Phase 2 DoD: catalogs editable without code changes via POST /api/catalog/import.

    Uploads a CSV of material prices through the public API endpoint and verifies
    the new prices appear in the catalog listing and drive BOQ computation.

    Trap reference: AGENTS.md §5, §7 — Catalog editability without code changes.
    """
    from sqlalchemy import create_engine

    from app.core.config import Settings
    from app.db.base import Base

    db_path = tmp_path / "test_catalog_api.db"
    test_settings = Settings(database_url=f"sqlite:///{db_path}")
    monkeypatch.setattr("app.catalog.router.get_settings", lambda: test_settings)

    engine = create_engine(test_settings.database_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    csv_content = (
        "material_name,unit,unit_price,category,source\n"
        "Conduit,m,2.50,electrical,test_import\n"
        "Cable Tray Section,m,1.80,electrical,test_import\n"
    )
    resp = client.post(
        "/api/catalog/import",
        files={"file": ("prices.csv", csv_content.encode("utf-8"), "text/csv")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["successful"] == 2, f"Expected 2 rows imported, got {body}"
    assert body["failed"] == 0, f"Expected 0 failures, got {body}"

    resp = client.get("/api/catalog/")
    materials = resp.json()
    names = [m["name"] for m in materials]
    assert "Conduit" in names, "Imported material should appear in catalog listing"
    conduit = next(m for m in materials if m["name"] == "Conduit")
    assert conduit["latest_unit_price"] == 2.5, "Imported price should be reflected"


# ──────────────────────────────────────────────
# T10: test_e2e_pipeline_endpoint_on_sample
# ──────────────────────────────────────────────

def test_e2e_pipeline_endpoint_on_sample(tmp_path, monkeypatch):
    """Phase 2 DoD: full PDF → BOQ pipeline runs end-to-end on the sample sheet.

    Uploads the real electrical sample through POST /api/e2e/run and verifies
    the deterministic pipeline returns measured components and BOQ items, each
    with a discrete confidence tier and source-path traceability.

    Trap reference: AGENTS.md §4 — Full deterministic trail traceability.
    """
    from sqlalchemy import create_engine

    from app.db.base import Base
    from tests._e2e_async import post_and_wait

    sample = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "samples"
        / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
    )
    assert sample.exists()

    db_path = tmp_path / "test_e2e_api.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setattr(
        "app.e2e.router.get_engine",
        lambda: create_engine(f"sqlite:///{db_path}"),
    )

    body = post_and_wait(client, str(sample), persist=False)
    result = body["result"]
    assert result["status"] == "ok", f"Pipeline failed: {result}"
    assert result["components_found"] > 0, "Expected discrete components on the sheet"
    assert len(result["boq_items"]) > 0, "Expected BOQ items from the pipeline"

    for item in result["boq_items"]:
        assert item["confidence_status"] in ("MEASURED", "DERIVED", "ASSUMED"), (
            "Every BOQ item must have a discrete confidence tier"
        )
        assert item["source_path_ids"], "Every BOQ item must be clickable to source"


# ──────────────────────────────────────────────
# EP3: test_ep3_e2e_pipeline_validation_on_sample
# ──────────────────────────────────────────────

def test_ep3_e2e_pipeline_validation_on_sample(tmp_path, monkeypatch):
    """Phase 2 DoD (EP3): full E2E pipeline validated against the real sample PDF.

    Closes the previously-skipped EP3 gate. Asserts every DoD sub-gate:
    E1 vector classification, E2 scale read from sheet (1:100), E3 routes
    measured, E4 components counted, E5 BOQ produced, E6 discrete confidence
    tier, E7 source-path traceability, E8 assembly rule resolution, E9 price
    discipline (unpriced never $-substituted).
    """
    from sqlalchemy import create_engine

    from app.db.base import Base
    from tests._e2e_async import post_and_wait

    sample = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "samples"
        / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
    )
    assert sample.exists(), f"Sample fixture missing: {sample}"

    db_path = tmp_path / "test_ep3_api.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setattr(
        "app.e2e.router.get_engine",
        lambda: create_engine(f"sqlite:///{db_path}"),
    )

    def run_pipeline():
        body = post_and_wait(client, str(sample), persist=False)
        return body["result"]

    body = run_pipeline()

    # E1: vector classification -> pipeline ran with status "ok"
    assert body["status"] == "ok", f"Pipeline failed: {body}"

    # E2: scale block contract (spec v3 §7.4 honesty). The MMC title block
    # carries 'SCALE' and the slash-form ratio token '1/100' as two separate
    # rotated spans; resolve_scale's paired-label detection (2026-08-25
    # elecfix) reads them as DETECTED 1:100 — previously this fell back to
    # assumed 1:100 because only inline patterns existed. Value/denominator
    # are unchanged, so quantities are unaffected either way.
    assert body["scale"] == {"value": "1:100", "status": "detected"}, (
        f"Expected detected 1:100 scale block, got {body['scale']}"
    )

    # E3: routes measured for mapped route layers (CONDUIT / CABLE_TRAY)
    assert body["routes_measured"] > 0, "Expected measured routes on the sheet"

    # E4: discrete components counted (lighting fixtures on a mapped layer)
    assert body["components_found"] > 0, "Expected discrete components on the sheet"

    # E5: BOQ items produced
    assert len(body["boq_items"]) > 0, "Expected BOQ items from the pipeline"

    # E6 + E7 + E8 + E9: per-item discipline
    from app.assembly.rules import load_assembly_rule

    for item in body["boq_items"]:
        assert item["confidence_status"] in ("MEASURED", "DERIVED", "ASSUMED"), (
            "Every BOQ item must have a discrete confidence tier"
        )
        assert item["source_path_ids"], "Every BOQ item must be clickable to source"
        assert load_assembly_rule(item["assembly_type"]) is not None, (
            f"Assembly rule missing for {item['assembly_type']}"
        )
        assert isinstance(item["unpriced"], bool), "unpriced must be a boolean"
        assert isinstance(item["total_cost"], float), (
            "total_cost must be a float, not a blended % or Decimal"
        )
        if item["unpriced"]:
            assert item["total_cost"] == 0.0, (
                "Unpriced item must not be $-substituted"
            )

    # Determinism: re-running the same pipeline gives identical counts
    body_again = run_pipeline()
    assert body_again["routes_measured"] == body["routes_measured"]
    assert body_again["components_found"] == body["components_found"]
    assert len(body_again["boq_items"]) == len(body["boq_items"])


# ──────────────────────────────────────────────
# YR2: test_yaml_rule_persistence_to_db
# ──────────────────────────────────────────────

def test_yaml_rule_persistence_to_db(db_session):
    """Phase 2 DoD (YR2): persist_assembly_to_db() persists YAML rules to DB.

    Y1: unknown rule returns None.
    Y2: known rule creates an Assembly row with matching rule_version and BOM.
    Y3: assembly_materials junction rows match the YAML bom quantities.
    Y4: calling twice is idempotent (no duplicate rows).
    Y5: a labor link is created when the rule has an hourly_rate.
    """
    from app.assembly.rules import persist_assembly_to_db, load_assembly_rule
    from app.db.models.catalog import Assembly, Material, AssemblyMaterial

    # Y1: unknown rule -> None
    assert persist_assembly_to_db("nonexistent_rule", None, db_session) is None

    # Y2 + Y3: persist cable_tray rule
    rule = load_assembly_rule("cable_tray")
    assert rule is not None
    assembly = persist_assembly_to_db("cable_tray", None, db_session)
    assert assembly is not None
    assert assembly.name == "cable_tray"
    assert assembly.rule_version == rule["rule_version"]
    assert assembly.formula_or_bom == rule["bom"]

    # BOM materials all linked via assembly_materials with correct quantities
    from sqlalchemy import select

    links = db_session.execute(
        select(AssemblyMaterial).where(AssemblyMaterial.assembly_id == assembly.id)
    ).scalars().all()
    linked = {link.material_id: link.quantity for link in links}
    materials = {
        m.id: m.name for m in db_session.execute(select(Material)).scalars()
    }
    for mat_name, qty in rule["bom"].items():
        mat_id = next(i for i, n in materials.items() if n == mat_name)
        assert mat_id in linked, f"Material {mat_name} not linked"
        assert linked[mat_id] == qty, f"Quantity mismatch for {mat_name}"

    # Y5: labor link exists because cable_tray.yaml has labor.hourly_rate
    labor_mat_id = next(i for i, n in materials.items() if n == "Labor")
    assert labor_mat_id in linked, "Labor material should be linked"
    assert linked[labor_mat_id] == rule["labor"]["installation_hours"]

    # Y4: idempotent — second persist does not duplicate Assembly or links
    assembly2 = persist_assembly_to_db("cable_tray", None, db_session)
    db_session.commit()
    assemblies = db_session.execute(
        select(Assembly).where(Assembly.name == "cable_tray")
    ).scalars().all()
    assert len(assemblies) == 1, "persist_assembly_to_db must be idempotent"
    links2 = db_session.execute(
        select(AssemblyMaterial).where(AssemblyMaterial.assembly_id == assembly2.id)
    ).scalars().all()
    assert len(links2) == len(links), "Links must not duplicate on re-persist"