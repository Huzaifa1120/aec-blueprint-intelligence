# Spec v3 Accuracy-Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the six spec-v3 conformance debts (C1–C6) plus the §7.3 amendment (C7): honest scale handling, live confidence tiers, visible data quality, per-row source regions, persisted corrections, and labor costing.

**Architecture:** Two waves. Wave 1 (Tasks 1–6) touches no schema — scale resolver, tier assignment, data-quality counters, frontend banner, spec amendment. Wave 2 (Tasks 7–14) is one Alembic migration plus traceability features: bbox capture, PDF file serving, stable IDs + validated review actions with correction persistence, labor costing.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (Python ≥3.11, venv at `backend/.venv`), PyMuPDF imported as `pymupdf`, Next.js 16 / React 19 / vitest frontend.

**Spec:** `docs/superpowers/specs/2026-08-25-spec-v3-accuracy-conformance-design.md` (read together with this plan; decisions §2 are owner rulings)

## Global Constraints

- Backend commands run from `backend/` using `& ".venv\Scripts\python.exe" -m pytest -q` (PowerShell) or `backend/.venv/Scripts/python.exe -m ...`; never bare `<tool>.exe`.
- Import PyMuPDF as `pymupdf`, never `fitz`.
- Unit prices/productivity rates live in catalog DB or YAML — never hardcoded in source. The YAML `hourly_rate` fallback in Task 12 is provenance-stamped, not a hardcode.
- No LLM/vision output ever becomes a quantity; narration numbers verbatim-checked (`verify_no_invented_numbers` must keep passing).
- No multi-sheet features. Multi-page mixed-scale handling stays out of scope.
- Pinned truth baselines must hold except explicitly-listed contract changes: DOWNPIPE_PIN=11, FIRE ALARM honest-zero, sheet_metal_m2 Σ≈48.76, S101 N=277, lighting 26, FU fu_total=70→40 mm. Intended changes: BOQ-line `confidence_status` values (Task 3) and absolute BOQ row counts once labor lines exist (Task 12).
- Pre-commit hook active (`core.hooksPath .githooks`): ruff on staged `.py`; eslint+tsc+prettier on staged frontend code. Run `python -m ruff check app tests` before every backend commit.
- Commit style: lowercase conventional (`feat:`, `fix:`, `docs:`, `test:`).
- Replay gate tolerance `1e-6*max(1, qty)`; never weaken it. New derivation payloads may add keys but must leave existing branches intact (unknown branches count as unchecked — acceptable).

---

## Wave 1 — Honesty (no schema changes)

### Task 1: Structured scale resolver

**Files:**
- Modify: `backend/app/parsing/scale.py`
- Test: `backend/tests/test_scale_resolver.py` (create)

**Interfaces:**
- Produces:
  ```python
  @dataclass(frozen=True)
  class ScaleResult:
      scale_str: str        # e.g. "1:100", '1/4"=1\'-0"'
      denominator: float    # 100.0, 48.0 …
      status: str           # "detected" | "assumed"

  def resolve_scale(text_spans: List[Dict[str, Any]]) -> ScaleResult
  def parse_scale_denominator(scale_str: str) -> Tuple[float, bool]  # (denominator, ok)
  ```
- Consumes: existing `detect_scale` span format (`{"text": ...}` dicts).

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_scale_resolver.py
from app.parsing.scale import resolve_scale, parse_scale_denominator


def _span(text):
    return {"text": text}


def test_electrical_scale_detected():
    res = resolve_scale([_span("ELECTRICAL.SCALE 1:100"), _span("noise")])
    assert res.status == "detected"
    assert res.denominator == 100.0
    assert res.scale_str == "1:100"


def test_architectural_quarter_inch():
    res = resolve_scale([_span('SCALE 1/4"=1\'-0"')])
    assert res.status == "detected"
    assert res.denominator == 48.0


def test_architectural_eighth_inch():
    assert resolve_scale([_span('1/8"=1\'-0"')]).denominator == 96.0


def test_generic_ratio_detected():
    res = resolve_scale([_span("SCALE 1:50")])
    assert res.status == "detected"
    assert res.denominator == 50.0


def test_missing_scale_is_assumed_1_100():
    res = resolve_scale([_span("no scale here"), _span("")])
    assert res.status == "assumed"
    assert res.scale_str == "1:100"
    assert res.denominator == 100.0


