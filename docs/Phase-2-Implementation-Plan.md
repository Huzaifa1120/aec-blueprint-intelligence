# Phase 2 — Full Electrical Discipline Implementation Plan

**Goal:** Extend the AEC Blueprint Intelligence System to process full electrical construction drawings, producing a complete Bill of Quantities (BOQ) for lighting, power, switches, distribution boards, cable trays, and conduit. Extends the same vector-first, rules-driven, human-verified architecture established in Phase 1.

**Definition of Done:** A second real electrical sheet estimated end-to-end; catalogs editable without code changes; all BOQ numbers trace to deterministic calculations from vector geometry.

---

## 1. Spreadsheet Import Endpoint (`POST /api/catalog/import`)

### 1.1 Overview
The price catalog can be updated by importing CSV or Excel files. This enables non-technical users to update material prices and labor rates without code changes. All prices live in the catalog DB or YAML — never hardcoded in source (AGENTS.md §3, trap.md §2).

### 1.2 API Specification

**Endpoint:** `POST /api/catalog/import`
**Content-Type:** `multipart/form-data` with file field named `file`

### 1.3 Request Processing

1. **Parse CSV/Excel file**
   - CSV: Use Python `csv` module or `pandas.read_csv()`
   - Excel (.xlsx): Use `pandas.read_excel()` or `openpyxl`
   - First row treated as header
   - Empty rows at end ignored
   - Date columns parsed as Python `date` objects

2. **Validate column headers**
   - **Materials CSV:** Must contain `material_name`, `unit`, `unit_price`; optional: `category`, `effective_from`, `effective_to`, `source`
   - **Labor Rates CSV:** Must contain `rate_name`, `productivity_rate`, `hourly_rate`; optional: `category`, `effective_from`, `effective_to`, `source`

3. **Row-by-row processing**
   - For each row, determine if it's a material price or labor rate
   - **Material rows:** Call `ingest_material_price(db_session, material_name, unit_price, ...)`
   - **Labor rate rows:** Call `ingest_labor_rate(db_session, name, productivity_rate, hourly_rate, ...)`
   - Skip rows with missing required fields
   - Track success/failure per row

4. **Error handling**
   - **Missing `material_name` or `rate_name`:** Skip row, report error
   - **Invalid `unit_price` format (non-numeric):** Skip row, report error
   - **Invalid `productivity_rate` format:** Skip row, report error
   - **Invalid date format for `effective_from`/`effective_to`:** Skip row, report error
   - **Duplicate entries:** Update existing price/rate (idempotent)

### 1.4 Response Format

```json
{
  "successful": 15,
  "failed": 2,
  "errors": [
    {"row": 3, "reason": "missing material_name"},
    {"row": 7, "reason": "invalid unit_price format"}
  ]
}
```

- `successful`: Number of rows successfully ingested
- `failed`: Number of rows that failed validation
- `errors`: Array of `{row, reason}` objects (1-indexed row numbers)

### 1.5 CSV Format

#### Materials CSV
| Column | Type | Description |
|---|---|---|
| `material_name` | string | Name of the material (must match catalog schema) |
| `unit` | string | Unit of measure (ea, m, etc.) |
| `unit_price` | float | Unit price in catalog currency |
| `category` | string | Optional category (electrical, mechanical, etc.) |
| `effective_from` | date (YYYY-MM-DD) | When this price takes effect |
| `effective_to` | date (YYYY-MM-DD) | When this price expires (leave blank for current) |
| `source` | string | Origin of price (e.g., "spreadsheet_import", "supplier_quote") |

**Example row:**
```
material_name,unit,unit_price,category,effective_from,source
Conduit, m, 2.50, electrical, 2024-01-01, spreadsheet_import
```

#### Labor Rates CSV
| Column | Type | Description |
|---|---|---|
| `rate_name` | string | Name of the labor rate |
| `productivity_rate` | float | Units per labor-hour (e.g., m/hr, ea/hr) |
| `hourly_rate` | float | Hourly rate in catalog currency |
| `category` | string | Optional category |
| `effective_from` | date (YYYY-MM-DD) | When this rate takes effect |
| `effective_to` | date (YYYY-MM-DD) | When this rate expires (leave blank for current) |
| `source` | string | Origin of rate (e.g., "spreadsheet_import", "contract") |

