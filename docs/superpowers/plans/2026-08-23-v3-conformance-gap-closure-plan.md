# v3 Conformance & Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all Phase 3 code-addressable gaps and build the missing spec-v3 components (persistence spine + replay proof, LAYER/SCHEDULE_BLOCK/annotations schema, layer registry, legend/schedule parser, text-layer walker, UNMAPPED tiering, JSON/XLSX/PDF exports, narrated scope of work).

**Architecture:** Persistence spine first (`SheetExtraction` bundle → single-writer transaction → estimates API with determinism-replay proof). Seven parallel batch-A tasks own disjoint files against frozen interfaces defined by Task 1; one serial integrator (Task 9) owns shared files (`e2e/router.py`, `e2e/persistence.py`, `main.py`). See spec §10 dispatch map.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, PyMuPDF (`import pymupdf`), openpyxl, reportlab (new dep), restricted-AST formula engine (existing), pytest + ruff.

## Global Constraints

- No LLM/vision model ever outputs a final quantity/length/area/price. Narration formats structured numbers verbatim only.
- Unit prices live in catalog DB/YAML — never hardcoded in source. Unpriced items flagged, never $0-substituted.
- Import PyMuPDF as `pymupdf` (never `fitz`). No `eval()`/`exec()` anywhere.
- Anthropic SDK stays import-gated (NOT added to pyproject). reportlab IS added to pyproject (BSD license).
- Suite baseline: 135 passed + 1 xfail. It may grow; it may never regress. Ruff clean at every checkpoint.
- Tests run FROM `backend/`: `backend/.venv/Scripts/python.exe -m pytest ...` (or activated venv `python -m pytest`).
- Branch: `feature/v3-conformance-gap-closure`. Commit messages prefixed `feat(v3c):` / `test(v3c):` / `fix(v3c):`. On `index.lock` error: sleep 3s and retry. NEVER commit `data/samples/*`.
- Spec of record: `docs/superpowers/specs/2026-08-23-v3-conformance-gap-closure-design.md`.

---

### Task 1: Extraction dataclasses + unified schema migration (T0 — SERIAL, runs alone)

**Files:**
- Create: `backend/app/e2e/extraction.py`
- Create: `backend/alembic/versions/a7f3c9d21e55_v3_conformance_schema.py`
- Modify: `backend/app/db/models/geometry.py` (add Layer model here too — no other task touches this file in batch A)
- Create: `backend/app/db/models/extraction.py` (Layer, ScheduleBlock, TextAnnotation ORM models)
- Modify: `backend/app/db/models/__init__.py` (re-export new models)
- Test: `backend/tests/test_v3_schema.py`

**Interfaces (FROZEN — every batch-A task imports these):**
```python
# app/e2e/extraction.py
from dataclasses import dataclass, field

@dataclass
class LayerRow:
    ocg_name: str
    classified_discipline: str          # electrical|mechanical|architectural|envelope|unclassified|...

@dataclass
class ScheduleBlockRow:
    block_type: str                     # "legend" | "attribute_schedule"
    page_region: dict                   # {x0,y0,x1,y1}
    entries: list[dict]                 # [{"cells": [...]}, ...] rows of the block

@dataclass
class TextAnnotationRow:
    text: str
    bbox: tuple[float, float, float, float]
    ocg_layer: str | None = None
    component_index: int | None = None  # index into SheetExtraction.components
    route_index: int | None = None      # index into SheetExtraction.routes

@dataclass
class ComponentRow:
    component_type: str | None          # None ⇒ UNMAPPED
    layer_ocg: str
    x: float
    y: float
    confidence_status: str = "MEASURED"
    confidence_score: float = 1.0
    source_path_ids: list[str] = field(default_factory=list)

@dataclass
class RouteRow:
    route_type: str
    layer_ocg: str
    length_m: float
    confidence_status: str = "MEASURED"
    confidence_score: float = 1.0
    size_json: dict | None = None       # cascade provenance {width_mm..,source,ref}

@dataclass
class SheetExtraction:
    sheet_name: str | None = None
    page_number: int | None = None
    scale: str | None = None
    discipline: str | None = None
    source_quality: str = "layered_vector"
    rule_version: str = "v3c-1"
    layers: list[LayerRow] = field(default_factory=list)
    components: list[ComponentRow] = field(default_factory=list)
    routes: list[RouteRow] = field(default_factory=list)
    schedule_blocks: list[ScheduleBlockRow] = field(default_factory=list)
    text_annotations: list[TextAnnotationRow] = field(default_factory=list)
```

