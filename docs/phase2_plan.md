# Phase 2 — Remaining Work Plan (Super‑powers mode)

*Use the **superpowers:subagent-driven-development** sub‑skill to tick off tasks one‑by‑one.  Each checklist item is a `‑ [ ]` that you replace with `‑ [x]` when the task is done.  All new code must respect the **trap.md** constraints listed in the “Compliance” column.*

---

## Legend
| Symbol | Meaning |
|--------|---------|
| `‑ [ ]` | Not started (replace with `‑ [x]` when complete) |
| `✅`   | Constraint Satisfied (shown in “Compliance” column) |
| `⚠️`   | Requires review – must be resolved before merge |

---

## 1. Regression Tests  (in `tests/test_phase2_regression.py`)

| # | Task | Description | Estimated effort | Dependencies | Compliance (trap.md / AGENTS.md) |
|---|------|-------------|------------------|--------------|-----------------------------------|
| **RT1** | **Component‑count test** | Implement `test_component_counts_from_electrical_sheet` – count lighting fixtures, switches, outlets, conduit runs, cable‑tray sections, distribution boards from DBSCAN clusters and assert ±5 % tolerance vs manual count. | 2 days | Scale detection (detect_scale), route measurement (measure_routes), YAML rules loaded | ✅ AGENTS.md §2 – Geometry calculates, no LLM output<br>✅ trap.md §2 – No hardcoded values; counts from DBSCAN |
| **RT2** | **E2E pipeline integration test** | Add `test_full_e2e_pipeline` that runs `classify_upload → parse_pdf → detect_scale → measure_routes → apply_assembly → compute_boq_item` on the sample PDF, asserting each stage produces deterministic output. | 3 days | RT1, all pipeline functions, catalog prices seeded | ✅ AGENTS.md §4 – Full deterministic trail traceability<br>✅ trap.md §1 – AI proposes. Geometry calculates.<br>✅ trap.md §2 – No hardcoded prices; catalog lookup used |
| **RT3** | **BOQ clickability test** | Implement `test_boq_clickability_to_source_region` – verify every BOQ item includes `source_path_ids` linking back to original PDF vector paths; traceability chain intact. | 1 day | RT2, `compute_boq_item` returns dict with `source_path_ids` | ✅ AGENTS.md §4 – Full deterministic trail traceability<br>✅ trap.md §2 – No blended confidence %; per‑line status only |
| **RT4** | **Un‑priced flag test** | Implement `test_unpriced_flag_never_substitutes_zero` – confirm `compute_boq_item(10.0, "UnknownMaterial", session)` returns `unpriced: True`, `total_cost: 0.0`, note “Material price not found in catalog — flag for review”; never $0. | 1 day | Catalog CRUD (`ingest_material_price`, `get_latest_price`) exist; `compute_boq_item` already has unpriced flag | ✅ AGENTS.md §17 – Missing price → “unpriced”, not $0<br>✅ trap.md §2 – Hardcoded Values: NEVER hardcode material unit prices |

---

## 2. E2E Pipeline Integration  (wire‑up in a new endpoint or CLI helper)

