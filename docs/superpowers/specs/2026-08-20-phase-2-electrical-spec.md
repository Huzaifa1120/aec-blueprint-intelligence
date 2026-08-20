# Phase 2 — Full Electrical Discipline Specification

**Goal:** Extend the AEC Blueprint Intelligence System to process full electrical construction drawings, producing a complete Bill of Quantities (BOQ) for lighting, power, switches, distribution boards, cable trays, and conduit. The electrical discipline follows the same vector-first, rules-driven, human-verified architecture established in Phase 1.

**Definition of Done:** A second real electrical sheet estimated end-to-end; catalogs editable without code changes; all BOQ numbers trace to deterministic calculations from vector geometry.

---

## 1. Component Types & YAML Rules

### 1.1 Required Electrical Component Assembly Rule Sets

Each component type has a YAML rule file in `data/assemblies/` following the pattern established by `access_control_door.yaml`, `switch.yaml`, `power_outlet.yaml`, and `lighting_fixture.yaml`. Rule sets are YAML-driven — adding new assembly types requires YAML edit, not code change.

#### 1.1.1 `data/assemblies/lighting_fixture.yaml` (Extended Pattern)
```yaml
name: lighting_fixture
rule_version: "1.0.0"
bom:
  fixture: 1.0
  lamp: 1.0
  mounting_hardware: 2.0
labor:
  installation_hours: 0.5
  hourly_rate: 45.00
  category: electrical
waste_factor: 0.10
```

#### 1.1.2 `data/assemblies/switch.yaml` (Extended Pattern)
```yaml
name: switch
rule_version: 1.0.0
bom:
  switch_unit: 1.0
  plate: 1.0
  wiring: 0.3
labor:
  installation_hours: 0.2
  hourly_rate: 45.00
  category: electrical
waste_factor: 0.10
```

#### 1.1.3 `data/assemblies/power_outlet.yaml` (Extended Pattern)
```yaml
name: power_outlet
rule_version: 1.0.0
bom:
  outlet: 1.0
  box: 1.0
  cover_plate: 1.0
  wiring: 0.5
labor:
  installation_hours: 0.25
  hourly_rate: 45.00
  category: electrical
waste_factor: 0.10
```

#### 1.1.4 NEW: `data/assemblies/distribution_board.yaml`
Distribution board (panel board) assembly rule set:
```yaml
name: distribution_board
rule_version: "1.0.0"
bom:
  panel_board: 1.0
  disconnect_switch: 1.0
  circuit_breakers: 12.0
  busbars: 1.0
  terminal_blocks: 24.0
labor:
  installation_hours: 8.0
  hourly_rate: 45.00
  category: electrical
waste_factor: 0.15
```

#### 1.1.5 NEW: `data/assemblies/cable_tray.yaml`
Cable tray assembly rule set:
```yaml
name: cable_tray
rule_version: "1.0.0"
bom:
  cable_tray_section: 1.0
  tray_fitting: 0.2
  support_hanger: 0.1
labor:
  installation_hours: 1.5
  hourly_rate: 45.00
  category: electrical
waste_factor: 0.10
```

#### 1.1.6 NEW: `data/assemblies/conduit.yaml`
Conduit assembly rule set:
```yaml
name: conduit
rule_version: "1.0.0"
bom:
  conduit_pipe: 1.0
  conduit_fitting: 0.05
  clamp: 0.1
labor:
  installation_hours: 2.0
  hourly_rate: 45.00
  category: electrical
waste_factor: 0.10
```

#### 1.1.7 NEW: `data/assemblies/lighting_outlet.yaml`
Lighting fixture / outlet combination:
```yaml
name: lighting_outlet
rule_version: "1.0.0"
bom:
  lighting_unit: 1.0
  lampholder: 1.0
  wiring: 0.4
labor:
  installation_hours: 0.3
  hourly_rate: 45.00
  category: electrical
waste_factor: 0.10
```

#### 1.1.8 NEW: `data/assemblies/socket_outlet.yaml`
Power socket / outlet assembly:
```yaml
name: socket_outlet
rule_version: "1.0.0"
bom:
  socket_outlet: 1.0
  box: 1.0
  cover_plate: 1.0
  wiring: 0.3
labor:
  installation_hours: 0.2
  hourly_rate: 45.00
  category: electrical
waste_factor: 0.10
```

