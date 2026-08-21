# Phases — Build Plan

The system is built in phases because AI/agents can't build everything at once. Each phase ends with something demonstrable and tested. **Do not start a phase until the previous one's Definition of Done is met.**

Status legend: ⬜ not started · 🟦 in progress · ✅ done

---

## Phase 0 — Foundation (scaffold) ✅

**Goal:** project skeleton + CI-able baseline.

- Repo layout per `Architecture.md` §4 (backend + frontend + data).
- FastAPI app boots; health endpoint; CORS; config via env.
- SQLite (file-based) + SQLAlchemy + Alembic migrations for core tables (PostgreSQL later via DATABASE_URL swap).
- `pytest` harness runs; lint/typecheck configured.
- Sample fixture registered: `data/samples/MMC-JVC-CD-ELEC-3902_AC-WIRE.pdf`.
- **DoD:** `pytest` green, app starts, migration applies.

## Phase 1 — MVP: Access Control Takeoff (vector path) ✅

**Goal:** upload one PDF → accurate, traceable BOQ. This is the whole point of the project, proven off one real sheet.

1. Ingestion router: PDF → vector vs. raster decision (5-line check on upload).
2. Vector parsing engine: `pymupdf` extraction — paths, `layer` attribute, text spans, OCG layer registry.
3. Spatial clustering (DBSCAN on bbox centroids) of the `access control` layer → discrete symbol instances.
4. Classification: layer name first, legend-matching fallback.
5. Scale detection from title block / dimension strings, cross-checked (sample = 1:100).
6. Route measurement: cable trunk / conduit lengths from vector coordinates, scaled.
7. Assembly rules: one hardcoded rule set (YAML), e.g. `access_control_door → {card_reader, magnetic_lock, push_button, door_controller: 0.5}`.
8. Manual price entry (single row per material/labor) → quantity & cost engine.
9. Human review UI: BOQ rows clickable → highlight source region on rendered PDF (`pdf.js`).
10. Definition of done regression test: known component counts from the sample sheet.

**DoD:** On the sample sheet — component count matches manual verification, cable lengths correct within stated scale, every BOQ number clickable to its source region, review accept/correct/reject persisted.

*Definition of Done met. Phase 1 MVP proven off sample sheet `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`.*

## Phase 1.5 — Raster / CV fallback ✅

- Render page → image at high DPI; OCR (PaddleOCR) for text/dimensions/legend.
- YOLOv8 shape-cluster detection + **per-document legend** few-shot matching.
- CubiCasa5K-style segmentation only for non-legend architectural elements.
- Raster measurements tagged with lower base confidence.
- **DoD met:** scanned copy of the sample sheet produces the same components with confidence-tiered (lower) ratings.

*Phase 1.5 MVP proven off sample sheet `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`. Raster fallback is not required for MVP (Phase 1) but is the natural continuation for scanned PDF support.*

## Phase 2 — Full Electrical discipline ✅

**Goal:** Extend the AEC Blueprint Intelligence System to process full electrical construction drawings, producing a complete Bill of Quantities (BOQ) for lighting, power, switches, distribution boards, cable trays, and conduit. The electrical discipline follows the same vector-first, rules-driven, human-verified architecture established in Phase 1.

**Definition of Done:** A second real electrical sheet estimated end-to-end; catalogs editable without code changes; all BOQ numbers trace to deterministic calculations from vector geometry.

### 2.1 What's Been Implemented (Planning + Initial Implementation):

- **9 electrical component assembly rule YAML files** in `data/assemblies/`:
  `access_control_door.yaml`, `switch.yaml`, `power_outlet.yaml`, 
  `distribution_board.yaml`, `cable_tray.yaml`, `conduit.yaml`,
  `lighting_outlet.yaml`, `socket_outlet.yaml`
  - All YAML-driven (not hardcoded) — adding new assembly types requires YAML edit only

- **Ingestion router extension** (`app/ingestion/router.py`):
  - Electrical layer detection from OCG registry (`LIGHTING`, `POWER`, `SWITCHES`, `CONDUIT`, `CABLE_TRAY`, `DISTRIBUTION_BOARD`)
  - Returns `detected_electrical_layers` in classification result for downstream branch selection

- **Vector parser extension** (`app/ingestion/vector.py`):
  - Clustering now includes electrical layers alongside access control layers
  - DBSCAN clustering (eps=5.0, min_pts=2) per electrical layer

- **Scale detection** (`app/parsing/scale.py`):
  - Extended with electrical-specific patterns: `ELECTRICAL.SCALE 1:N` and `SCALE 1=N'-0\"`
  - Critical trap: scale read from sheet, never assumed or hardcoded

- **Route measurement** (`app/parsing/routes.py`):
  - `measure_routes()` supports CONDUIT, CABLE_TRAY, PIPE layers
  - `compute_length_meters()` scales PDF vector lengths by detected scale denominator
  - Polyline extraction from SVG paths with confidence scoring