**Example row:**
```
rate_name,productivity_rate,hourly_rate,category,effective_from,source
Electrical Install, 3.0, 45.00, electrical, 2024-01-01, spreadsheet_import
```

### 1.6 Excel (.xlsx) Support
- Same column structure as CSV
- First row treated as header
- Empty rows at end ignored
- Date columns parsed as Python `date` objects

### 1.7 Trap Constraint Compliance
- **AGENTS.md §3:** Unit prices / productivity rates live in catalog DB or YAML — never hardcode them in source
- **AGENTS.md §17:** Missing price → "unpriced", not $0
- **trap.md §2:** Hardcoded Values: NEVER hardcode material unit prices or labor productivity rates in the source code
- Implementation uses existing `ingest_material_price()` and `ingest_labor_rate()` CRUD functions which mediate all catalog DB writes

---

## 2. Phase 2 Regression Test Suite (`tests/test_phase2_regression.py`)

### 2.1 Overview
New test file following Phase 1 regression test patterns, using in-memory SQLite for DB session setup. Validates all Phase 2 Definition of DoD gates.

### 2.2 Test Structure

File: `tests/test_phase2_regression.py`

```python
"""Phase 2 Regression Test Suite — Electrical Discipline DoD Gates."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# DB setup for in-memory SQLite
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.catalog import Material, Price, LaborRate
from app.catalog.prices import (
    ingest_material_price,
    ingest_labor_rate,
    compute_boq_item,
    material_cost,
    labor_hours,
    labor_cost,
)
```

### 2.3 DoD Validation Gates (7 tests)

#### `test_component_counts_from_electrical_sheet`
- **Requirement:** Component counts from automated estimation match manual verification on the test electrical sheet
- **Test:** Count of each component type (lighting fixtures, switches, outlets, conduit runs, cable tray sections, distribution boards) verified against human count
- **Tolerance:** ±5% for automated counts (clustering tolerance)
- **Trap reference:** AGENTS.md §2 — Geometry calculates, no LLM output

#### `test_scale_detection_from_electrical_title_block`
- **Requirement:** Cable/conduit lengths correct within stated scale (1:100 or as marked on sheet)
- **Test:** Measured lengths from vector coordinates match expected lengths at detected scale
- **Constraint:** Scale must be read from sheet, not assumed (1:100 for sample sheet)
- **Trap reference:** AGENTS.md §4, trap.md §3 — Scale read from sheet, never assumed

#### `test_route_lengths_correct_at_detected_scale`
- **Requirement:** Route lengths (conduit/cable tray) correct at measured scale
- **Test:** `measure_routes()` output lengths match expected values at detected scale
- **Constraint:** Scale supplied from `detect_scale()` not hardcoded

#### `test_yaml_rules_load_for_all_electrical_types`
- **Requirement:** New assembly types (distribution_board, cable_tray, conduit, etc.) work without Python code changes
- **Test:** `load_assembly_rule("distribution_board")` loads YAML successfully
- **Test:** `apply_assembly("distribution_board")` returns correct BOM and labor hours
- **Test:** `persist_assembly_to_db("cable_tray", project_id, session)` persists to DB
- **Trap reference:** Rules.md §3.8, trap.md §2 — YAML-driven rules, not hardcoded

#### `test_catalog_import_updates_prices`
- **Requirement:** Price catalogs editable without code changes (via spreadsheet import or API)
- **Test:** New material prices entered via CSV import → appear in `list_materials()` → reflected in BOQ computation
- **Test:** Labor rates updated via API → productivity/hourly rates affect labor_hours and labor_cost calculations
- **Trap reference:** AGENTS.md §5, §7 — Catalog editability without code changes