| # | Task | Description | Estimated effort | Dependencies | Compliance |
|---|------|-------------|------------------|--------------|------------|
| **EP1** | **Spreadsheet import endpoint** | Implement `POST /api/catalog/import` – accept `multipart/form-data` with file field `file`, parse CSV/Excel, validate columns, call `ingest_material_price()` / `ingest_labor_rate()`, return `{successful, failed, errors: [{row, reason}]}`. | 1 day | Catalog CRUD functions, column‑header validation logic | ✅ AGENTS.md §3 – Unit prices / productivity rates live in catalog DB or YAML — never hardcode in source<br>✅ trap.md §2 – Hardcoded Values: NEVER hardcode material unit prices or labor productivity rates<br>✅ trap.md §3 – Use `python -m pytest`, `python -m ruff check` (not executables) |
| **EP2** | **Full E2E pipeline integration** | Wire together `classify_upload → parse_pdf → detect_scale → measure_routes → apply_assembly → compute_boq_item` in a complete PDF→BOQ pipeline. Scale detected from title block (never assumed), routes measured at detected scale, assemblies applied from YAML rules, BOQ items computed with catalog price lookup. Return BOQ items with `confidence_status` (MEASURED/DERIVED/ASSUMED) and `source_path_ids` for frontend clickability. | 3 days | EP1, all pipeline functions operational, sample electrical PDF with 1:100 scale | ✅ AGENTS.md §4 – Scale read from sheet, never assumed<br>✅ trap.md §3 – Scale read from sheet, never assumed<br>✅ trap.md §1 – AI proposes. Geometry calculates.<br>✅ trap.md §2 – No hardcoded values |
| **EP3** | **E2E pipeline validation with sample PDF** | Run the integrated pipeline against `MMC‑JVC‑CD‑ELEC‑3902_AC‑WIRE‑Model.pdf`. Verify: classification as “vector”, scale “1:100”, conduit/cable‑tray routes measured, assemblies applied, BOQ items computed (priced or unpriced‑flagged), and human‑review UI fields present (`source_path_ids`, `confidence_status`). Fix any detection/clustering failures. | 2 days | EP2 completed, sample PDF fixture, catalog DB seeded with electrical material prices (via EP1 or direct DB insert) | ✅ trap.md §5 – DO NOT build raster/CV fallback before v1 vector MVP proven<br>✅ trap.md §6 – DO NOT estimate raw materials from single‑discipline sheets |

---

- [x] **EP1** – Spreadsheet import endpoint implemented and tested (see `POST /api/catalog/import` smoke test).
- [x] **EP2** – E2E pipeline endpoint implemented and tested (see `POST /api/e2e/run` smoke test with sample PDF).
- [skip] **EP3** – E2E pipeline validation with sample PDF (skipped per user request; full end-to-end PDF validation not run).
- [ ] **RT1** – Component‑count test (plan marked complete; actual test body pending pytest green verification).
- [ ] **RT2** – E2E pipeline integration test (plan marked complete; actual test body pending pytest green verification).
- [ ] **RT3** – BOQ clickability test (plan marked complete; actual test body pending pytest green verification).
- [ ] **RT4** – Un‑priced flag test (plan marked complete; actual test body pending pytest green verification).

## 3. YAML Rules Compliance

| # | Task | Description | Estimated effort | Dependencies | Compliance |
|---|------|-------------|------------------|--------------|------------|
| **YR1** | **Verify all 8 electrical assembly YAML rules load** | Confirm `load_assembly_rule()` successfully loads all electrical assembly types (`access_control_door`, `switch`, `power_outlet`, `distribution_board`, `cable_tray`, `conduit`, `lighting_outlet`, `socket_outlet`) without any Python code changes. Validate each returns correct `bom`, `labor.installation_hours`, `labor.hourly_rate`, `waste_factor`, and `rule_version`. | 0.5 day | YAML files exist in `data/assemblies/`; `app/assembly/rules.py` `load_assembly_rule()` and `apply_assembly()` already implemented | ✅ Rules.md §3.8 – YAML‑driven rules, not hardcoded<br>✅ trap.md §2 – Hardcoded Values: NEVER hardcode material unit prices or labor productivity rates<br>✅ trap.md §15 – DO NOT build raster/CV fallback before v1 vector MVP proven |
| **YR2** | **Add `persist_assembly_to_db` test coverage** | Add test that `persist_assembly_to_db("cable_tray", project_id, session)` persists assembly and material‑price links to DB; verify Assembly, Material, and AssemblyMaterial records created correctly. | 0.5 day | YR1 completed; DB session fixture; `app/db/models/catalog.py` Assembly/ Material models exist | ✅ Rules.md §3.8 – YAML‑driven rules<br>✅ trap.md §2 – No hardcoded values |

---

## 4. Trap‑Constraints Verification  (run after every code change)

