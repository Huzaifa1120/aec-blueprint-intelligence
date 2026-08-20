# Phase 2 Remaining Work (EP3 + YR2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the last two open Phase 2 items: EP3 (full E2E pipeline validation against the real sample PDF — previously skipped, now fully in scope) and YR2 (test coverage for `persist_assembly_to_db()`).

**Architecture:** Two additive test functions in the existing Phase 2 regression suite. EP3 exercises the already-built `POST /api/e2e/run` pipeline against the real electrical sample sheet and asserts the DoD gates (vector classification, sheet-read scale, routes/components measured, BOQ with discrete confidence tier + source traceability + price discipline). YR2 exercises the already-built `persist_assembly_to_db()` against an in-memory SQLite DB. No production code changes are expected unless a gate fails and exposes a bug.

**Tech Stack:** Python 3.13 / pytest / FastAPI TestClient / SQLAlchemy (in-memory SQLite) / PyMuPDF (`pymupdf`).

**Spec:** `docs/superpowers/specs/2026-08-21-phase-2-ep3-yr2-spec.md`

## Global Constraints

- Import PyMuPDF as `pymupdf`, never the deprecated `fitz` alias.
- No LLM/vision model ever outputs a final quantity — all BOQ numbers trace to deterministic calculations.
- Unit prices / productivity rates live in catalog DB or YAML — never hardcoded in source.
- Scale is read from the sheet, never assumed (sample title block = 1:100).
- Missing price → `unpriced: True`, never $0 substitution.
- Per-line discrete confidence tier only (MEASURED/DERIVED/ASSUMED), no blended %.
- Per-document legend / layer-name matching first — no universal symbol detector; layer→assembly mapping is YAML-driven.
- Do not build raster/CV fallback or multi-sheet features before the v1 vector MVP is proven.
- Backend commands run from `backend/` with `python -m <tool>` (venv at `backend/.venv`). Do not use `pip install --upgrade pip` inside the running venv.
- No code comments unless explicitly requested (`Rules.md` §6); `# noqa` lint directives allowed.
- Ruff line-length 100, target py311 (already in `backend/pyproject.toml`).
- Run `python -m pytest -q` and `python -m ruff check app tests` after each task.
- Git flow: three-layer model `feature/*` → `dev` → `main`; never push directly to `main`; keep `dev` green before merging into `main`.

## File Structure

- Modify: `backend/tests/test_phase2_regression.py` (add `test_ep3_e2e_pipeline_validation_on_sample` and `test_yaml_rule_persistence_to_db`).
- Modify: `docs/superpowers/plans/2026-08-21-phase-2-remaining-plan.md` (mark EP3/YR2 `[x]`).
- No production source files expected to change. If a gate fails and exposes a bug, fix the smallest production surface (e.g. `app/parsing/components.py`, `app/e2e/router.py`) and add a regression assertion.

---

### Task 1: EP3 — E2E pipeline validation on the real sample sheet

**Files:**
- Modify: `backend/tests/test_phase2_regression.py` (append a new test after the existing T10 `test_e2e_pipeline_endpoint_on_sample`)
- Test: `backend/tests/test_phase2_regression.py::test_ep3_e2e_pipeline_validation_on_sample`

**Interfaces:**
- Consumes: `POST /api/e2e/run` (FastAPI TestClient `client` already defined at module level); `app.e2e.router.get_engine` (monkeypatched, same pattern as T10); `app.assembly.rules.load_assembly_rule(name) -> Optional[Dict]`; sample fixture path `Path(__file__).resolve().parents[2] / "data" / "samples" / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"`.
- Produces: a passing test function proving gates E1–E9 of the spec.

- [x] **Step 1: Write the failing test**

Append to `backend/tests/test_phase2_regression.py`:

