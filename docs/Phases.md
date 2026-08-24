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

## Phase 1.5 — Raster / CV fallback ✅ *(technique superseded by spec v3 — see Phase 2.5)*

- Render page → image at high DPI; OCR (PaddleOCR) for text/dimensions/legend.
- YOLOv8 shape-cluster detection + **per-document legend** few-shot matching.
- CubiCasa5K-style segmentation only for non-legend architectural elements.
- Raster measurements tagged with lower base confidence.
- **DoD met:** scanned copy of the sample sheet produces the same components with confidence-tiered (lower) ratings.

*Phase 1.5 MVP proven off sample sheet `MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`. Raster fallback is not required for MVP (Phase 1) but is the natural continuation for scanned PDF support.*

> **Spec v3 re-scope (2026-08-22):** the YOLOv8-based technique above is superseded — Ultralytics YOLOv8 is removed from the default stack (AGPL-3.0 requires an Enterprise License even for internal-only proprietary use, vendor-confirmed). The raster path moves to the two-technique split (classical-CV legend matching via OpenCV `matchTemplate`/ORB-SIFT + Detectron2 region segmentation + rotation-aware OCR) and must be re-proven by the Phase 2.5 raster spike against vector-derived ground truth. The historical record above is retained as-is.

## Phase 2 — Full Electrical discipline ✅

**Goal:** Extend the AEC Blueprint Intelligence System to process full electrical construction drawings, producing a complete Bill of Quantities (BOQ) for lighting, power, switches, distribution boards, cable trays, and conduit. The electrical discipline follows the same vector-first, rules-driven, human-verified architecture established in Phase 1.

**Definition of Done:** A second real electrical sheet estimated end-to-end; catalogs editable without code changes; all BOQ numbers trace to deterministic calculations from vector geometry.

### 2.1 What's Been Implemented (Planning + Initial Implementation):

- **9 electrical component assembly rule YAML files** in `data/assemblies/`:
  8 rule files: `access_control_door.yaml`, `switch.yaml`, `power_outlet.yaml`, 
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

## Phase 2.5 — Spec v3 Alignment ✅ *(completed 2026-08-23)*

**Goal:** bring the codebase in line with `AEC-Blueprint-System-Design-Spec-v3.md` before starting Phase 3. The v3 revision changed four things that touch existing code, and added two new obligations. Nothing here re-opens Phase 1/2 results — it hardens them.

1. **Input Quality Gate** (`app/ingestion/quality_gate.py`, new; spec §7.2) — ✅ done:
   - Score layer richness on vector-path uploads: distinct OCG count, fraction of paths with non-null `layer`, extractable legend/schedule text.
   - Below threshold → flag `degraded_vector`; loop-back message + `POST /drawings/{id}/request-reexport` (closed deployment); otherwise route to raster with lower base-confidence multiplier.
   - Spike: deliberately produce a flattened version of the sample sheet (print-to-PDF / discard-hidden-layers export) and assert the gate flags it.
   - Endpoints: `GET /drawings/{id}/quality`, `POST /drawings/{id}/request-reexport`.
2. **Clustering migration** (`app/ingestion/vector.py`; spec §7.4) — ✅ done: replace scikit-learn DBSCAN (`eps=5.0`) with deterministic distance-threshold connected-components (union-find), threshold derived per sheet from the smallest legend symbol's real-world size. Regression: same component counts on the sample sheet before/after.
3. **Raster path re-proof** (spec §12a Stage 1.5 spike) — ✅ closed as documented dead-end (human ruling A, amendment below): extract glyph templates from the sample's legend region → classical template matching against a rendered copy of the same sheet → compare counts to the vector ground truth from Phases 0–2. Do **not** build Detectron2 segmentation yet. Retire/quarantine the ultralytics import gate (`app/raster/yolo_detection.py`) so YOLOv8 can never enter the default stack.
4. **Schema migration** — ✅ done: add `source_quality` column (`layered_vector` | `degraded_vector` | `raster`) to `COMPONENT`, `ROUTE`, `SPACE` (+ `SCHEDULE_BLOCK` when created); Alembic migration; populate existing rows as `layered_vector`.
5. **Review-time instrumentation** (spec §7.13) — ✅ done: log review time per sheet and per confidence tier; expose `GET /projects/{id}/review-metrics`. Agree a target threshold with the business stakeholder before calling this done.
6. **Dependency hygiene** — ✅ done (resolved: removed): declare `scikit-learn` in `pyproject.toml` or drop it after task 2 removes the last DBSCAN use.