def test_parse_denominator_ok_and_not():
    assert parse_scale_denominator("1:100") == (100.0, True)
    assert parse_scale_denominator("garbage")[1] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_scale_resolver.py -v` (from `backend/`)
Expected: FAIL — `ImportError: cannot import name 'resolve_scale'`

- [ ] **Step 3: Implement**

In `backend/app/parsing/scale.py`, add above `detect_scale`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ScaleResult:
    scale_str: str
    denominator: float
    status: str  # "detected" | "assumed"


# Architectural inch scales -> denominator (feet per inch * 12 * ratio inverse)
_ARCH_DENOMINATORS = {
    "1/2": 24.0,
    "3/4": 16.0,
    "1": 12.0,
    "3/32": 128.0,
    "1/8": 96.0,
    "3/16": 64.0,
    "1/4": 48.0,
    "3/8": 32.0,
}


def resolve_scale(text_spans: List[Dict[str, Any]]) -> ScaleResult:
    """Read the scale from sheet text; NEVER silently invent one.

    Returns status="detected" with the matched scale, or status="assumed"
    with 1:100 when nothing parseable exists — callers must surface the
    assumed state (spec v3 §7.4: scale is never assumed globally).
    """
    for span in text_spans:
        text = span.get("text", "") or ""
        if not text:
            continue
        m = re.search(r"\bELECTRICAL\.SCALE\s+(1:\d+)\b", text) or re.search(
            r"\bSCALE\s+1=(\d+)'\''-0\"\b", text
        )
        if m:
            return _from_ratio(m.group(1))
        arch = re.search(r'\b(\d+/\d+|\d+)"\s*=\s*1\'\s*-?\s*0?"?', text)
        if arch and arch.group(1) in _ARCH_DENOMINATORS:
            denom = _ARCH_DENOMINATORS[arch.group(1)]
            return ScaleResult(f'{arch.group(1)}"=1\'-0"', denom, "detected")
        m = re.search(r"\b(1:\d+)\b", text)
        if m:
            return _from_ratio(m.group(1))
    return ScaleResult("1:100", 100.0, "assumed")


def _from_ratio(ratio: str) -> ScaleResult:
    denom = float(ratio.split(":")[1])
    return ScaleResult(ratio, denom, "detected")


def parse_scale_denominator(scale_str: str) -> Tuple[float, bool]:
    try:
        return float(str(scale_str).split(":")[1]), True
    except (IndexError, ValueError, AttributeError):
        return 100.0, False
```

Add `Tuple` to the typing import. Leave existing `detect_scale`/`scale_needs_review` untouched (other callers/tests use them this task).

- [ ] **Step 4: Run tests to pass**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_scale_resolver.py -v`
Expected: PASS (6 tests). Then full file: `& ".venv\Scripts\python.exe" -m pytest tests/test_phase2_regression.py -q` still green (no behavior change yet).

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/scale.py backend/tests/test_scale_resolver.py
git commit -m "feat: structured scale resolver with architectural scales + assumed status"
```

### Task 2: Wire scale honesty end-to-end (kill the 1:1 fallback)

**Files:**
- Modify: `backend/app/parsing/routes.py:70-84` (`compute_length_meters`)
- Modify: `backend/app/e2e/router.py:428-436` (use `resolve_scale`, stamp `scale` into response)
- Modify: `backend/app/ingestion/vector.py:262-269` (`parse_pdf` threshold denominator via `parse_scale_denominator`)
- Modify: `backend/app/e2e/extraction.py` (add optional `scale_status: str | None = None` + `scale_str: str | None = None` fields to the extraction schema root — locate the root `SheetExtraction`-style pydantic model)
- Test: `backend/tests/test_scale_honesty.py` (create)

**Interfaces:**
- Consumes: `resolve_scale`/`parse_scale_denominator` (Task 1).
- Produces: e2e run response key `"scale": {"value": "...", "status": "detected"|"assumed"}`; extraction root fields `scale_status`, `scale_str` (Task 4/8 consume). `measure_routes` signature unchanged (still takes `scale: str`).

- [ ] **Step 1: Failing tests**

```python
# backend/tests/test_scale_honesty.py
import math
from app.parsing.routes import compute_length_meters
from app.parsing.scale import resolve_scale


def test_unparseable_scale_no_longer_means_1_to_1():
    # 10pt at 1:100 = 0.353m (existing pinned truth). Garbage must equal missing.
    assert compute_length_meters([(0, 0), (10, 0)], "garbage") == compute_length_meters(
        [(0, 0), (10, 0)], "1:100"
    )


def test_resolver_flags_missing_scale_for_pipeline():
    assert resolve_scale([]).status == "assumed"
```

Plus an API-level test appended to the same file using the existing e2e test client pattern from `tests/test_e2e_pipeline_validation.py` (copy its client/fixture setup for one tiny layered-vector fixture; if building a fixture is heavy, instead assert on `resolve_scale` + response-schema unit level via `TestClient` monkeypatching `parse_pdf` — see existing monkeypatch style in `tests/test_phase4_regression.py` for how the app is exercised without real PDFs):

