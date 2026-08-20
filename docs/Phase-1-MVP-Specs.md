# Phase 1 — MVP: Access Control Takeoff Specifications

**Version:** 1.0.0  
**Based on:** `Phases.md` §1, `Architecture.md` §3, `Rules.md`  
**Definition of Done:** On the sample sheet (`MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`):
- Component count matches manual verification
- Cable/conduit lengths correct within stated scale (1:100)
- Every BOQ number clickable to its source region on the drawing
- Review accept/correct/reject actions persisted in DB
- All BOQ numbers have confidence status (`MEASURED`/`DERIVED`/`ASSUMED`)
- No LLM/vision model outputs a final quantity directly — all numbers trace to deterministic calculations
- Price catalog can be updated via API without code changes

---

## 1. Overview

Phase 1 implements the **Access Control Takeoff** MVP: upload one real PDF electrical sheet → accurate, traceable BOQ proven off one sheet. This is the whole point of the project.

**Architecture:** Hybrid, vector-first, rules-driven, human-verified.  
**Primary data source:** PyMuPDF vector extraction (not raster/CV).  
**Confidence model:** Per-line `MEASURED` / `DERIVED` / `ASSUMED` — never blended "%".

---

## 2. File Structure (Target State)

```
backend/
├── app/
│   ├── ingestion/          # NEW
│   │   ├── router.py        # PDF → vector/raster decision
│   │   ├── vector.py        # PyMuPDF extraction engine
│   │   └── classification.py # Layer-based component classification
│   ├── parsing/            # NEW (or within ingestion)
│   │   ├── scale.py         # Scale detection from title block/dimensions
│   │   └── routes.py        # Route measurement (cable trunk/conduit)
│   ├── assembly/           # EXISTING + extended
│   │   ├── rules.py         # YAML-driven rule engine
│   │   └── sync.py          # YAML → DB sync
│   ├── catalog/            # EXISTING + extended
│   │   ├── prices.py        # Price catalog CRUD API
│   │   └── labor_rates.py   # Productivity rate CRUD API
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   └── models/          # Extended: Measurement, BoqItem, Estimate relationships
│   └── main.py              # + new routers
├── data/
│   ├── assemblies/          # YAML rule sets
│   │   └── access_control_door.yaml
│   └── samples/             # Sample fixture (already present)
├── frontend/
│   └── app/
│       └── components/
│           └── ReviewOverlay/  # Human review UI (Canvas/SVG + pdf.js)
└── docs/
    └── Phase-1-MVP-Specs.md   ← this file
```

---