**DoD:** quality gate flags a deliberately flattened sample and passes a layered one; clustering migration reproduces Phase 1/2 component counts exactly; raster spike counts within agreed tolerance of vector ground truth; no ultralytics import outside a quarantined module; every persisted measurement carries `source_quality`; ruff + full pytest suite green.

**Amendment 2026-08-23 (human ruling A):** the raster-spike tolerance line closes as a documented dead-end rather than a passing count — NCC template matching measured non-discriminative (363× false positives at ceiling 0.903; hollow legend text blocks labeling). Raster path remains quarantined; ORB/SIFT designated successor (spec v3 §7.7A); revisit triggers on first real degraded upload. Evidence: `docs/superpowers/reviews/2026-08-22-raster-spike-report.md`.

*Landed side-effects:* clustering switchover re-baselined component counts under human approval (tie-break filter applied; door 2 / tray 1 / lighting 26); route-length units corrected pt → paper-mm → real-m (previous magnitudes were physically impossible; cable tray now 0.752 m).

*Phase 2.5 complete 2026-08-23 — all six items landed on `feature/phase-2.5-implementation` (HEAD `979a7c5`); full suite green incl. one expected xfail (raster spike, ruling A); ruff clean.*

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
- Design spec: `docs/superpowers/specs/2026-08-23-phase-3-mechanical-hvac-design.md`; implementation plan: `docs/superpowers/plans/2026-08-23-phase-3-mechanical-hvac-plan.md`. Fixture note: no dedicated HVAC sheet exists — S101's `M-EQPT-*` layers give a real equipment-counting proof; duct/pipe formulas prove against a generated deterministic fixture until the owner supplies a real mechanical sheet.

### 3.1 What's implemented (2026-08-23, branch `feature/phase-3-mechanical-hvac`):

- **Restricted-AST formula engine** (`app/assembly/formulas.py`): YAML-declared parameterized formulas evaluated without eval/exec; whitelisted ops (`+ - * / **`), functions (`min/max/round/abs`); fail-closed `FormulaValidationError` at load; gauge/spec lookup tables by threshold.
- **Rule extension** (`app/assembly/rules.py`): BOM entries may be linear multipliers (legacy, byte-identical behavior) or `{formula}` / `{gauge_lookup}` dicts with per-line waste factors; `variables`/`defaults` in rule files; `validate_rule_file()` excludes broken rules fail-closed.
- **Mechanical rules** (`data/assemblies/`): `duct_rectangular`, `duct_round`, `pipe_insulated`, `hvac_equipment` + layer mapping for M-DUCT/M-DUCT-RND/M-PIPE/M-EQPT-* families.
- **Size-resolution cascade** (`app/parsing/sizes.py`): schedule table → text label (`600x400`, `DN150`, `Ø250`, `12"`) → measured geometry → ASSUMED default from YAML; every resolution records `{source, ref}` provenance. Schedule-table detection via header keywords behind config.
- **Provenance schema**: `routes.size_json`, `boq_items.derivation_json`, `boq_items.size_source` (+ Alembic migration; spurious autogenerate ops stripped).
- **E2E mechanical branch** (`app/e2e/router.py`): sized assemblies quantified by formulas with bound variables; equipment counted via existing clustering; BOQ rows carry derivation + size_source.
- **Validation**: exact-math golden tests (evaluator 17, rules 9, cascade 14, schedule 4); generated deterministic HVAC fixture (layer-rich, OCG-tagged, scale 1:100); real-sheet S101 equipment regression (277 units pipeline-derived — pending human visual verification); full suite 125 passed + 1 xfail.