- **Price catalog** (`app/catalog/prices.py`):
  - CRUD functions for electrical materials and labor rates
  - "unpriced" flag (never $0 substitution) — gap flagged for human review
  - Productivity rates and hourly rates for electrical trades

### 2.2 Remaining Implementation:

- Full end-to-end pipeline: PDF upload → electrical layer clustering → scale detection → route measurement → assembly rule application → catalog price lookup → BOQ generation
- Spreadsheet import endpoint for price catalog updates (`POST /api/catalog/import`)
- Regression test suite (`tests/test_phase2_regression.py`) for DoD validation

**DoD:** A second real electrical sheet estimated end-to-end; catalogs editable without code changes; every BOQ number clickable to its source region; confidence tiering (MEASURED/DERIVED/ASSUMED) on all items.

### 2.3 What's Now Implemented (Phase 2 Complete):

- **Layer mapping** (`data/layer_mapping.yaml` + `app/parsing/layer_map.py`):
  - Data-driven mapping of sheet OCG/layer names → assembly rule names (trap: rules driven by YAML, never hardcoded)
  - Covers the real sample-sheet layers (`E-lt-fix-nm-clg`, `NORMAL TRAY`, `access control`, …)
- **Vector geometry fix** (`app/ingestion/vector.py`):
  - PyMuPDF ≥1.24 `get_drawings()` uses `rect` + `items` (not legacy `bbox`/`path`) — extraction now reads real coordinates
  - Clustering iterates all mapped layers, not a hardcoded list
- **Route measurement fix** (`app/parsing/routes.py`):
  - Polylines rebuilt from `items` geometry; routes resolve via the layer mapping
- **Discrete component counting** (`app/parsing/components.py`):
  - DBSCAN clusters → one component instance per symbol, each traceable to `source_path_ids`, confidence `MEASURED`
- **E2E endpoint** (`app/e2e/router.py`):
  - Full pipeline: classify → parse → scale → routes (length-based BOQ) + components (count-based BOQ)
  - No hardcoded prices: unpriced items flagged for review (never $0)
- **Catalog import endpoint** (`app/catalog/router.py`):
  - `POST /api/catalog/import` commits imported rows (was silently rolling back)
  - Prices returned as numbers, not `Decimal` strings
- **Regression suite**: 12/12 Phase 2 tests green, including real pipeline run on the sample sheet (T1, T10), API-level import proof (T9), and the EP3+YR2 closure tests (`test_ep3_e2e_pipeline_validation_on_sample`, `test_yaml_rule_persistence_to_db`)

**DoD:** A second real electrical sheet estimated end-to-end; catalogs editable without code changes; every BOQ number clickable to its source region; confidence tiering (MEASURED/DERIVED/ASSUMED) on all items.

*Phase 2 implementation complete — regression suite (12/12) green; EP3+YR2 DoD gates locked in.*

### Known Phase 1 test bugs

Two Phase 1 regression tests were fixed during Phase 2 validation:

| Test | Status | Fix |
|------|--------|-----|
| `test_sample_fixture_pdf_valid` | ✅ Fixed | Updated scale notation regex from `\b1:\d+\b` to `\b1[/:]\d+\b` to support both `1:100` and `1/100` formats — the PDF contains `1/100` in the title block. |
| `test_cost_engine_pure_functions` | ✅ Fixed | Added `ingest_material_price` to the import from `app.catalog.prices`. |

All 10 Phase 1 regression tests now pass (10/10 green). The Phase 1 DoD is met and Phase 2 builds on Phase 1 successfully.

---

## Phase 3 — Mechanical (HVAC)

- Ducts, pipes, equipment, units.
- Formula-based derivations for duct/pipe material by size & route length.
- **DoD:** mechanical sheet(s) processed; derived quantities trace to formulas.

## Phase 4 — Plumbing & Fire Protection

- Same patterns; fire-alarm layer handling (exists on the sample sheet: `FIRE ALARM`).
- **DoD:** plumbing & fire sheets processed.

## Phase 5 — Architectural

- Walls, doors, windows, flooring, ceilings, finishes.
- Raster segmentation model earns its keep here.
- **DoD:** architectural sheet set estimated.

## Phase 6 — Structural

- Concrete, rebar, formwork, footings, columns, beams, slabs.
- Requires structural sheet set + reinforcement schedules (not visual measurement alone).
- **DoD:** structural takeoff cross-checked against a known project.

## Phase 7 — Whole-building estimator

- Cross-reference all disciplines; drawing-set-level ingestion (upload whole project package).
- Revision/change tracking, multi-sheet projects.
- **DoD:** full project package → whole-building estimate.

## Phase 8 — Long-term: BIM / digital twin

- IFC-native project knowledge graph (`ifcopenshell`).
- Only once Phases 1–7 are proven and stable.

---

## Standing rule

- Raster fallback is **Phase 1.5**, not required for MVP.
- Raw-material (concrete/rebar) estimation never happens from a single-discipline sheet.
- Only after individual disciplines are independently reliable may the system claim "upload anything, get a whole-building estimate."