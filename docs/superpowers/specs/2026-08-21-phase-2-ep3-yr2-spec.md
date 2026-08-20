# Phase 2 Remaining Work — EP3 + YR2 Design Spec

**Project:** AEC Blueprint Intelligence System  
**Date:** 2026-08-21  
**Phase:** 2 — Full Electrical discipline (remaining items)  
**Status:** In progress — closes the last two open Phase 2 tasks

---

## 1. Purpose

Phase 2 core pipeline (ingestion, clustering, scale, routes, components, YAML
rules, catalog, E2E endpoint) is implemented, tested (10/10 green), and pushed
to GitHub. Two plan items remain open from `docs/superpowers/plans/2026-08-21-phase-2-remaining-plan.md`:

1. **EP3** — E2E pipeline validation with the sample PDF (previously skipped;
   now fully in scope, nothing skipped).
2. **YR2** — test coverage for `persist_assembly_to_db()`.

This spec defines exactly what EP3 and YR2 must verify and how they will be
validated. It is the design of record for the plan that implements them.

---

## 2. Constraints (from AGENTS.md / Rules.md / trap.md)

- **No LLM/vision model outputs a final quantity** — every BOQ number traces to
  deterministic geometry/rules. `AI proposes. Geometry calculates.`
- **Import PyMuPDF as `pymupdf`, never `fitz`.**
- **Unit prices / productivity rates live in catalog DB or YAML — never
  hardcoded in source.**
- **Scale read from sheet, never assumed** — `detect_scale()` reads the title
  block; `scale_needs_review()` flags absence.
- **Missing price → `unpriced: True`, never $0 substitution.**
- **Per-line discrete confidence tier** (MEASURED/DERIVED/ASSUMED), no blended %.
- **Per-document legend / layer-name matching first** — no universal symbol
  detector. Layer→assembly mapping is YAML-driven.
- **Do not build raster/CV fallback or multi-sheet features before v1 vector
  MVP is proven.**
- **Do not estimate raw materials from a single-discipline sheet.**
- Backend commands run from `backend/` with `python -m <tool>` (venv at
  `backend/.venv`).

---

## 3. EP3 — E2E Pipeline Validation with Sample PDF

### 3.1 Scope

Run the full integrated pipeline against the real electrical sample sheet
`data/samples/MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf` via the public endpoint
`POST /api/e2e/run`, and assert each DoD gate below. This closes the previously
skipped EP3 item — it is **not** optional.

### 3.2 Required assertions (DoD gates)

| # | Gate | Assertion | Source |
|---|------|-----------|--------|
| E1 | Vector classification | `POST /api/e2e/run` returns `status == "ok"` (pipeline ran, i.e. the PDF classified as vector). | `classify_upload` → `app/ingestion/router.py` |
| E2 | Scale read from sheet | `body["scale"] == "1:100"` (sample title block is 1:100). | `detect_scale` → `app/parsing/scale.py` |
| E3 | Routes measured | `body["routes_measured"] > 0` for mapped route layers (CONDUIT / CABLE_TRAY). | `measure_routes` → `app/parsing/routes.py` |
| E4 | Components counted | `body["components_found"] > 0` (lighting fixtures on mapped layer). | `count_components` → `app/parsing/components.py` |
| E5 | BOQ produced | `len(body["boq_items"]) > 0`. | `_boq_line` → `app/e2e/router.py` |
| E6 | Confidence tiering | Every BOQ item has `confidence_status in {"MEASURED","DERIVED","ASSUMED"}`. | `app/parsing/confidence_tiering.py` |
| E7 | Source traceability | Every BOQ item has non-empty `source_path_ids` (clickable to PDF region). | `count_components` / `measure_routes` |
| E8 | Assembly mapping | Every BOQ item's `assembly_type` resolves via `load_assembly_rule()` (YAML-driven). | `layer_to_assembly` → `app/parsing/layer_map.py` |
| E9 | Price discipline | Every BOQ item has `unpriced` flag; `total_cost` is float; unpriced items have `total_cost == 0.0` (never $-substituted) and descriptive note. | `compute_boq_item` → `app/catalog/prices.py` |

### 3.3 How it is tested

A new test function `test_ep3_e2e_pipeline_validation_on_sample` in
`backend/tests/test_phase2_regression.py` that:

- Uploads the sample PDF to `POST /api/e2e/run` (in-memory or tmp SQLite via
  `monkeypatch` on `app.e2e.router.get_engine`, matching the existing T10
  pattern).
- Asserts gates E1–E9 above.
- Re-runs the pipeline and asserts deterministic output (same counts/routes on
  second run).

> Note: gate E9 "unpriced has `total_cost == 0.0`" — catalog may or may not
> contain prices during the test. The assertion is structural: the `unpriced`
> key exists, the value is boolean, and if `unpriced is True` then
> `total_cost == 0.0`. No price values are asserted from a hardcoded expectation.

---

## 4. YR2 — `persist_assembly_to_db` Test Coverage

### 4.1 Scope

Add test coverage for `persist_assembly_to_db(rule_name, project_id, session)`
in `backend/app/assembly/rules.py:123`. The function is currently untested
(only a docstring reference in the test file).

### 4.2 Required assertions

| # | Gate | Assertion |
|---|------|-----------|
| Y1 | Unknown rule | `persist_assembly_to_db("nonexistent", None, session)` returns `None`. |
| Y2 | Assembly persisted | For `"cable_tray"` (or `"conduit"`), an `Assembly` row exists with `name == rule_name`, `rule_version` matching the YAML, and `formula_or_bom` populated. |
| Y3 | Materials linked | `assembly_materials` junction rows exist; each material in the YAML `bom` is represented, with correct `quantity`. |
| Y4 | Idempotent | Calling the function twice with the same rule does not duplicate Assembly/material rows (existing links reused). |
| Y5 | Labor link | If the YAML rule has `labor.hourly_rate`, a `Labor` material link exists with quantity = `installation_hours`. |

### 4.3 How it is tested

A new test function `test_yaml_rule_persistence_to_db` (and a small helper) in
`backend/tests/test_phase2_regression.py` using the existing in-memory SQLite
`db_session` fixture.

---

## 5. Success Criteria

- `python -m pytest tests/test_phase2_regression.py -q` → all pass (10 existing
  + EP3 test + YR2 test).
- `python -m ruff check app tests` → no new violations in changed files.
- Phase 2 plan checkbox for EP3 and YR2 marked `[x]`.
- No feature beyond the scope of EP3/YR2 is added (YAGNI).

---

## 6. Out of Scope (explicitly)

- Raster/CV fallback work (Phase 1.5, already done).
- Multi-sheet / whole-project ingestion (Phase 7).
- Frontend changes (ReviewOverlay routing is a Phase 1 follow-up, not Phase 2 DoD).
- Tagging a release (`v2.0.0` tag) — deferred unless requested.

---

## 7. References

- `docs/superpowers/plans/2026-08-20-phase-2-electrical-plan.md` — original plan
- `docs/superpowers/plans/2026-08-21-phase-2-remaining-plan.md` — remaining-work plan (EP3 marked skipped; this spec supersedes that skip)
- `docs/superpowers/specs/2026-08-20-phase-2-electrical-spec.md` — Phase 2 spec
- `docs/Phases.md` — phase status