```python
def test_run_response_carries_scale_block(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.e2e.router as er

    class FakeParsed(dict):
        pass

    fake = FakeParsed(
        raw_drawings=[],
        raw_text_spans=[{"text": "nothing useful"}],
        clusters=[],
        components=[],
        annotations=[],
        schedule_rows=[],
    )
    monkeypatch.setattr(er, "classify_upload", lambda p: {"status": "vector", "source_quality": "layered_vector"})
    monkeypatch.setattr(er, "parse_pdf", lambda p: fake)

    client = TestClient(app)
    resp = client.post(
        "/api/e2e/run",
        files={"file": ("t.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scale"]["status"] == "assumed"
    assert body["scale"]["value"] == "1:100"
```

Match the fake-parse keys to whatever `e2e_run` actually consumes from `parsed` (read `router.py:430-470` first; adjust `fake` so downstream loops no-op gracefully — empty lists everywhere achieves this).

- [ ] **Step 2: Run to verify failure**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_scale_honesty.py -v`
Expected: FAIL — `compute_length_meters` garbage returns 1:1 value (0.0035≠0.353) and response has no `scale` key.

- [ ] **Step 3: Implement**

`routes.py` — replace the fallback block:

```python
    # Parse scale "1:100" → denominator = 100
    try:
        denominator = float(scale.split(":")[1])
    except (IndexError, ValueError):
        # Spec v3 §7.4: never assume 1:1. Unparseable == missing → 1:100,
        # and the pipeline stamps such runs scale_status="assumed".
        denominator = 100.0
```

`e2e/router.py` — change import (line 56) to `from app.parsing.scale import resolve_scale`, then at 428:

```python
        scale_res = resolve_scale(parsed.get("raw_text_spans", []))
        scale = scale_res.scale_str
```

and add `"scale": {"value": scale_res.scale_str, "status": scale_res.status}` to BOTH early-return raster dict and the final success response dict. Stamp the extraction root when building it: `scale_status=scale_res.status, scale_str=scale_res.scale_str`.

`vector.py:262-269` — replace `detect_scale(...)` + `_scale_denominator(scale)` with:

```python
        from app.parsing.scale import parse_scale_denominator
        scale_res = resolve_scale(all_text_spans)
        scale = scale_res.scale_str
        threshold_px = derive_threshold_px(None, scale_res.denominator)
```

(import `resolve_scale` at top alongside existing imports; delete the now-unused local `detect_scale` only if fallow/grep confirms zero remaining references.)

- [ ] **Step 4: Run tests + regressions**

Run: `& ".venv\Scripts\python.exe" -m pytest tests/test_scale_honesty.py tests/test_phase2_regression.py tests/test_phase3_regression.py tests/test_phase4_regression.py -q`
Expected: PASS. MMC-dependent tests keep passing because MMC carries `ELECTRICAL.SCALE 1:100` (detected).

- [ ] **Step 5: Ruff + commit**

```bash
& ".venv\Scripts\python.exe" -m ruff check app tests
git add -A backend/app backend/tests/test_scale_honesty.py
git commit -m "feat: honest scale handling — assumed-scale flagging, 1:1 fallback removed"
```

### Task 3: Live confidence-tier assignment (DERIVED default, ASSUMED downgrades)

**Files:**
- Modify: `backend/app/e2e/router.py:81-113` (`_boq_line`) and call sites 518/562
- Test: `backend/tests/test_confidence_wiring.py` (create)

**Interfaces:**
- Consumes: `confidence_tiering.confidence_score(status, source_quality)`.
- Produces: `_boq_line(assembly_type, material_name, quantity, measurement_status, source_path_ids, db, *, source_quality="layered_vector", derivation=None, size_source=None, rule_version=None, scale_assumed=False)` — BOQ lines now emit `confidence_status ∈ {DERIVED, ASSUMED}` (never MEASURED at BOQ level) and composed scores. Later tasks rely on nothing new here; frontend already renders DERIVED (◑ glyph verified).

- [ ] **Step 1: Failing tests**

```python
# backend/tests/test_confidence_wiring.py
from app.e2e.router import _boq_line


class FakeDB:
    pass


def _line(**kw):
    base = dict(
        assembly_type="duct_round",
        material_name="sheet_metal_m2",
        quantity=1.0,
        measurement_status="MEASURED",
        source_path_ids=["p1"],
        db=FakeDB(),
    )
    base.update(kw)
    return _boq_line(**base)


