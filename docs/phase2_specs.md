# Phase 2 — Remaining Work Plan

**Status:** Phase 2 Definition of Done partially met. Core pipeline functions (scale detection, route measurement, assembly rules, BOQ computation, catalog CRUD) are implemented and tested. Remaining work focuses on the spreadsheet import endpoint, E2E pipeline integration with the sample electrical PDF, regression test completeness, and trap-constraint verification.

---

## 1. Regression Tests

| # | Task | Description | Estimated Effort | Dependencies | Git Flow Steps | Trap Constraints |
|---|------|-------------|------------------|--------------|----------------|------------------|
| RT1 | **Complete component-count test** | Implement `test_component_counts_from_electrical_sheet` to validate automated component counts (lighting fixtures, switches, outlets, conduit runs, cable tray sections, distribution boards) against human count on the sample electrical PDF, with ±5% tolerance using DBSCAN clustering results. | 2 days | T2 (scale detection), T3 (route lengths), YAML rules loaded; in-memory SQLite session | `feature/phase2-regression-tests`<br>`commit: "feat: add component-count validation test for electrical sheet"` | ✅ AGENTS.md §2 — Geometry calculates, no LLM output<br>✅ trap.md §2 — No hardcoded values; counts from DBSCAN clustering |
| RT2 | **Add E2E pipeline integration test** | Add `test_full_e2e_pipeline` that runs `classify_upload` → `parse_pdf` → `detect_scale` → `measure_routes` → `apply_assembly` → `compute_boq_item` end-to-end with the sample PDF (`MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`), asserting each stage produces deterministic output. | 3 days | RT1 completed; all pipeline functions operational; catalog has price entries for electrical materials | `feature/phase2-e2e-test`<br>`commit: "feat: add full E2E pipeline integration test"` | ✅ AGENTS.md §4 — Full deterministic trail traceability<br>✅ trap.md §1 — AI proposes. Geometry calculates.<br>✅ trap.md §2 — No hardcoded prices; catalog lookup used |
| RT3 | **Add BOQ clickability test** | Implement `test_boq_clickability_to_source_region` to verify every BOQ item includes `source_path_ids` linking back to original PDF vector paths, and that the deterministic trail (PDF → vector paths → clusters → classification → scale → measurement → assembly rules → catalog prices → BOQ) is intact. | 1 day | RT2; `compute_boq_item` returns dict with `source_path_ids` | `feature/phase2-boq-clickability`<br>`commit: "feat: add BOQ clickability traceability test"` | ✅ AGENTS.md §4 — Full deterministic trail traceability<br>✅ trap.md §2 — No blended confidence %; per-line status only |
| RT4 | **Verify unpriced flag test** | Implement `test_unpriced_flag_never_substitutes_zero` to confirm `compute_boq_item(10.0, "UnknownMaterial", session)` returns `unpriced: True`, `total_cost: 0.0`, and note "Material price not found in catalog — flag for review"; never $0 substitution. | 1 day | Catalog CRUD functions (`ingest_material_price`, `get_latest_price`) exist; `compute_boq_item` already implements unpriced flag | `feature/phase2-unpriced-flag`<br>`commit: "feat: verify unpriced flag does not substitute $0"` | ✅ AGENTS.md §17 — Missing price → "unpriced", not $0<br>✅ trap.md §2 — Hardcoded Values: NEVER hardcode material unit prices |

---

## 2. E2E Pipeline Integration

