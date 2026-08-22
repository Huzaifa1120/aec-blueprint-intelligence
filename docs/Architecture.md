# Architecture — AEC Blueprint Intelligence System

**Status:** Approved direction, ready for implementation
**Source of truth:** `AEC-Blueprint-System-Design-Spec-v3.md` (supersedes v2 and the original spec)

---

## 1. Architecture decision

**Hybrid, vector-first, rules-driven, human-verified.**

Three-tier ingestion (BIM/CAD → vector PDF → raster image, in order of preference) feeding a single canonical drawing model, then a deterministic assembly/rules engine, then mandatory human review before any number is finalized.

**Revised framing (spec v3):** vector-first is the *preferred* path when available, not the *assumed default input*. Real-world CAD-to-PDF practice delivers flattened, layer-stripped files routinely; every upload passes the Input Quality Gate before pipeline selection (§3.1b).

Rejected alternatives:
- ❌ Pure CV/ML pipeline (image in → quantities out) — caps out on accuracy; fallback only.
- ❌ BIM/digital-twin-first — right long-term destination, too much scope before anything is proven.
- ❌ LLM-vision-only — no traceability, hallucinated quantities. Never.

## 2. End-to-end flow

```
                    INPUT
       ┌──────────────┼───────────────┐
       │               │               │
   CAD / BIM      Vector PDF      Raster image
   (IFC/DWG/DXF)  (AutoCAD export) (scan/photo)
       │               │               │
        └───────────────┼───────────────┘
                        ▼
                Ingestion Router
                        ▼
        Input Quality Gate (spec v3)
  (scores layer richness; flags degraded files;
   requests re-export when deployment allows)
          ┌─────────────┴─────────────┐
          ▼ (layer-rich)               ▼ (degraded / raster)
 Layer Registry & Domain         Raster / CV Fallback Engine
 Classifier                      ├─ Classical CV template match
          ▼                      │  (legend-based symbol counting)
  Vector Parsing Engine          ├─ Detectron2 region segmentation
  (distance-threshold            │  (walls/rooms — trained model)
   clustering, polygon           └─ Rotation-aware OCR
   reconstruction, route                  │
   tracing)                               │
          ▼                               │
  Text–Layer Association Walker           │
          ▼                               │
  Legend & Schedule Parser                │
          └───────────────┬───────────────┘
                        ▼
                Canonical Drawing Model
      (geometry + CAD layers + text, each item tagged
       MEASURED / DERIVED / ASSUMED / UNMAPPED confidence
       + source_quality: layered_vector/degraded_vector/raster)
                        ▼
        ┌───────────────┴────────────────┐
        ▼                                 ▼
 Assembly & Rules Engine            Cost & Labor Catalog
 (component → material/labor)      (unit prices, productivity)
        └───────────────┬────────────────┘
                        ▼
              Quantity & Cost Engine
              (deterministic calculations only)
                        ▼
                Human Review UI
    (click-through to source geometry; review time logged;
     filterable by discipline, layer confidence, source_quality)
                        ▼
             BOQ / Cost Estimate / Scope of Work
```

## 3. Component breakdown

### 3.1 Ingestion router
On upload, inspect the file:
- **PDF** → PyMuPDF: count `page.get_drawings()` vs `page.get_images()`. High vector count + extractable text → **vector path**. Dominated by full-page raster images → **raster path**.
- **DWG/DXF** → `ezdxf` CAD path (always preferred when available).
- **PNG/JPG/scanned PDF** → **raster path**.

After file-type routing, perform **layer classification**: enumerate every OCG on the sheet (`doc.get_ocgs()`), classify each by regex against a human-editable config (e.g. `layer_classification_rules.yaml`), and persist the classification per sheet. Downstream branches on this decision.

### 3.1b Input Quality Gate *(new in spec v3 §7.2)*

Sits between the router and everything else. Its job: don't let a degraded file silently run the wrong pipeline.