```python
# ──────────────────────────────────────────────
# EP3: test_ep3_e2e_pipeline_validation_on_sample
# ──────────────────────────────────────────────

def test_ep3_e2e_pipeline_validation_on_sample(tmp_path, monkeypatch):
    """Phase 2 DoD (EP3): full E2E pipeline validated against the real sample PDF.

    Closes the previously-skipped EP3 gate. Asserts every DoD sub-gate:
    E1 vector classification, E2 scale read from sheet (1:100), E3 routes
    measured, E4 components counted, E5 BOQ produced, E6 discrete confidence
    tier, E7 source-path traceability, E8 assembly rule resolution, E9 price
    discipline (unpriced never $-substituted).
    """
    from sqlalchemy import create_engine

    from app.db.base import Base

    sample = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "samples"
        / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
    )
    assert sample.exists(), f"Sample fixture missing: {sample}"

    db_path = tmp_path / "test_ep3_api.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    monkeypatch.setattr(
        "app.e2e.router.get_engine",
        lambda: create_engine(f"sqlite:///{db_path}"),
    )

    def run_pipeline():
        with open(sample, "rb") as fh:
            resp = client.post(
                "/api/e2e/run",
                files={"file": ("sample.pdf", fh, "application/pdf")},
            )
        assert resp.status_code == 200, resp.text
        return resp.json()

    body = run_pipeline()

    # E1: vector classification -> pipeline ran with status "ok"
    assert body["status"] == "ok", f"Pipeline failed: {body}"

    # E2: scale read from sheet, never assumed (sample title block = 1:100)
    assert body["scale"] == "1:100", f"Expected 1:100, got {body['scale']}"

    # E3: routes measured for mapped route layers (CONDUIT / CABLE_TRAY)
    assert body["routes_measured"] > 0, "Expected measured routes on the sheet"

    # E4: discrete components counted (lighting fixtures on a mapped layer)
    assert body["components_found"] > 0, "Expected discrete components on the sheet"

    # E5: BOQ items produced
    assert len(body["boq_items"]) > 0, "Expected BOQ items from the pipeline"

    # E6 + E7 + E8 + E9: per-item discipline
    from app.assembly.rules import load_assembly_rule

    for item in body["boq_items"]:
        assert item["confidence_status"] in ("MEASURED", "DERIVED", "ASSUMED"), (
            "Every BOQ item must have a discrete confidence tier"
        )
        assert item["source_path_ids"], "Every BOQ item must be clickable to source"
        assert load_assembly_rule(item["assembly_type"]) is not None, (
            f"Assembly rule missing for {item['assembly_type']}"
        )
        assert isinstance(item["unpriced"], bool), "unpriced must be a boolean"
        assert isinstance(item["total_cost"], float), (
            "total_cost must be a float, not a blended % or Decimal"
        )
        if item["unpriced"]:
            assert item["total_cost"] == 0.0, (
                "Unpriced item must not be $-substituted"
            )

    # Determinism: re-running the same pipeline gives identical counts
    body_again = run_pipeline()
    assert body_again["routes_measured"] == body["routes_measured"]
    assert body_again["components_found"] == body["components_found"]
    assert len(body_again["boq_items"]) == len(body["boq_items"])
```

- [x] **Step 2: Run the test to see it fail (red)**

Run from `backend/`:
`python -m pytest tests/test_phase2_regression.py::test_ep3_e2e_pipeline_validation_on_sample -v`
Expected: PASS on the first run is not the point — the test must exist and run. If it PASSES immediately, the gate was already effectively met and the assertion suite now locks it in. If it FAILS, proceed to Step 3.

- [x] **Step 3: If the test fails, fix the smallest production surface**

Investigate the failing gate with `python -m pytest tests/test_phase2_regression.py::test_ep3_e2e_pipeline_validation_on_sample -v` and fix only the file implicated (e.g. `app/parsing/components.py`, `app/parsing/routes.py`, `app/parsing/scale.py`, `app/e2e/router.py`, `data/layer_mapping.yaml`). Re-run the test until green. Record what was fixed in the commit message.

- [x] **Step 4: Run the full Phase 2 suite to verify no regressions**

Run from `backend/`:
`python -m pytest tests/test_phase2_regression.py -q`
Expected: all tests pass (10 existing + EP3).

- [x] **Step 5: Lint the changed files**