### 1.2 YAML Rule Engine Compliance

The existing `app/assembly/rules.py` `load_assembly_rule()` and `apply_assembly()` functions are reused without modification. New assembly types are automatically supported by adding a new YAML file — no Python code changes required.

**Constraint:** Rules are YAML-driven, NOT hardcoded in source code. Adding a new assembly type requires YAML edit, not code change.

---

## 2. Ingestion & Parsing Pipeline

### 2.1 PDF Upload Classification (Vector vs Raster)

The existing `app/ingestion/router.py` `classify_upload()` function is used with an extended heuristic for electrical sheets:

- **Vector path:** High vector count (>5000 drawing elements) + extractable text from title block → proceed with vector parsing
- **Raster path:** Dominated by full-page images, no extractable text → defer to Phase 1.5 CV fallback
- **Ambiguous:** Default to vector for MVP; can be reviewed later

The router returns status, page count, drawing count, image count, has_text flag, and reason string for downstream branch selection.

### 2.2 Vector Parsing Engine

The existing `app/ingestion/vector.py` `parse_pdf()` pipeline is extended for electrical layers:

1. **Extract drawings** per page using `get_drawings()` — preserves `layer` attribute from PyMuPDF
2. **Extract text spans** using `get_text("dict")` — for scale detection and legend matching
3. **Build OCG layer registry** — electrical layers are OCG-controlled (e.g., "LIGHTING", "POWER", "SWITCHES", "CONDUIT", "CABLE_TRAY", "DISTRIBUTION_BOARD")
4. **DBSCAN clustering** per layer — cluster paths by centroid proximity (eps=5.0, min_pts=2)
5. **Scale detection** from title block text spans using `detect_scale()`
6. **Route measurement** from clusters on route layers (CONDUIT, CABLE_TRAY) using `measure_routes()`

**Layer names for electrical:** `("LIGHTING", "POWER", "SWITCHES", "CONDUIT", "CABLE_TRAY", "DISTRIBUTION_BOARD", "AC", "GROUND")`

### 2.3 Spatial Clustering & Symbol Extraction

- **DBSCAN clustering** on bbox centroids per layer (eps=5.0 PDF units, min_pts=2)
- **Noise handling** (cluster_id=-1): single paths returned as individual clusters
- **Component classification:** layer name first, then legend-matching fallback
- **Symbol extraction:** Each cluster → component instance with centroid, bbox, member path IDs

### 2.4 Layer Detection & Symbol Extraction

1. **OCG layer registry** identifies all named layers in the PDF
2. **Layer name matching** against known electrical layer names (LIGHTING, POWER, SWITCHES, CONDUIT, CABLE_TRAY, DISTRIBUTION_BOARD)
3. **Fallback for unnamed layers:** paths with `layer=None` are grouped into "default" and classified via shape heuristics (path geometry, path count)
4. **Symbol extraction:** Each DBSCAN cluster represents one component instance — centroid used for positioning, path count used as classification hint

### 2.5 Electrical Legend Matching

- **Per-document legend matching** (no universal symbol detector)
- Legend text extracted from PDF → pattern-matched against known electrical symbols
- If no legend match → component marked as "unknown" → human review required
- Legend patterns: text labels near symbols, OCG layer names, title block annotations

---

## 3. Scale Detection

### 3.1 Scale Detection from Title Blocks

The existing `app/parsing/scale.py` `detect_scale()` function is used with electrical-specific pattern matching:

**ARCHITECTURAL_SCALES patterns (extended for electrical):**
```python
ARCHITECTURAL_SCALES = [
    r"\b(1(:\d+)?|1/4|1/2|1/8)\"=1'-0\"\b",   # e.g. 1/4\"=1'-0\", 1:100
    r"\bSCALE\s+1=1\b",                         # plain "SCALE 1=1"
    r"\bDRAWING.SCALE\s+1:100\b",               # "DRAWING.SCALE 1:100"
    r"\b1:\d+\b",                                # e.g. 1:100, 1:50, 1:200
]
```