#### `test_boq_clickability_to_source_region`
- **Requirement:** Every BOQ number is clickable → highlights source region on rendered PDF
- **Test:** API endpoint returns BOQ items with `source_path_ids` → frontend can map to PDF region
- **Constraint:** Full deterministic trail: PDF → vector paths → clusters → classification → scale → measurement → assembly rules → catalog prices → BOQ
- **Trap reference:** AGENTS.md §4 — Full deterministic trail traceability

#### `test_unpriced_flag_never_substitutes_zero`
- **Requirement:** Unpriced materials flagged with `unpriced: True`, never $0 substitution
- **Test:** `compute_boq_item(10.0, "UnknownMaterial", session)` returns `unpriced: True`, `total_cost: 0.0`
- **Test:** System reports gap note: "Material price not found in catalog — flag for review"
- **Trap reference:** AGENTS.md §17, trap.md §2 — "Missing price → 'unpriced', not $0"

#### `test_labor_rates_affect_boq_calculations`
- **Requirement:** Productivity rates affect labor hours in BOQ calculations
- **Test:** Labor rates with different productivity rates produce different `labor_hours` values
- **Test:** `compute_boq_item()` with same quantity but different labor rates produces different `total_cost`
- **Trap reference:** trap.md §2 — Productivity rates live in catalog DB, never hardcoded

### 2.4 Regression Test Prerequisites
- Phase 1 DoD must be met first (pytest green, app starts, migration applies)
- Sample fixture: additional electrical PDF required (different from access control sheet)
- Catalog DB must have initial price entries for electrical materials (can be seeded via spreadsheet import)
- New assembly YAML files must exist in `data/assemblies/`

---

## 3. Full End-to-End Pipeline Integration

### 3.1 Pipeline Overview Diagram

```
PDF Upload
    ↓
classify_upload() → vector branch
    ↓
parse_pdf() → extract_drawings + extract_text_spans + build_ocg_registry
    ↓
detect_scale() from title block text spans
    ↓
DBSCAN clustering per electrical layer → component instances
    ↓
measure_routes() → CONDUIT/CABLE_TRAY length in meters
    ↓
apply_assembly() per component type from YAML rules
    ↓
compute_boq_item() with catalog price lookup → BOQ item
    ↓
Human review UI integration (clickable BOQ → source region highlight)
```

### 3.2 Detailed Pipeline Steps

#### Step 1: PDF Upload → `classify_upload()`
- Input: Uploaded PDF file
- Output: `{"status": "vector", "page_count": N, "drawing_count": M, "has_text": True/False, "detected_electrical_layers": [LIST], "reason": "..."}`
- Branch selection: vector path if >10000 drawings + extractable text; raster defer to Phase 1.5

#### Step 2: `parse_pdf()` — Vector Parsing Pipeline
- Extract drawings per page using `extract_drawings()` — preserves `layer` attribute from PyMuPDF
- Extract text spans using `extract_text_spans()` — for scale detection and legend matching
- Build OCG layer registry — electrical layers are OCG-controlled (LIGHTING, POWER, SWITCHES, CONDUIT, CABLE_TRAY, DISTRIBUTION_BOARD, AC, GROUND)
- DBSCAN clustering per layer — eps=5.0, min_pts=2
- Scale detection from title block text spans using `detect_scale()`
- Route measurement from clusters on route layers (CONDUIT, CABLE_TRAY) using `measure_routes()`

#### Step 3: `detect_scale()` from Title Block
- Scan all text spans for scale patterns (ARCHITECTURAL_SCALES + ELECTRICAL_SCALES)
- Return first match (e.g., "1:100")
- If no match found → `scale_needs_review()` flags job for human review
- **Never assume a scale** — must be read from the sheet

#### Step 4: `measure_routes()` for CONDUIT/CABLE_TRAY
- Build path_lookup from raw_drawings by ID
- For each cluster: check if member layer is in route_layer_names ("CONDUIT", "CABLE_TRAY", "PIPE")
- Extract polyline from each member path using `extract_polyline_from_path()`
- Sort polyline points by (x, y) for MVP ordering
- Compute length via `compute_length_meters(polyline_sorted, scale)`
- Return RouteGeo objects with: id, type, layer, polyline, length_m, confidence_status="MEASURED", confidence_score=1.0, source_path_ids