## 3. API Surface (v1 — Phase 1 additions)

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/ingestion/pdf` | Upload PDF → vector/raster decision → parse → store model |
| `GET` | `/api/v1/ingestion/status/{sheet_id}` | Parse job status (queued/parsing/done/error) |
| `GET` | `/api/v1/drawings/{id}/model` | Canonical drawing model (same as Architecture.md Fig flow) |
| `POST` | `/api/v1/review/accept` | Accept BOQ line → persist, mark `MEASURED` |
| `POST` | `/api/v1/review/correct` | Correct BOQ line → update value, log signal |
| `POST` | `/api/v1/review/reject` | Reject BOQ line → mark `needs_review` |
| `GET` | `/api/v1/catalogs/materials` | List materials with unit prices |
| `GET` | `/api/v1/catalogs/labor-rates` | List labor rates with productivity rates |
| `GET` | `/api/v1/assemblies` | List assembly rule sets and versions |

*Note: Existing endpoints from Phase 0 remain: `GET /`, `GET /health`, CORS, DB sessions.*

---

## 4. Core Implementation Tasks

### Task 1 — Ingestion Router (5-line check on upload)
**File:** `backend/app/ingestion/router.py`  
**Function:** `classify_upload(file_path: str) → dict`
- Check PyMuPDF extraction results:
  - If `page.get_drawings()` has high vector count + extractable text → **vector path**
  - If dominated by full-page raster images → **raster path** (deferred to Phase 1.5)
- Log decision for downstream branches
- Return: `{"status": "vector", "page_count": N, "layer_count": M}` or `{"status": "raster", "reason": "..."}`
**Trap constraints:** Must import `pymupdf` (not `fitz`); fail loudly if unparseable; never silently return zeros.

### Task 2 — Vector Parsing Engine (PyMuPDF extraction)
**File:** `backend/app/ingestion/vector.py`  
**Core functions:**
- `extract_drawings(page) → list[dict]`: `page.get_drawings()` (paths + `layer` attribute)
- `extract_text_spans(page) → list[dict]`: `page.get_text('dict')` (spans + bbox + font size)
- `build_ocg_registry(doc) → dict`: `doc.get_ocgs()` (layer registry)
- `cluster_paths(paths, layer, eps, min_pts) → list[dict]`: DBSCAN on bbox centroids
- `parse_pdf(pdf_path) → ParsedResult`: Full pipeline
**Integration:** Populate `Component`, `Route`, `Measurement` DB models.  
**Trap constraints:** `import pymupdf` only; no hardcoded scale; all geometry traceable to `get_drawings()` path IDs.

### Task 3 — Classification (Layer Name First, Legend Fallback)
**File:** `backend/app/ingestion/classification.py`  
**Function:** `classify_cluster(cluster, text_spans, layer_registry) → str`
- Primary: CAD layer name as classification signal (e.g., `AC-DOOR`, `AC-CARDREADER`)
- Fallback: Legend-matching when layer name ambiguous/missing
- Return: `{"type": "door", "method": "layer_name", "confidence": 0.95}` or `{"type": "unknown", "method": "legend_fallback", "confidence": 0.6}`
**Trap constraints:** Classification is **proposal only** — must be confirmed by rules engine or human review. Never output a "count" or "quantity" from classification alone.

### Task 4 — Scale Detection (Title-Block/Dimension)
**File:** `backend/app/parsing/scale.py` or `backend/app/ingestion/scale.py`  
**Function:** `detect_scale(text_spans, default="1:100") → str`
- Parse title block text for scale notation (e.g., "1:100")
- Detect scale bar in drawing geometry (optional)
- Cross-check dimension strings in text spans
- Store scale per sheet — never assume global default
- Return: `{"scale": "1:100", "method": "title_block", "confidence": 0.98}`
**Trap constraints:** **Critical:** Scale must be read from the sheet — never hardcoded or assumed. If scale cannot be determined → mark job `needs_review`; never fabricate a value.

### Task 5 — Route Measurement (Cable Trunk/Conduit Lengths)
**File:** `backend/app/parsing/routes.py` or within `vector.py`  
**Function:** `measure_routes(clusters, scale) → list[RouteGeo]`
- Identify route layer (e.g., `AC-CONDUIT`, `AC-CABLE`)
- Extract ordered polylines from vector paths
- Measure lengths using detected scale → real-world meters
- Track waste factor (e.g., 10% extra for bends/terminations) via assembly rules
- Output: `Route` objects with `length_m`, `route_type`, `confidence_status`
**Trap constraints:** Lengths must be deterministic calculations from real coordinates. No LLM/vision model outputs final length directly.

### Task 6 — Assembly Rules (YAML-Driven)
**File:** `data/assemblies/access_control_door.yaml` (NEW)  
**File:** `backend/app/assembly/rules.py` (NEW)  
**Rule set example:**
```yaml
name: access_control_door
rule_version: "1.0.0"
bom:
  card_reader: 1
  magnetic_lock: 1
  push_button: 1
  door_controller: 0.5
labor:
  installation_hours: 2.5