def test_boq_lines_default_derived():
    line = _line()
    assert line["confidence_status"] == "DERIVED"
    assert line["confidence_score"] == 0.8


def test_size_assumed_downgrades_to_assumed():
    line = _line(size_source="assumed")
    assert line["confidence_status"] == "ASSUMED"
    assert line["confidence_score"] == 0.3


def test_scale_assumed_downgrades_to_assumed():
    line = _line(scale_assumed=True)
    assert line["confidence_status"] == "ASSUMED"


def test_degraded_multiplier_composes_with_derived():
    line = _line(source_quality="degraded_vector")
    assert line["confidence_status"] == "DERIVED"
    assert math.isclose(line["confidence_score"], round(0.8 * 0.8, 4))
```

(`import math` at top. `compute_boq_item` hits the DB for price lookup — with an empty test DB it returns `unpriced` harmlessly; mirror however existing router unit tests construct sessions, e.g. the in-memory engine fixture in `tests/conftest.py` — reuse that fixture instead of `FakeDB` if `_boq_line` requires a real session.)

- [ ] **Step 2: Run to verify failure**

Expected: FAIL — current `_boq_line` echoes caller status (MEASURED) and sets `confidence_score = base_score` (1.0).

- [ ] **Step 3: Implement**

Rewrite the tail of `_boq_line`:

```python
    boq = compute_boq_item(quantity, material_name, db)
    from app.parsing.confidence_tiering import confidence_score

    if size_source == "assumed" or scale_assumed:
        tier = "ASSUMED"
    else:
        tier = "DERIVED"
    score = (
        0.3
        if tier == "ASSUMED"
        else confidence_score("DERIVED", {"rule_version": rule_version or "1.0.0"})
    )
    if source_quality == "degraded_vector":
        score = round(score * get_settings().degraded_confidence_multiplier, 4)
    return {
        ...  # existing keys unchanged ...
        "confidence_status": tier,
        "confidence_score": score,
        ...
    }
```

Call sites: route loop (line ~518) passes `rule_version=mech_rule.get("rule_version"), scale_assumed=(scale_status == "assumed")`; component loop (line ~562) passes `rule_version=rule.get("rule_version")`. Make `scale_status` a variable captured from Task 2's `scale_res.status` in `e2e_run` scope.

Keep `Measurement`/`RouteRow` row-level statuses as-is (MEASURED direct geometry) — the BOQ tier is what drives UI review.

- [ ] **Step 4: Suite sweep — update deliberate contract breaks**

Run: `& ".venv\Scripts\python.exe" -m pytest -q`
Grep failures for `"MEASURED"` assertions on BOQ payloads (likely `tests/test_v3_integration.py`, `tests/test_phase3_s101_equipment.py`). Change expectations from MEASURED→DERIVED only where the assertion targets BOQ-line confidence; row/measurement-level MEASURED assertions stay. Each edited assertion gets a one-line `# contract change: spec conformance 2026-08-25` comment.
The phase1_5 module-level tests (lines 134–193, 239–271) call `assign_confidence_status` directly — they must NOT need changes.

- [ ] **Step 5: Ruff + commit**

```bash
& ".venv\Scripts\python.exe" -m ruff check app tests
git add -A backend/app backend/tests
git commit -m "feat: pipeline assigns DERIVED/ASSUMED confidence tiers (spec v3 §7.12)"
```

### Task 4: Data-quality counters (nothing vanishes silently)

**Files:**
- Create: `backend/app/e2e/data_quality.py`
- Modify: `backend/app/e2e/router.py` (drop sites 413-416, 477-483, 489-501, 537-554; unmapped tally; response)
- Modify: `backend/app/parsing/routes.py` (`measure_routes(..., stats=None)` fills `stats["degenerate_skipped"]`)
- Modify: `backend/app/parsing/fixture_units.py` (`accumulate_fixture_units(..., stats=None)` fills `stats["fu_corridor_excluded"]`)
- Test: `backend/tests/test_data_quality.py` (create)

**Interfaces:**
- Produces:
  ```python
  @dataclass
  class DataQuality:
      dropped_routes: int = 0
      dropped_symbols: int = 0
      unmapped_count: int = 0
      degenerate_skipped: int = 0
      fu_corridor_excluded: int = 0
      classifier_errors: int = 0
      def as_dict(self) -> Dict[str, int]: ...
  ```
  Response gains `"data_quality": {...}`. Task 8/13 persist and export it.

- [ ] **Step 1: Failing tests** — force each loss path with the same monkeypatch style as Task 2 Step 1 (fake `parse_pdf` returning one route whose `resolve_route_context` returns None via a bogus assembly mapping; assert `body["data_quality"]["dropped_routes"] == 1`). Write one test per counter you can trigger cheaply; `unmapped_count` via a clustered pseudo-layer absent from `layer_mapping.yaml`.