| # | Task | Description | Estimated Effort | Dependencies | Git Flow Steps | Trap Constraints |
|---|------|-------------|------------------|--------------|----------------|------------------|
| EP1 | **Spreadsheet import endpoint** | Implement `POST /api/catalog/import` endpoint that accepts `multipart/form-data` with file field `file`, parses CSV/Excel, validates column headers (`material_name`, `unit`, `unit_price` for materials; `rate_name`, `productivity_rate`, `hourly_rate` for labor), calls `ingest_material_price()` / `ingest_labor_rate()` per row, and returns `{successful, failed, errors: [{row, reason}]}`. | 1 day | Catalog CRUD functions (`ingest_material_price`, `ingest_labor_rate`); column header validation logic | `feature/phase2-spreadsheet-import`<br>`commit: "feat: add spreadsheet import endpoint for catalog prices"` | ✅ AGENTS.md §3 — Unit prices / productivity rates live in catalog DB or YAML — never hardcode in source<br>✅ trap.md §2 — Hardcoded Values: NEVER hardcode material unit prices or labor productivity rates<br>✅ trap.md §3 — Use `python -m pytest`, `python -m ruff check` (not executables) |
| EP2 | **Full E2E pipeline integration** | Wire together `classify_upload` → `parse_pdf` → `detect_scale` → `measure_routes` → `apply_assembly` → `compute_boq_item` in a complete PDF→BOQ pipeline. Ensure scale is detected from title block (not assumed), routes measured at detected scale, assemblies applied from YAML rules, and BOQ items computed with catalog price lookup. Return BOQ items with `confidence_status` (MEASURED/DERIVED/ASSUMED) and `source_path_ids` for frontend clickability. | 3 days | EP1 (spreadsheet import); all pipeline functions (classify_upload, parse_pdf, detect_scale, measure_routes, apply_assembly, compute_boq_item) operational; sample electrical PDF with 1:100 scale | `feature/phase2-e2e-pipeline`<br>`commit: "feat: integrate full E2E pipeline vector-first"` | ✅ AGENTS.md §4 — Scale read from sheet, never assumed<br>✅ trap.md §3 — Scale read from sheet, never assumed<br>✅ trap.md §1 — AI proposes. Geometry calculates.<br>✅ trap.md §2 — No hardcoded values |
| EP3 | **E2E pipeline validation with sample PDF** | Run the integrated E2E pipeline against the sample electrical sheet (`MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf`), verify: classification as "vector", scale detected as "1:100", conduit/cable tray routes measured, assemblies applied, BOQ items computed (priced or unpriced flagged), and human-review UI fields present (`source_path_ids`, `confidence_status`). Fix any detection/clustering failures. | 2 days | EP2 completed; sample PDF fixture available; catalog DB seeded with electrical material prices (via EP1 or direct DB insert) | `feature/phase2-e2e-validation`<br>`commit: "feat: validate E2E pipeline with sample electrical PDF"` | ✅ trap.md §5 — DO NOT build raster/CV fallback before v1 vector MVP proven<br>✅ trap.md §6 — DO NOT estimate raw materials from single-discipline sheets |

---

## 3. YAML Rules Compliance

| # | Task | Description | Estimated Effort | Dependencies | Git Flow Steps | Trap Constraints |
|---|------|-------------|------------------|--------------|----------------|------------------|
| YR1 | **Verify all 8 electrical assembly YAML rules load** | Confirm `load_assembly_rule()` successfully loads all 8 electrical assembly types (`access_control_door`, `switch`, `power_outlet`, `distribution_board`, `cable_tray`, `conduit`, `lighting_outlet`, `socket_outlet`) without any Python code changes. Validate each returns correct `bom`, `labor.installation_hours`, `labor.hourly_rate`, `waste_factor`, and `rule_version`. | 0.5 day | YAML files exist in `data/assemblies/`; `app/assembly/rules.py` `load_assembly_rule()` and `apply_assembly()` already implemented | `feature/phase2-yaml-rules`<br>`commit: "feat: verify all electrical assembly YAML rules load"` | ✅ Rules.md §3.8 — YAML-driven rules, not hardcoded<br>✅ trap.md §2 — Hardcoded Values: NEVER hardcode material unit prices or labor productivity rates<br>✅ trap.md §15 — DO NOT build raster/CV fallback before v1 vector MVP proven |
| YR2 | **Add `persist_assembly_to_db` test coverage** | Add test that `persist_assembly_to_db("cable_tray", project_id, session)` persists assembly and material-price links to DB; verify Assembly, Material, and AssemblyMaterial records created correctly. | 0.5 day | YR1 completed; DB session fixture; `app/db/models/catalog.py` Assembly/ Material models exist | `feature/phase2-yaml-db-persistence`<br>`commit: "feat: add persist_assembly_to_db test coverage"` | ✅ Rules.md §3.8 — YAML-driven rules<br>✅ trap.md §2 — No hardcoded values |

---

## 4. Trap Constraints Verification