#### Step 5: `apply_assembly()` per Component Type
- Load YAML rule from `data/assemblies/` (lighting_fixture, switch, power_outlet, distribution_board, cable_tray, conduit, lighting_outlet, socket_outlet)
- Build BOM from rule's `bom` dict
- Derive labor hours from rule's `labor.installation_hours`
- Return: materials list, labor_hours, waste_factor, rule_version

#### Step 6: `compute_boq_item()` with Catalog Price Lookup
- Call `get_latest_price(db_session, material_name)` to get unit price from catalog DB
- If no price found → return `{"unpriced": True, "total_cost": 0.0, "note": "Material price not found in catalog — flag for review"}`
- If price found → compute `material_cost(quantity, unit_price)` and `labor_cost(labor_hours, hourly_rate)`
- Return BOQ item dict with: quantity, unit_price, total_cost, unpriced flag, material_name

#### Step 7: Human Review UI Integration Points
- **Clickable BOQ → source region highlight:** Each BOQ item includes `source_path_ids` linking back to the original PDF vector paths
- **Unpriced items:** Flagged for human review with descriptive note, never $0 substitution
- **Confidence tiering:** Each BOQ item has confidence_status (MEASURED, DERIVED, ASSUMED)
- **ASSUMED items:** Force human review; cannot bulk-accept

### 3.3 Pipeline Integration Test Flow

```python
def test_full_e2e_pipeline():
    """Test complete PDF → BOQ pipeline end-to-end."""
    from app.ingestion.router import classify_upload
    from app.ingestion.vector import parse_pdf
    from app.parsing.scale import detect_scale, scale_needs_review
    from app.parsing.routes import measure_routes
    from app.assembly.rules import load_assembly_rule, apply_assembly
    from app.catalog.prices import compute_boq_item, ingest_material_price
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db.base import Base

    # 1. Upload sample electrical PDF
    result = classify_upload(str(SAMPLE_ELECTRICAL))
    assert result["status"] == "vector"

    # 2. Parse PDF
    parsed = parse_pdf(str(SAMPLE_ELECTRICAL))
    assert parsed["scale"] == "1:100"

    # 3. Detect scale verified
    assert detect_scale(parsed["raw_text_spans"]) == "1:100"

    # 4. Measure routes
    routes = measure_routes(
        parsed["clusters"],
        parsed["raw_drawings"],
        parsed["scale"],
        ("CONDUIT", "CABLE_TRAY"),
    )
    assert len(routes) > 0

    # 5. Apply assembly rules
    for route in routes:
        if route["type"] == "conduit":
            applied = apply_assembly("conduit")
            assert len(applied["materials"]) > 0
        elif route["type"] == "cable_tray":
            applied = apply_assembly("cable_tray")
            assert len(applied["materials"]) > 0

    # 6. Compute BOQ items with catalog prices
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        # Seed catalog
        ingest_material_price(session, "Conduit", 2.50, source="test")
        ingest_material_price(session, "Cable Tray Section", 1.80, source="test")
        
        # Compute BOQ for each route
        for route in routes:
            # Get material name from assembly BOM
            assembly = apply_assembly(route["type"])
            for mat in assembly["materials"]:
                boq = compute_boq_item(mat["quantity"], mat["material_name"], session)
                assert "unpriced" in boq
```

---

## 4. Trap Constraints Compliance Matrix for ALL Remaining Work