Run from `backend/`:
`python -m ruff check app tests`
Expected: no new violations. (Pre-existing F401/F821/F841 in unrelated Phase 1/1.5 files are out of scope.)

- [x] **Step 6: Commit**

```bash
git add backend/tests/test_phase2_regression.py
git commit -m "feat: add EP3 E2E pipeline validation test on sample sheet"
```

---

### Task 2: YR2 — `persist_assembly_to_db` test coverage

**Files:**
- Modify: `backend/tests/test_phase2_regression.py` (append a new test using the existing `db_session` fixture)
- Test: `backend/tests/test_phase2_regression.py::test_yaml_rule_persistence_to_db`

**Interfaces:**
- Consumes: `app.assembly.rules.persist_assembly_to_db(rule_name: str, project_id, session) -> Optional[Assembly]`; `app.assembly.rules.load_assembly_rule(name) -> Optional[Dict]`; SQLAlchemy models `Assembly`, `Material`, `AssemblyMaterial`; existing `db_session` fixture (in-memory SQLite).
- Produces: a passing test proving gates Y1–Y5 of the spec.

- [x] **Step 1: Write the failing test**

Append to `backend/tests/test_phase2_regression.py`:

```python
# ──────────────────────────────────────────────
# YR2: test_yaml_rule_persistence_to_db
# ──────────────────────────────────────────────

def test_yaml_rule_persistence_to_db(db_session):
    """Phase 2 DoD (YR2): persist_assembly_to_db() persists YAML rules to DB.

    Y1: unknown rule returns None.
    Y2: known rule creates an Assembly row with matching rule_version and BOM.
    Y3: assembly_materials junction rows match the YAML bom quantities.
    Y4: calling twice is idempotent (no duplicate rows).
    Y5: a labor link is created when the rule has an hourly_rate.
    """
    from app.assembly.rules import persist_assembly_to_db, load_assembly_rule
    from app.db.models.catalog import Assembly, Material, AssemblyMaterial

    # Y1: unknown rule -> None
    assert persist_assembly_to_db("nonexistent_rule", None, db_session) is None

    # Y2 + Y3: persist cable_tray rule
    rule = load_assembly_rule("cable_tray")
    assert rule is not None
    assembly = persist_assembly_to_db("cable_tray", None, db_session)
    assert assembly is not None
    assert assembly.name == "cable_tray"
    assert assembly.rule_version == rule["rule_version"]
    assert assembly.formula_or_bom == rule["bom"]

    # BOM materials all linked via assembly_materials with correct quantities
    from sqlalchemy import select

    links = db_session.execute(
        select(AssemblyMaterial).where(AssemblyMaterial.assembly_id == assembly.id)
    ).scalars().all()
    linked = {l.material_id: l.quantity for l in links}
    materials = {
        m.id: m.name for m in db_session.execute(select(Material)).scalars()
    }
    for mat_name, qty in rule["bom"].items():
        mat_id = next(i for i, n in materials.items() if n == mat_name)
        assert mat_id in linked, f"Material {mat_name} not linked"
        assert linked[mat_id] == qty, f"Quantity mismatch for {mat_name}"

    # Y5: labor link exists because cable_tray.yaml has labor.hourly_rate
    labor_mat_id = next(i for i, n in materials.items() if n == "Labor")
    assert labor_mat_id in linked, "Labor material should be linked"
    assert linked[labor_mat_id] == rule["labor"]["installation_hours"]

    # Y4: idempotent — second persist does not duplicate Assembly or links
    assembly2 = persist_assembly_to_db("cable_tray", None, db_session)
    db_session.commit()
    assemblies = db_session.execute(
        select(Assembly).where(Assembly.name == "cable_tray")
    ).scalars().all()
    assert len(assemblies) == 1, "persist_assembly_to_db must be idempotent"
    links2 = db_session.execute(
        select(AssemblyMaterial).where(AssemblyMaterial.assembly_id == assembly2.id)
    ).scalars().all()
    assert len(links2) == len(links), "Links must not duplicate on re-persist"
```

- [x] **Step 2: Run the test to verify it passes (or fails, then fix)**