waste_factor: 0.10  # 10%
```
**Function:** `apply_assembly(comp_type, rule_version) → dict`
- Map component type to BOM → create `AssemblyMaterial` records
- Derive `labor_hours` from `labor.installation_hours`
- Record `rule_version` on every `Measurement`
**Trap constraints:** Rules are YAML-driven, not hardcoded — adding a new assembly type requires YAML edit, not code change. Every BOQ item must trace back through `measurements` table to its source geometry. Rule versions must be recorded for auditability.

### Task 7 — Price Entry / Cost Engine
**File:** `backend/app/catalog/prices.py` (extend existing)  
**File:** `backend/app/catalog/labor_rates.py` (extend existing)  
**Pure functions:**
- `material_cost = quantity * unit_price`
- `labor_hours = measured_quantity / productivity_rate` (rate from catalog, never hardcoded)
- `labor_cost = labor_hours * hourly_rate`
- `total = material_cost + labor_cost + equipment_cost + waste + contingency`
**Catalog CRUD APIs:**
- `GET /catalogs/materials`, `POST /catalogs/materials`
- `GET /catalogs/labor-rates`, `POST /catalogs/labor-rates`
- Missing price/productivity rate → BOQ line shows `"unpriced"` with gap flagged, **not** $0
**Trap constraints:** ❌ NEVER hardcode unit prices or productivity rates in source code. ✅ All prices/rates loaded from `Price` DB table or YAML catalog at runtime. ✅ A missing price → `"unpriced"` flag, not $0.

### Task 8 — Human Review UI (Overlay, Click-to-Highlight)
**File:** `frontend/src/components/ReviewOverlay/` (NEW — Next.js/React)  
**Features:**
- Canvas/SVG overlay + `pdf.js` rendering original drawing
- Every extracted quantity/component displayed as clickable overlay item
- Click BOQ line → highlight exact source geometry on drawing
- Accept / correct / reject per item; corrections logged as rule-improvement signal
- Bulk-accept for `MEASURED`; force review for `ASSUMED`
- Persist corrections to DB (measurement status updates)
**Trap constraints:** ❌ No LLM/vision model ever outputs a final quantity, length, area, or price. ✅ Human must accept/reject each number — system cannot auto-finalize. ✅ Corrections logged as training/rule-improvement signal for future rule refinement.

### Task 9 — Regression Test (Known Component Counts from Sample)
**File:** `tests/test_phase1_regression.py` (NEW)  
**Function of test:**
- Use sample fixture: `data/samples/MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`
- Verify: component count matches manual verification
- Verify: cable lengths correct within stated scale (1:100)
- Verify: every BOQ number clickable to source region
- Verify: review accept/correct/reject persisted in DB
- Verify: all confidence statuses are `MEASURED`/`DERIVED`/`ASSUMED`
**Trap constraints:** ❌ Critical: this is a regression test against known values — if counts are off, the pipeline has a bug, not a feature. ✅ All BOQ numbers must trace to deterministic calculations (Rules.md §1).

### Task 10 — Confidence Tiering (MEASURED/DERIVED/ASSUMED)
**Integration:** Every `Measurement` record has `confidence_status` field
- `MEASURED` — directly read from vector geometry (default)
- `DERIVED` — calculated via assembly rules or formulas from measured input
- `ASSUMED` — filled from default assumption, no source data (rare in MVP; forced review in human UI)
- Display confidence status per BOQ line, never a single blended "%"
**Trap constraints:** ❌ Never present a blended accuracy % — each line has a single status. ✅ `ASSUMED` values must be explicitly flagged and force-reviewed in the human UI (Rules.md §3.9). ✅ Confidence score (0–1) may accompany the status but is separate from the status itself.

---

## 5. Database Model Extensions (already partially present, need migration/fill)

| Table | New/Extended Fields | Purpose |
|---|---|---|
| `measurements` | `calculation_method` (String), `rule_version` (String) | Record how the value was derived |
| `boq_items` | None new (already exists) | Links `measurement → estimate` |
| `estimates` | None new (already exists) | Aggregates `boq_items` totals |
| `components` | None new (already exists) | `confidence_status` defaults to `"MEASURED"` |
| `routes` | None new (already exists) | `confidence_status` defaults to `"MEASURED"` |
| `sheets` | `scale` (String, nullable) | Store detected scale per sheet |
| `assemblies` | `rule_version` (String, already exists) | Which rule set produced derived quantities |

**Migration:** Alembic head already creates all tables (Phase 0 DoD). No new migration needed for core tables. May need to add `calculation_method` and `rule_version` to existing `measurements` table via new migration if DB already exists with old schema (check current `aec.db`).

---

## 6. YAML Rule Sets (data/assemblies/)

| File | Purpose |
|---|---|
| `data/assemblies/access_control_door.yaml` | Access control door assembly rule set (MVP) |
| Future: `data/assemblies/access_control_route.yaml` | Conduit/cable route assembly rules |

**Minimum MVP content (`access_control_door.yaml`):**
```yaml
name: access_control_door
rule_version: "1.0.0"
bom:
  card_reader: 1
  magnetic_lock: 1
  push_button: 1
  door_controller: 0.5
