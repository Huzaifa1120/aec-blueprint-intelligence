# Phase 3 — Mechanical (HVAC) — Design Spec

- **Date:** 2026-08-23
- **Status:** Approved (brainstorming session 2026-08-23)
- **Supersedes:** nothing; implements `docs/Phases.md` §Phase 3
- **Governed by:** `docs/AEC-Blueprint-System-Design-Spec-v3.md` (sole source of truth), `AGENTS.md` non-negotiable rules

---

## 1. Goal & scope

Extend the system from electrical-only to the **mechanical (HVAC) discipline**, per `Phases.md`:

- **Ducts** (rectangular, round) and **pipes** — quantity derived by formula from route length × size.
- **Equipment / units** (AHU, FCU, VAV boxes, fans) — counted as discrete symbols via existing clustering.
- **Formula-based derivations** for duct/pipe material by size & route length.

Human decisions locked during brainstorming:

| Decision | Ruling |
| --- | --- |
| Scope | **Full scope** — ducts + pipes + equipment + formulas in one phase |
| Size source | **All sources** — cascade: schedule table → text label → measured geometry → flagged ASSUMED |
| Fixture reality | No dedicated HVAC sheet exists. `ABC-SC03-S101.pdf` carries real mechanical layers (`M-EQPT-NEW`, `M-EQPT-FUTR`, xref `M-EQUIP`/`M-Clearances`) → real-sheet equipment proof. Duct/pipe ground truth via a generated test sheet until the owner supplies a real HVAC drawing |
| Build quality | **Production grade, input-agnostic** — nothing keys off any specific fixture; works on whatever mechanical drawing arrives |

## 2. Non-goals (YAGNI)

- Multi-sheet rollups / whole-project packages (Phase 7).
- Insulation thickness auto-selection beyond a YAML lookup table.
- Acoustic / seismic bracing rules.
- Any raster-path work (stays quarantined per Phase 2.5 ruling A).
- New extraction code for symbol counting — extraction is discipline-agnostic after Stage 1 (spec v3 §13); this phase adds *rules*, not parsers.

## 3. Architecture

New/changed components (all inside the existing layout):

```
backend/app/
  assembly/
    rules.py        # extended: loads optional formula sections; validates at load time
    formulas.py     # NEW — restricted AST evaluator (whitelisted operators only)
  parsing/
    sizes.py        # NEW — size-resolution cascade with provenance
    routes.py       # unchanged — already measures polyline lengths per layer
    components.py   # unchanged — discrete equipment counting works as-is
  e2e/router.py     # extended: mechanical branch wires cascade → formulas → BOQ
data/assemblies/    # NEW rules: duct_rectangular.yaml, duct_round.yaml,
                    # pipe_insulated.yaml, hvac_equipment.yaml
data/layer_mapping.yaml   # extended entries (M-DUCT, M-PIPE, M-EQPT, ...)
```

### 3.1 Example rule file (`duct_rectangular.yaml`)

```yaml
name: duct_rectangular
rule_version: "1.0.0"
variables: [length_m, width_mm, height_mm]
bom:
  sheet_metal_m2:
    formula: "2 * (width_mm + height_mm) / 1000 * length_m"
    waste_factor: 0.15
  duct_fitting: 0.2            # legacy linear multiplier still allowed
  gauge_lookup:                 # size-dependent selection table
    by: max_mm
    rows:
      300: gauge_0.8mm
      750: gauge_1.0mm
      999999: gauge_1.2mm
labor:
  installation_hours_per_m2: 0.35
  hourly_rate: 50.00
  category: mechanical
```

Linear multipliers (Phase 1/2 style) remain valid — they evaluate as constant expressions through the same engine.

## 4. Size-resolution cascade (`parsing/sizes.py`)

For each route segment, resolve `{width_mm, height_mm}` or `{diameter_mm}`, best source first:

1. **Schedule table** — if the sheet contains a duct/pipe schedule, its rows win. Confidence tier `MEASURED`.
2. **Text label** — regex over extractable text spans near the route geometry: `600x400`, `600×400`, `12"`, `DN150`, `Ø250`. Proximity = label centroid within threshold of the route bbox (same matching philosophy as legend matching). Tier `MEASURED`.
3. **Measured geometry** — double-line ducts: drawn width from vector coordinates × detected scale; depth inferred from declared aspect ratio (default 2:1). Tier drops to `DERIVED`.
4. **ASSUMED fallback** — no source resolved → configurable default size, tier `ASSUMED`, row flagged for human entry. Never silently guessed.

Every resolution records `{value, source, source_ref}` onto the BOQ row — this is what makes "derived quantities trace to formulas" auditable.