| # | Task | Description | Estimated Effort | Dependencies | Git Flow Steps | Trap Constraints |
|---|------|-------------|------------------|--------------|----------------|------------------|
| TC1 | **Import PyMuPDF as `pymupdf`, never `fitz`** | Grep all new files for `import fitz` (must be 0) and confirm `import pymupdf` used exclusively. Add import guard in `conftest.py` or pre-commit hook to enforce. | 0.5 day | All new Python files in `app/` and tests/ | `feature/phase2-trap-import-guard`<br>`commit: "feat: enforce pymupdf import guard, no fitz alias"` | ✅ trap.md §1 — PyMuPDF Alias Breakage: NEVER import `fitz` |
| TC2 | **Verify no hardcoded unit prices or productivity rates** | Search all new code for any float literals used as material unit prices or labor productivity rates. Ensure all prices/rates flow through catalog DB (`ingest_material_price`, `ingest_labor_rate`) or YAML rule `labor.hourly_rate` / `labor.installation_hours`. Add lint rule flagging hardcoded prices. | 1 day | EP1 (spreadsheet import); YAML rules; `compute_boq_item` uses catalog lookup | `feature/phase2-trap-no-hardcoded-prices`<br>`commit: "feat: verify no hardcoded unit prices or rates in source"` | ✅ trap.md §2 — Hardcoded Values: NEVER hardcode material unit prices or labor productivity rates in source code |
| TC3 | **Verify scale read from sheet, never assumed** | Confirm `detect_scale()` reads scale from title block text spans; no hardcoded default of "1:100" except as fallback when scale not found (which triggers `scale_needs_review()`). Ensure `measure_routes()` receives scale from `detect_scale()`, not a hardcoded value. | 0.5 day | scale.py `detect_scale()` implementation; EP2 pipeline integration | `feature/phase2-trap-scale-from-sheet`<br>`commit: "feat: verify scale read from sheet never assumed"` | ✅ trap.md §3 — Scale read from sheet, never assumed<br>✅ trap.md §4 — DO NOT build raster/CV fallback before v1 vector MVP proven |
| TC4 | **Verify ASSUMED forces human review, no bulk-accept** | Confirm BOQ items with `confidence_status: "ASSUMED"` have confidence_score=0.3 and UI forces manual review; no bulk-accept path that bypasses per-item review. | 0.5 day | Confidence tiering logic in `confidence_tiering.py`; EP2 pipeline output | `feature/phase2-trap-assumed-review`<br>`commit: "feat: enforce ASSUMED forces human review"` | ✅ trap.md §7 — No blended confidence %<br>✅ trap.md §8 — ASSUMED forces human review |
| TC5 | **Verify missing price → "unpriced", not $0** | Ensure `compute_boq_item()` returns `unpriced: True` + `total_cost: 0.0` + descriptive note when no catalog price exists; never substitutes $0. Add test covering edge case of material with empty price history. | 0.5 day | `compute_boq_item` implementation in `app/catalog/prices.py` | `feature/phase2-trap-unpriced-flag`<br>`commit: "feat: verify unpriced flag never substitutes $0"` | ✅ AGENTS.md §17 — Missing price → "unpriced", not $0<br>✅ trap.md §2 — Hardcoded Values |
| TC6 | **Verify per-document legend matching, no universal symbol detector** | Confirm component classification uses per-document legend matching + layer name fallback; no universal symbol detector or cross-company symbol library. "Unknown" components marked for human review. | 0.5 day | Component classification logic in `app/ingestion/vector.py` / `app/parsing/` | `feature/phase2-trap-legend-matching`<br>`commit: "feat: verify per-document legend matching only"` | ✅ AGENTS.md §2 — Per-document legend matching first<br>✅ trap.md §2 — No universal symbol detector |

---

## 5. Documentation