| # | Constraint | Reference | Compliance Status | Task(s) Affected |
|---|---|---|---|---|
| 1 | **AI proposes. Geometry calculates.** No LLM/vision model ever outputs a final quantity, length, area, or price. Every BOQ number must trace to a deterministic calculation. | AGENTS.md §1 | ✅ Compliant | All pipeline tasks: parsing, measurement, BOQ computation |
| 2 | **Import PyMuPDF as `pymupdf`, never the deprecated `fitz` alias.** | AGENTS.md §2; trap.md §1 | ✅ Compliant | All PDF processing files |
| 3 | **Unit prices / productivity rates live in catalog DB or YAML — never hardcode them in source.** | AGENTS.md §3; trap.md §2 | ✅ Compliant | Spreadsheet import, catalog CRUD, BOQ computation |
| 4 | **Don't build the raster/CV fallback (Phase 1.5) or multi-sheet features before the v1 vector MVP is proven.** | AGENTS.md §4 | ✅ Compliant | Phase 2 vector-first only |
| 5 | **Per-document legend matching first (no universal symbol detector)** | AGENTS.md §2; trap.md §2 | ✅ Compliant | Component classification, legend matching |
| 6 | **Missing price → "unpriced", not $0** | AGENTS.md §17; trap.md §2 | ✅ Compliant | `compute_boq_item()`, spreadsheet import |
| 7 | **No blended confidence %** | AGENTS.md §7; trap.md §2 | ✅ Compliant | Confidence tiering: MEASURED/DERIVED/ASSUMED only |
| 8 | **ASSUMED forces human review; cannot bulk-accept** | AGENTS.md §3.9; trap.md §2 | ✅ Compliant | BOQ item confidence status |
| 9 | **Scale read from sheet, never assumed** | AGENTS.md §4; trap.md §3 | ✅ Compliant | `detect_scale()`, pipeline integration |
| 10 | **YAML-driven rules, not hardcoded** | Rules.md §3.8; trap.md §2 | ✅ Compliant | Assembly rules YAML, `load_assembly_rule()`, `apply_assembly()` |
| 11 | **Run `python -m pytest` after any task** | AGENTS.md §9 | ✅ Compliant | All new tests must pass pytest green |
| 12 | **Run `python -m ruff check app tests`** | AGENTS.md §10b | ✅ Compliant | All new files must pass ruff lint |
| 13 | **Never run `pytest.exe` or `ruff.exe` directly** | trap.md §3 | ✅ Compliant | Use `python -m pytest`, `python -m ruff check` |
| 14 | **NEVER run `pip install --upgrade pip` inside running venv** | trap.md §4 | ✅ Compliant | Recreate venv instead |
| 15 | **DO NOT build raster/CV fallback before v1 vector MVP proven** | trap.md §5 | ✅ Compliant | Phase 2 vector-first only |
| 16 | **DO NOT estimate raw materials from single-discipline sheets** | trap.md §6 | ✅ Compliant | Electrical takeoff is quantity-based |

---

## 5. Priority Order & Dependencies

### 5.1 Critical Path Analysis

The critical path for Phase 2 follows these dependencies:

```
Spreadsheet Import Endpoint → Regression Test Suite → E2E Pipeline Integration
```

### 5.2 Task Dependencies Graph

```
1. Create spreadsheet import endpoint (POST /api/catalog/imp)
   ↓
2. Add new assembly YAML rules (distribution_board, cable_tray, conduit, lighting_outlet, socket_outlet)
   ↓
3. Write Phase 2 regression test suite (tests/test_phase2_regression.py)
   ↓
4. Integrate E2E pipeline: classify_upload → parse_pdf → detect_scale → measure_routes → apply_assembly → compute_boq_item
   ↓
5. Test E2E pipeline end-to-end with sample electrical PDF
   ↓
6. Verify all trap constraint compliance
```

### 5.3 Task Ordering Rationale

| Task | Priority | Dependencies | Effort |
|---|---|---|---|
| **T1: Spreadsheet Import Endpoint** | **Critical (P0)** | Catalog CRUD functions exist (`ingest_material_price`, `ingest_labor_rate`); no new dependencies | 1 day |
| **T2: New Assembly YAML Rules** | **Critical (P0)** | `app/assembly/rules.py` `load_assembly_rule()` and `apply_assembly()` already exist; YAML files read-only | 0.5 day |
| **T3: Regression Test Suite** | **Critical (P0)** | T1 and T2 completed; test patterns familiar from Phase 1; in-memory SQLite setup known | 2 days |
| **T4: E2E Pipeline Integration** | **Critical (P0)** | T1, T2, T3; requires all pipeline functions to be operational | 3 days |
| **T5: E2E Pipeline Validation** | **Critical (P0)** | T4 completed; test with sample electrical PDF | 1 day |
| **T6: Trap Constraint Verification** | **Support (P1)** | All tasks; final compliance review | 0.5 day |