### Known gaps / follow-ups

- No dedicated HVAC sheet yet: duct/pipe formulas proven on the generated fixture only; swap in a real owner sheet when available (trigger: first real mechanical upload).
- S101 FUTR count (276) suspiciously high — likely cluster over-splitting on the xref layer; human eyeball owed before merge.
- Clustering contract gap discovered: centroid-grid proposal misses bbox-touching elongated paths (candidate fix re-landable after human count re-baseline).
- `test_migrations.py` planted instruction string removed (2026-08-23 fix wave).
- Final whole-branch review (2026-08-23): BLOCK → fix wave landed (double-scaling of fittings, fail-closed rule gate wired into `load_assembly_rule`, shape-aware cascade + assumed stamping, evaluator hardening) → scoped re-review **ALL ADDRESSED**. Suite now **135 passed + 1 xfail**.
- Owner sign-offs owed at merge: gauge hanger-kit semantics (qty 1.0 per route vs per meter); ASSUMED default sizes in YAML; derivation persistence is response-level today — DB columns (`derivation_json`) unwired pending human decision.
- Deferred minors: exponent-cap bypass via nested unary/variable exponents; `validate_rule_file` AttributeError on non-dict YAML root.

## Phase 3.5 — v3 Conformance & Gap Closure ✅ *(completed 2026-08-23)*

Closes every code-addressable Phase 3 leftover and builds the spec-v3 components that did not exist yet (spec: `docs/superpowers/specs/2026-08-23-v3-conformance-gap-closure-design.md`; plan: `docs/superpowers/plans/2026-08-23-v3-conformance-gap-closure-plan.md`). Architecture unchanged: AI proposes, geometry calculates, rules derive, humans approve.

### What's implemented (branch `feature/v3-conformance-gap-closure`)

- **G1 — Persistence spine + replay proof:** unified `SheetExtraction` bundle → single-writer `persist_extraction` transaction (Project▸Drawing▸Sheet▸layers/routes/components/blocks/annotations + Measurements + BoqItems); `GET /api/estimates/{id}/boq` serves persisted rows verbatim; `GET /api/estimates/{id}/replay` recomputes every quantity from its recorded derivation (formula / linear_per_m / gauge_lookup) and hard-fails 409 on any mismatch or corrupt payload — a tampered database can never replay clean.
- **G2 — Evaluator/loader hardening:** nested-unary exponent-cap bypass closed, variable exponents bounded, `validate_rule_file` fail-closed on non-dict YAML roots.
- **G3 — Layer registry + LAYER table:** human-editable `data/layer_classification.yaml` (ordered first-match-wins regexes) classifies every OCG via `classify_layers`; per-sheet `layers` rows persist the classification and back nullable `layer_id` FKs on components/routes/spaces.
- **G4 — Legend/schedule parser + SCHEDULE_BLOCK table:** pure `detect_blocks` heuristic over cascade text spans (header keywords, y-row grouping, ≥2 aligned rows); blocks persist with region + entries JSON.
- **G5 — Text–layer association walker:** deterministic nearest-target join of text spans to component centroids / route polylines (`associate_text`, 18 pt threshold), OCG membership probed per span where PyMuPDF exposes it; annotations persist with resolved component/route FKs.
- **G6 — UNMAPPED tiering:** symbol clusters on OCG layers that map to no assembly rule are clustered at the same fallback threshold, surfaced in `/api/e2e/run` as `unmapped_items` ({layer, count, source_path_ids sample}), persisted as Components with `confidence_status="UNMAPPED"`, and **never priced** (no Measurement references them).
- **G7 — Exports:** `GET /api/exports/estimates/{id}/export?format=json|xlsx|pdf` renders the shared BOQ payload (JSON export byte-for-value equal to `/boq`; openpyxl + reportlab writers).
- **G8 — Narrated scope of work:** `GET /api/narration/estimates/{id}` formats the structured payload verbatim (template narrator default; Anthropic import-gated behind a key, runtime number-verbatimism gate with template fallback on any violation).
- **Integration:** `main.py` serves estimates/exports/narration routers; triplicated payload builders consolidated into `app/estimates/payload.py` (one source of truth for reads and downloads).
- **Validation:** 223 passed + 1 xfail (was 135+1 before this phase), incl. a full-pipeline integration suite on generated fixtures (persist → replay → export → narration; unmapped surfacing/persistence); ruff clean; regression locks byte-identical.