- [ ] **Step 2: Verify failures** (`KeyError: 'data_quality'`).

- [ ] **Step 3: Implement** — instantiate `dq = DataQuality()` at top of `e2e_run`; increment at each site (replace bare `continue`s with `dq.dropped_routes += 1` etc.; classify bare-except site increments `classifier_errors` AND logs `logger.exception` before degrading); `measure_routes(..., stats=dq_dict_proxy)` and FU accumulation fill their counters; final response dict gains `"data_quality": dq.as_dict()`.

- [ ] **Step 4:** Full suite green; **Step 5:**

```bash
& ".venv\Scripts\python.exe" -m ruff check app tests
git add -A backend/app backend/tests/test_data_quality.py
git commit -m "feat: data_quality counters surfaced in e2e run response"
```

### Task 5: Frontend assumed-scale banner + payload types

**Files:**
- Modify: `frontend/src/types/estimate.ts` (EstimateBoq gains `scale?: { value: string; status: "detected" | "assumed" } | null; data_quality?: Record<string, number> | null`)
- Create: `frontend/src/components/estimate/AssumedScaleBanner.tsx`
- Modify: `frontend/src/app/estimates/[id]/EstimateClient.tsx` (~line 428, next to `<UnpricedGap>`)
- Test: `frontend/src/components/estimate/AssumedScaleBanner.test.tsx`

Model both on `UnpricedGap.tsx` (conditional null-return strip, lucide icon, `text-warning`). Banner copy: `Scale not detected — lengths measured at 1:100 and flagged for review.` with `role="status"`.

- [ ] **Step 1: Failing vitest** (mirror ConfidenceBadge.test.tsx structure):

```tsx
import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { AssumedScaleBanner } from "./AssumedScaleBanner"

describe("AssumedScaleBanner", () => {
  it("renders warning when scale assumed", () => {
    render(<AssumedScaleBanner status="assumed" />)
    expect(screen.getByRole("status")).toHaveTextContent(/1:100/)
  })
  it("renders nothing when detected", () => {
    const { container } = render(<AssumedScaleBanner status="detected" />)
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 2: fail** (`Cannot find module`), **Step 3: implement** component + mount `{boq.scale?.status === "assumed" && <AssumedScaleBanner status="assumed" />}`, **Step 4:** `npm run test`, `npm run lint`, `npm run typecheck` all green, **Step 5:**

```bash
git add frontend/src
git commit -m "feat(frontend): assumed-scale banner + payload scale types"
```

### Task 6: Spec §7.3 amendment (C7)

**Files:**
- Modify: `docs/AEC-Blueprint-System-Design-Spec-v3.md` (§Changelog + §7.3 example config)

- [ ] **Step 1:** In §7.3's YAML example: remove `FIRE ALARM` from the electrical pattern; add three disciplines:
```yaml
  - pattern: '^(P-)'
    discipline: plumbing
  - pattern: '^(FP-)'
    discipline: fire_protection
  - pattern: '^(FA-)'
    discipline: fire_alarm
```
change envelope pattern to `'^M_SAUDI_(WATER_INSULATING|VENT_identy)'`, and add `- pattern: '^M_SAUDI_RAIN DOWNPIPE'` → `discipline: plumbing`.
- [ ] **Step 2:** Changelog bullet: `- **2026-08-25: §7.3 layer-classification example aligned with shipped owner rulings (Phase 4): FIRE ALARM → fire_alarm discipline; M_SAUDI_RAIN DOWNPIPE → plumbing (counted storm-downpipe kit); NCS P-/FP-/FA- families added.**`
- [ ] **Step 3:** `git add docs/AEC-Blueprint-System-Design-Spec-v3.md && git commit -m "docs: spec v3 §7.3 amendment — Phase 4 layer rulings"`

---

## Wave 2 — Traceability (one migration)

### Task 7: Migration — bbox, corrections fields, data-quality, PDF path

**Files:**
- Modify: `backend/app/db/models/estimate.py` (BoqItem + Estimate)
- Modify: `backend/app/db/models/review.py` (ReviewAction)
- Create: `backend/alembic/versions/<gen-id>_accuracy_conformance_schema.py`
- Test: `backend/tests/test_accuracy_conformance_migration.py` (create)

**Interfaces:**
- Produces (model attributes later tasks use): `BoqItem.source_bbox_json: Mapped[str | None]`, `Estimate.data_quality_json: Mapped[str | None]`, `Estimate.scale_status: Mapped[str | None]`, `Estimate.source_pdf_path: Mapped[str | None]`, `ReviewAction.boq_item_id: Mapped[uuid.UUID | None]` (FK `boq_items.id`), `ReviewAction.reason: Mapped[str | None]` (Text), `ReviewAction.corrected_value: Mapped[float | None]`.

- [ ] **Step 1: Write the migration-content test FIRST**

```python
# backend/tests/test_accuracy_conformance_migration.py
import json
from sqlalchemy import inspect
from app.db.models.base import Base  # match the Base import used by tests/test_migrations.py
from app.db.session import get_engine  # match existing migration-test imports