ORM models follow existing file conventions (see `app/db/models/geometry.py`): `Layer(layer_name unique-per-sheet via sheet_id+ocg_name, classified_discipline String(50), human_override_discipline nullable)`, `ScheduleBlock(block_type String(30), page_region_json String(500), entries_json Text)`, `TextAnnotation(text Text, bbox_json String(200), ocg_layer nullable, component_id/route_id/space_id nullable FKs)`, plus `layer_id` nullable FK on Component/Route/Space.

- [ ] **Step 1: Write failing schema test**

```python
# backend/tests/test_v3_schema.py
"""v3 conformance schema — tables + FKs exist per spec §8."""
from sqlalchemy.orm import Session as OrmSession
from app.db.models.extraction import Layer, ScheduleBlock, TextAnnotation


def test_new_tables_in_metadata():
    names = {t for t in Base.metadata.tables}
    assert {"layers", "schedule_blocks", "text_annotations"} <= names


def test_layer_fk_on_geometry_models():
    from app.db.models.geometry import Component, Route, Space
    for model in (Component, Route, Space):
        assert hasattr(model, "layer_id")
```
(add `from app.db.base import Base` import)

- [ ] **Step 2: Run** `python -m pytest tests/test_v3_schema.py -v` → FAIL (ImportError)
- [ ] **Step 3: Implement** models + dataclasses exactly as specified above; create migration with `revision = "a7f3c9d21e55"`, `down_revision = "5bf57251ec38"`, ops: `create_table` ×3, `add_column("layer_id", sa.Uuid(), nullable=True)` + ForeignKey on components/routes/spaces.
- [ ] **Step 4: Run** `python -m pytest tests/test_v3_schema.py tests/test_migrations.py -v` → PASS
- [ ] **Step 5:** `alembic upgrade head` against dev DB succeeds.
- [ ] **Step 6: Commit** `feat(v3c): unified conformance schema + frozen extraction interfaces`

---

### Task 2 (A1): Persistence spine + replay proof — PARALLEL BATCH A

Owns ONLY: `app/e2e/persistence.py` (new), `app/estimates/` (new package), `app/e2e/router.py` (A1 is the ONLY batch-A task allowed to touch it; Task 9 takes ownership after), `backend/tests/test_persistence_spine.py` (new).

**Interfaces:**
- Consumes: `SheetExtraction` et al. from `app.e2e.extraction`; `evaluate_formula(formula_str: str, variables: dict) -> float` from `app.assembly.formulas`.
- Produces:
```python
def persist_extraction(db: OrmSession, project_id: uuid.UUID | None,
                       extraction: SheetExtraction) -> uuid.UUID  # returns estimate_id
```
Idempotency: if a Sheet with same drawing/sheet_name exists under the project, DELETE its measurements/boq_items/cascade children then re-insert (replace strategy). Creates Project(name="Default Project") when project_id None.
Estimate endpoints: `GET /api/estimates/{id}/boq` → rows; `GET /api/estimates/{id}/replay` → 200 `{checked:N, mismatches:[]}` or 409 `{detail, mismatches:[boq_item_ids]}`.

- [ ] **Step 1: Failing tests** — cover: (a) round-trip persist→boq equals input quantities; (b) second persist same sheet replaces rows (no duplicates); (c) replay 200 zero mismatches; (d) replay 409 when stored formula tampered (update derivation_json directly in DB); (e) unpriced items keep flag.
```python
# backend/tests/test_persistence_spine.py
import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession
from app.db.session import get_engine
from app.e2e.extraction import (SheetExtraction, RouteRow, LayerRow)
from app.e2e.persistence import persist_extraction
from app.estimates.router import router as estimates_router


def _client():
    app = FastAPI()
    app.include_router(estimates_router)
    return TestClient(app)


def _extraction() -> SheetExtraction:
    return SheetExtraction(
        sheet_name="TEST-SHEET", page_number=1, scale="1:100",
        layers=[LayerRow("M-DUCT", "mechanical")],
        routes=[RouteRow("duct", "M-DUCT", 12.5,
                         size_json={"width_mm": 600, "height_mm": 400,
                                    "source": "label", "ref": "600x400"})],
    )


def test_round_trip_and_replace():
    with OrmSession(get_engine()) as db:
        est1 = persist_extraction(db, None, _extraction())
        est2 = persist_extraction(db, None, _extraction())
        assert est1 != est2
    c = _client()
    body = c.get(f"/api/estimates/{est2}/boq").json()
    assert body["routes"][0]["length_m"] == 12.5
    assert body["routes"][0]["size_json"]["source"] == "label"


def test_replay_ok_then_tamper_409():
    with OrmSession(get_engine()) as db:
        est = persist_extraction(db, None, _extraction())
    c = _client()
    assert c.get(f"/api/estimates/{est}/replay").status_code == 200
    # tamper: store an impossible formula result
    from app.db.models.estimate import BoqItem
    with OrmSession(get_engine()) as db:
        item = db.query(BoqItem).filter_by(estimate_id=est).first()
        d = json.loads(item.derivation_json or "{}")
        d["formula"], d["inputs"] = "1 + 1", {}
        item.derivation_json = json.dumps(d)
        db.commit()
    r = c.get(f"/api/estimates/{est}/replay")
    assert r.status_code == 409
```
(BoqItem rows are created per material line; for routes without derivations store `derivation_json={"linear_per_m": qty/length, "inputs": {"length_m": L}}` so replay covers legacy scaling too — recompute `qty == linear_per_m * length_m`.)

