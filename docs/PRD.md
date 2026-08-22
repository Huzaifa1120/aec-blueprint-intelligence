# PRD — AEC Blueprint Intelligence System

**Status:** Approved
**Owner:** Saad Ahmad
**Source of truth:** `AEC-Blueprint-System-Design-Spec.md`. If a conflict arises, the Design Spec wins unless this document is explicitly updated.

---

## 1. What we are building

A system that ingests construction blueprints (CAD/BIM files, vector PDFs, or scanned/raster images) and produces structured, priced, traceable construction estimates:

1. **Geometric quantities** — counts, lengths, areas, volumes of components (card readers, locks, doors, walls, rooms) and routes (cable runs, conduit, trunking).
2. **Raw material estimates** — from geometry via deterministic engineering formulas.
3. **Priced estimates** — quantity × user-supplied price catalog.
4. **Scope of work & workforce** — trades, crew sizes, labor-hours/days.

Delivery: a Python backend behind a web interface. User uploads a blueprint; backend processes it; the system returns a BOQ / cost estimate / scope of work where every number is clickable back to its source geometry.

## 2. Target users

**Primary (v1):** the owner/estimator at a single AEC/contracting company (internal closed tool).

- Reads construction drawings daily to produce bids and budgets.
- Trusts a number only when they can see where it came from on the sheet.
- Supplies their own price catalogs and productivity rates.
- Will reject any tool that quietly produces wrong quantities.

**Explicit non-goal:** general-purpose "upload any blueprint" public SaaS. That market is funded and crowded (Togal.AI, Kreo, STACK, etc.). We solve a single company's constrained problem first, then decide whether to generalize.

## 3. Problem statement

Estimating quantity takeoff (QTO) from drawings is manual, slow, and error-prone. Existing tools are either generic (low accuracy) or require retraining on each company's drawing conventions. Our system must:

- Turn an uploaded sheet into accurate measured quantities.
- Never present a number that isn't traceable to a deterministic calculation.
- Let the user review, correct, and approve everything before it becomes an estimate.

## 4. Core principles

> **AI proposes. Geometry calculates. Engineering rules derive. Humans approve.**

- A vision model/LLM may *propose* a classification or interpret a legend — never output a final quantity.
- A geometry engine *measures* from real vector coordinates.
- A rules engine *derives* materials/labor with deterministic, human-editable formulas.
- A human *reviews and approves* every number. This is mandatory, not a v2 feature.

## 5. Features

### v1 (MVP — Access Control Takeoff)
- Upload a single electrical/access-control PDF sheet.
- Vector parsing only (raster fallback is v1.5).
- Extract & cluster the `access control` CAD layer into discrete components: card readers, push buttons, magnetic locks, controllers.
- Measure cable trunk / conduit route lengths from vector geometry, calibrated to the sheet's stated scale (1:100 on the sample sheet).
- Apply one hardcoded assembly rule set (e.g. `1 controller per 2 doors`).
- Accept one manually-entered price row per material/labor type.
- Output a BOQ where every row is clickable and highlights its source region on the rendered PDF.

