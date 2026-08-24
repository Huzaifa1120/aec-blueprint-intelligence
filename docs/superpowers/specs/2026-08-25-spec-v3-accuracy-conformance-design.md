# Spec v3 Accuracy-Conformance Package — Design

**Date:** 2026-08-25
**Status:** Approved in-session (owner approved all sections + Approach B)
**Branch:** `feature/spec-v3-accuracy-conformance`
**Supersedes:** nothing. Amends `docs/AEC-Blueprint-System-Design-Spec-v3.md` §7.3 (see §6 below).
**Validation basis:** full parameter audit + clause-by-clause validation against spec v3, 2026-08-25 (session log; findings summarized in §1).

---

## 1. Problem — conformance debts that are also the biggest accuracy levers

An audit of every accuracy-affecting parameter (geometry constants, 30 assembly YAMLs, cascade tolerances, layer coverage) validated against Design Spec v3 identified six clauses the code does not yet honor. Each is simultaneously a spec violation and a top accuracy lever:

| # | Finding | Spec v3 clause | Verdict |
|---|---------|----------------|---------|
| C1 | Missing/unparseable scale silently defaults to 1:100 (`parsing/scale.py:16-49`, `vector.py:263`); architectural scales fall back to **1:1** (`parsing/routes.py:74-77`); `scale_needs_review()` is dead code | §7.4 "never assumed globally"; title-block/dimension cross-check | Violation |
| C2 | Production pipeline never assigns DERIVED/ASSUMED confidence tiers — everything ships MEASURED/1.0 even when sized from YAML defaults (`e2e/router.py:81-113`); `confidence_tiering.py` imported only by tests | §7.12, §6 canonical model, §15 per-tier tracking | Violation |
| C3 | No source region persisted per BOQ row; click-to-source dormant twice over (no bbox in payload; `PDFViewer src={null}`) | §7.8 `source_region`; §7.13 overlay/click-through; §11 Stage-0 DoD "every number traceable to a highlighted source region" | Violation |
| C4 | Review corrections collected then discarded (`useReviewSession.ts:70-75` sends only `{item_id, action, confidence_tier}`; no storage columns) | §15 "Log human-review corrections" | Violation |
| C5 | Labor computed (`labor_hours`) but never consumed; `estimate.total_labor_cost` hardcoded 0.0 (`persistence.py:485`) | §1(4), §7.14 workforce/labor estimate output | Violation |
| C6 | Dropped routes/rules/symbols warn-and-vanish (`e2e/router.py:477-483, 537-554`; `persistence.py:175-182`) — invisible in payloads and totals | §7.9 spirit ("tagged UNMAPPED, not dropped") extended to broken-rule drops | Extension |
| C7 | Spec text drift: §7.3 example config contradicts shipped owner-approved behavior (FIRE ALARM discipline, RAIN DOWNPIPE field, NCS families) | "This document wins unless explicitly updated" | Amendment required |

Related-but-excluded (documented in §8): waste factor on constant BOM lines, legend-derived clustering threshold (gated behind lighting re-ruling), fuzzy layer matching, multi-page quality gate.

## 2. Owner decisions (in-session rulings)

1. **Scale policy — flag & proceed.** When scale is missing or unconfident, run at assumed 1:100, stamp scale-dependent quantities ASSUMED (forces review), banner on the estimate. Never hard-block.
2. **Source region — bbox only.** Persist page + rectangle per row; exact path-id highlighting stays future work.
3. **Labor — unpriced-flag pattern.** Hours × rate; missing rate → line flagged `unpriced`, excluded from totals, disclosed. Mirrors materials behavior.
4. **Corrections — logged annotation only.** Corrections are stored and displayed but never override computed quantities; replay gate untouched.
5. **Scope — five code violations (C1–C5) plus the spec amendment (C7), extended with the data_quality visibility item (C6); waste-on-constants deferred.**
6. **Delivery — Approach B, two waves.** Wave 1 honesty (zero schema change), Wave 2 traceability (one migration). Each wave independently testable and revertable.

## 3. Wave 1 — Honesty (no schema changes)

### 3.1 Scale handling (C1)