| # | Task | Description | Estimated effort | Dependencies | Compliance |
|---|------|-------------|------------------|--------------|------------|
| **TC1** | **Import PyMuPDF as `pymupdf`, never `fitz`** | Grep all new files for `import fitz` (must be 0) and confirm `import pymupdf` used exclusively. Add import guard in `conftest.py` or pre‑commit hook to enforce. | 0.5 day | All new Python files in `app/` and tests/ | ✅ trap.md §1 – PyMuPDF Alias Breakage: NEVER import `fitz` |
| **TC2** | **Verify no hardcoded unit prices or productivity rates** | Search all new code for any float literals used as material unit prices or labor productivity rates. Ensure all prices/rates flow through catalog DB (`ingest_material_price`, `ingest_labor_rate`) or YAML rule `labor.hourly_rate` / `labor.installation_hours`. Add lint rule flagging hardcoded prices. | 1 day | EP1 (spreadsheet import), YAML rules, `compute_boq_item` uses catalog lookup | ✅ trap.md §2 – Hardcoded Values: NEVER hardcode material unit prices or labor productivity rates in source code |
| **TC3** | **Verify scale read from sheet, never assumed** | Confirm `detect_scale()` reads scale from title block text spans; no hardcoded default of “1:100” except as fallback when scale not found (which triggers `scale_needs_review()`). Ensure `measure_routes()` receives scale from `detect_scale()`, not a hardcoded value. | 0.5 day | scale.py `detect_scale()` implementation; EP2 pipeline integration | ✅ trap.md §3 – Scale read from sheet, never assumed<br>✅ trap.md §4 – DO NOT build raster/CV fallback before v1 vector MVP proven |
| **TC4** | **Verify ASSUMED forces human review, no bulk‑accept** | Confirm BOQ items with `confidence_status: "ASSUMED"` have confidence_score=0.3 and UI forces manual review; no bulk‑accept path that bypasses per‑item review. | 0.5 day | Confidence tiering logic in `confidence_tiering.py`; EP2 pipeline output | ✅ trap.md §7 – No blended confidence %<br>✅ trap.md §8 – ASSUMED forces human review |
| **TC5** | **Verify missing price → "unpriced", not $0** | Ensure `compute_boq_item()` returns `unpriced: True` + `total_cost: 0.0` + descriptive note when no catalog price exists; never substitutes $0. Add test covering edge case of material with empty price history. | 0.5 day | `compute_boq_item` implementation in `app/catalog/prices.py` | ✅ AGENTS.md §17 – Missing price → “unpriced”, not $0<br>✅ trap.md §2 – Hardcoded Values |
| **TC6** | **Verify per‑document legend matching, no universal symbol detector** | Confirm component classification uses per‑document legend matching + layer name fallback; no universal symbol detector or cross‑company symbol library. “Unknown” components marked for human review. | 0.5 day | Component classification logic in `app/ingestion/vector.py` / `app/parsing/` | ✅ AGENTS.md §2 – Per‑document legend matching first<br>✅ trap.md §2 – No universal symbol detector |

---

## 5. Documentation Updates

| # | Task | Description | Estimated effort | Dependencies | Compliance |
|---|------|-------------|------------------|--------------|------------|
| **DOC1** | **Update Phase 2 Specification with remaining tasks** | Reflect completed/remaining tasks in `docs/Phase-2-Specification.md`: add API spec for `POST /api/catalog/import`, E2E pipeline diagram updated with spreadsheet import step, revised trap‑constraint compliance matrix, and updated Definition‑of‑Done gate list. | 1 day | All task definitions above; existing spec sections | N/A (documentation) |
| **DOC2** | **Add trap‑constraint compliance matrix section** | Document each task’s compliance with AGENTS.md §1‑17 and trap.md §1‑6 constraints; mark ✅ compliant or ⚠️ requires review. This matrix should be the authoritative reference for PR reviewers. | 0.5 day | DOC1 completed; all task definitions referencing specific trap constraints | N/A |
| **DOC3** | **Record git workflow updates for Phase 2** | Update `docs/GIT_WORKFLOW.md` with Phase 2 branch‑naming convention (`feature/phase2-<short-description>`) and any new commit‑message types specific to this phase (e.g., `feat: phase2 spreadsheet import endpoint`, `fix: phase2 scale detection fallback`). | 0.5 day | Git workflow already established in `GIT_WORKFLOW.md`; no breaking changes needed | N/A |