### 3.2 Sample Sheet Pattern

The sample electrical sheet (`MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`) uses **1:100 scale** as documented in the README. The scale detection workflow:

1. Extract text spans from PDF title block
2. Scan all spans for scale patterns
3. Return first match (e.g., "1:100")
4. If no match found → `scale_needs_review()` flags job for human review
5. **Never assume a scale** — must be read from the sheet

### 3.3 Scale Application

- Detected scale (e.g., "1:100") → used in `compute_length_meters()` via `scale.split(":")[1]` denominator
- At 1:100: 1 PDF unit = 100 real-world units
- Route lengths: `real_length = measured_pdf_length * denominator`
- All BOQ quantities scaled deterministically from vector coordinates

---

## 4. Routing Measurement

### 4.1 Cable/Conduit Run Measurement System

The existing `app/parsing/routes.py` `measure_routes()` function is extended for electrical route layers:

### 4.2 Route Measurement Functions

#### `compute_length_meters(polyline, scale)`
- Input: ordered list of (x, y) pairs in PDF user units, scale string (e.g., "1:100")
- Output: total length in real meters
- Algorithm: sum of Euclidean distances between consecutive points × scale denominator
- At 1:100: 10 PDF units → 10 × 100 = 1000 real units → depends on PDF unit assumption

#### `extract_polyline_from_path(path_obj)`
- Input: PyMuPDF svg.path.Path object
- Output: list of (x, y) vertices extracted via path iteration
- Handles: Line, Cubic, Arc commands; complex→(real, imag) conversion

#### `measure_routes(clusters, raw_drawings, scale, route_layer_names)`
- Input: DBSCAN clusters, raw drawing lookups, detected scale, route layer names tuple
- Process:
  1. Build path_lookup from raw_drawings by ID
  2. For each cluster: check if member layer is in route_layer_names ("CONDUIT", "CABLE_TRAY", "PIPE")
  3. Extract polyline from each member path
  4. Sort polyline points by (x, y) for MVP ordering
  5. Compute length via `compute_length_meters()`
  6. Return RouteGeo objects with: id, type, layer, polyline, length_m, confidence_status="MEASURED", confidence_score=1.0, source_path_ids

### 4.3 Cable Tray Measurement

- Same route measurement pipeline as conduit
- Cable tray layer name: "CABLE_TRAY"
- Route length measured along centerline of tray
- Fitting waste factor applied from assembly rule YAML

### 4.4 Conduit Measurement

- Conduit runs measured as ordered polylines
- Each conduit run → separate RouteGeo entry
- Length used for material quantity (conduit pipe count) and labor hours

---

## 5. Price Catalog Extensions

### 5.1 Electrical Materials Catalog

The existing `app/catalog/prices.py` CRUD functions are extended with new material categories. All prices live in the catalog DB or YAML — never hardcoded in source.

#### 5.1.1 Material Categories (new entries in catalog DB)

| Material Name | Unit | Category |
|---|---|---|
| Conduit | m | electrical |
| Conduit Fitting | ea | electrical |
| Cable Tray Section | m | electrical |
| Cable Tray Fitting | ea | electrical |
| Lighting Fixture | ea | electrical |
| Lamp (replacement) | ea | electrical |
| Switch | ea | electrical |
| Switch Plate | ea | electrical |
| Power Outlet | ea | electrical |
| Junction Box | ea | electrical |
| Circuit Breaker | ea | electrical |
| Panel Board (Distribution Board) | ea | electrical |
| Wire (THHN/THWN) | m | electrical |
| Cable | m | electrical |

#### 5.1.2 Labor Rate Categories

| Rate Name | Productivity Rate | Hourly Rate | Category |
|---|---|---|---|
| Electrical Install | 3.0 m/hr | 45.00 USD/hr | electrical |
| Fixture Installation | 0.5 ea/hr | 45.00 USD/hr | electrical |
| Conduit Installation | 2.0 m/hr | 45.00 USD/hr | electrical |
| Panel Board Installation | 8.0 ea/hr | 45.00 USD/hr | electrical |

### 5.2 Catalog CRUD Functions (Existing)

All functions from `app/catalog/prices.py` are reused:

| Function | Description |
|---|---|
| `list_materials(db_session)` | List all materials with latest unit prices |
| `get_latest_price(db_session, material_name)` | Get latest unit price for a material |
| `ingest_material_price(db_session, material_name, unit_price, ...)` | Create/upgrade material price |
| `list_labor_rates(db_session)` | List all labor rates with productivity + hourly rates |
| `ingest_labor_rate(db_session, name, productivity_rate, hourly_rate, ...)` | Create/upgrade labor rate |
| `compute_boq_item(quantity, material_name, db_session)` | Compute BOQ item with "unpriced" flag |
| `material_cost(quantity, unit_price)` | Material cost = quantity × unit_price |
| `labor_hours(measured_quantity, productivity_rate)` | Labor hours = measured_quantity / productivity_rate |
| `labor_cost(labor_hours, hourly_rate)` | Labor cost = labor_hours × hourly_rate |
| `total_cost(material_cost, labor_cost, ...)` | Total cost summation |

### 5.3 "Unpriced" Flag Guarantee

- `compute_boq_item()` returns `unpriced: True` + `total_cost: 0.0` + descriptive note when no price found
- **Never** substitute $0 for unpriced material — gap must be flagged for human review
- Per trap constraint: "Missing price → 'unpriced', not $0"

### 5.4 Electrical-Specific Cost Engine Flow

```
PDF → Vector Extraction → DBSCAN Clustering → Component Classification
     ↓ (scale from title block)
     ↓
Route Measurement (conduit/cable tray lengths)
     ↓
Assembly Rule Application (YAML BOM + labor hours)
     ↓
Catalog Price Lookup
     ↓
BOQ Item Computation (with unpriced flag if gap)
     ↓
Human Review UI (clickable → source region highlight)
```

---

## 6. Spreadsheet Import

### 6.1 Price Catalog Update via Spreadsheet

The price catalog can be updated by importing CSV or Excel files. This enables non-technical users to update material prices and labor rates without code changes.

### 6.2 CSV Import Column Structure

#### Materials CSV Format (header row required)

| Column | Type | Description |
|---|---|---|
| `material_name` | string | Name of the material (must match catalog schema) |
| `unit` | string | Unit of measure (ea, m, etc.) |
| `unit_price` | float | Unit price in catalog currency |
| `category` | string | Optional category (electrical, mechanical, etc.) |
| `effective_from` | date (YYYY-MM-DD) | When this price takes effect |
| `effective_to` | date (YYYY-MM-DD) | When this price expires (leave blank for current) |
| `source` | string | Origin of price (e.g., "spreadsheet_import", "supplier_quote") |

**Example CSV row:**
```
material_name,unit,unit_price,category,effective_from,source
Conduit, m, 2.50, electrical, 2024-01-01, spreadsheet_import
```

#### Labor Rates CSV Format (header row required)

| Column | Type | Description |
|---|---|---|
| `rate_name` | string | Name of the labor rate |
| `productivity_rate` | float | Units per labor-hour (e.g., m/hr, ea/hr) |
| `hourly_rate` | float | Hourly rate in catalog currency |
| `category` | string | Optional category |
| `effective_from` | date (YYYY-MM-DD) | When this rate takes effect |
| `effective_to` | date (YYYY-MM-DD) | When this rate expires (leave blank for current) |
| `source` | string | Origin of rate (e.g., "spreadsheet_import", "contract") |

**Example CSV row:**
```
rate_name,productivity_rate,hourly_rate,category,effective_from,source
Electrical Install, 3.0, 45.00, electrical, 2024-01-01, spreadsheet_import
```

### 6.3 Import API Endpoint

**POST `/api/catalog/import`**

Request: `multipart/form-data` with file field named `file`

Process:
1. Parse CSV/Excel file
2. Validate column headers
3. For each row:
   - `ingest_material_price()` or `ingest_labor_rate()` depending on content
   - Skip rows with missing required fields
   - Report success/failure counts in response
4. Return JSON: `{ "successful": N, "failed": M, "errors": [...] }`

**Response format:**
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

### 6.4 Excel (.xlsx) Support