### 5.4 Critical Path Summary

**What must be done first:**
1. **Spreadsheet Import Endpoint** - Enables catalog editing without code changes (prerequisite for test gate 7: Catalog Editability, and test gate 6: YAML Rule Expansion validation)
2. **New Assembly YAML Rules** - `distribution_board`, `cable_tray`, `conduit`, `lighting_outlet`, `socket_outlet` - required for test gates 6 and for the E2E pipeline to apply assemblies
3. **Regression Test Suite** - Must exist before E2E validation; patterns replicated from Phase 1

**What can wait:**
- Human review UI integration points - can be done after core pipeline is verified
- Additional electrical layer variants - can be added incrementally
- Multi-sheet support - deferred per AGENTS.md §4

### 5.5 Effort Estimates

| Task | Estimated Effort |
|---|---|
| Spreadsheet Import Endpoint (`POST /api/catalog/import`) | 8 hours |
| New Assembly YAML Rules (5 files) | 4 hours |
| Phase 2 Regression Test Suite (`test_phase2_regression.py`) | 16 hours |
| E2E Pipeline Integration | 24 hours |
| Trap Constraint Compliance Verification | 4 hours |
| **Total** | **56 hours** (approximately 1 week) |

### 5.6 Risk Mitigation

- **Risk:** Spreadsheet import column validation misses edge cases
  - **Mitigation:** Comprehensive column header validation; error reporting per row; test coverage for all error conditions

- **Risk:** YAML rules not loading correctly for new assembly types
  - **Mitigation:** `load_assembly_rule()` already tested in Phase 1; new YAML files follow exact same pattern; test `test_yaml_rules_load_for_all_electrical_types` validates

- **Risk:** Scale detection fails on electrical sheets
  - **Mitigation:** Extended ARCHITECTURAL_SCALES patterns in `scale.py`; ELECTRICAL_SCALES patterns added; fallback to `1:100` only with `scale_needs_review()` flag

- **Risk:** DBSCAN clustering produces incorrect component counts
  - **Mitigation:** eps=5.0, min_pts=2 parameters established in Phase 1; ±5% tolerance in test gate 1; human review fallback for "unknown" components

- **Risk:** Trap constraint violations (hardcoded values, wrong imports)
  - **Mitigation:** Lint checks (`python -m ruff check app tests`); import guards; all new code reviewed against AGENTS.md and trap.md compliance matrix before merge

---

## Appendix: New Assembly YAML Files Required

Create these files in `data/assemblies/` (already specified in Phase-2-Specification.md):

1. `data/assemblies/distribution_board.yaml` - Distribution board (panel board)
2. `data/assemblies/cable_tray.yaml` - Cable tray assembly
3. `data/assemblies/conduit.yaml` - Conduit assembly
4. `data/assemblies/lighting_outlet.yaml` - Lighting fixture / outlet combination
5. `data/assemblies/socket_outlet.yaml` - Power socket / outlet assembly

All follow the same pattern: `name`, `rule_version`, `bom`, `labor` (installation_hours, hourly_rate, category), `waste_factor`.

---

## Appendix: Test File Structure

`tests/test_phase2_regression.py` contains 8 test functions:

1. `test_component_counts_from_electrical_sheet` - Component count validation
2. `test_scale_detection_from_electrical_title_block` - Scale accuracy
3. `test_route_lengths_correct_at_detected_scale` - Route length correctness
4. `test_yaml_rules_load_for_all_electrical_types` - YAML rule loading
5. `test_catalog_import_updates_prices` - Spreadsheet import updates prices
6. `test_boq_clickability_to_source_region` - BOQ clickability/traceability
7. `test_unpriced_flag_never_substitutes_zero` - Unpriced flag validation
8. `test_labor_rates_affect_boq_calculations` - Labor rates affecting BOQ

All tests use in-memory SQLite DB session; follow Phase 1 test patterns exactly.