| # | Task | Description | Estimated Effort | Dependencies | Git Flow Steps | Trap Constraints |
|---|------|-------------|------------------|--------------|----------------|------------------|
| DOC1 | **Update Phase 2 Specification with remaining tasks** | Reflect completed/remaining tasks in `docs/Phase-2-Specification.md`: add API spec for `POST /api/catalog/import`, E2E pipeline diagram updated with spreadsheet import step, revised trap-constraint compliance matrix, and updated Definition of Done gate list. | 1 day | All task definitions above; existing spec sections | `feature/phase2-update-spec`<br>`commit: "docs: update Phase 2 specification with remaining work plan"` | N/A (documentation task) |
| DOC2 | **Add trap-constraint compliance matrix section** | Document each task's compliance with AGENTS.md §1-17 and trap.md §1-6 constraints; mark ✅ compliant or ⚠️ requires review. This matrix should be the authoritative reference for PR reviewers. | 0.5 day | DOC1 completed; all task definitions referencing specific trap constraints | `feature/phase2-update-trap-matrix`<br>`commit: "docs: add trap-constraint compliance matrix for Phase 2"` | N/A |
| DOC3 | **Record git workflow updates for Phase 2** | Update `docs/GIT_WORKFLOW.md` with Phase 2 branch naming convention (`feature/phase2-<short-description>`) and any new commit message types specific to this phase (e.g., `feat: phase2 spreadsheet import endpoint`, `fix: phase2 scale detection fallback`). | 0.5 day | Git workflow already established in `GIT_WORKFLOW.md`; no breaking changes needed | `feature/phase2-update-git-workflow`<br>`commit: "docs: update git workflow for Phase 2"` | N/A |

---

## 6. Git Workflow Updates

| # | Task | Description | Estimated Effort | Dependencies | Git Flow Steps | Trap Constraints |
|---|------|-------------|------------------|--------------|----------------|------------------|
| GW1 | **Create feature branch from `dev`** | `git checkout -b feature/phase2-spreadsheet-import dev` then develop endpoint; after completion, merge into `dev` with `--no-ff`. | 0.25 day | `dev` branch must be green (tests passing) before merge | `feature/phase2-spreadsheet-import` → merge into `dev`<br>`commit: "merge: phase2 spreadsheet import into dev"`<br>`git merge --no-ff feature/phase2-spreadsheet-import -m "merge: phase2 spreadsheet import into dev"` | ✅ trap.md §3 — Use `python -m pytest`, `python -m ruff check` (not executables) |
| GW2 | **Merge feature branches into `dev`** | After each task (RT1-RT4, EP1-EP3, YR1-YR2, TC1-TC6, DOC1-DOC3, GW1-GW6), merge into `dev` with `--no-ff` to keep history explicit. Ensure `python -m pytest -q` passes after each merge. | 0.25 day per merge | All preceding tasks green; ruff lint `python -m ruff check app tests` passes | `git checkout dev` → `git merge --no-ff <feature-branch> -m "merge: <description> into dev"` → `git push -u origin dev` | ✅ AGENTS.md §11 — Run `python -m pytest` after any task<br>✅ AGENTS.md §12 — Run `python -m ruff check app tests` |
| GW3 | **Merge `dev` into `main` for Phase 2 release** | When all Phase 2 Definition of Done gates are met (regression tests green, E2E pipeline validated, trap constraints verified), merge `dev` into `main` with `--no-ff`. Tag release (e.g., `v2.0.0`). | 0.25 day | All tasks complete; all tests passing; trap compliance matrix green | `git checkout main` → `git merge --no-ff dev -m "merge: dev into main for production release v2.0.0"` → `git push -u origin main` | ✅ trap.md §15 — DO NOT build raster/CV fallback before v1 vector MVP proven<br>✅ trap.md §4 — Pip upgrades: never inside running venv |

---

## Summary Table: Critical Path & Effort

| Phase | Task ID | Task Name | Effort | Dependent On |
|-------|---------|-----------|--------|--------------|
| **P0 Critical** | RT1 | Complete component-count test | 2 days | RT2, T3, YAML rules |
| | EP1 | Spreadsheet import endpoint | 1 day | Catalog CRUD |
| | EP2 | Full E2E pipeline integration | 3 days | EP1, all pipeline functions |
| | EP3 | E2E pipeline validation with sample PDF | 2 days | EP2 |
| | RT2 | Add E2E pipeline integration test | 3 days | EP2 |
| **P1 Support** | YR1 | Verify all 8 electrical assembly YAML rules load | 0.5 day | YAML files exist |
| | TC1-TC6 | Trap-constraint verification (6 tasks) | 4 days | All code changes |
| **Documentation** | DOC1-DOC3 | Update specs, matrix, git workflow | 2 days | All task flow complete |
| **Total Estimated Effort** | | **~22 workdays (≈ 1 month)** | | |

**Note:** Effort estimates assume existing codebase stability (catalog CRUD, assembly rules, scale detection, route measurement already implemented). Contingency for unexpected PDF parsing quirks on the sample electrical sheet should be allocated within EP3.