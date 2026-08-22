# PRD — AEC Blueprint Intelligence System

**Status:** Approved
**Owner:** Saad Ahmad
**Source of truth:** `AEC-Blueprint-System-Design-Spec-v3.md` (supersedes v2 and the original spec). If a conflict arises, the Design Spec wins unless this document is explicitly updated.

> Naming note: the release labels below (v1, v1.5, v2, v3…) are *product releases*. "Spec v3" is the *design-spec revision* (`AEC-Blueprint-System-Design-Spec-v3.md`). The two numberings are unrelated.

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
- An **Input Quality Gate** (spec v3) *flags* degraded (flattened/rasterized) input before parsing — it never guesses through it.
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

### v1.5 — Raster fallback (re-scoped by spec v3)
- Input Quality Gate first: every upload is scored for layer richness; a flattened export is flagged `degraded_vector` and (in closed deployment) routed back to the uploader for re-export — never silently processed as the happy path.
- Two-technique split, matched to two sub-problems:
  - **Legend-based symbol counting → classical CV** — OpenCV `matchTemplate` / ORB-SIFT against glyph templates extracted from the sheet's own legend. No training data, no license cost; mirrors the vector path's legend-matching strategy.
  - **Architectural region segmentation → Detectron2 (Apache-2.0)** — the sole trained-model dependency, reserved for walls/rooms/doors with no legend entry.
- ~~Ultralytics YOLOv8~~ removed as default — AGPL-3.0 requires an Enterprise License even for internal proprietary use (vendor-confirmed); revisit only as a deliberate, budgeted decision if the split above proves insufficient.
- Rotation-aware OCR: rotation prior taken from the nearest line segment where hybrid vector context exists; brute-force angle sweep (0°/90°/180°/270°, refined) for pure scans.
- Every measurement carries a `source_quality` flag (`layered_vector` / `degraded_vector` / `raster`); raster-derived values carry lower base confidence and are visibly tagged in the review UI.

### v2 — Full electrical discipline
- Lighting, power, switches, sockets, distribution boards, cable trays.
- Price catalog & labor rate CRUD (upload/spreadsheet import, multiple price sets).

### v3 — Multi-Domain Extraction Upgrade
- Extract maximum recoverable data across **every** domain present in a sheet, not just the domain the sheet is titled after.
- Layer classification & domain taxonomy: each OCG classified as architectural, electrical, envelope, structural, or unclassified (human-correction supported).
- Symbol-instance clustering: generalized deterministic distance-threshold clustering (spec v3 §7.4) per classified layer (access-control devices, lighting fixtures, CCTV cameras, fire-alarm devices).
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
| Accuracy | Per-item confidence status (`MEASURED` / `DERIVED` / `ASSUMED`); never one blended "%". Track accuracy per tier **and per `source_quality` tier** (layered vector vs degraded vector vs raster). |
| Input honesty | Incoming files are never assumed layer-rich; the Input Quality Gate scores every upload and visibly tags downstream output by `source_quality`. |
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
- Average human review time per sheet and per confidence tier is tracked from day one (spec v3) and stays under the threshold agreed with the business stakeholder — review overhead staying low is the commercial case for the system.
- Corrections logged during review persist as rule-improvement signal for assembly-rule refinement.

## 8. Out of scope (v1 — explicitly)

- Raster/scanned drawings (v1.5).
- Raw building materials (concrete/rebar/bricks — need structural/architectural sheets).
- Multi-sheet projects, revision comparison, multi-user collaboration.
- A universal cross-company "construction symbol" detector.
- Any claim of "upload anything, get a 100% accurate BOQ."

## 8.2 Out of scope (v3 — Multi-Domain, until Phase 9)

- Universal cross-company "construction symbol" detector before per-document legend matching is exhausted.
- Any detector requiring an unbudgeted commercial license — Ultralytics YOLOv8 (AGPL-3.0) is removed from the default stack (spec v3 §7.7, §9).
- Raw material estimation (concrete/rebar/bricks) from a single-discipline sheet — requires structural/architectural set.
- Multi-tenant deployment (single-tenant internal first recommended).
- BIM/IFC-native knowledge graph (Phase 8+ long-term).

## 9. Open questions

- Will most incoming drawings be layer-rich vector PDFs, or should we plan around degraded (flattened) input being the norm rather than the exception? This decides how much of the raster spike gets invested versus deferred (spec v3 §16).
- Is native DWG/DXF/IFC available for the target company instead of PDF exports? Strictly higher fidelity, and the highest-leverage fix for the flattening risk.
- Which company's price catalog and productivity rates seed the Cost & Labor Catalog first?
- Single-tenant internal deployment confirmed? (Recommended — strengthened in spec v3: it's the only deployment where the Input Quality Gate's re-export loop-back request is actually actionable.)