### Human gates outstanding (not code)

1. S101 FUTR=276 equipment-count visual verification.
2. Lighting count re-baseline ruling (unblocks the clustering bbox-touching fix, G9).
3. Hanger-kit semantics confirmation (qty 1.0/route stands meanwhile).
4. ASSUMED default duct/pipe sizes in `data/assemblies/*.yaml` confirmation.
5. Real HVAC sheet supply (fixture swap trigger).

## Phase 4 — Plumbing & Fire Protection 🟦 *(in progress — DoD completes on human confirmation of the YAML values below + first real sheet)*

- Same patterns; fire-alarm layer handling (exists on the sample sheet: `FIRE ALARM`).
- **DoD:** plumbing & fire sheets processed.
- Design spec: `docs/superpowers/specs/2026-08-24-phase-4-plumbing-fire-protection-design.md`; implementation plan: `docs/superpowers/plans/2026-08-24-phase-4-plumbing-fire-protection.md`.

### 4.1 What's implemented (2026-08-24, branch `feature/phase-4-plumbing-fire-protection`)

- **Layer classification disciplines:** plumbing / fire_protection / fire_alarm added to the human-editable registry (`data/layer_classification.yaml`) — e.g. `M_SAUDI_RAIN DOWNPIPE` → plumbing, `FP-SPRK-*` → fire_protection, `FA-*` and `FIRE ALARM` → fire_alarm; electrical/mechanical classifications untouched.
- **Geometry-derived fittings** (`app/parsing/fittings.py`, new): 90° elbows at true polyline corners; tees where a sibling route's vertex lands on this route's interior (sibling-route junction wiring in `resolve_route_context`); chained-segment join-point duplicates collapsed so corners never degrade to zero-length segments; degenerate (zero-extent) clusters produce no route instead of ghost BOQ rows.
- **Stroke-dedup correctness fix:** pymupdf ≥1.28 emits every stroked segment forward AND reversed, so route polylines double-traversed each stroke (lengths ≈3× drawn truth). The exact-reversal dedup in `extract_polyline_from_items` fixes lengths at the source; the consequent `SHAPE_EMISSION_FACTOR` rebase 3.0→1.0 in `test_phase3_regression` moves sheet_metal_m2 Σ 146.28→48.76 m² — which equals the drawn truth (the old number was triple-counted input, not a mechanical regression).
- **Fixture-unit sizing** (`app/parsing/fixture_units.py`, new): deterministic accumulation of YAML-declared fixture units for components within a corridor of a water-supply polyline; total resolves a nominal diameter through the owner-editable code table. New `fixture_units` cascade tier sits between schedule and label tiers (`app/parsing/sizes.py`); provenance `{diameter_mm, fu_total, ref:[type@key,...], source:"fixture_units"}` rides `Route.size_json`.
- **Rules data:** 18 new assembly YAMLs under `data/assemblies/` (sanitary_drainage, water_supply, vent, sprinkler_branch, sprinkler_head, standpipe, storm_downpipe, hose_cabinet, cleanout, floor_drain, wc, lavatory, sink, water_heater, smoke_detector, call_point, sounder, facp) incl. `water_supply.fixture_unit_gauge`; `load_assembly_rule` passes through `fixture_units` and `fixture_unit_gauge`; typed fixture symbol layers `P-FIX-WC` / `P-FIX-LAV` keep symbols off route geometry paths.
- **E2E branch:** canonical route-layer set via the shared `ROUTE_ASSEMBLIES` import (no parallel list); plumbing/fire routes quantified with fittings + FU sizes; deterministic generated fixture (`tests/fixtures/make_plumbing_fire_fixture.py`, production code never references it).
- **Replay coherence verification** (`app/estimates/router.py`): `/api/estimates/{id}/replay` additionally verifies every `fixture_units`-sourced route reachable via BoqItem → Measurement.route — gauge(fu_total) must re-resolve diameter_mm, ref tokens must exist in the rule YAML and sum to fu_total; present-but-corrupt size_json fails honest (mirrors the derivation F2 rule). Replay verifies fitting line items by inputs-coherence and FU sizes by derivation coherence (gauge/breakdown sums), not geometric recomputation — route polylines are unpersisted (Phase 3.5 gap family). Replay reads rule YAML live: owner edits to FU values/gauge thresholds will 409 historical estimates until re-derived — fail-closed by design, relevant to the pending human-confirm tuning round.