def test_accuracy_conformance_columns_and_table():
    insp = inspect(get_engine())
    boq_cols = {c["name"] for c in insp.get_columns("boq_items")}
    assert {"source_bbox_json"} <= boq_cols
    est_cols = {c["name"] for c in insp.get_columns("estimates")}
    assert {"data_quality_json", "scale_status", "source_pdf_path"} <= est_cols
    act_cols = {c["name"] for c in insp.get_columns("review_actions")}
    assert {"boq_item_id", "reason", "corrected_value"} <= act_cols
```

(Mirror setup/teardown mechanics from `tests/test_migrations.py` — it already proves `alembic upgrade head` against a scratch DB; extend rather than reinvent.)

- [ ] **Step 2:** `& ".venv\Scripts\python.exe" -m alembic revision --autogenerate -m "accuracy conformance schema"` — then EDIT the generated file: autogenerate notoriously strips the drifted `labor_rates` table (known gotcha); delete any spurious drops/creates it invents, keep ONLY: `op.add_column("boq_items", sa.Column("source_bbox_json", sa.Text(), nullable=True))`, three `estimates` columns (`data_quality_json` Text, `scale_status` String(20), `source_pdf_path` String(500)), and for `review_actions`: `boq_item_id` (`sa.Uuid(), nullable=True` + `ForeignKeyConstraint(["boq_item_id"], ["boq_items.id"])` via `op.create_foreign_key(...)` with an explicit name), `reason` (`sa.Text()`), `corrected_value` (`sa.Float()`). Set `down_revision = 'c37396f6713e'`.
- [ ] **Step 3:** Update the three model files with the attributes above (match existing typing/mapped_column style).
- [ ] **Step 4:** `& ".venv\Scripts\python.exe" -m alembic upgrade head && & ".venv\Scripts\python.exe" -m pytest tests/test_accuracy_conformance_migration.py tests/test_migrations.py -q` PASS.
- [ ] **Step 5:**

```bash
& ".venv\Scripts\python.exe" -m ruff check app tests
git add backend/app/db backend/alembic backend/tests/test_accuracy_conformance_migration.py
git commit -m "feat: accuracy-conformance schema — bbox, corrections, dq, pdf path"
```

### Task 8: Capture + emit source regions and persist scale/dq

**Files:**
- Modify: `backend/app/parsing/routes.py` (each returned route dict gains `"bbox": (x0, y0, x1, y1)` computed from its polyline, `"page": page_index_or_0`)
- Modify: `backend/app/e2e/router.py` (route/component BOQ dicts gain `"source": {"page": ..., "bbox": [...]}`)
- Modify: `backend/app/e2e/persistence.py:304-326` (`_add_boq_item` writes `source_bbox_json=json.dumps(payload["source"])` when present; `persist_extraction` writes `estimate.scale_status/scale_str?/data_quality_json` from the extraction root — store `scale_str` inside… keep column set from Task 7: persist `scale_status` and fold `scale_str` into `data_quality_json`? NO — cleaner: rename Task 7's estimate column plan here: `scale_status` stores the status; add the resolved string to the same JSON? Simplest consistent choice: persist `scale_status` column + put `{"scale_str": ..., **dq}` into `data_quality_json`.)
- Modify: `backend/app/estimates/payload.py:43-87` (per-row `"item_id": str(item.id)`, `"source": parse_json_object(item.source_bbox_json)`; top-level `"scale": {...}, "data_quality": {...}` from estimate columns)
- Test: `backend/tests/test_source_region_persistence.py` (create) — run the synthetic plumbing/fire fixture through POST /api/e2e/run?persist=true (reuse `tests/fixtures/make_plumbing_fire_fixture.py` + the integration-test client pattern from `tests/test_v3_integration.py`), then assert: response rows carry `source.bbox`; GET `/api/estimates/{id}/boq` rows carry `item_id` + non-null `source` for route-derived rows; `scale.status` present; legacy-row tolerance (manually null a row's `source_bbox_json`, payload emits `"source": None`).

- [ ] Steps: test → fail → implement → suite green → ruff → `git commit -m "feat: per-row source regions + persisted scale/dq provenance"`

### Task 9: Store + serve the original PDF

**Files:**
- Modify: `backend/app/e2e/router.py` (when `persist`, read `Path(tmp_path).read_bytes()` before the finally-unlink and pass to `persist_extraction(..., pdf_bytes=...)`)
- Modify: `backend/app/e2e/persistence.py` (`persist_extraction(db, project_id, extraction, pdf_bytes: bytes | None = None)` — writes to `data/uploads/<estimate_id>.pdf`, creating the dir, records `estimate.source_pdf_path`)
- Modify: `backend/app/estimates/router.py` (new endpoint below)
- Modify: `.gitignore` (root: `backend/data/uploads/`)
- Test: `backend/tests/test_sheet_file_endpoint.py`

Endpoint (in `estimates/router.py`, prefix `/api/estimates`):

```python
@router.get("/{estimate_id}/file")
def get_estimate_file(estimate_id: uuid.UUID, db: OrmSession = Depends(get_db)):
    estimate = db.get(Estimate, estimate_id)
    if estimate is None or not estimate.source_pdf_path:
        raise HTTPException(status_code=404, detail="Source file not stored for this estimate")
    path = Path(estimate.source_pdf_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Source file missing on disk")
    return FileResponse(path, media_type="application/pdf", filename=path.name)
```

Test: persist-run on the synthetic fixture with real bytes → GET returns 200 `application/pdf` and bytes match; GET on legacy estimate → 404.
Commit: `feat: store uploaded drawing per estimate + GET /api/estimates/{id}/file`

### Task 10: Stable IDs + validated review actions with correction persistence

**Files:**
- Modify: `backend/app/review/router.py:17-25, 86-102`
- Test: `backend/tests/test_review_corrections.py` (create)

New request model:

```python
class AddActionRequest(BaseModel):
    item_id: str
    action: Literal["accept", "reject", "correct"]
    confidence_tier: Literal["MEASURED", "DERIVED", "ASSUMED", "UNMAPPED"]
    boq_item_id: uuid.UUID | None = None
    reason: str | None = None
    corrected_value: float | None = None
```

`add_action` writes the three new columns when provided; invalid enum/body → FastAPI auto-422 (Literal). Tests: valid correct-action with reason+value+boq_item_id persists (query ReviewAction back); bad action → 422; legacy free-string clients now 422 (deliberate contract change, noted).

Response rows already carry `item_id` from Task 8 — ephemeral (non-persisted) runs generate `str(uuid.uuid4())` per row in the router loops so frontend contracts are uniform.

Commit: `feat: validated review actions + persisted corrections (spec v3 §15)`

### Task 11: Frontend click-to-source + correction wiring

**Files:**
- Modify: `frontend/src/types/estimate.ts` (`BoqLine`/`BoqRouteLine` gain `item_id?: string; source?: { page: number; bbox: [number, number, number, number] } | null`)
- Modify: `frontend/src/app/estimates/[id]/EstimateClient.tsx` — `normalizeBoq`: `key: route.item_id ?? \`route-${index}\``, map `source`: when present convert array → `HighlightBBox` as `{ x1: b[0], y1: b[1], x2: b[2], y2: b[3] }`, pass `source_quality` through; line ~363: `<PDFViewer src={estimateId ? \`${API_BASE}/api/estimates/${estimateId}/file\` : null} ...>` (import `API_BASE` from `@/lib/api`)
- Modify: `frontend/src/hooks/useReviewSession.ts` — `ActionPayload` gains optional `boq_item_id?: string; reason?: string; corrected_value?: number`; `logAction` forwards them when defined
- Test: update/extend `frontend/src/lib/bulkAccept.test.ts` neighbor — create `frontend/src/app/estimates/[id]/normalizeBoq.test.ts` covering: id-keying preference, source array→object conversion, null-source rows, and one `useReviewSession` payload-shape test mocking `apiPost` (pattern: `vi.hoisted` + `vi.mock("@/lib/api")` as in `usePipelineRun.test.tsx`).

Steps: failing tests → implement → `npm run test && npm run lint && npm run typecheck` green → `git commit -m "feat(frontend): live click-to-source + correction persistence wiring"`

### Task 12: Labor costing (unpriced-flag pattern)

**Files:**
- Modify: `backend/app/catalog/prices.py` — add:
  ```python
  def compute_labor_cost(
      db_session: Session, category: str | None, hours: float, yaml_hourly_rate: float | None
  ) -> Dict[str, Any]:
      """Rate resolution: catalog LaborRate(category, latest) > YAML hourly_rate > unpriced."""
  ```
  returning `{"unit_rate", "total_cost", "unpriced", "rate_source": "catalog"|"yaml"|None}` (reuse `Decimal` rounding from `labor_cost`).
- Modify: `backend/app/e2e/router.py` + `backend/app/e2e/persistence.py` — after each successful `apply_assembly`, if the rule's `labor` block has nonzero `installation_hours`, emit one extra BOQ line: `material_name=f"labor:{category or assembly_type}"`, `quantity=applied["labor_hours"]`, `unit="hour"`, derivation payload `{"labor": {"category": ..., "rate_source": ...}, "rule_name": assembly, "rule_version": ...}` (replay treats it as unchecked-honest; do NOT touch `_replay_item`).
- Modify: `backend/app/e2e/persistence.py:478-488` — `total_labor_cost = round(sum priced labor rows, 2)`; `total_cost = total_material_cost + total_labor_cost`.
- Modify: `data/assemblies/access_control_door.yaml` — labor block gains `hourly_rate: 45.00` + `category: electrical` (aligns with the electrical rate family).
- Test: `backend/tests/test_labor_costing.py` — catalog-rate path (seed LaborRate via `ingest_labor_rate`), YAML-fallback path (empty catalog → rate_source "yaml"), unpriced path (no rate anywhere → line flagged, excluded from totals), and a totals-reconciliation test: grand == Σ priced material + Σ priced labor over the synthetic fixture run.

**Blast radius:** absolute BOQ row-count baselines grow by one labor line per applied rule-with-labor. Grep tests pinning counts (`assert len(body["materials"]) == N`, `114`, totals equalities) and update with the `# contract change: labor lines 2026-08-25` comment.

Commit: `feat: labor costing via unpriced-flag pattern (spec v3 §7.14)`

### Task 13: Exports + narration disclose dq/labor honestly

**Files:**
- Modify: `backend/app/exports/xlsx_export.py` (after totals block: blank row + `Data Quality` section listing each nonzero counter; corrections annex if `rows.get("corrections")` non-empty: header + one row per correction `item/material, action, reason, corrected_value, date`)
- Modify: `backend/app/exports/pdf_export.py` (same two blocks as paragraphs after the totals table, reusing existing styles)
- Modify: `backend/app/estimates/payload.py` — payload gains `"data_quality"` (from estimate) and `"corrections"` (query `ReviewAction.boq_item_id → BoqItem.estimate_id == estimate.id`, joined for material_name via derivation)
- Modify: `backend/app/narration/providers.py` — after the Unpriced Items section: `Assumptions & Data Quality` section printing scale-assumed notice when payload scale status assumed and any nonzero dq counters (counts are allowed tokens via `len()` mechanics already present)
- Test: extend `backend/tests/test_v3_integration.py` with one export test asserting the XLSX contains the dq section and one narration test asserting verbatimism still passes with the new section.

Commit: `feat: exports/narration disclose data quality + corrections annex`

### Task 14: Conformance sweep + docs

- [ ] Full backend suite: `& ".venv\Scripts\python.exe" -m pytest -q` — green including updated baselines; replay endpoint smoke on a pre-Wave-2 persisted estimate (null bbox tolerated, 200 not 409).
- [ ] `& ".venv\Scripts\python.exe" -m ruff check app tests`; frontend `npm run lint && npm run typecheck && npm run test && npm run build`.
- [ ] Update `docs/Memory.md` progress-log row + snapshot (phase: spec-v3 accuracy conformance; decisions C1–C7 landed; baseline deltas listed).
- [ ] Commit: `docs: memory update — spec-v3 accuracy-conformance package landed`

---

## Self-review notes (already applied)

- Spec coverage: C1→T1/T2, C2→T3, C3→T8/T9/T11, C4→T7/T10/T11/T13, C5→T12, C6→T4 (+T8/T13 persistence/export), C7→T6. Success criteria 1–7 of the spec map to T2/T5 (1), T3 (2), T4/T13 (3), T8/T9/T11 (4), T10/T11/T13 (5), T12/T13 (6), T14 (7).
- Type consistency: `ScaleResult` fields identical across T1/T2; `source` shape `{page, bbox:[x0,y0,x1,y1]}` consistent T8→T11; `AddActionRequest` names match frontend `ActionPayload` additions.
- One deliberate deviation from the spec text: corrections live as nullable columns on the existing `review_actions` table instead of a separate `review_corrections` table (avoids duplicating action/session/timestamp; same §15 semantics). The spec's §4.1 should be read with this note — executor should add one line to the spec's §4.1 when landing Task 7.