- For a vector-path file, don't stop at the binary vector/raster decision — score **layer richness**: count of distinct OCGs, fraction of paths carrying a non-null `layer` attribute, presence of extractable legend/schedule text.
- Below threshold (e.g. fewer than 3 distinct layers, or >90% of paths untagged — consistent with a flattened export) → flag the file `degraded_vector`.
- **Closed/internal deployment:** loop back first — surface "this file has no layer data; re-export with layers included, or provide native DWG/DXF" to the uploader before falling through to raster. Only possible because deployment is our own company / controlled partners.
- If loop-back isn't possible: route automatically to the raster engine and tag every downstream measurement with a lower base-confidence multiplier; the review UI visibly distinguishes "measured from a flattened file".
- Exposed via `GET /drawings/{id}/quality`; loop-back via `POST /drawings/{id}/request-reexport`.

*Implementation status (2026-08-22):* `classify_upload()` in `app/ingestion/router.py` performs only the binary vector/raster decision (hard-coded >10,000-drawings heuristic; ambiguous defaults to vector). Layer-richness scoring, `degraded_vector` flagging, and the loop-back endpoints are **not implemented yet** — see Phases.md Phase 2.5.

### 3.2 Vector parsing engine (primary)

- Library: `PyMuPDF` (import `pymupdf`, not deprecated `fitz`).
- Extract: `page.get_drawings()` (paths + `layer` attribute), `page.get_text('dict')` (text spans with bbox + font size), `doc.get_ocgs()` (layer name registry).
- **Each layer is classified by the Layer Registry (see §3.1) into: symbol, region, or route geometry.**
- **Branch by classified geometry type:**
  - **Symbol layers** → deterministic distance-threshold clustering (union-find over bbox pairs within a per-sheet threshold derived from the smallest legend symbol's real-world bounding-box size) → discrete component instances (access-control devices, lighting fixtures, CCTV cameras, fire-alarm devices). Replaces DBSCAN per spec v3 §7.4: no density parameter to tune per drawing, and the merge rule reduces to a sentence a reviewer can be given verbatim — "these segments are within N real-world millimeters, the size of the smallest symbol on this sheet's own legend."
  - **Region layers** → reconstruct polygons via `shapely.polygonize` on line segments → `Space` rooms, filtered by area threshold and cross-checked against paired name/area text. `networkx`-based planar-graph fallback only if `polygonize` proves insufficient on a real sheet — don't pre-build it.
  - **Route layers** → extract polylines → `Route` lengths measured and scaled (CONDUIT, CABLE_TRAY, PIPE, E-PWER-CABL-TRAY-HATCH).
- Classify each cluster: first by CAD layer name (deterministic), falling back to legend-matching when ambiguous.
- Determine scale from title-block text / scale bar / dimension string, cross-checked. Store per sheet — never assume a global default.
- Output: typed geometry objects with real-world coordinates, each linked back to its raw source paths for traceability.

*Implementation status (2026-08-22):* `app/ingestion/vector.py` still clusters with scikit-learn DBSCAN (`eps=5.0, min_pts=2`); migration to distance-threshold union-find is Phase 2.5 work. Note: `sklearn` is imported but **not declared** in `pyproject.toml`.

### 3.3 Raster / CV fallback (secondary — rewritten per spec v3 §7.7)

Split into techniques matched to two different sub-problems, plus rotation-aware OCR — this removes the YOLOv8 licensing exposure:

- Render page at high DPI (`page.get_pixmap(dpi=...)`).
- **A. Legend-based symbol counting → classical computer vision (default):** OpenCV `matchTemplate` or ORB/SIFT keypoint matching against glyph templates extracted from the sheet's own legend table; non-max suppression at a configured threshold. No training data, no model license; conceptually the same technique as the vector path's legend matching on a different input type.
- **B. Architectural region segmentation → Detectron2 (Apache-2.0):** the sole trained-model dependency in the stack (CubiCasa5K-style pretraining) — reserved for walls/rooms/doors with no legend entry to match against.
- **Ultralytics YOLOv8: removed as default.** AGPL-3.0 requires an Enterprise License even for internal-only proprietary use (vendor-confirmed). Revisit only if A+B prove insufficient on real degraded files, and only as a deliberate, budgeted licensing decision.
- **C. Rotation-aware OCR (spec v3):** PaddleOCR primary / Tesseract fallback, made rotation-aware: where hybrid vector context exists (flattened file with some line data nearby), use the angle of the nearest line segment as rotation prior; for pure scans run an angle sweep (0°/90°/180°/270°, refined in finer steps) and keep the highest-confidence result.
- Scale calibration same principle as vector path.
- All raster-derived measurements carry lower base confidence and `source_quality="raster"`, visibly tagged in the review UI.

*Implementation status (2026-08-22):* `app/raster/` has import-gated modules (`legend.py`, `ocr.py` Paddle/Tesseract, `yolo_detection.py` ultralytics-gated, `segmentation.py` detectron2-gated, `renderer.py`). Heavy deps are optional at runtime and none are declared in `pyproject.toml`. Classical-CV template matching and rotation-aware OCR are **not implemented yet** — see Phases.md Phase 2.5.

### 3.4 Canonical drawing model
Unified internal representation. Element types:
- `Component` (door, card reader, lock, fixture, panel)
- `Route` (cable run, pipe run, conduit) — ordered polyline, measured length, waste factor
- `Space` (room, parking bay) — polygon, area, label
- `Structural element` (wall, stair, ramp)
- `Annotation` (dimension string, note, schedule entry) — raw text + position

Every object stores: `source_sheet`, `source_region`, `measurement_type`, `raw_value`, `confidence_status` (`MEASURED`/`DERIVED`/`ASSUMED`), `confidence_score`, and a **`source_quality` flag** (`layered_vector` / `degraded_vector` / `raster`) from the Input Quality Gate (spec v3 §7.8); the layer reference is nullable for raster-sourced items with no layer.

### 3.5 Assembly & rules engine
Human-editable YAML/DB rules, **not** a trained model.
- Direct assemblies: `access_control_door → {card_reader: 1, magnetic_lock: 1, push_button: 1, door_controller: 0.5, labor: {installation_hours: 2.5}}`.
- Formula derivations: `volume_m3 = area_m2 * thickness_m * (1 + waste_pct)`.
- Rules are versioned; every derived quantity records its rule version.

### 3.6 Cost & labor catalog
DB of unit prices & productivity rates, scoped per company/region/supplier. User-supplied price lists ingested here — never hardcoded. Multiple price sets coexist and swap without touching geometry/quantity layers.

### 3.7 Quantity & cost engine
Pure arithmetic, unit-tested, zero AI:
```
material_cost = quantity * unit_price
labor_hours  = measured_quantity / productivity_rate
labor_cost   = labor_hours * hourly_rate
total        = material_cost + labor_cost + equipment_cost + waste + contingency
```

### 3.8 Confidence tiering
| Status | Meaning |
|---|---|
| `MEASURED` | Directly read from vector geometry |
| `DERIVED` | Calculated via assembly/formula from a measured input |
| `ASSUMED` | Filled from a default assumption, no source data |
| `UNMAPPED` | Measured successfully but no assembly rule exists yet to turn it into a costed BOQ line |

Show status per line, never a single blended "accuracy %". `UNMAPPED` decouples "did we look" from "can we price it yet."
### 3.9 Text-layer association walker

First check whether the installed PyMuPDF version exposes OCG membership on text spans directly; if not, fall back to a `BDC/EMC`-tracking content-stream walker tracking `BDC /OC … EMC` nesting around `Tj`/`TJ` operators. **Output: every text span tagged with its controlling layer (or "untagged" if none), ready for spatial join.** Prototyped and validated against the sample sheet using `pikepdf.parse_content_stream` — it correctly separated all 388 text-show operations by controlling layer. Once each text span has a layer, join `M_SAUDI_ROOM-nametr` + `M_SAUDI_ROOM-area` text to the nearest `M_SAUDI_AREAS` polygon centroid to get a labeled, area-verified `Space` row — geometry measures the area, text confirms the label, no model involved.

### 3.10 Generic schedule & attribute-block parser

Config-driven regex pattern library for common AEC schedule field shapes (`"<label> \(<unit>\):<value>"`, `"%<slope> - <run>cm"`, `"<block-prefix>-<letter><NN>"`). Anything the regex library doesn't match falls through to the LLM interpretation tier for a proposed classification, which a human confirms. This matches the existing guiding principle: "AI proposes, geometry/rules decide," without adding a new exception to it.

### 3.11 Human review UI

- Overlay every extracted quantity/component on the original drawing.
- Click BOQ line → highlight exact source geometry.
- Accept / correct / reject per item; corrections logged as training/rule-improvement signal.
- Bulk-accept for `MEASURED`; force review for `ASSUMED` and `UNMAPPED`.
- Filter/group by discipline, layer-classification confidence, and **`source_quality`** (layered vector / degraded vector / raster).
- **Review-time instrumentation (spec v3 §7.13):** log average review time per sheet and per confidence tier, surfaced via `GET /projects/{id}/review-metrics`. This is the direct measure of whether the system beats manual takeoff — if it exceeds the agreed threshold as coverage grows, recalibrate confidence/bulk-accept rules before expanding scope.

### 3.12 Output generation

- BOQ, BOM, scope of work (LLM narrates *from structured data only*), workforce/labor estimate.
- Exports: JSON (API), XLSX, PDF.

## 4. Repository structure (target)

```
AEC-software/
├── docs/                      # project documents (this set)
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI entrypoint
│   │   ├── api/               # routers: projects, drawings, review, catalogs, assemblies
│   │   ├── ingestion/
│   │   │   ├── router.py      # file → path decision
│   │   │   ├── vector.py      # PyMuPDF vector parsing
│   │   │   ├── cad.py         # ezdxf (later)
│   │   │   └── raster.py      # CV/OCR fallback (v1.5)
│   │   ├── model/             # canonical drawing model (Pydantic)
│   │   ├── assembly/          # rules engine (YAML-driven)
│   │   ├── quantity/          # quantity & cost engine (pure functions)
│   │   ├── catalogs/          # materials, prices, labor rates
│   │   ├── workers/           # Celery tasks
│   │   └── db/                # SQLAlchemy models, migrations
│   ├── tests/
│   └── pyproject.toml
├── frontend/                  # Next.js + TypeScript
│   ├── app/
│   ├── components/            # Review UI overlay (Canvas/SVG + pdf.js)
│   └── ...
└── data/
    ├── assemblies/            # YAML rule sets
    └── samples/               # real test fixtures (MMC-JVC-CD-ELEC-3902_AC-WIRE)
```

## 5. Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (async) |
| Vector PDF parsing | PyMuPDF (`pymupdf`) |
| PDF cross-validation | `pikepdf`, `pdfminer.six` — dev-time verification only |
| CAD parsing | `ezdxf` |
| BIM parsing | `ifcopenshell` (later phase; LGPL — no closed-source obligation) |
| Raster CV | **OpenCV (`matchTemplate`, ORB/SIFT)** — legend-based template matching, default; no training, no license cost |
| Region segmentation (raster) | **Detectron2 (Apache-2.0)** — default; sole trained-model dependency (CubiCasa5K-style pretraining) |
| ~~Object detection~~ | ~~Ultralytics YOLOv8~~ — removed as default: AGPL-3.0 requires an Enterprise License even for internal-only use; revisit only as a deliberate paid decision |
| OCR | PaddleOCR / Tesseract + rotation-aware preprocessing (spec v3 §7.7C) |
| Geometry | Shapely (`polygonize`); `networkx` conditional fallback only if polygonize proves insufficient |
| Database | SQLite (file-based) via SQLAlchemy; PostgreSQL (+PostGIS) later via DATABASE_URL swap | Phase 0 decision: file DB works on serverless & server |
| Job queue | Redis + Celery |
| Object storage | S3-compatible (Cloudflare R2 / AWS S3 / MinIO) |
| Frontend | Next.js + TypeScript |
| Review overlay | Canvas/SVG overlay + `pdf.js` |
| Auth | Clerk |
| LLM layer | Claude API (function-calling / structured output) — interpretation & narration only |
| Containerization | Docker (K8s later if scaling) |
| Layer classification | Human-editable regex config (`layer_classification_rules.yaml`) |
| Text-layer association | `pikepdf` content-stream walker (BDC/EMC nesting) |
| Schedule parser | Config-driven regex patterns + LLM fallback |

## 6. Data model (core tables)

`PROJECT → DRAWING → DRAWING_REVISION → SHEET → {COMPONENT | ROUTE | SPACE}`
`LAYER` — every OCG on every sheet, classified by discipline (architectural, electrical, envelope, structural, unclassified); human-correction supported; foreign key into `COMPONENT.source_layer`, `ROUTE.source_layer`, and `SPACE.source_layer`
`SCHEDULE_BLOCK` — parsed elevator-spec-style free text and generalizes the existing legend table handling; fields: block_type, parsed_fields (key: value pairs with confidence), source_region
`COMPONENT → MEASUREMENT` (audit trail: source_sheet, source_region, method, raw/final value, confidence)
`MEASUREMENT → BOQ_ITEM → ESTIMATE`
`ASSEMBLY → {MATERIAL, LABOR_TYPE}`; `MATERIAL → PRICE` (effective_from/to)

**Spec v3 addition:** a `source_quality` column (`layered_vector` | `degraded_vector` | `raster`) on `COMPONENT`, `ROUTE`, `SPACE`, and `SCHEDULE_BLOCK`; layer FKs nullable for raster-sourced items.

*Implementation status (2026-08-22):* the `LAYER` and `SCHEDULE_BLOCK` tables are designed but **not yet migrated** — `Component.source_layer` is a plain string today, and no `source_quality` column exists. Migration is Phase 2.5 scope.

**Key point:** `MEASUREMENT` is the audit-trail table. Every `BOQ_ITEM` traces back through it to `source_sheet` + `source_region` + `calculation_method`. This is what makes the review UI possible. Full ERD in the Design Spec §8.

## 7. API surface

**Implemented so far (Phase 0–2):**
```
GET    /health                          # app + DB status
POST   /api/e2e/run                     # full vector pipeline PDF → BOQ
POST   /api/catalog/import              # CSV/Excel price import
GET    /api/catalog/                    # list materials with latest prices
```

**Planned (v1 sketch):**
```
POST   /projects
POST   /projects/{id}/drawings          # upload PDF/image/DWG
GET    /drawings/{id}/status            # queued/parsing/done/error
GET    /drawings/{id}/model             # canonical drawing model
POST   /drawings/{id}/review            # human corrections
GET    /projects/{id}/estimate          # BOQ/cost/labor
POST   /catalogs/materials              # price catalog upload/update
POST   /catalogs/labor-rates            # productivity rates
GET    /assemblies | POST /assemblies   # list/edit/version rules
POST   /drawings/{id}/classify-layers   # enumerate + classify OCGs per discipline
POST   /drawings/{id}/text-layers       # tag text spans with controlling OCGs
POST   /drawings/{id}/parse-schedules   # parse schedule/attribute blocks
```

**Added by spec v3:**
```
GET    /drawings/{id}/quality              # Input Quality Gate score + flags
POST   /drawings/{id}/request-reexport     # loop-back request to uploader (closed deployment)
GET    /projects/{id}/review-metrics       # average review time per sheet / per tier
```