**Spec refinements locked by the plan (verbatim from its Global Constraints):**

> 1. `storm_downpipe` is implemented as a **counted device kit**, not a sized route — vertical riser length is physically unmeasurable from a floor plan, so per-meter formulas would be fiction. Sized-route treatment arrives with real riser-diagram sheets (same swap trigger as spec §9).
> 2. Replay parity for `fixture_units` sizes verifies **derivation coherence** (gauge(fu_total) == diameter_mm; `fu_breakdown` sums == fu_total; breakdown values match rule YAML) rather than geometric recomputation — route polylines are not persisted (known Phase 3.5 deferred gap, `path_ids_json` family). Fail-closed intent preserved.

**Validation:** fixture e2e green end-to-end (counts, waste factors, elbow/tee truths to drawn geometry); MMC downpipe pin = **11** (owner ruling 2026-08-24: 44 paths merge into exactly 11 symbol clusters, probe-confirmed twice — determinism proof recorded in the test comment); FIRE ALARM empty-OCG honest zero (layer persists as `fire_alarm`, no devices invented); replay tamper case — a DB-flipped `fu_total` flips replay to 409 while the clean run stays green.

**Human-confirm gate outstanding:** fixture-unit values (wc 3 / lavatory 1 / sink 2), water-supply gauge thresholds, ASSUMED default sizes — owner-editable YAML pending ruling. Device rates already owner-confirmed ($38/h + 0.05 waste plumbing; $45/h + 0.02 waste fire protection + fire alarm).

**Real-sheet swap trigger:** plumbing/fire proofs run against the generated fixture until the owner supplies a real plumbing or fire-protection sheet (no dedicated HVAC/duct sheet exists either); swap in the real sheet and re-pin expectations when available.

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

- Never assume incoming files are layer-rich vector PDFs; run the Input Quality Gate first (spec v3 §7.2, §5.5). Flattened input is common, not an edge case.
- No detector that requires an unbudgeted commercial license (e.g. Ultralytics YOLOv8 / AGPL) enters the default stack.
- Raster fallback was **Phase 1.5** (not required for MVP); the Phase 2.5 spike measured NCC template matching non-discriminative (human ruling A, 2026-08-23), so the raster path stays **quarantined** — ORB/SIFT is the designated successor technique (spec v3 §7.7A); revisit triggers on the first real degraded upload.
- Raw-material (concrete/rebar) estimation never happens from a single-discipline sheet.
- Only after individual disciplines are independently reliable may the system claim "upload anything, get a whole-building estimate."