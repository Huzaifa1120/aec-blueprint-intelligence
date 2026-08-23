# Phase 4 — Plumbing & Fire Protection — Design Spec

- **Date:** 2026-08-24
- **Status:** Approved (brainstorming session 2026-08-24)
- **Supersedes:** nothing; implements `docs/Phases.md` §Phase 4
- **Governed by:** `docs/AEC-Blueprint-System-Design-Spec-v3.md` (sole source of truth), `AGENTS.md` non-negotiable rules

---

## 1. Goal & scope

Extend the system to the **plumbing & fire-protection disciplines**, per `Phases.md`: "Same patterns; fire-alarm layer handling." Full sub-domain scope locked during brainstorming:

- **Domestic plumbing** — sanitary/waste/vent pipe routes, hot/cold water-supply routes, storm drainage (downpipes); counted fixtures (WC, lavatory, sink, floor drain, cleanout, water heater).
- **Fire suppression** — sprinkler heads (counted), sprinkler branch lines and standpipes (sized routes), hose cabinets (counted).
- **Fire alarm** — smoke detectors, manual call points, sounders, FACP (counted devices).

Human decisions locked during brainstorming:

| Decision | Ruling |
| --- | --- |
| Scope | **All of Phase 4** — plumbing + suppression + alarm in one phase; no future phases pulled forward |
| Fixture reality | Existing 5 samples only. No plumbing/sprinkler geometry exists anywhere on disk; the `FIRE ALARM` OCG on the MMC sheet is **empty** (0 paths; only "FIRE EXIT" text on architectural layers). Real content: `M_SAUDI_RAIN DOWNPIPE` (~44 paths ≈ 11 symbol locations). Validation therefore follows the Phase 3 pattern: generated deterministic fixtures + real-sheet downpipe regression |
| BOQ depth | **Maximum** — counted devices + sized routes + explicit fittings + fixture-unit sizing |
| Approach | **A: reuse + two engine extensions** (geometry-derived fittings; fixture-unit accumulation). Rules-only (B) rejected as under-scope; hydraulic network solver (C) rejected as YAGNI with zero real sheets to validate against |
| Outstanding Phase 3/3.5 human gates | **Deferred** — S101 FUTR eyeball, lighting re-baseline, hanger-kit semantics, ASSUMED default sizes, real HVAC sheet. Phase 4 designs around current behavior |

## 2. Non-goals (YAGNI)

- Hydraulic network solving, pressure-zone modeling, riser-diagram parsing (no real sheets; revisit when supplied).
- Sprinkler hydraulic calculations (k-factor density/area) beyond YAML gauge tables.
- Cross-discipline rollups / whole-building estimates (Phase 7).
- Any raster-path work (stays quarantined per Phase 2.5 ruling A).
- Symbol-clustering of tiny drawn fitting symbols (elbow/tee blocks) — superseded by §4 geometry-derived fittings.
- New extraction code for symbol counting — extraction stays discipline-agnostic (spec v3 §13).

## 3. Architecture & data model

No pipeline change: classify → parse → scale → routes/components → assemblies → BOQ → persist → replay → export. New/changed components:

```
backend/app/
  parsing/
    fittings.py       # NEW — elbow/tee derivation from route polylines (§4)
    fixture_units.py  # NEW — FU accumulation + code-table gauge resolution (§5)
    sizes.py          # extended — cascade gains 'fixture_units' tier between schedule and label
  e2e/router.py       # extended — plumbing/fire branch binds fittings + FUs into assembly variables
data/assemblies/      # NEW rules (§6)
data/layer_mapping.yaml      # extended entries (§6)
data/layer_classification.yaml # new disciplines plumbing / fire_protection / fire_alarm (§3.1)
backend/app/config.py # thresholds for fittings/FU (angle, junction tolerance, corridor distance)
```

No schema migration required: fittings and FU provenance live inside the existing `boq_items.derivation_json` / `routes.size_json`; replay gate learns the two new derivation kinds.

### 3.1 Layer classification changes

Ordered rules in `data/layer_classification.yaml` (first match wins):

- `FIRE ALARM` moves from `electrical` → **`fire_alarm`**.
- `M_SAUDI_RAIN DOWNPIPE` moves from `envelope` → **`plumbing`** (storm drainage).
- Future-proof NCS-family patterns added: `^(P-)` → `plumbing`, `^(FP-)` → `fire_protection`, `^(FA-)` → `fire_alarm`.

The empty `FIRE ALARM` OCG must classify cleanly and yield **zero components** (honest-zero), never phantom BOQ rows.

## 4. Engine extension 1 — geometry-derived fittings (`app/parsing/fittings.py`)

Tiny drawn fitting symbols are unreliable to cluster and there is no real sheet to tune against. Fittings derive deterministically from route polylines that `measure_routes` already produces:

- **Elbow:** an interior polyline vertex whose direction change ≥ `fitting_bend_angle_deg` (config, default 30°) where both adjacent segments ≥ `fitting_min_segment_pt` counts as one elbow. Provenance: `{source: "geometry_fittings", ref: <vertex coords>}`.
- **Tee/cross:** a vertex of route A within `fitting_junction_tol_pt` of the *interior* (non-endpoint) of route B's polyline adds a tee to route B. Deterministic geometric predicate, bbox pre-filtered. Candidate pairs are restricted to routes whose layers classify into the same discipline (`plumbing` with `plumbing`, etc.) so an electrical tray crossing a water pipe never yields a tee.
- Output per route: derived variables `elbows_90`, `tees`, bound into `apply_assembly` variables exactly like `length_m`, so YAML formulas consume them (e.g., `malleable_elbow: {formula: "elbows_90 * 1.05"}`).
- Confidence **DERIVED**; provenance persisted into `derivation_json`; replay gate recomputes from stored polylines.

