# Architecture — AEC Blueprint Intelligence System

**Status:** Approved direction, ready for implementation
**Source of truth:** `AEC-Blueprint-System-Design-Spec.md`

---

## 1. Architecture decision

**Hybrid, vector-first, rules-driven, human-verified.**

Three-tier ingestion (BIM/CAD → vector PDF → raster image, in order of preference) feeding a single canonical drawing model, then a deterministic assembly/rules engine, then mandatory human review before any number is finalized.

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
              Ingestion & Parsing Engine
        (vector-first extraction; CV+OCR fallback)
                        ▼
               Canonical Drawing Model
     (geometry + CAD layers + text, each item tagged
        MEASURED / DERIVED / ASSUMED confidence)
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
        (every number click-through to source geometry)
                        ▼
             BOQ / Cost Estimate / Scope of Work
```

## 3. Component breakdown

### 3.1 Ingestion router
On upload, inspect the file:
- **PDF** → PyMuPDF: count `page.get_drawings()` vs `page.get_images()`. High vector count + extractable text → vector path. Dominated by full-page raster images → raster path.
- **DWG/DXF** → `ezdxf` CAD path (always preferred when available).
- **PNG/JPG/scanned PDF** → raster path.
- Route logged per file; downstream branches on this decision.

### 3.2 Vector parsing engine (primary)
- Library: `PyMuPDF` (import `pymupdf`, not deprecated `fitz`).
- Extract: `page.get_drawings()` (paths + `layer`), `page.get_text('dict')` (spans + bbox + font size), `doc.get_ocgs()` (layer registry).
- Cluster same-layer paths by spatial proximity (DBSCAN on bbox centroids, tuned per layer) → discrete component instances.
- Classify each cluster: CAD layer name first (deterministic), legend-matching fallback when ambiguous.
- Determine scale from title-block text / scale bar / dimension string, cross-checked. Store per sheet — never assume a global default.
- Output: typed geometry objects with real-world coordinates, linked back to source paths.

### 3.3 Raster / CV fallback (secondary)
- Render page at high DPI (`page.get_pixmap(dpi=...)`).
- OCR: PaddleOCR (primary) / Tesseract (lightweight fallback).
- Detection: Ultralytics YOLOv8 — **not** a universal symbol detector. Parse the sheet's own legend → template/few-shot match → fall back to a pretrained wall/door/room segmentation model (CubiCasa5K-style) only for non-legend elements.
- Scale calibration same principle as vector path.
- Raster measurements get lower base confidence.

### 3.4 Canonical drawing model
Unified internal representation. Element types:
- `Component` (door, card reader, lock, fixture, panel)
- `Route` (cable run, pipe run, conduit) — ordered polyline, measured length, waste factor
- `Space` (room, parking bay) — polygon, area, label
- `Structural element` (wall, stair, ramp)
- `Annotation` (dimension string, note, schedule entry) — raw text + position

Every object stores: `source_sheet`, `source_region`, `measurement_type`, `raw_value`, `confidence_status` (`MEASURED`/`DERIVED`/`ASSUMED`), `confidence_score`.

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

Show status per line, never a single blended "accuracy %".

### 3.9 Human review UI
- Overlay every extracted quantity/component on the original drawing.
- Click BOQ line → highlight exact source geometry.
- Accept / correct / reject per item; corrections logged as training/rule-improvement signal.
- Bulk-accept for `MEASURED`; force review for `ASSUMED`.

### 3.10 Output generation
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
| CAD parsing | `ezdxf` |
| BIM parsing | `ifcopenshell` (later phase) |
| Raster CV | OpenCV + Ultralytics YOLOv8 |
| Segmentation fallback | CubiCasa5K-pretrained / Detectron2 |
| OCR | PaddleOCR / Tesseract |
| Geometry | Shapely |
| Database | SQLite (file-based) via SQLAlchemy; PostgreSQL (+PostGIS) later via DATABASE_URL swap | Phase 0 decision: file DB works on serverless & server |
| Job queue | Redis + Celery |
| Object storage | S3-compatible (Cloudflare R2 / AWS S3 / MinIO) |
| Frontend | Next.js + TypeScript |
| Review overlay | Canvas/SVG overlay + `pdf.js` |
| Auth | Clerk |
| LLM layer | Claude API (function-calling / structured output) — interpretation & narration only |
| Containerization | Docker (K8s later if scaling) |

## 6. Data model (core tables)

`PROJECT → DRAWING → DRAWING_REVISION → SHEET → {COMPONENT | ROUTE | SPACE}`
`COMPONENT → MEASUREMENT` (audit trail: source_sheet, source_region, method, raw/final value, confidence)
`MEASUREMENT → BOQ_ITEM → ESTIMATE`
`ASSEMBLY → {MATERIAL, LABOR_TYPE}`; `MATERIAL → PRICE` (effective_from/to)

**Key point:** `MEASUREMENT` is the audit-trail table. Every `BOQ_ITEM` traces back through it — this is what makes the review UI possible. Full ERD in the Design Spec §8.

## 7. API surface (v1 sketch)

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
```