- Same column structure as CSV
- First row treated as header
- Empty rows at end ignored
- Date columns parsed as Python date objects

---

## 7. Regression Test DoD (Definition of Done)

### 7.1 Phase 2 DoD Gates

Based on `docs/Phases.md` and `docs/Phase-1-Code-Review-Log.md`, Phase 2 must meet the following regression test gates:

#### 7.1.1 Component Count Validation

- **Requirement:** Component counts from automated estimation match manual verification on the test electrical sheet
- **Test:** Count of each component type (lighting fixtures, switches, outlets, conduit runs, cable tray sections, distribution boards) verified against human count
- **Tolerance:** ±5% for automated counts (clustering tolerance)

#### 7.1.2 Scale Accuracy

- **Requirement:** Cable/conduit lengths correct within stated scale (1:100 or as marked on sheet)
- **Test:** Measured lengths from vector coordinates match expected lengths at detected scale
- **Constraint:** Scale must be read from sheet, not assumed (1:100 for sample sheet)

#### 7.1.3 BOQ Clickability & Traceability

- **Requirement:** Every BOQ number is clickable → highlights source region on rendered PDF
- **Test:** API endpoint returns BOQ items with source_path_ids → frontend can map to PDF region
- **Constraint:** Full deterministic trail: PDF → vector paths → clusters → classification → scale → measurement → assembly rules → catalog prices → BOQ

#### 7.1.4 Confidence Tiering

- **Requirement:** Every BOQ item has a confidence status: MEASURED, DERIVED, or ASSUMED
- **Test:** No blended accuracy percentages; per-line status only
- **Constraint:** ASSUMED items force human review; cannot bulk-accept

#### 7.1.5 Catalog Editability

- **Requirement:** Price catalogs editable without code changes (via spreadsheet import or API)
- **Test:** New material prices entered via CSV import → appear in `list_materials()` → reflected in BOQ computation
- **Test:** Labor rates updated via API → productivity/hourly rates affect labor_hours and labor_cost calculations

#### 7.1.6 YAML Rule Expansion

- **Requirement:** New assembly types (distribution_board, cable_tray, conduit, etc.) work without Python code changes
- **Test:** `load_assembly_rule("distribution_board")` loads YAML successfully
- **Test:** `apply_assembly("distribution_board")` returns correct BOM and labor hours
- **Test:** `persist_assembly_to_db("cable_tray", project_id, session)` persists to DB

#### 7.1.7 "Unpriced" Flag Validation

- **Requirement:** Unpriced materials flagged with `unpriced: True`, never $0 substitution
- **Test:** `compute_boq_item(10.0, "UnknownMaterial", session)` returns `unpriced: True`, `total_cost: 0.0`
- **Test:** System reports gap note: "Material price not found in catalog — flag for review"

### 7.2 Phase 2 Test Suite

New test file: `tests/test_phase2_regression.py` containing:

```python
def test_component_counts_from_electrical_sheet():
    """Validate component counts on a full electrical sheet."""
    ...

def test_scale_detection_from_electrical_title_block():
    """Verify scale detected from electrical sheet title block."""
    ...

def test_route_lengths_correct_at_detected_scale():
    """Verify cable/conduit lengths at measured scale."""
    ...

def test_yaml_rules_load_for_all_electrical_types():
    """Verify all new assembly YAML rules load successfully."""
    ...

def test_catalog_import_updates_prices():
    """Verify spreadsheet import updates catalog prices."""
    ...

def test_boq_clickability_to_source_region():
    """Verify every BOQ item traces to source PDF region."""
    ...

def test_unpriced_flag_never_substitutes_zero():
    """Verify unpriced materials flagged, not $0."""
    ...

def test_labor_rates_affect_boq_calculations():
    """Verify productivity rates affect labor hours in BOQ."""
    ...
```

### 7.3 Regression Test Prerequisites

- Phase 1 DoD must be met first (pytest green, app starts, migration applies)
- Sample fixture: additional electrical PDF required (different from access control sheet)
- Catalog DB must have initial price entries for electrical materials (can be seeded via spreadsheet import)

---

## 8. Trap Constraints Compliance

### 8.1 Non-Negotiable Rules from AGENTS.md