- [ ] **Step 2: Run** → FAIL (modules missing)
- [ ] **Step 3: Implement** persistence.py + estimates/router.py. Replay semantics: for each BoqItem parse derivation_json; branch: `formula` → `abs(evaluate_formula(f, inputs) - quantity) <= 1e-6*max(1,quantity)`; `linear_per_m` → same vs `linear_per_m*length_m`; `gauge_lookup` → equality of recorded resolved value; none → skip (counted unchecked).
- [ ] **Step 4: Wire A1 slice of e2e/router.py**: params `persist: bool = False, project_id: uuid.UUID | None = None`; build minimal SheetExtraction from existing `routes`/`components` lists (map size dicts → RouteRow.size_json); on persist, call persist_extraction inside the existing OrmSession block; response gains `"estimate_id"` only when persist=true. Default-off keeps every existing test byte-identical.
- [ ] **Step 5: Full targeted suite** `python -m pytest tests/test_persistence_spine.py tests/test_phase2_regression.py tests/test_phase3_regression.py -v` → PASS (locks prove default-off safety)
- [ ] **Step 6: Commit** `feat(v3c): persistence spine + replay determinism gate (G1)`

---

### Task 3 (A2): Evaluator & loader hardening — PARALLEL BATCH A

Owns ONLY: `app/assembly/formulas.py`, `app/assembly/rules.py`, `tests/test_formulas.py`, `tests/test_rules_formulas.py`. [Phase 3 leftovers G2]

**Interfaces:** unchanged public API; strictly tighter rejection.

- [ ] **Step 1: Failing tests**
```python
def test_pow_rejects_nested_unary_huge_exponent():
    with pytest.raises(FormulaValidationError):
        evaluate_formula("2 ** --5000", {})

def test_pow_rejects_variable_bound_huge_exponent():
    with pytest.raises(FormulaValidationError):
        evaluate_formula("base ** k", {"base": 2, "k": 999999})

def test_validate_rule_file_list_root_is_invalid_not_crash(tmp_path):
    p = tmp_path / "bad.yaml"; p.write_text("- just\n- a\n- list\n")
    assert validate_rule_file(str(p)).errors  # no AttributeError
```
- [ ] **Step 2: Run** → FAIL (first two raise TypeError/Overflow today; third raises AttributeError)
- [ ] **Step 3: Implement** — move the exponent bound from parse-time constant-check to eval-time: in `_eval` binary-op branch, `if isinstance(node.op, ast.Pow) and abs(right) > 1000: raise FormulaValidationError(...)`. This single check closes nested-unary AND variable-exponent bypasses uniformly. In `_validate_rule_data`: `if not isinstance(data, dict): errors.append("rule root must be a mapping")` before any `.get` access.
- [ ] **Step 4: Run** targeted + `tests/test_phase3_regression.py` → PASS (golden math untouched: exponents ≤1000 unaffected)
- [ ] **Step 5: Commit** `fix(v3c): eval-time exponent bound closes unary/var bypasses; list-root YAML guarded (G2)`

---

### Task 4 (A3): Narrator — PARALLEL BATCH A

Owns ONLY: `app/narration/` (new package: `__init__.py`, `providers.py`, `router.py`), `tests/test_narrator.py`.

