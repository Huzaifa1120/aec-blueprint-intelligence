# Design Spec — v3 Conformance & Gap Closure

Date: 2026-08-23
Status: Approved (scope: Full A+B + narration-with-fallback; approach: persistence spine first)
Supersedes: nothing. Complements `AEC-Blueprint-System-Design-Spec-v3.md` (sole source of truth) and the Phase 3 design/plan docs.

---

## 1. Goal

Close every code-addressable gap left open through Phase 3 and build the spec-v3 components that do not exist yet, so the system matches v3 §6–§10 architecture end-to-end:

| # | Gap | Spec ref | Wave |
|---|-----|----------|------|
| G1 | Provenance never persists (`BoqItem`/`Measurement` unwritten); no replay proof | §8, §9 | A1 |
| G2 | Evaluator minors: nested-unary exponent-cap bypass; variable exponents unbounded; `validate_rule_file` AttributeError on non-dict YAML root | Phase 3 deferred | A2 |
| G3 | `LAYER` table absent — classification not persisted per sheet; no `layer_id` FKs | §7.3, §8 | T0+A5a+B4 |
| G4 | No general Legend/Schedule-Attribute-Block Parser; no `SCHEDULE_BLOCK` table | §7.6, §8 | T0+A5b+B4 |
| G5 | Text–Layer Association Walker absent | §7.5 | A5c+B4 |
| G6 | Unmapped measured elements silently skipped instead of `UNMAPPED` | §7.9, §7.12 | B4 |
| G7 | No output exports (JSON/XLSX/PDF) | §7.14 | A4 |
| G8 | No narrated scope of work | §7.14 | A3 |
| G9 | Clustering contract gap (bbox-touching elongated paths) | Phase 3 ledger | HUMAN-GATED task |

## 2. Non-goals

- No raster-path work (quarantined by human ruling A; ORB/SIFT successor untouched).
- No Phase 4 plumbing/fire discipline work.
- No multi-sheet / revision-diff features (Phase 7 scope).
- No change to any Phase 1/2/3 BOQ output value — electrical + mechanical regression locks stay byte-identical where they lock today.
- No LLM/vision model ever outputs a final quantity, length, area, or price (narration formats structured numbers verbatim; it never computes).

## 3. Architecture

Persistence spine first (approach 1, user-approved). Everything else hangs off it or runs beside it behind a narrow integration seam.

```
e2e/run ──persist──► SheetExtraction (in-memory bundle)
                        │  built by pure builders: routes/components/sizes (existing),
                        │  layer_registry (A5a), schedules (A5b), text_walker (A5c),
                        │  unmapped (B4)
                        ▼
              persistence.py (single writer, one transaction)
                        ▼
        Project ▸ Drawing ▸ Sheet ▸ {Layer, Component, Route, Space,
                                     ScheduleBlock, TextAnnotation,
                                     Measurement, BoqItem, Estimate}
                        ▼
   estimates/router.py ── GET boq │ GET replay (determinism proof)
   exports/router.py   ── GET export?format=json|xlsx|pdf
   narration/router.py ── GET narration  (Template default; Anthropic if key)
```

Integration seam (the one rule that makes parallel waves safe): **wave tasks never edit shared files concurrently.** Pure modules are built in parallel against frozen interfaces; a single integrator task wires them into `e2e/router.py`, `persistence.py`, and `main.py`.

## 4. Components

### 4.1 Unified schema migration (T0 — serial, first)

One Alembic revision creates everything so later tasks never collide on migrations:

- `layers`: id, sheet_id FK, ocg_name, classified_discipline, human_override_discipline nullable.
- `schedule_blocks`: id, sheet_id FK, block_type (`legend` | `attribute_schedule`), page_region JSON, entries_json.
- `text_annotations`: id, sheet_id FK, text, bbox_json, ocg_layer nullable, component_id/route_id/space_id FKs all nullable.
- `layer_id` nullable FK columns on `components`, `routes`, `spaces` (string `source_layer` retained).
- `sheets.source_quality` column if absent (quality flag lives on measurements' parents per §8).

### 4.2 A1 — Persistence spine + replay proof (G1)

- `POST /api/e2e/run` gains optional `persist: bool = False`, `project_id: UUID | None`. Default preserves every existing behavior/test.
- New `app/e2e/persistence.py`: `persist_extraction(session, extraction, project_id) -> estimate_id`. Single transaction; re-run on same sheet **replaces** prior measurement/BOQ/annotation rows (idempotent); `rule_version` stamped on Measurements.
- `Measurement` rows: one per source element (route length / component instance), `calculation_method` = formula id or `linear_multiplier`.
- `BoqItem` rows carry `derivation_json` + `size_source` exactly as computed response-side today.
- New `app/estimates/router.py`:
  - `GET /api/estimates/{id}/boq` — persisted rows out.
  - `GET /api/estimates/{id}/replay` — re-evaluates every stored `derivation_json` through the formula engine from recorded inputs; asserts equality with stored quantities. Any mismatch → HTTP 409 with the offending item ids. This endpoint **is** the §9 DoD gate ("replays from persisted derivation_json").

### 4.3 A2 — Evaluator & loader hardening (G2, Phase 3 leftover)

- Deep-unwrap chained unary ops before the constant-exponent check; reject non-constant exponents above a bounded iteration count (fail closed, `FormulaValidationError`).
- `_validate_rule_data` treats a non-mapping YAML root as an invalid rule (warn + exclude), never AttributeError.

### 4.4 A5a — Layer registry pure module (G3)

- `data/layer_classification.yaml` (human-editable, §7.3 pattern list) + `app/parsing/layer_registry.py::classify_layers(ocg_registry) -> [LayerRow]`.
- Regex precedence order preserved; unmatched → `unclassified` (never guessed).

### 4.5 A5b — Schedule/legend parser pure module (G4)

- `app/parsing/schedules.py::detect_blocks(spans) -> [ScheduleBlock]`: grid-alignment + header-keyword heuristics; multiple legends per sheet supported; typed blocks.
- Cascade keeps working unchanged; `resolve_route_size` accepts optional pre-parsed blocks (pure additive param) so A5b never edits `sizes.py` internals beyond that hook.

### 4.6 A5c — Text–layer walker pure module (G5)

- `app/parsing/text_walker.py`: (1) probe PyMuPDF span→OCG membership; (2) fallback content-stream `BDC/EMC` tracker validated on the sample sheet; (3) spatial join span↔nearest component centroid/route polyline within threshold.
- Output: `[TextAnnotationRow]`; geometry measures, text confirms.

### 4.7 B4 — Integrator + UNMAPPED (G3/G4/G5/G6 wiring)

Single serial task (owns `e2e/router.py`, `e2e/persistence.py`, `main.py` after A1 merged):
- Wire the A5a/A5b/A5c builder outputs into `SheetExtraction` and the persist transaction.
- UNMAPPED: clusters whose layer resolves to no assembly rule emit `unmapped_items` in the run response AND persist as `Component` rows with `confidence_status="UNMAPPED"` (visible, never dropped, never forced — §7.9).
- Register `estimates`/`exports`/`narration` routers in `main.py`.

### 4.8 A4 — Exports (G7)

- `app/exports/`: json/xlsx/pdf writers reading persisted Estimate rows.
- XLSX via openpyxl (installed). PDF via reportlab — **added to pyproject dependencies** (BSD-style license; see D4).
- Every line carries material, quantity, unit, confidence_status, size_source, unpriced flag; unpriced renders flagged, never $0.

### 4.9 A3 — Narrator (G8)

- `app/narration/`: `NarratorProvider` protocol → `TemplateNarrator` (deterministic default, always available) → `AnthropicNarrator` (import-gated SDK, activates only when `ANTHROPIC_API_KEY` set; SDK **not** added to pyproject — mirrors the heavy-deps policy).
- Input = persisted structured BOQ only, never raw images. Guard test: every numeric token in output exists verbatim in the BOQ payload.

### 4.10 Human-gated task (G9)

Clustering bbox-touching fix: implemented behind a flag, executed only after the owner re-baselines counts (lighting 26 vs 23 ruling). Not part of any wave's exit criteria.

## 5. Data flow

Run → classify (quality gate, unchanged) → parse → scale → routes/components/sizes (unchanged math) → builders enrich (layers/blocks/annotations/unmapped) → respond (+persist when asked) → estimates API serves/replays → exports render → narrator narrates. All numbers trace: response row ⇄ BoqItem.derivation_json ⇄ Measurement.raw_value ⇄ vector path ids.

## 6. Error handling

- Fail-closed everywhere: invalid rule YAML excluded with warning (existing gate); malformed schedule block skipped + logged, never guessed; replay mismatch = hard 409 (non-determinism is a defect, not a warning).
- Persist failures roll back the whole transaction (no partial sheets).
- Narrator: template fallback on any provider error; missing key logs once and pins template mode.

## 7. Testing strategy

- Per-task golden/unit tests (TDD, red→green) + targeted suite runs inside each sub-agent.
- Controller runs FULL suite + ruff between batches; regression locks (Phase 1/2/3) green at every merge point.
- W1 exit gate: replay endpoint returns 200 with zero mismatches on a persisted sample-sheet run.
- Narrator number-verbatimism test; exports round-trip test (export → parse → equals BOQ).
- Suite baseline today: 135 passed + 1 xfail; must never regress.

## 8. Decision log (for future agents — do not re-litigate)

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | One unified Alembic migration (T0) before parallel work | Parallel branches editing migrations ⇒ forked heads; schema-first removes the collision class entirely |
| D2 | `persist=False` default on `/api/e2e/run` | Zero behavior change for existing callers/tests; persistence is opt-in until frontend adopts it |
| D3 | Builders are pure modules; single integrator owns `e2e/router.py`/`persistence.py` | File-collision-free parallel dispatch; the seam is one dataclass (`SheetExtraction`) |
| D4 | reportlab added to pyproject; anthropic SDK stays import-gated | reportlab needed for §7.14 PDF export (BSD, no AGPL exposure); Anthropic is optional runtime enhancement — consistent with heavy-deps policy |
| D5 | Replay mismatch = HTTP 409 hard failure | §2 guiding principle: determinism is the product; silent drift would violate it |
| D6 | Hanger kits remain qty 1.0/route until owner rules otherwise | Current shipped semantics; changing without ruling would silently move BOQ numbers |
| D7 | ASSUMED default sizes stay as-is, always stamped `size_source="assumed"` | Owner confirmation still owed; honest provenance meanwhile |
| D8 | Clustering bbox-fix implemented-but-flagged, not merged to behavior | Re-baselines human-approved counts (lighting 26→23 question); owner ruling owed |
| D9 | UNMAPPED items persist + surface; never priced | §7.9 verbatim; pricing an unmapped element would fabricate scope |

## 9. Human gates outstanding (not code)

1. S101 FUTR=276 visual verification.
2. Lighting count re-baseline ruling (unblocks D8 execution).
3. Hanger-kit semantics confirmation (D6 stands meanwhile).
4. Real HVAC sheet supply (fixture swap trigger).

## 10. Parallel execution map (sub-agent dispatch)

```
T0 (serial): unified migration
Batch A — 7 parallel sub-agents, disjoint files:
  A1 persistence spine        A2 evaluator/loader hardening
  A3 narrator                 A4 exports
  A5a layer registry module   A5b schedule parser module   A5c text walker module
Checkpoint: controller full suite + ruff + merge batch A
Batch B — B4 integrator (serial; owns e2e/router.py, e2e/persistence.py, main.py)
Final: full suite + ruff + regression locks + docs (Phases.md, Memory.md) update
```