Malformed labels near a route are ignored (cascade falls through) and logged at debug level.

Equipment/units need **no cascade**: counted symbols via existing clustering, exactly like distribution boards today.

## 5. Formula engine (`assembly/formulas.py`)

- Each formula is parsed once at YAML load with Python `ast.parse`; a restricted walker accepts only:
  numbers, declared variables, operators `+ - * / **` and parentheses, and the functions `min`, `max`, `round`, `abs`.
- Anything else — unknown names, disallowed calls, attribute/subscript access — raises `FormulaValidationError` with file/line context; **the rule fails closed** and is excluded from the catalog while the rest of the catalog keeps serving.
- Variables bind per route segment: `{length_m, width_mm, height_mm, diameter_mm}` plus gauge-lookup results. A missing variable at eval time flags the row — never a silent zero.
- Every evaluated BOM line returns `{quantity, formula_text, inputs_snapshot}`; the exact expression string and bound values persist to the estimate so each BOQ number can be replayed deterministically.
- Gauge/spec tables are ordered threshold rows in YAML (`by: max_mm`): first row where driving variable ≤ threshold wins. The same mechanism later serves pipe schedules (sch 40 vs 80 by DN).
- No use of `eval()`/`exec()` anywhere.

## 6. Data model changes

Alembic migration adding:

- `ROUTE.size_json` — nullable JSON, e.g. `{"width_mm":600,"height_mm":400,"source":"label","ref":"text_span_42"}`; null for non-sized routes (cable trays etc.).
- `ESTIMATE_ITEM.derivation_json` — nullable JSON `{formula, inputs, rule_name, rule_version}`.
- `ESTIMATE_ITEM.size_source` — nullable enum-as-string: `schedule | label | geometry | assumed`; null for count-based rows.

Confidence tiering reuses the existing MEASURED/DERIVED/ASSUMED machinery unchanged. `source_quality` stamping (Phase 2.5) applies to mechanical rows identically.

## 7. Validation strategy

Layered, input-agnostic:

1. **Formula unit tests (exact math).** Golden cases per rule — e.g. 10 m of 600×400 rectangular duct → `2*(600+400)/1000*10 = 20 m²`, +15% waste → 23 m²; Ø250 round × 8 m → `π·0.25·8 ≈ 6.283 m²`. Boundary tests on gauge thresholds (exact-cut values). Security tests: formulas containing names/calls/attributes must fail validation at load.
2. **Cascade unit tests.** Synthetic vector pages with known label/geometry placements verify each source wins in priority order and un-resolvable routes land `ASSUMED` with the flag set.
3. **End-to-end proofs, two fixtures:**
   - **S101 (real client sheet):** equipment counting over `M-EQPT-NEW` / `M-EQPT-FUTR` (+ xref `M-EQUIP`) — proves the mechanical branch on an actual drawing today.
   - **Generated HVAC sheet (scaffolding only):** we emit a small layer-rich vector PDF (known duct/pipe runs, equipment, labels, mini schedule at scale 1:100) giving exact ground truth for the full duct/pipe pipeline. Marked synthetic everywhere; swapped for a real owner sheet when available. No production code may reference this fixture by name.
4. **Phase 2 regression lock.** All existing tests stay green; electrical BOQ outputs byte-identical (linear rules flow through the constant-expression path).

## 8. Error handling (fail closed, flag for human)

| Failure | Behavior |
| --- | --- |
| Formula load/validation error | Rule excluded + logged; rest of catalog serves normally |
| Missing size variable at eval | Row flagged `ASSUMED`; never zero, never silently skipped |
| Unpriced mechanical catalog item | Existing "unpriced" flag path — no $0 substitution |
| Malformed size label near route | Ignored; cascade falls through; debug log |

## 9. Definition of Done

- Mechanical branch processes both e2e fixtures: S101 equipment counts match manual verification; generated-sheet duct/pipe quantities match hand-computed formula results exactly.
- Every mechanical BOQ number replays from persisted `derivation_json` (formula + inputs).
- All four new YAML rules load without code changes; a deliberately malformed YAML fails validation with a clear error and is excluded fail-closed.
- Phase 2 suite (63 tests) green with identical electrical BOQ outputs.
- `ruff check app tests` clean.

## 10. Open items handed to planning

- Exact regex set for size labels (imperial `12"`, metric `DN150`, `Ø250`, `WxH`) — finalized against generated-sheet + real-label corpus during implementation.
- Schedule-table detection heuristic (which text block constitutes a schedule) — start with header-keyword matching ("DUCT SIZE", "PIPE SCHEDULE"), keep behind config.
- Default ASSUMED sizes per rule — owner to confirm values; ship with clearly-labeled placeholders in YAML.