## 5. Engine extension 2 — fixture-unit accumulation (`app/parsing/fixture_units.py`)

Classic plumbing-code sizing, scoped honestly to what plan-view geometry supports:

- Fixture rules declare `fixture_units: <number>` in YAML (code-table value, owner-editable).
- After component counting, each water-supply route accumulates the FUs of fixtures whose centroids fall within `fu_corridor_pt` (config) of its polyline. Provenance records contributing component ids.
- Size cascade gains tier **`fixture_units` between `schedule` and `label`**: accumulated FU total → diameter via a gauge table declared in the rule YAML (`fixture_unit_gauge:` threshold rows). Resolution provenance: `{source: "fixture_units", ref: [component ids], fu_total: N}`.

Cascade order becomes: `schedule > fixture_units > label > geometry > assumed`. Replay gate recomputes FU totals from persisted component/route rows and fails closed (409) on any mismatch.

## 6. Rules, mappings, catalog

New assembly YAML files (all prices stay in catalog DB; unpriced flags standard):

| Family | Files | Notes |
| --- | --- | --- |
| Pipe routes | `sanitary_drainage.yaml`, `water_supply.yaml` (hot/cold via variable), `storm_downpipe.yaml`, `vent.yaml` | Sized formulas reusing `length_m`/`diameter_mm`; fitting lines consume `elbows_90`/`tees` |
| Fixtures | `wc.yaml`, `lavatory.yaml`, `sink.yaml`, `floor_drain.yaml`, `cleanout.yaml`, `water_heater.yaml` | Counted devices carrying `fixture_units` |
| Fire suppression | `sprinkler_head.yaml`, `sprinkler_branch.yaml` (route), `standpipe.yaml` (route), `hose_cabinet.yaml` | Branch/standpipe routes sized via cascade like other pipes |
| Fire alarm | `smoke_detector.yaml`, `call_point.yaml`, `sounder.yaml`, `facp.yaml` | Counted devices; wiring/cable falls under existing electrical conduit rules |

`data/layer_mapping.yaml` additions: real layer `M_SAUDI_RAIN DOWNPIPE` → `storm_downpipe`; pre-mapped NCS families `P-*` (sanitary/supply/storm sub-patterns), `FP-*` (sprinkler/standpipe), `FA-*` (detector/call-point/sounder/FACP) for future real sheets.

ASSUMED fallback sizes, gauge tables, waste factors, labor categories all live in these YAML files only.

## 7. Validation & testing

1. **Generated deterministic fixture** (Phase 3 pattern): layer-rich, OCG-tagged plumbing+fire sheet at 1:100 with known device counts, known route lengths, deliberate bends and T-junctions, and FU-labeled fixtures feeding a supply main — exercises classification → clustering → cascade (incl. both new tiers/kinds) → formulas → BOQ → persist → replay → export end-to-end. Production code must not reference it by name.
2. **Real-sheet regressions (MMC sample):**
   - `M_SAUDI_RAIN DOWNPIPE` downpipe count — exact expected cluster count pinned by a pymupdf probe before implementation lands.
   - Empty `FIRE ALARM` OCG → classified `fire_alarm`, zero components, zero BOQ rows (honest-zero).
3. **Unit goldens:** bend detector (angle/min-length boundaries); tee predicate (interior vs endpoint, tolerance edges); FU accumulation + gauge resolution incl. no-fixture route; cascade ordering with the new tier.
4. **Replay gate:** tampered `geometry_fittings` or `fixture_units` derivations must hard-fail 409.
5. Full pytest suite green + ruff clean; regression locks for existing disciplines byte-identical.

## 8. Error handling

- Fail-closed at every existing gate: broken YAML excluded by `validate_rule_file`; missing formula variables raise `FormulaValidationError` (drop-not-500 guards already wired).
- All new thresholds (`fitting_bend_angle_deg`, `fitting_min_segment_pt`, `fitting_junction_tol_pt`, `fu_corridor_pt`) come from config with YAML-declared defaults — never hardcoded in source.
- Unmapped plumbing/fire layers surface through existing UNMAPPED tiering automatically (clustered, persisted, never priced).

## 9. Definition of Done (refined)

`Phases.md` says "plumbing & fire sheets processed" — nothing on disk can satisfy that literally yet, so:

- Generated fixture estimated end-to-end; every BOQ number replays clean through the derivation gate.
- MMC real-sheet downpipe regression exact; FIRE ALARM honest-zero proven.
- Unit golden suites green; full suite green; ruff clean.
- Real-sheet swap trigger fires when the owner supplies plumbing/fire drawings (same clause as Phase 3): re-pin expected values against reality before production reliance.

## 10. Open items carried (not this phase)

- The five deferred Phase 3/3.5 human gates (see §1 table).
- Deferred minors ledger from Phase 3.5 final review.
- `../catalog/` vendor PDFs as price-catalog sources — separate catalog-side decision, not taken here.