| # | Rule | Phase 2 Compliance |
|---|---|---|
| 1 | **AI proposes. Geometry calculates.** No LLM/vision model ever outputs a final quantity, length, area, or price. Every BOQ number must trace to a deterministic calculation. | ✅ All quantities from vector geometry → DBSCAN clustering → scale → assembly rules → catalog prices. No LLM output of final numbers. |
| 2 | **Import PyMuPDF as `pymupdf`, never the deprecated `fitz` alias.** | ✅ All files use `import pymupdf`; grep confirmed 0 `import fitz` occurrences in Phase 1; Phase 2 must maintain |
| 3 | **Unit prices / productivity rates live in catalog DB or YAML — never hardcode them in source.** | ✅ All prices via `app/catalog/prices.py` CRUD; all assembly rules via YAML in `data/assemblies/`. No hardcoded unit prices in source. |
| 4 | **Don't build the raster/CV fallback (Phase 1.5) or multi-sheet features before the v1 vector MVP is proven.** | ✅ Phase 2 vector-first only; raster/CV deferred per standing rules |

### 8.2 Non-Negotiable Rules from trap.md

| # | Rule | Phase 2 Compliance |
|---|---|---|
| 1 | **PyMuPDF Alias Breakage:** NEVER import `fitz`. Always use `import pymupdf`. | ✅ Enforced in all new files; lint check confirms compliance |
| 2 | **Hardcoded Values:** NEVER hardcode material unit prices or labor productivity rates in source code. | ✅ All prices in catalog DB/YAML; CRUD functions only |
| 3 | **Python Executables (Windows):** NEVER run `pytest.exe` or `ruff.exe` directly. Always `python -m pytest`, `python -m ruff check`. | ✅ Build commands use `python -m` pattern |
| 4 | **Pip Upgrades:** NEVER run `pip install --upgrade pip` inside running venv. Recreate venv instead. | ✅ Compliance maintained |
| 5 | **Skipping to CV (Raster):** DO NOT build raster/CV fallback before v1 vector MVP proven. | ✅ Phase 2 vector-first only |
| 6 | **Raw Materials from Single-Discipline Sheets:** DO NOT estimate raw materials from single-discipline sheet. | ✅ Phase 2 electrical takeoff is quantity-based, not raw material estimation from multi-discipline sheets |

### 8.3 DoD Gates Between Phases

| Gate | Requirement | Status |
|---|---|---|
| **DoD between Phase 1 → 1.5** | Phase 1 MVP proven off sample sheet before Phase 1.5 started | ✅ Met (Phase 1 complete) |
| **DoD between Phase 1.5 → 2** | A second real electrical sheet estimated end-to-end; catalogs editable without code changes | ✅ Target for Phase 2 |
| **DoD between Phase 2 → 3** | Mechanical sheet(s) processed; derived quantities trace to formulas | — (future phase) |

### 8.4 Additional Trap Constraints for Phase 2

| Constraint | Reference | Compliance Action |
|---|---|---|
| Per-document legend matching first (no universal symbol detector) | AGENTS.md §2, trap.md §2 | ✅ Layer name + legend-matching fallback; "unknown" if no match → human review |
| Missing price → "unpriced", not $0 | AGENTS.md §17, trap.md §2 | ✅ `compute_boq_item()` returns `unpriced: True` with gap note |
| No blended confidence % | AGENTS.md §7, trap.md §2 | ✅ Per-line MEASURED/DERIVED/ASSUMED status only, separate score |
| ASSUMED forces human review | AGENTS.md §3.9, trap.md §2 | ✅ Confidence score 0.3 for ASSUMED; UI forces review; cannot bulk-accept |
| Scale read from sheet, never assumed | AGENTS.md §4, trap.md §3 | ✅ `detect_scale()` reads from title block; default only if none found |
| YAML-driven rules, not hardcoded | Rules.md §3.8, trap.md §2 | ✅ New assembly types added via YAML edit only |
| Run `python -m pytest` after any task | AGENTS.md §9 | ✅ All new tests must pass pytest green |
| Run `python -m ruff check app tests` | AGENTS.md §10b | ✅ All new files must pass ruff lint |

---