- `app/parsing/scale.py`: extend detection to architectural scales — `1/4"=1'-0"` → denominator 48, `1/8"=1'-0"` → 96, `3/32"=1'-0"` → 128, `3/16"=1'-0"` → 64, `1/2"=1'-0"` → 24 — plus existing electrical/generic `1:N`. Return structured `{scale_str, denominator, status}` where status ∈ {`detected`, `assumed`}.
- Remove the 1:1 fallback in `routes.py:74-77`: any unparseable or absent scale resolves to denominator 100 with `status:"assumed"`, logged loudly once per run.
- Wire `scale_needs_review()` semantics into the e2e router: the run response and persisted payload carry `scale_status` and `scale_str`.
- When `status:"assumed"`, every quantity whose derivation depends on the scale denominator (route lengths and anything computed from them) is stamped `confidence_status:"ASSUMED"` with provenance ref `"scale:assumed_1_100"`. Pure counts (device symbols, fixture kits) keep their own tier. This reuses §7.12 vocabulary exactly and activates existing frontend machinery without new UI concepts (badge, bulk-accept exclusion, scroll-to-first-assumed).
- Frontend: workspace shows a dismissible banner when `scale_status == "assumed"` ("Scale not detected — lengths measured at 1:100 and flagged for review").
- Multi-page mixed-scale PDFs remain single-scale for now (multi-sheet scope is explicitly out of bounds per project rules); noted as a known limitation in the spec doc.

### 3.2 Confidence-tier assignment (C2)

- BOQ lines default to **DERIVED** (score 0.8): every material line is rule-derived arithmetic per §7.11.
- Downgrade to **ASSUMED** (score 0.3) when `size_source == "assumed"` (existing condition, `e2e/router.py:345-349`) or when the row's quantity is scale-dependent under an assumed scale (§3.1).
- Component/Route rows emit real statuses through `confidence_tiering.assign_confidence_status` (module becomes production-wired): layered-vector measured rows MEASURED/1.0; degraded-vector rows keep the ×0.8 multiplier; UNMAPPED components unchanged.
- Contract-change call-out: pinned score assertions in `tests/test_phase1_5_regression.py` are updated deliberately as part of this wave.

### 3.3 Data-quality block (C6)

- Router and persistence accumulate counters at every warn-and-drop site:
  `data_quality = {dropped_routes, dropped_symbols, unmapped_count, degenerate_skipped, fu_corridor_excluded}`
- Emitted in `/api/e2e/run` response, persisted estimate payload, `/api/estimates/{id}/boq`, JSON/XLSX/PDF exports (XLSX/PDF gain a data-quality note section).
- Narration may cite counts verbatim (structured facts pass `verify_no_invented_numbers`).
- No behavioral change to what drops — only visibility.

### 3.4 Spec §7.3 amendment (C7)

Edit `docs/AEC-Blueprint-System-Design-Spec-v3.md` directly:

- Example config: `FIRE ALARM` moves from electrical to a `fire_alarm` discipline pattern.
- `M_SAUDI_RAIN DOWNPIPE` classified plumbing (counted storm-downpipe kit per Phase 4 owner ruling), out of envelope.
- Add NCS family patterns `^(P-)` plumbing, `^(FP-)` fire_protection, `^(FA-)` fire_alarm.
- Changelog entry dated 2026-08-25 citing the Phase 4 owner rulings as the authority.

### 3.5 Wave 1 testing

- Architectural-scale parser unit tests (each pattern → expected denominator; malformed → assumed).
- Scale-flag tests: sheet with no scale → response/payload `scale_status:"assumed"`, length rows ASSUMED, count rows untouched.
- Tier-assignment tests: formula-derived line → DERIVED; size-assumed line → ASSUMED; degraded-vector multiplier preserved.
- Forced-drop test proving each `data_quality` counter increments on its specific loss path.
- Full backend suite green (DOWNPIPE_PIN 11, sheet_metal 48.76 m², FU→40 mm baselines must be byte-identical — Wave 1 changes no quantity math).

## 4. Wave 2 — Traceability (one Alembic migration)

### 4.1 Migration (single revision)

- `boq_items.source_bbox_json` TEXT NULL — `{page, x0, y0, x1, y1}` in PDF points.
- `review_corrections` table — `id PK`, `estimate_id FK`, `boq_item_id FK`, `action`, `confidence_tier`, `reason TEXT NULL`, `corrected_value FLOAT NULL`, `created_at`.
- No new labor columns (`total_labor_cost` exists).

### 4.2 Stable row identities