**Interfaces:**
```python
# providers.py
class NarrationResult(typing.TypedDict):
    narrative: str
    provider: str            # "template" | "anthropic"

class NarratorProvider(Protocol):
    name: str
    def narrate(self, boq_payload: dict) -> NarrationResult: ...

def get_provider() -> NarratorProvider   # anthropic iff env key set AND sdk importable else template
```
Endpoint `GET /api/narration/estimates/{estimate_id}` loads persisted BOQ (same shape as `/boq`), calls provider, 404 on unknown id, template fallback on ANY provider exception (log once).

- [ ] **Step 1: Failing tests** — template narrator produces sections (Summary/Materials/Labor/Unpriced flags); **number-verbatimism guard**:
```python
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")

def test_no_invented_numbers():
    payload = _small_payload()           # quantities {12.5, 3.0}, totals {87.5}
    res = TemplateNarrator().narrate(payload)
    allowed = {"12.5", "3.0", "87.5"} | {str(len(payload["materials"]))}
    for n in _NUM_RE.findall(res["narrative"]):
        assert n in allowed, f"invented number {n}"
```
Anthropic provider: unit-tested with a stubbed client injection (`_call_client` seam); real SDK never invoked in tests.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (template renders deterministic sentences from rows; anthropic adapter builds prompt containing ONLY serialized payload + instruction "you may not introduce numbers"). 
- [ ] **Step 4: Run** targeted → PASS. **Step 5: Commit** `feat(v3c): scope-of-work narrator, template default + gated Anthropic adapter (G8)`

---

### Task 5 (A4): Exports — PARALLEL BATCH A

Owns ONLY: `app/exports/` (new: `json_export.py`, `xlsx_export.py`, `pdf_export.py`, `router.py`), `pyproject.toml` (add `reportlab>=4`), `tests/test_exports.py`.