---

## 6. Git‑Workflow Updates  (three‑layer model: `main` ← `dev` ← `feature/*`)

| # | Task | Description | Estimated effort | Dependencies | Compliance |
|---|------|-------------|------------------|--------------|------------|
| **GW1** | **Create feature branch from `dev`** | `git checkout -b feature/phase2-spreadsheet-import dev` then develop endpoint; after completion, merge into `dev` with `--no-ff`. | 0.25 day | `dev` branch must be green (tests passing) before merge | ✅ trap.md §3 – Use `python -m pytest`, `python -m ruff check` (not executables) |
| **GW2** | **Merge feature branches into `dev`** | After each task (RT1‑RT4, EP1‑EP3, YR1‑YR2, TC1‑TC6, DOC1‑DOC3, GW1‑GW6), merge into `dev` with `--no-ff` to keep history explicit. Ensure `python -m pytest -q` passes after each merge. | 0.25 day per merge | All preceding tasks green; ruff lint `python -m ruff check app tests` passes | ✅ AGENTS.md §11 – Run `python -m pytest` after any task<br>✅ AGENTS.md §12 – Run `python -m ruff check app tests` |
| **GW3** | **Merge `dev` into `main` for Phase 2 release** | When all Phase 2 Definition‑of‑Done gates are met (regression tests green, E2E pipeline validated, trap constraints verified), merge `dev` into `main` with `--no-ff`. Tag release (e.g., `v2.0.0`). | 0.25 day | All tasks complete; all tests passing; trap compliance matrix green | ✅ trap.md §15 – DO NOT build raster/CV fallback before v1 vector MVP proven<br>✅ trap.md §4 – Pip upgrades: never inside running venv |

---

## Summary – Critical Path & Effort

| Phase | Task ID | Task Name | Effort | Depends On |
|-------|---------|-----------|--------|------------|
| **P0 Critical** | RT1 | Complete component‑count test | 2 days | RT2, T3, YAML rules |
| | EP1 | Spreadsheet import endpoint | 1 day | Catalog CRUD |
| | EP2 | Full E2E pipeline integration | 3 days | EP1, all pipeline functions |
| | EP3 | E2E pipeline validation with sample PDF | 2 days | EP2 |
| | RT2 | Add E2E pipeline integration test | 3 days | EP2 |
| **P1 Support** | YR1 | Verify all 8 electrical assembly YAML rules load | 0.5 day | YAML files exist |
| | TC1‑TC6 | Trap‑constraint verification (6 tasks) | 4 days | All code changes |
| **Documentation** | DOC1‑DOC3 | Update specs, matrix, git workflow | 2 days | All task flow complete |
| **Total Estimated Effort** | | **~22 work‑days (≈ 1 month)** | | |

**Note:** Effort estimates assume existing codebase stability (catalog CRUD, assembly rules, scale detection, route measurement already implemented). Contingency for unexpected PDF parsing quirks on the sample electrical sheet should be allocated within EP3.

---

### How to use this plan

1. **Start a feature branch** (GW1) – e.g. `git checkout -b feature/phase2-spreadsheet-import dev`.
2. **Pick the first tick‑boxed task** (RT1 or EP1) and implement it.
3. **When a task is done**, replace `‑ [ ]` with `‑ [x]`, commit with a meaningful message (e.g. `feat: add component‑count validation test for electrical sheet`), then merge into `dev` (GW2).
4. **Repeat** until every `‑ [ ]` is `‑ [x]`.
5. **When all are done**, merge `dev` into `main` (GW3) and tag the release.

---

**Acknowledgment** – Once you confirm you’re ready to start, I will begin the first task (e.g., create the feature branch, write the first regression test, or implement the spreadsheet‑import endpoint) and keep you posted on progress. At the end of Phase 2 (when all tasks are `‑ [x]` and the three‑layer merge is complete) I will give you a final acknowledgment that Phase 2 is finished, including a summary of what was delivered and the final Git state (`main`, `dev`, feature branches).

*Tell me which task you’d like to start with, or let me run the first step automatically.*