- Payload exposes persisted `boq_items.id` per row; frontend `normalizeBoq` keys by it; review actions reference it.
- Backend validates `action` ∈ {accept, reject, correct} and `confidence_tier` against enums; rejects free text with 422.

### 4.3 Click-to-source activation (C3)

- Persistence captures route-polyline/component bbox into `source_bbox_json` at BOQ derivation time; `payload.py` emits `source: {page, bbox}`.
- New endpoint `GET /api/sheets/{id}/file` serves stored original PDF bytes → `PDFViewer src` becomes real; dual-panel preview activates.
- Frontend `SourceHighlight` draws the rectangle using existing §4 Y-flip mapping.

### 4.4 Corrections persistence (C4)

- `POST /api/review/actions` accepts optional `reason`, `corrected_value`; writes `review_corrections`.
- Semantics: annotation only. Computed numbers stay canonical until a re-run incorporates better rules; UI renders corrections as annotations; exports gain a corrections annex section.
- Replay gate unchanged.

### 4.5 Labor costing (C5)

- `labor_hours` from `apply_assembly` become BOQ rows: `unit:"hour"`, category from the rule's labor block.
- Rate resolution order: catalog `LaborRate` by category → YAML `hourly_rate` fallback (documented in derivation_json as `rate_source: catalog|yaml`). Neither → `unpriced:true`, excluded from totals exactly like unpriced materials.
- `estimate.total_labor_cost` = Σ priced labor rows; payload/narration disclose unpriced-labor count explicitly.
- Data fix: `access_control_door.yaml` gains missing `hourly_rate` + `category`.

### 4.6 Known blast radius

- Labor rows add new BOQ lines → absolute row-count baselines shift once (e.g., MMC 114-item estimate). Updated in tests deliberately; material-line quantities unchanged.
- Confidence contract changes from Wave 1 carry forward.

### 4.7 Wave 2 testing

- Migration assertion test (columns + table present, incl. reexport/review tables still intact).
- Corrections round-trip: POST with reason/corrected_value → persisted → surfaced in payload/export annex; invalid enum → 422.
- Click-to-source: route-derived rows carry non-null `source_bbox_json`; component-only rows carry their cluster bbox when available, null otherwise (UI renders "region unavailable" — never an empty rectangle).
- Labor unit tests: catalog-rate path, YAML-fallback path, unpriced path; e2e total reconciliation (materials + priced labor == grand total).
- Frontend vitest: stable-ID keying, source normalization feeding SourceHighlight, correction dialog persistence.
- Replay gate green on both fresh and pre-migration estimates (old rows lack bbox → null tolerated).

## 5. Non-negotiables preserved

- AI proposes / geometry calculates / rules derive / humans approve — nothing here lets any model output a number; all additions are deterministic bookkeeping.
- Unit prices and rates stay in catalog/YAML (§7.10 honored; YAML fallback is explicit, provenance-stamped).
- Import PyMuPDF as `pymupdf`.
- No multi-sheet features introduced.
- Every BOQ number remains traceable; traceability now reaches the UI per §11.

## 6. Out of scope (explicitly deferred)

- Waste factor on constant BOM lines (shifts human-approved baselines; separate owner ruling needed).
- Legend-derived clustering threshold wiring (blocked by lighting 26↔23 re-ruling, G9).
- Fuzzy layer matching (determinism-first: normalization + UNMAPPED flagging preferred; future package).
- Multi-page/multi-sheet gate handling.
- path_ids-level highlight fidelity (bbox satisfies §11; path ids remain the named next-migration family after this).
- XREF-prefix classification splitting, sink/floor_drain/cleanout/water_heater mappings (accuracy Tier-2 follow-up package).

## 7. Success criteria

1. A sheet with no detectable scale produces a fully-priced but honestly-flagged estimate: banner + ASSUMED length rows + excluded from bulk accept.
2. Zero BOQ lines ship as MEASURED unless they are direct measurements; every assumption is visible in the tier system.
3. Every drop site in the pipeline increments a counter a human can see in response, payload, exports, and narration.
4. Clicking any BOQ row highlights its source region on a visible drawing.
5. Corrections survive the session: stored, listed in exports, feeding the future §15 refinement loop.
6. Grand total = materials + priced labor, with unpriced lines disclosed, never silently zeroed.
7. All pinned truth baselines hold except the explicitly-called-out contract changes (confidence scores, labor row-count shifts).