**Interfaces:** `GET /api/exports/estimates/{id}/export?format=json|xlsx|pdf` → StreamingResponse/file download; writers signature `render(rows: dict) -> bytes`. Rows shape = `/api/estimates/{id}/boq` payload (consumes Task 2's contract; implement against that documented shape — integration live in Task 9).

- [ ] **Step 1:** `pip install reportlab` in venv + add to pyproject dependencies.
- [ ] **Step 2: Failing tests** — json round-trip equality; xlsx written→openpyxl read-back cell equality (incl. unpriced flag column, confidence_status, size_source); pdf starts `%PDF-`; unknown format → 422.
- [ ] **Step 3: Implement.** Every exported line carries material, quantity, confidence_status, size_source, unpriced; unpriced shows "UNPRICED — review required", never $0.
- [ ] **Step 4: Run** targeted → PASS. **Step 5: Commit** `feat(v3c): BOQ exports json/xlsx/pdf (G7)`

---

### Task 6 (A5a): Layer registry pure module — PARALLEL BATCH A

Owns ONLY: `data/layer_classification.yaml` (new), `app/parsing/layer_registry.py` (new), `tests/test_layer_registry.py`.

**Interfaces:** `classify_layers(ocg_registry: dict[str, dict]) -> list[LayerRow]` (registry shape from `vector.build_ocg_registry`: name → {ocg,status,count}). Config file format mirrors spec §7.3 exactly (ordered `layer_classification_rules:` list, first-match-wins, `.*` → unclassified last). Include electrical (`^(E-|ADO |FIRE ALARM|NORMAL TRAY|access control)`), mechanical (`^(M-DUCT|M-PIPE|M-EQPT)`), architectural/envelope/material_rendering patterns from spec §7.3.

- [ ] **Step 1: Failing test** — precedence (E-… beats later catch-all), unclassified fallback, M-EQPT-FUTR → mechanical, empty registry → [].
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (load YAML once via lru_cache keyed by mtime-free simple cache; compile regexes). **Step 4: Run** → PASS. **Step 5: Commit** `feat(v3c): human-editable layer classification registry (G3 part 1)`

---

### Task 7 (A5b): Legend & schedule parser pure module — PARALLEL BATCH A

Owns ONLY: `app/parsing/schedules.py` (new), `tests/test_schedules.py`.

**Interfaces:** `detect_blocks(spans: list[dict]) -> list[ScheduleBlockRow]` where span = `{text,x0,y0,x1,y1}` (cascade shape). Heuristics: (1) header keywords (`SYMBOL`+`DESCRIPTION` ⇒ legend; `SIZE`+(`THICK`|`GAUGE`)|`DUCT SIZE` ⇒ attribute_schedule); (2) rows grouped by y-centerline tolerance (≤ max(span_height)*0.6); (3) ≥2 aligned rows required; block bbox = union. Multiple blocks supported; garbage → [].

- [ ] **Step 1: Failing tests** — synthetic 3-row duct-size table → one attribute_schedule with entries `[{"cells":["600x400","0.8","25"]},...]`; symbol/desc legend → legend block; scattered text → []; two separate tables → two blocks.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** `feat(v3c): generic legend & schedule-block detector (G4 part 1)`

---

### Task 8 (A5c): Text–layer association walker pure module — PARALLEL BATCH A

Owns ONLY: `app/parsing/text_walker.py` (new), `tests/test_text_walker.py`.

**Interfaces:**
```python
def associate_text(
    spans: list[dict],                       # {text,x0,y0,x1,y1}
    components: list[tuple[float, float]],   # centroids, index-aligned with ComponentRow list
    routes: list[list[tuple[float, float]]], # polylines, index-aligned with RouteRow list
    ocg_by_span: dict[int, str] | None = None,  # optional span-index → ocg name
    threshold_pt: float = 18.0,
) -> list[TextAnnotationRow]
```
Nearest-target join: distance = point-to-centroid for components, point-to-segment min for routes; attach closest within threshold; unattached spans dropped (they're covered by schedule parser). `ocg_by_span` filled later by BDC/EMC probe in Task 9 wiring; module also exports `probe_span_ocgs(page) -> dict[int,str]` attempting `page.get_text("dict")` span ocg field if the installed PyMuPDF exposes it, else `{}` (graceful).

- [ ] **Step 1: Failing tests** — span near centroid attaches with component_index; nearer route wins; beyond threshold dropped; ocg passthrough.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS. **Step 5: Commit** `feat(v3c): text–layer association walker (G5 part 1)`

---

### CHECKPOINT (controller): merge batch A, full suite + ruff, resolve conflicts (none expected — disjoint files verified above)

---

### Task 9 (B4): Integrator — builders wiring, UNMAPPED, router registration — SERIAL

Owns: `app/e2e/router.py`, `app/e2e/persistence.py`, `app/main.py`, `app/parsing/components.py` (only change: expose unmapped), `docs/Phases.md`, `docs/Memory.md`, `tests/test_v3_integration.py` (new).

**Steps:**
- [ ] **Step 1: Failing integration test** — run `POST /api/e2e/run?persist=true` on the generated HVAC fixture (`tests/fixtures/make_hvac_fixture.py` output): response contains `layers_count ≥ 1`, `schedule_blocks_count ≥ 0`, `estimate_id`; `GET /api/estimates/{id}/replay` → 200; unmapped synthetic layer surfaces in `unmapped_items` with confidence_status UNMAPPED and persists as Component rows; `main.py` app serves `/api/estimates/...`, `/api/exports/...`, `/api/narration/...` (TestClient on the real app).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement:**
  - `components.count_components(..., include_unmapped=False)` → True returns extra dicts with `assembly_type=None` (never priced).
  - Router builds full SheetExtraction: `classify_layers(parsed["ocg_registry"])`, `detect_blocks(cascade_spans)`, `associate_text(...)` with centroids/polylines from parsed geometry, unmapped components appended with `component_type=None`.
  - persistence.py: insert Layers (+resolve layer_id FKs), ScheduleBlocks, TextAnnotations (index→FK), unmapped Components with `confidence_status="UNMAPPED"`.
  - Response additions: `unmapped_items` list, builder counts. Existing keys unchanged.
  - main.py: `include_router(estimates_router)`, `include_router(exports_router)`, `include_router(narration_router)`.
- [ ] **Step 4: FULL suite + ruff**: `python -m pytest -q` (≥136 passed + 1 xfail) and `python -m ruff check app tests` clean.
- [ ] **Step 5: Docs**: Phases.md — new "Phase 3.5 — v3 Conformance" section (implemented items + remaining human gates); Memory.md progress row.
- [ ] **Step 6: Commits**: `feat(v3c): integrate layer/schedule/walker builders + UNMAPPED tiering (G3-G6)`; `docs(v3c): phases + memory updates`.

---

## Self-review record

- Spec coverage: G1→T2, G2→T3, G3→T1+T6+T9, G4→T1+T7+T9, G5→T1+T8+T9, G6→T9, G7→T5, G8→T4, G9→human-gated (spec §4.10, intentionally no task). ✔
- Placeholder scan: none — all steps carry concrete code/signatures/run commands. ✔
- Type consistency: all tasks import frozen dataclasses from `app.e2e.extraction` (T1); `persist_extraction` signature identical in T2 definition and T9 usage; writer signature uniform in T5. ✔