labor:
  installation_hours: 2.5
waste_factor: 0.10
```

---

## 7. Definition of Done for Phase 1 MVP

✅ **Component count** matches manual verification of the sample sheet  
✅ **Cable/conduit lengths** correct within stated scale (1:100)  
✅ **Every BOQ number** is clickable to its source region on the drawing  
✅ **Review accept/correct/reject** actions are persisted in DB  
✅ **All BOQ numbers** have confidence status of `MEASURED`, `DERIVED`, or `ASSUMED`  
✅ **No LLM/vision model** outputs a final quantity directly — all numbers trace to deterministic calculations  
✅ **Price catalog** can be updated via API without code changes  
✅ **`pytest`** green for all Phase 1 tests  
✅ **`ruff check`** passes on all new files  
✅ Alembic migration `head` creates all required tables  

---

## 8. Trap File Constraints (must observe)

| # | Constraint | Compliance |
|---|---|---|
| 1 | **No hardcoded values** — no unit prices, productivity rates, or Eps/MinPts in source code | All values from catalog DB or YAML config at runtime |
| 2 | **Must use `pymupdf` not `fitz`** — every import must be `import pymupdf` | Lint rule; `import fitz` causes CI failure |
| 3 | **AI proposes, geometry calculates** — classification/proposal only; quantities from deterministic geometry | Never output final quantity from LLM/vision guess |
| 4 | **Scale not assumed** — must be read from sheet (title block / scale bar / dimension string) | If scale unavailable → `needs_review`, never fabricate |
| 5 | **One sheet at a time** — MVP processes single PDF; multi-sheet is Phase 2+ | Do not build multi-sheet features before v1 MVP proven |
| 6 | **Missing price → "unpriced", not $0** — flag the gap, never substitute $0 | Rules.md §5.1 |
| 7 | **No blended confidence %** — per-line status only (`MEASURED`/`DERIVED`/`ASSUMED`) | Rules.md §7.1 |
| 8 | **Corrections logged as rule-improvement signal** — human review feeds future rules | Rules.md §3.9 |
| 9 | **Run `python -m pytest`** after any task — all tests must pass | Rules.md §6.1 |
| 10 | **Run `python -m ruff check app tests`** — lint must pass | Rules.md §6.1 |

---

## 9. Priority & Dependency Order

| Order | Task | Depends On | Effort |
|---|---|---|---|
| 1 | Ingestion router (classify upload) | None | Small |
| 2 | Vector parsing engine (extract drawings/text/OCG) | 1 | Medium |
| 3 | Scale detection (title block / dimensions) | 2 | Medium |
| 4 | Classification (layer name + legend fallback) | 2 | Medium |
| 5 | Route measurement (cable trunk/conduit lengths) | 2, 3, 4 | Medium |
| 6 | Assembly rules YAML + rule engine | 3, 4 | Medium |
| 7 | Price catalog CRUD + cost engine pure functions | 6 | Medium |
| 8 | Human review UI (overlay, click-to-highlight) | 1–7 (backend) | Large (frontend) |
| 9 | Regression test (sample fixture end-to-end) | 1–8 | Medium |
|10 | Confidence tiering (MEASURED/DERIVED/ASSUMED per line) | 2, 6, 7, 8 | Small |

---

*End of Phase 1 MVP Specifications.*