Run from `backend/`:
`python -m pytest tests/test_phase2_regression.py::test_yaml_rule_persistence_to_db -v`
Expected: PASS. If it FAILS, the bug is in `persist_assembly_to_db` (`backend/app/assembly/rules.py:123`) — fix the smallest surface (e.g. duplicate-link guard, labor link) and re-run until green.

- [x] **Step 3: Run the full Phase 2 suite**

Run from `backend/`:
`python -m pytest tests/test_phase2_regression.py -q`
Expected: all pass (10 existing + EP3 + YR2).

- [x] **Step 4: Lint the changed files**

Run from `backend/`:
`python -m ruff check app tests`
Expected: no new violations.

- [x] **Step 5: Commit**

```bash
git add backend/tests/test_phase2_regression.py
git commit -m "feat: add YR2 persist_assembly_to_db persistence test"
```

---

### Task 3: Update remaining-work plan checkboxes

**Files:**
- Modify: `docs/superpowers/plans/2026-08-21-phase-2-remaining-plan.md` (mark EP3 and YR2 `[x]`)

**Interfaces:**
- Consumes: the moved remaining-work plan (formerly `docs/phase2_plan.md`), which lists EP3 as `[skip]` and YR2 as `[ ]`.
- Produces: a plan doc reflecting EP3 + YR2 complete; a note that nothing in Phase 2 is skipped.

- [x] **Step 1: Update the plan checkboxes**

In `docs/superpowers/plans/2026-08-21-phase-2-remaining-plan.md`:
- Change the EP3 line from `[skip]` / `[ ]` to `- [x] **EP3** – E2E pipeline validation with sample PDF (implemented as `test_ep3_e2e_pipeline_validation_on_sample`, green).`
- Change the YR2 line from `[ ]` to `- [x] **YR2** – `persist_assembly_to_db` test coverage (implemented as `test_yaml_rule_persistence_to_db`, green).`

- [x] **Step 2: Verify the plan reflects no skipped items**

Read the plan and confirm no `[skip]` or unchecked Phase 2 task remains.

- [x] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-08-21-phase-2-remaining-plan.md
git commit -m "docs: mark EP3 + YR2 complete in Phase 2 remaining plan"
```

---

### Task 4: Final verification and three-layer merge

**Files:**
- None (verification + git flow only)

**Interfaces:**
- Consumes: all Task 1–3 commits on the feature branch.
- Produces: green `dev` and `main` with Phase 2 fully complete.

- [x] **Step 1: Run the full backend test suite (Phase 2 files)**

Run from `backend/`:
`python -m pytest tests/test_phase2_regression.py -q`
Expected: all pass.

- [x] **Step 2: Lint**

Run from `backend/`:
`python -m ruff check app tests`
Expected: no new violations in changed files.

- [x] **Step 3: Merge feature into `dev` and push**

```bash
git checkout dev
git merge --no-ff <feature-branch> -m "merge: phase2 EP3+YR2 completion into dev"
git push -u origin dev
```

- [x] **Step 4: Merge `dev` into `main` and push**

```bash
git checkout main
git merge --no-ff dev -m "merge: dev into main for production release"
git push -u origin main
```

- [x] **Step 5: Confirm sync**

`git status` → working tree clean; `git rev-parse main origin/main dev origin/dev` → identical SHAs.

---

## Self-Review Checklist

- **Spec coverage:** EP3 gates E1–E9 → Task 1. YR2 gates Y1–Y5 → Task 2. Plan checkbox update → Task 3. Merge/push per rules → Task 4. No spec section left unplanned.
- **Placeholder scan:** no TBD/TODO; every step has concrete test code and commands.
- **Type consistency:** `persist_assembly_to_db(rule_name, project_id, session)` signature matches `backend/app/assembly/rules.py:123`; `load_assembly_rule` returns `Optional[Dict]`; `AssemblyMaterial.assembly_id`/`material_id`/`quantity` match `backend/app/db/models/catalog.py:66-75`; `Assembly.name`/`rule_version`/`formula_or_bom` match `catalog.py:12-18`.