### v1.5 — Raster fallback
- CV/OCR path for scans, photos, and flattened PDFs.
- Legend-based few-shot matching (parse *this document's own legend*), not a universal symbol detector.
- Raster-derived measurements tagged with lower base confidence than vector-derived ones.

### v2 — Full electrical discipline
- Lighting, power, switches, sockets, distribution boards, cable trays.
- Price catalog & labor rate CRUD (upload/spreadsheet import, multiple price sets).

### v3 — Multi-Domain Extraction Upgrade
- Extract maximum recoverable data across **every** domain present in a sheet, not just the domain the sheet is titled after.
- Layer classification & domain taxonomy: each OCG classified as architectural, electrical, envelope, structural, or unclassified (human-correction supported).
- Symbol-instance clustering: generalized DBSCAN per classified layer (access-control devices, lighting fixtures, CCTV cameras, fire-alarm devices).
- Polygon/region reconstruction: room boundaries from `M_SAUDI_AREAS`-type layers reassembled into closed polygons via `shapely.polygonize`, filtered by area threshold and cross-checked against paired name/area text.
- Text–layer association walker: every text span tagged with its controlling layer via `BDC/EMC` content-stream nesting; room name+area text joined to nearest room polygon centroid.
- Generic schedule & attribute-block parser: regex-pattern library for known AEC field shapes (elevator specs, ramp slopes, parking counts), with LLM fallback for unmatched blocks.
- Legend/schedule-table generalization: detect any tabular symbol-key block on a sheet and match cluster counts against the present table, rather than assuming exactly one legend per sheet.
- Four confidence statuses: `MEASURED`, `DERIVED`, `ASSUMED`, `UNMAPPED` (measured but no assembly rule exists yet to turn it into a costed BOQ line).
- Output BOQ/BOM/scope where every number is traceable to a highlighted source region, with discipline-level filtering in the review UI.

### v3.1 — Mechanical (HVAC)
- Ducts, pipes, equipment, units.
- Formula-based derivations for duct/pipe material by size & route length.

### v3.2 — Plumbing & Fire Protection
- Same patterns; fire-alarm layer handling (exists on the sample sheet: `FIRE ALARM`).

### v4 — Architectural
- Walls, doors, windows, flooring, ceilings, finishes.
- Raster segmentation model earns its keep here.

### v5+
- Structural (concrete, rebar, formwork).
- Multi-sheet / whole-project ingestion, revision/change tracking.
- BIM/IFC-native knowledge graph.

## 6. Non-functional requirements

| Area | Requirement |
|---|---|
| Accuracy | Per-item confidence status (`MEASURED` / `DERIVED` / `ASSUMED`); never one blended "%". Track accuracy per tier. |
| Traceability | Every BOQ line links back through a `MEASUREMENT` audit record to source sheet + region + method. |
| Async processing | Drawing processing is not instant → job queue, status polling. |
| Configurable | Assembly rules, price catalogs, labor rates are human-editable data, not code. |
| Testable | Quantity & cost engines are pure, unit-tested arithmetic. |
| Security | User-supplied price data is never hardcoded or committed; no secrets in the repo. |

## 7. Success metrics (v1)

- Given the real sample sheet (`MMC-JVC-CD-ELEC-3902_AC-WIRE`): correctly counts all access-control components (verified once manually → becomes the regression test).
- Computes correct cable/conduit lengths within the sheet's stated scale.
- Every output number is traceable to a highlighted region on the rendered PDF.
- Time-to-estimate for that sheet drops below manual baseline.
- Corrections logged during review are persisted as rule-improvement signal.

## 7.3 Success metrics (v3 — Multi-Domain)

- All 46 layers on the sample sheet are classified; no layer silently ignored.
- `M_SAUDI_AREAS` room polygons extracted and paired with `M_SAUDI_ROOM-nametr`/`M_SAUDI_ROOM-area` text.
- Symbol instances across all electrical sub-layers (access control, fire alarm, CCTV, lighting, cable tray) are clustered and counted.
- Route lengths for CONDUIT, CABLE_TRAY, and E-PWER-CABL-TRAY-HATCH layers are measured and scaled.
- Every BOQ number is traceable to a highlighted source region with a confidence status (`MEASURED`/`DERIVED`/`ASSUMED`/`UNMAPPED`).
- Review UI supports filtering by discipline and layer-classification confidence.
- Corrections logged during review persist as rule-improvement signal for assembly-rule refinement.

## 8. Out of scope (v1 — explicitly)

- Raster/scanned drawings (v1.5).
- Raw building materials (concrete/rebar/bricks — need structural/architectural sheets).
- Multi-sheet projects, revision comparison, multi-user collaboration.
- A universal cross-company "construction symbol" detector.
- Any claim of "upload anything, get a 100% accurate BOQ."

## 8.2 Out of scope (v3 — Multi-Domain, until Phase 9)

- Universal cross-company "construction symbol" detector before per-document legend matching is exhausted.
- Raw material estimation (concrete/rebar/bricks) from a single-discipline sheet — requires structural/architectural set.
- Multi-tenant deployment (single-tenant internal first recommended).
- BIM/IFC-native knowledge graph (Phase 8+ long-term).

## 9. Open questions

- What ratio of incoming drawings will be vector PDFs vs. scans?
- Is native DWG/DXF available for the target company? (Strictly higher fidelity than PDF vector parsing.)
- Which company's price catalog seeds the Cost & Labor Catalog first?
- Single-tenant internal deployment confirmed? (Recommended.)