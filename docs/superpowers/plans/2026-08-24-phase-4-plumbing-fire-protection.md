# Phase 4 — Plumbing & Fire Protection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the QTO system to domestic plumbing, fire suppression, and fire-alarm devices — new discipline rules plus two engine extensions (geometry-derived fittings, fixture-unit sizing) — validated end-to-end on a generated deterministic fixture and the real MMC sample sheet.

**Architecture:** No pipeline change (classify → parse → scale → routes/components → assemblies → BOQ → persist → replay → export). Phase 4 is data-first (16 assembly YAMLs, layer classification/mapping edits) plus two bounded modules (`app/parsing/fittings.py`, `app/parsing/fixture_units.py`), a cascade tier insertion in `sizes.py`, e2e wiring in `app/e2e/router.py`, and a replay-parity extension in `app/estimates/router.py`.

**Tech Stack:** Python ≥3.11, FastAPI, SQLAlchemy/Alembic, PyMuPDF (`import pymupdf`, never `fitz`), pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-08-24-phase-4-plumbing-fire-protection-design.md`

## Global Constraints

- Venv invocation from `backend/`: `backend/.venv/Scripts/python.exe -m pytest -q` and `backend/.venv/Scripts/python.exe -m ruff check app tests`. Never bare `pytest.exe`.
- Import PyMuPDF as `pymupdf`, never `fitz`.
- No prices, productivity rates, thresholds, or default sizes hardcoded in source — YAML/config only.
- No LLM/vision output ever becomes a quantity; every number traces to deterministic calculation with provenance.
- Baseline before work: **238 passed + 1 xfail**, ruff clean. Full suite must stay green after every task.
- Existing regression locks (electrical/mechanical counts, exports byte-for-value) must stay byte-identical.
- Branch: `feature/phase-4-plumbing-fire-protection`, cut from latest `main`.
- **Spec refinements locked in this plan** (record in Phases.md amendment at Task 8):
  1. `storm_downpipe` is implemented as a **counted device kit**, not a sized route — vertical riser length is physically unmeasurable from a floor plan, so per-meter formulas would be fiction. Sized-route treatment arrives with real riser-diagram sheets (same swap trigger as spec §9).
  2. Replay parity for `fixture_units` sizes verifies **derivation coherence** (gauge(fu_total) == diameter_mm; `fu_breakdown` sums == fu_total; breakdown values match rule YAML) rather than geometric recomputation — route polylines are not persisted (known Phase 3.5 deferred gap, `path_ids_json` family). Fail-closed intent preserved.

## Task Dependency Graph

```
T1 ─┐
T2 ─┼─► T7 ► T8
T3 ─┤
T4 ─┤
T5 ─┘
    T6 ──► T7   (T6 needs T1+T5)
```

---

### Task 1: Layer classification — plumbing / fire_protection / fire_alarm

**Files:**
- Modify: `data/layer_classification.yaml`
- Test: `backend/tests/test_layer_registry.py` (append)

**Interfaces:**
- Consumes: `classify_layers(ocg_registry: dict[str, dict]) -> list[LayerRow]` from `app/parsing/layer_registry.py` (exists).
- Produces: discipline strings `"plumbing"`, `"fire_protection"`, `"fire_alarm"` on LayerRows; later tasks (T5 mapping, T7 assertions) rely on `FIRE ALARM` → `fire_alarm` and `M_SAUDI_RAIN DOWNPIPE` → `plumbing`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_layer_registry.py`:

```python
def test_phase4_disciplines():
    from app.parsing.layer_registry import classify_layers

    registry = {
        i: {"name": n, "on": True, "intent": "Draw"}
        for i, n in enumerate(
            [
                "FIRE ALARM",
                "M_SAUDI_RAIN DOWNPIPE",
                "P-SAN-MAIN",
                "P-DOM-CW",
                "FP-SPRK-BRANCH",
                "FA-DETECTOR",
                "E-lt-fix-nm-clg",          # stays electrical
                "M_SAUDI_WATER_INSULATING", # stays envelope
            ]
        )
    }
    rows = classify_layers(registry)
    got = {r.ocg_name: r.classified_discipline for r in rows}
    assert got["FIRE ALARM"] == "fire_alarm"
    assert got["M_SAUDI_RAIN DOWNPIPE"] == "plumbing"
    assert got["P-SAN-MAIN"] == "plumbing"
    assert got["P-DOM-CW"] == "plumbing"
    assert got["FP-SPRK-BRANCH"] == "fire_protection"
    assert got["FA-DETECTOR"] == "fire_alarm"
    assert got["E-lt-fix-nm-clg"] == "electrical"
    assert got["M_SAUDI_WATER_INSULATING"] == "envelope"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_layer_registry.py::test_phase4_disciplines -v`
Expected: FAIL — `fire_alarm`/`plumbing`/`fire_protection` not produced (current YAML classifies `FIRE ALARM` as electrical, `M_SAUDI_RAIN DOWNPIPE` as envelope).

- [ ] **Step 3: Edit `data/layer_classification.yaml`**

Replace the electrical rule and envelope rule; add the three new families. Final ordered list (first match wins):

```yaml
layer_classification_rules:
  - pattern: '^(M_SAUDI_(WALL|DOOR|STAIRS|ROOM|AREAS)|M-PART-GLZW)'
    discipline: architectural
  - pattern: '^FIRE ALARM'
    discipline: fire_alarm
  - pattern: '^(E-|ADO |NORMAL TRAY|access control)'
    discipline: electrical
  - pattern: '^(M-DUCT|M-PIPE|M-EQPT)'
    discipline: mechanical
  - pattern: '^(P-)'
    discipline: plumbing
  - pattern: '^(FP-)'
    discipline: fire_protection
  - pattern: '^(FA-)'
    discipline: fire_alarm
  - pattern: '^M_SAUDI_RAIN DOWNPIPE'
    discipline: plumbing
  - pattern: '^M_SAUDI_(WATER_INSULATING|VENT_identy)'
    discipline: envelope
  - pattern: '^M_SAUDI_(MAT|METAL|PATT|NPLT|PRPT|AGRAF|DOT|ACCESSORY|HIDDEN)'
    discipline: material_rendering   # non-structural
  - pattern: '.*'
    discipline: unclassified
```

Update the header comment: disciplines now include plumbing, fire_protection, fire_alarm (Phase 4).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_layer_registry.py -v`
Expected: ALL PASS (new test + existing registry tests).

- [ ] **Step 5: Commit**

```bash
git add data/layer_classification.yaml backend/tests/test_layer_registry.py
git commit -m "feat(phase4): classify plumbing/fire-protection/fire-alarm layers"
```

---

### Task 2: Config thresholds + geometry-derived fittings module

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/parsing/fittings.py`
- Test: `backend/tests/test_phase4_fittings.py` (create)

**Interfaces:**
- Consumes: nothing outside stdlib/numpy-free math.
- Produces:
  - `Settings` fields: `fitting_bend_angle_deg: float = 30.0`, `fitting_min_segment_pt: float = 2.0`, `fitting_junction_tol_pt: float = 6.0`, `fu_corridor_pt: float = 24.0` (last consumed by T3).
  - `derive_fittings(route: Dict, other_routes: Optional[List[Dict]] = None, *, bend_angle_deg: float = 30.0, min_segment_pt: float = 2.0, junction_tol_pt: float = 6.0) -> Dict` returning `{"elbows_90": int, "tees": int, "provenance": [{"kind": str, "ref": str}, ...]}`. Routes are dicts with key `"polyline": List[Tuple[float,float]]` in PDF points (shape produced by `measure_routes`). Consumed by T7.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_phase4_fittings.py`:

```python
"""Golden tests for geometry-derived fittings (Phase 4 spec §4)."""

from app.parsing.fittings import derive_fittings


def _route(pts):
    return {"polyline": [(float(x), float(y)) for x, y in pts], "layer": "P-SAN-MAIN"}


def test_right_angle_bends_count_as_elbows():
    # Two 90-degree corners; all segments long enough
    r = _route([(0, 0), (100, 0), (100, 80), (40, 80)])
    out = derive_fittings(r)
    assert out["elbows_90"] == 2
    assert out["tees"] == 0


def test_shallow_bend_below_threshold_is_not_elbow():
    # 15-degree direction change < 30-degree default threshold
    import math
    p0 = (0.0, 0.0)
    p1 = (100.0, 0.0)
    ang = math.radians(15.0)
    p2 = (p1[0] + 100.0 * math.cos(ang), p1[1] + 100.0 * math.sin(ang))
    out = derive_fittings(_route([p0, p1, p2]))
    assert out["elbows_90"] == 0


def test_tiny_segment_vertex_is_skipped():
    # Collinear long segments joined by a sub-threshold jog vertex
    r = _route([(0, 0), (100, 0), (100, 1.0), (200, 1.0)])
    out = derive_fittings(r, min_segment_pt=2.0)
    # The 1-pt segment is below min length; neither adjacent vertex counts
    assert out["elbows_90"] == 0


def test_tee_when_foreign_vertex_hits_interior():
    target = _route([(0, 0), (200, 0)])          # horizontal main
    branch = _route([(100, 0), (100, 80)])       # branch endpoint ON main interior
    out = derive_fittings(target, [branch])
    assert out["tees"] == 1


def test_endpoint_touch_is_not_tee_on_interior_route():
    # Branch tip meets main's ENDPOINT -> collinear continuation, no tee
    target = _route([(0, 0), (100, 0)])
    other = _route([(100, 0), (100, 80)])
    out = derive_fittings(target, [other])
    assert out["tees"] == 0


def test_junction_tolerance_edge():
    target = _route([(0, 0), (200, 0)])
    near = _route([(100.0, 5.9), (100.0, 80.0)])   # within 6pt tol
    far = _route([(100.0, 6.1), (100.0, 80.0)])    # outside tol
    assert derive_fittings(target, [near], junction_tol_pt=6.0)["tees"] == 1
    assert derive_fittings(target, [far], junction_tol_pt=6.0)["tees"] == 0


def test_provenance_records_kind_and_ref():
    r = _route([(0, 0), (100, 0), (100, 80)])
    out = derive_fittings(r)
    kinds = [p["kind"] for p in out["provenance"]]
    assert kinds == ["geometry_fittings:elbow"]
    assert "100.0,0.0" in out["provenance"][0]["ref"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase4_fittings.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.parsing.fittings'`

- [ ] **Step 3: Implement config + module**

In `backend/app/core/config.py`, inside `Settings`, after `review_time_target_min`:

```python
    fitting_bend_angle_deg: float = 30.0
    fitting_min_segment_pt: float = 2.0
    fitting_junction_tol_pt: float = 6.0
    fu_corridor_pt: float = 24.0
```

Create `backend/app/parsing/fittings.py`:

```python
"""Geometry-derived pipe fittings from route polylines (Phase 4 spec §4).

Tiny drawn fitting symbols are unreliable to cluster; instead, elbows and
tees derive deterministically from the ordered polylines measure_routes
already produces. Pure geometry — no LLM/vision output ever becomes a count.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

Point = Tuple[float, float]


def _unit(v: Tuple[float, float]) -> Optional[Tuple[float, float]]:
    norm = math.hypot(*v)
    if norm == 0.0:
        return None
    return (v[0] / norm, v[1] / norm)


def _angle_between(v1: Point, v2: Point) -> float:
    u1, u2 = _unit(v1), _unit(v2)
    if u1 is None or u2 is None:
        return 0.0
    dot = max(-1.0, min(1.0, u1[0] * u2[0] + u1[1] * u2[1]))
    return math.degrees(math.acos(dot))


def derive_fittings(
    route: Dict,
    other_routes: Optional[List[Dict]] = None,
    *,
    bend_angle_deg: float = 30.0,
    min_segment_pt: float = 2.0,
    junction_tol_pt: float = 6.0,
) -> Dict:
    """Count elbows/tees for one route from its own and foreign vertices."""
    polyline: List[Point] = [(float(x), float(y)) for x, y in route.get("polyline") or []]
    elbows = 0
    provenance: List[Dict[str, str]] = []

    for i in range(1, len(polyline) - 1):
        prev, cur, nxt = polyline[i - 1], polyline[i], polyline[i + 1]
        seg_in = (cur[0] - prev[0], cur[1] - prev[1])
        seg_out = (nxt[0] - cur[0], nxt[1] - cur[1])
        if math.hypot(*seg_in) < min_segment_pt or math.hypot(*seg_out) < min_segment_pt:
            continue
        if _angle_between(seg_in, seg_out) >= bend_angle_deg:
            elbows += 1
            provenance.append({
                "kind": "geometry_fittings:elbow",
                "ref": f"{cur[0]:.1f},{cur[1]:.1f}",
            })

    tees = 0
    for other in other_routes or []:
        if other is route:
            continue
        for qx, qy in (other.get("polyline") or []):
            if _distance_to_polyline_interior((qx, qy), polyline, junction_tol_pt):
                tees += 1
                provenance.append({
                    "kind": "geometry_fittings:tee",
                    "ref": f"{qx:.1f},{qy:.1f}",
                })
                break  # one foreign route contributes at most one tee here

    return {"elbows_90": elbows, "tees": tees, "provenance": provenance}


def _distance_to_polyline_interior(
    point: Point, polyline: List[Point], tol: float
) -> bool:
    """True if point lies within tol of a segment whose far endpoints are
    both distinct from the polyline ends (i.e., an interior crossing)."""
    if len(polyline) < 2:
        return False
    px, py = point
    first, last = polyline[0], polyline[-1]
    for j in range(len(polyline) - 1):
        ax, ay = polyline[j]
        bx, by = polyline[j + 1]
        # Skip segments flush against either open end of the target route:
        # a branch meeting the route's own endpoint is a continuation, not a tee.
        if (ax, ay) == first and (bx, by) != last and j == 0:
            interior_start = False
        else:
            interior_start = True
        dx, dy = bx - ax, by - ay
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq == 0.0:
            continue
        t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * dx, ay + t * dy
        dist = math.hypot(px - cx, py - cy)
        if dist <= tol and interior_start:
            return True
    return False
```

Note on `test_endpoint_touch_is_not_tee_on_interior_route`: the branch tip touches `(100,0)` which IS the target's last vertex; the only segment `(0,0)->(100,0)` has `j == 0` and `(bx,by)` is the last point — the guard keeps `interior_start=False`, so no tee fires. If your implementation makes this clearer with an explicit "projection strictly between endpoints" check, prefer that form — but the golden tests above are the contract.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase4_fittings.py -v`
Expected: 7 PASS

- [ ] **Step 5: Lint + full suite**

Run: `cd backend && .venv/Scripts/python.exe -m ruff check app tests && .venv/Scripts/python.exe -m pytest -q`
Expected: ruff clean; suite green (baseline + 7 new).

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/config.py backend/app/parsing/fittings.py backend/tests/test_phase4_fittings.py
git commit -m "feat(phase4): geometry-derived fittings from route polylines"
```

---

### Task 3: Fixture-unit accumulation module

**Files:**
- Create: `backend/app/parsing/fixture_units.py`
- Test: `backend/tests/test_phase4_fixture_units.py` (create)

**Interfaces:**
- Consumes: `load_assembly_rule(name) -> dict | None` from `app/assembly/rules.py`; `data/assemblies/<type>.yaml` optional top-level `fixture_units:` value (authored in T5).
- Produces (consumed by T7):
  - `fixture_units_for_type(component_type: str) -> float` — YAML-declared FU value, 0.0 when absent/unloadable.
  - `accumulate_fixture_units(route_polyline: List[Tuple[float,float]], components: List[Dict], corridor_pt: float = 24.0) -> Tuple[float, List[Dict]]` — components are dicts `{"key": Any, "component_type": str, "x": float, "y": float}`; returns `(fu_total, breakdown)` where breakdown is `[{"key":..., "component_type":..., "fu": float}, ...]`.
  - `resolve_size_from_fixture_units(fu_total: float, rows: Dict[str, str]) -> Optional[Dict]` — rows map threshold-string → diameter_mm-string; returns `{"diameter_mm": float, "shape": "round"}` or None. Same threshold semantics as `lookup_gauge` (first sorted-float threshold ≥ fu_total).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_phase4_fixture_units.py`:

```python
"""Golden tests for fixture-unit accumulation and code-table sizing."""

from app.parsing.fixture_units import (
    accumulate_fixture_units,
    fixture_units_for_type,
    resolve_size_from_fixture_units,
)


def test_fixture_units_for_type_reads_yaml():
    # wc authored in T5 with fixture_units: 3 — skip if T5 not landed yet:
    assert fixture_units_for_type("nonexistent_rule_xyz") == 0.0


def test_accumulate_within_corridor_only():
    polyline = [(0.0, 0.0), (400.0, 0.0)]
    comps = [
        {"key": "a", "component_type": "wc", "x": 100.0, "y": 10.0},    # in
        {"key": "b", "component_type": "lavatory", "x": 200.0, "y": -20.0},  # in
        {"key": "c", "component_type": "wc", "x": 300.0, "y": 200.0},   # out
    ]
    total, breakdown = accumulate_fixture_units(polyline, comps, corridor_pt=24.0)
    # FU values come from YAML (wc=3, lavatory=1); keys c excluded
    keys = sorted(b["key"] for b in breakdown)
    assert keys == ["a", "b"]
    assert total == sum(b["fu"] for b in breakdown)


def test_resolve_size_first_threshold_at_or_above_total():
    rows = {"16": "25", "60": "32", "120": "40"}
    assert resolve_size_from_fixture_units(11.0, rows)["diameter_mm"] == 25.0
    assert resolve_size_from_fixture_units(60.0, rows)["diameter_mm"] == 32.0
    assert resolve_size_from_fixture_units(121.0, rows)["diameter_mm"] == 40.0
    assert resolve_size_from_fixture_units(500.0, rows) is None


def test_resolve_size_shape_is_round():
    out = resolve_size_from_fixture_units(10.0, {"16": "25"})
    assert out == {"diameter_mm": 25.0, "shape": "round"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase4_fixture_units.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement**

Create `backend/app/parsing/fixture_units.py`:

```python
"""Fixture-unit accumulation and code-table pipe sizing (Phase 4 spec §5).

Classic plumbing-code sizing scoped honestly to plan-view geometry: fixtures
near a water-supply route contribute their YAML-declared fixture units; the
total resolves a diameter through an owner-editable gauge table. Pure
deterministic logic — no LLM/vision output ever becomes a quantity.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.assembly.rules import load_assembly_rule


def fixture_units_for_type(component_type: str) -> float:
    """YAML-declared fixture units for a counted component type (0 if none)."""
    rule = load_assembly_rule(component_type)
    if not rule:
        return 0.0
    try:
        return float(rule.get("fixture_units") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _point_to_polyline_distance(
    px: float, py: float, points: List[Tuple[float, float]]
) -> float:
    if len(points) < 2:
        return math.inf
    best = math.inf
    for i in range(1, len(points)):
        ax, ay = points[i - 1]
        bx, by = points[i]
        dx, dy = bx - ax, by - ay
        seg_sq = dx * dx + dy * dy
        if seg_sq == 0.0:
            continue
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg_sq))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


def accumulate_fixture_units(
    route_polyline: List[Tuple[float, float]],
    components: List[Dict],
    corridor_pt: float = 24.0,
) -> Tuple[float, List[Dict]]:
    """Sum fixture units of components within corridor_pt of the polyline."""
    total = 0.0
    breakdown: List[Dict] = []
    for comp in components:
        d = _point_to_polyline_distance(float(comp["x"]), float(comp["y"]), route_polyline)
        if d > corridor_pt:
            continue
        fu = fixture_units_for_type(str(comp.get("component_type") or ""))
        if fu <= 0.0:
            continue
        total += fu
        breakdown.append({
            "key": comp.get("key"),
            "component_type": comp.get("component_type"),
            "fu": fu,
        })
    return total, breakdown


def resolve_size_from_fixture_units(
    fu_total: float, rows: Dict[str, str]
) -> Optional[Dict]:
    """First threshold >= fu_total wins (mirrors lookup_gauge semantics)."""
    for key in sorted(rows, key=float):
        if float(key) >= fu_total:
            return {"diameter_mm": float(rows[key]), "shape": "round"}
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase4_fixture_units.py -v`
Expected: PASS (the YAML-dependent assertion tolerates T5 ordering).

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/fixture_units.py backend/tests/test_phase4_fixture_units.py
git commit -m "feat(phase4): fixture-unit accumulation + code-table sizing"
```

---

### Task 4: Cascade gains `fixture_units` tier

**Files:**
- Modify: `backend/app/parsing/sizes.py`
- Test: `backend/tests/test_size_cascade.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `resolve_route_size(route, text_spans, scale, schedule_rows=None, default_size=None, label_proximity_pt=25.0, fixture_unit_size: Optional[Dict] = None)` — when `fixture_unit_size` is given, it wins over label/geometry/assumed but loses to schedule. `SIZE_SOURCE_ORDER` becomes `("schedule", "fixture_units", "label", "geometry", "assumed")`. The passed-in dict already carries `source`-eligible extras (`fu_total`, `ref`) from the caller (T7); this function stamps `source: "fixture_units"` and passes everything else through. Consumed by T7.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_size_cascade.py`:

```python
def test_fixture_units_tier_beats_label_and_geometry_but_not_schedule():
    from app.parsing.sizes import resolve_route_size

    route = {"polyline": [(0.0, 0.0), (300.0, 0.0)], "layer": "P-DOM-CW"}
    fu = {"diameter_mm": 32.0, "fu_total": 70.0, "ref": ["c1", "c2"]}
    spans = [{"text": "DN50", "x0": 10.0, "y0": 10.0, "x1": 30.0, "y1": 14.0}]

    out = resolve_route_size(route, spans, "1:100", fixture_unit_size=dict(fu))
    assert out["source"] == "fixture_units"
    assert out["diameter_mm"] == 32.0
    assert out["fu_total"] == 70.0

    # Schedule still outranks FU
    sched = [{
        "diameter_mm": 40.0, "ref": "sched:r1",
        "x0": 10.0, "y0": 10.0, "x1": 30.0, "y1": 14.0,
    }]
    out2 = resolve_route_size(
        route, spans, "1:100", schedule_rows=sched, fixture_unit_size=dict(fu)
    )
    assert out2["source"] == "schedule"

    # No FU supplied -> label still works as before
    out3 = resolve_route_size(route, spans, "1:100")
    assert out3["source"] == "label"


def test_size_source_order_constant_updated():
    from app.parsing.sizes import SIZE_SOURCE_ORDER

    assert SIZE_SOURCE_ORDER == ("schedule", "fixture_units", "label", "geometry", "assumed")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_size_cascade.py -v`
Expected: new tests FAIL (unexpected keyword `fixture_unit_size` / order mismatch); existing cascade tests PASS.

- [ ] **Step 3: Implement**

In `backend/app/parsing/sizes.py`:

Change line 16 to:

```python
SIZE_SOURCE_ORDER = ("schedule", "fixture_units", "label", "geometry", "assumed")
```

Extend the signature and insert the tier between the schedule block and the label block (docstring updated accordingly):

```python
def resolve_route_size(
    route: Dict,
    text_spans: List[Dict],
    scale: str,
    schedule_rows: Optional[List[Dict]] = None,
    default_size: Optional[Dict] = None,
    label_proximity_pt: float = 25.0,
    fixture_unit_size: Optional[Dict] = None,
) -> Optional[Dict]:
```

After the `# 1. Schedule table wins` loop and BEFORE `# 2. Text label near the route`, insert:

```python
    # 2. Fixture-unit accumulation (Phase 4): caller precomputed the FU
    # resolution from counted fixtures; schedule still outranks it.
    if fixture_unit_size is not None:
        out = dict(fixture_unit_size)
        out["source"] = "fixture_units"
        return out
```

Renumber the following comments (label becomes 3, geometry 4, ASSUMED 5).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_size_cascade.py tests/test_schedule_detection.py -v`
Expected: ALL PASS (existing cascade goldens unaffected).

- [ ] **Step 5: Commit**

```bash
git add backend/app/parsing/sizes.py backend/tests/test_size_cascade.py
git commit -m "feat(phase4): fixture_units tier in size-resolution cascade"
```

---

### Task 5: Sixteen assembly YAMLs + layer mappings + rule-passthrough

**Files:**
- Create: `data/assemblies/{sanitary_drainage,water_supply,vent,sprinkler_branch,standpipe}.yaml` (routes); `data/assemblies/{wc,lavatory,sink,floor_drain,cleanout,water_heater,storm_downpipe,sprinkler_head,hose_cabinet,smoke_detector,call_point,sounder,facp}.yaml` (devices)
- Modify: `data/layer_mapping.yaml`; `backend/app/assembly/rules.py` (`load_assembly_rule` passes through `fixture_unit_gauge`)
- Test: `backend/tests/test_phase4_rules.py` (create)

**Interfaces:**
- Consumes: `load_assembly_rule`, `validate_rule_file` machinery (exists, fail-closed).
- Produces: rule names consumed by mapping/wiring/replay: `sanitary_drainage`, `water_supply`, `vent`, `sprinkler_branch`, `standpipe` (sized routes); `storm_downpipe`, `sprinkler_head`, `hose_cabinet`, `wc`, `lavatory`, `sink`, `floor_drain`, `cleanout`, `water_heater`, `smoke_detector`, `call_point`, `sounder`, `facp` (counted devices; `wc`=3 FU, `lavatory`=1, `sink`=2 — owner-confirmable values, like ASSUMED defaults). `load_assembly_rule("water_supply")["fixture_unit_gauge"]` → `{"by": "fu_total", "rows": {...}}`. Consumed by T6/T7/T8.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_phase4_rules.py`:

```python
"""Fail-closed validation proof for Phase 4 rule files."""

import pytest

from app.assembly.rules import load_assembly_rule

ROUTE_RULES = [
    "sanitary_drainage",
    "water_supply",
    "vent",
    "sprinkler_branch",
    "standpipe",
]
DEVICE_RULES = [
    "storm_downpipe", "sprinkler_head", "hose_cabinet",
    "wc", "lavatory", "sink", "floor_drain", "cleanout", "water_heater",
    "smoke_detector", "call_point", "sounder", "facp",
]


@pytest.mark.parametrize("name", ROUTE_RULES + DEVICE_RULES)
def test_rule_loads_cleanly(name):
    rule = load_assembly_rule(name)
    assert rule is not None, f"{name} failed fail-closed validation"
    assert rule["name"] == name
    assert rule["rule_version"] == "1.0.0"


@pytest.mark.parametrize("name", DEVICE_RULES)
def test_device_rules_have_no_formula_variables(name):
    rule = load_assembly_rule(name)
    assert rule["variables"] == [] or rule["variables"] is None


def test_water_supply_carries_fixture_unit_gauge():
    rule = load_assembly_rule("water_supply")
    gauge = rule.get("fixture_unit_gauge")
    assert gauge and gauge["by"] == "fu_total"
    # ascending thresholds, string->string
    assert int(gauge["rows"]["16"]) == 25


def test_route_rules_declare_fitting_variables():
    for name in ROUTE_RULES:
        rule = load_assembly_rule(name)
        declared = set(rule["variables"])
        assert {"length_m", "diameter_mm", "elbows_90", "tees"} <= declared


def test_fixture_units_declared():
    assert load_assembly_rule("wc").get("fixture_units") == 3.0
    assert load_assembly_rule("lavatory").get("fixture_units") == 1.0
    assert load_assembly_rule("sink").get("fixture_units") == 2.0
    assert load_assembly_rule("floor_drain").get("fixture_units", 0.0) in (None, 0.0)


def test_layer_mapping_routes_new_layers():
    from app.parsing.layer_map import layer_to_assembly

    assert layer_to_assembly("M_SAUDI_RAIN DOWNPIPE") == "storm_downpipe"
    assert layer_to_assembly("P-SAN-MAIN") == "sanitary_drainage"
    assert layer_to_assembly("P-DOM-CW") == "water_supply"
    assert layer_to_assembly("P-VENT") == "vent"
    assert layer_to_assembly("FP-SPRK-BRANCH") == "sprinkler_branch"
    assert layer_to_assembly("FP-SPRK-HEADS") == "sprinkler_head"
    assert layer_to_assembly("FP-STANDPIPE") == "standpipe"
    assert layer_to_assembly("FA-DETECTOR") == "smoke_detector"
    assert layer_to_assembly("FA-CALLPOINT") == "call_point"
    assert layer_to_assembly("FA-SOUNDER") == "sounder"
    assert layer_to_assembly("FA-FACP") == "facp"
    assert layer_to_assembly("FP-HOSE-CAB") == "hose_cabinet"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase4_rules.py -v`
Expected: FAIL — rules don't exist.

- [ ] **Step 3: Author the five route-rule YAMLs**

`data/assemblies/sanitary_drainage.yaml`:

```yaml
name: sanitary_drainage
rule_version: "1.0.0"
variables: [length_m, diameter_mm, elbows_90, tees]
defaults:
  diameter_mm: 100
bom:
  drain_pipe_m:
    formula: "length_m"
    waste_factor: 0.05
  bend_90_elbow:
    formula: "elbows_90 * 1.05"
    waste_factor: 0.0
  junction_tee:
    formula: "tees"
    waste_factor: 0.0
  pipe_bracket: 0.7
labor:
  installation_hours: 1.2
  hourly_rate: 42.00
  category: plumbing
waste_factor: 0.10
```

`data/assemblies/water_supply.yaml`:

```yaml
name: water_supply
rule_version: "1.0.0"
variables: [length_m, diameter_mm, elbows_90, tees]
defaults:
  diameter_mm: 25
bom:
  supply_pipe_m:
    formula: "length_m"
    waste_factor: 0.05
  elbow_fitting:
    formula: "elbows_90"
    waste_factor: 0.0
  tee_fitting:
    formula: "tees"
    waste_factor: 0.0
  pipe_bracket: 0.8
labor:
  installation_hours: 1.0
  hourly_rate: 40.00
  category: plumbing
waste_factor: 0.10
# Owner-editable code table: accumulated fixture units -> nominal diameter_mm.
fixture_unit_gauge:
  by: fu_total
  rows: {"16": "25", "60": "32", "120": "40", "250": "50", "500": "65", "900": "80"}
```

`data/assemblies/vent.yaml`:

```yaml
name: vent
rule_version: "1.0.0"
variables: [length_m, diameter_mm, elbows_90, tees]
defaults:
  diameter_mm: 50
bom:
  vent_pipe_m:
    formula: "length_m"
    waste_factor: 0.05
  bend_90_elbow:
    formula: "elbows_90 * 1.05"
    waste_factor: 0.0
labor:
  installation_hours: 0.8
  hourly_rate: 40.00
  category: plumbing
waste_factor: 0.10
```

`data/assemblies/sprinkler_branch.yaml`:

```yaml
name: sprinkler_branch
rule_version: "1.0.0"
variables: [length_m, diameter_mm, elbows_90, tees]
defaults:
  diameter_mm: 25
bom:
  branch_pipe_m:
    formula: "length_m"
    waste_factor: 0.05
  elbow_fitting:
    formula: "elbows_90"
    waste_factor: 0.0
  tee_fitting:
    formula: "tees"
    waste_factor: 0.0
  hanger_bracket: 1.2
labor:
  installation_hours: 1.1
  hourly_rate: 45.00
  category: fire_protection
waste_factor: 0.10
```

`data/assemblies/standpipe.yaml`:

```yaml
name: standpipe
rule_version: "1.0.0"
variables: [length_m, diameter_mm, elbows_90, tees]
defaults:
  diameter_mm: 100
bom:
  standpipe_m:
    formula: "length_m"
    waste_factor: 0.05
  bend_90_elbow:
    formula: "elbows_90 * 1.05"
    waste_factor: 0.0
  coupling: 0.5
labor:
  installation_hours: 1.4
  hourly_rate: 48.00
  category: fire_protection
waste_factor: 0.10
```

- [ ] **Step 4: Author the thirteen device-rule YAMLs**

Pattern (kit lines are plain multipliers — legacy linear behavior; labor category carries discipline):

`data/assemblies/storm_downpipe.yaml`:

```yaml
name: storm_downpipe
rule_version: "1.0.0"
bom:
  downpipe_kit: 1        # roof outlet + rainwater shoe, per instance
  wall_clip_set: 2
labor:
  installation_hours: 0.9
  hourly_rate: 38.00
  category: plumbing
waste_factor: 0.05
```

`data/assemblies/sprinkler_head.yaml`:

```yaml
name: sprinkler_head
rule_version: "1.0.0"
bom:
  sprinkler_head: 1
  flexible_drops: 0      # owner flips to 1 when flex-drop practice applies
labor:
  installation_hours: 0.5
  hourly_rate: 45.00
  category: fire_protection
waste_factor: 0.02
```

`data/assemblies/hose_cabinet.yaml`:

```yaml
name: hose_cabinet
rule_version: "1.0.0"
bom:
  hose_cabinet: 1
  landing_valve: 1
  hose_30m: 1
labor:
  installation_hours: 2.5
  hourly_rate: 45.00
  category: fire_protection
waste_factor: 0.02
```

`data/assemblies/wc.yaml`:

```yaml
name: wc
rule_version: "1.0.0"
bom:
  water_closet: 1
  angle_valve: 1
  wax_ring: 1
  supply_line: 1
labor:
  installation_hours: 1.5
  hourly_rate: 38.00
  category: plumbing
waste_factor: 0.05
fixture_units: 3
```

`data/assemblies/lavatory.yaml`: same shape — materials `lavatory: 1`, `pop_up_waste: 1`, `angle_valve: 1`, `supply_line: 1`; hours `1.2`; `fixture_units: 1`.

`data/assemblies/sink.yaml`: materials `sink: 1`, `trap: 1`, `angle_valve: 1`, `supply_line: 1`; hours `1.3`; `fixture_units: 2`.

`data/assemblies/floor_drain.yaml`: materials `floor_drain: 1`, `p_trap: 1`; hours `0.8`; **no** `fixture_units` key (drains carry no FU).

`data/assemblies/cleanout.yaml`: materials `cleanout: 1`; hours `0.5`; no FU.

`data/assemblies/water_heater.yaml`: materials `water_heater: 1`, `expansion_vessel: 1`, `isolating_valve: 2`; hours `3.0`; no FU (sized equipment counted per instance).

`data/assemblies/smoke_detector.yaml`: materials `smoke_detector: 1`, `base_plate: 1`; hours `0.4`; category `fire_alarm`.

`data/assemblies/call_point.yaml`: materials `manual_call_point: 1`, `back_box: 1`; hours `0.4`; category `fire_alarm`.

`data/assemblies/sounder.yaml`: materials `sounder: 1`, `back_box: 1`; hours `0.5`; category `fire_alarm`.

`data/assemblies/facp.yaml`: materials `fire_alarm_panel: 1`, `batteries: 1`; hours `6.0`; category `fire_alarm`.

Write every file explicitly (each follows exactly one of the two patterns shown above with the listed material names/quantities — no invented extras).

- [ ] **Step 5: Extend `load_assembly_rule` passthrough + layer mappings**

In `backend/app/assembly/rules.py`, add two lines to the returned dict (after `"defaults"`):

```python
        "fixture_units": data.get("fixture_units"),
        "fixture_unit_gauge": data.get("fixture_unit_gauge") or {},
```

Without the `fixture_units` passthrough, `fixture_units_for_type` (T3) would silently read 0.0 for every fixture — this line is what makes FU accumulation live.

Append to `data/layer_mapping.yaml` (before EOF):

```yaml
  - assembly: sanitary_drainage
    layers:
      - P-SAN-MAIN
      - P-SAN-BRANCH
      - SANITARY
  - assembly: water_supply
    layers:
      - P-DOM-CW
      - P-DOM-HW
      - WATER SUPPLY
  - assembly: vent
    layers:
      - P-VENT
      - VENT PIPE
  - assembly: storm_downpipe
    layers:
      - M_SAUDI_RAIN DOWNPIPE
      - P-STORM
      - DOWNPIPE
  - assembly: sprinkler_branch
    layers:
      - FP-SPRK-BRANCH
      - SPRINKLER PIPE
  - assembly: standpipe
    layers:
      - FP-STANDPIPE
      - STANDPIPE
  - assembly: sprinkler_head
    layers:
      - FP-SPRK-HEADS
      - SPRINKLER HEAD
  - assembly: hose_cabinet
    layers:
      - FP-HOSE-CAB
      - HOSE CABINET
  - assembly: smoke_detector
    layers:
      - FA-DETECTOR
      - FIRE ALARM DETECTOR
  - assembly: call_point
    layers:
      - FA-CALLPOINT
      - FIRE ALARM CALLPOINT
  - assembly: sounder
    layers:
      - FA-SOUNDER
      - FIRE ALARM SOUNDER
  - assembly: facp
    layers:
      - FA-FACP
      - FIRE ALARM PANEL
```

- [ ] **Step 6: Run tests to verify they pass + full suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase4_rules.py tests/test_mechanical_rules.py -v && .venv/Scripts/python.exe -m pytest -q`
Expected: new tests PASS; mechanical rule tests unchanged; full suite green.

- [ ] **Step 7: Commit**

```bash
git add data/assemblies data/layer_mapping.yaml backend/app/assembly/rules.py backend/tests/test_phase4_rules.py
git commit -m "feat(phase4): plumbing/fire-suppression/fire-alarm assembly rules + mappings"
```

---

### Task 6: Generated deterministic plumbing+fire fixture

**Files:**
- Create: `backend/tests/fixtures/make_plumbing_fire_fixture.py`
- Test: `backend/tests/test_phase4_fixture_pdf.py` (create)

**Interfaces:**
- Consumes: helper style of `tests/fixtures/make_hvac_fixture.py` (**read that file first and reuse its document/OCG/text-drawing helpers verbatim by copy or import — it is the reviewed precedent for building OCG-tagged PDFs with pymupdf**).
- Produces: `tests/fixtures/out/plumbing_fire_fixture.pdf` (gitignored output dir like HVAC's), deterministic bytes across runs; consumed by T7's integration test. Ground truth encoded as module constants `EXPECTED = {...}` exported for T7.

- [ ] **Step 1: Read the HVAC fixture generator**

Read `backend/tests/fixtures/make_hvac_fixture.py` end-to-end. Mirror its structure: how it creates the document, registers OCGs, draws tagged paths, inserts text spans, and how its test pins determinism.

- [ ] **Step 2: Write the generator**

Sheet: A3 landscape (1191×842 pt), scale 1:100, title-block text `SCALE 1:100` (so `detect_scale` finds it — copy the HVAC fixture's title-block convention). Register OCGs named exactly: `P-SAN-MAIN`, `P-SAN-BRANCH`, `P-DOM-CW`, `P-VENT`, `FP-SPRK-BRANCH`, `FP-SPRK-HEADS`, `FP-STANDPIPE`, `FA-DETECTOR`, `FA-CALLPOINT`, `FA-SOUNDER`, `FA-FACP`.

Draw (coordinates in pt; every number below is ground truth):

| Element | Geometry | Labels/spans |
| --- | --- | --- |
| Sanitary main | polyline `(100,700)→(400,700)→(400,550)` on `P-SAN-MAIN` — two true 90° bends | text `DN150` centered at `(180,694)` |
| Sanitary branch | polyline `(250,700)→(250,600)` on `P-SAN-BRANCH` — lower endpoint lies ON the main's first segment interior → 1 tee on main | none |
| Cold-water main | polyline `(100,400)→(500,400)` with ONE true elbow via `(500,400)→(560,340)`… draw as `(100,400)→(500,400)→(560,340)` | **no size label** (forces FU tier) |
| CW fixtures | WC symbol (small rect 4×4 pt) ×20 and lavatory circle ×10 placed at y=410..430 spread x=120..480 (within 24 pt corridor of the main); PLUS 1 extra WC at `(800,650)` (far outside corridor — must be excluded) | none |
| Vent stub | single 1-point path on `P-VENT` (degenerate — must produce no route, no phantom BOQ) | none |
| Sprinkler branch | polyline `(700,700)→(950,700)→(950,600)` on `FP-SPRK-BRANCH` — two 90° bends | text `Ø50` at `(760,694)` |
| Sprinkler heads | 6 small circles on `FP-SPRK-HEADS` spread along y≈690 above the branch, each ≥24 pt away from OTHER layers' polylines | none |
| Standpipe | vertical polyline `(1100,750)→(1100,300)` on `FP-STANDPIPE`, zero bends | text `DN100` at `(1090,520)` |
| FA devices | 4 rects on `FA-DETECTOR`, 2 on `FA-CALLPOINT`, 2 circles on `FA-SOUNDER`, 1 larger rect on `FA-FACP` — clustered in legend-like group at `(80..140, 120..220)` | none |

Module tail (exact contract for T7):

```python
EXPECTED = {
    "scale": "1:100",
    "sanitary_main": {"length_pt": 450.0, "size_label": "DN150", "elbows": 2},
    "cold_main": {"length_pt": 458.31, "fu_expected": 70.0, "excluded_fixtures": 1},
    "sprinkler_branch": {"length_pt": 350.0, "size_label": "Ø50", "elbows": 2},
    "standpipe": {"length_pt": 450.0, "size_label": "DN100"},
    "heads": 6,
    "fixtures_in_corridor": {"wc": 20, "lavatory": 10},
    "fa_devices": {"smoke_detector": 4, "call_point": 2, "sounder": 2, "facp": 1},
}

if __name__ == "__main__":
    main()  # writes tests/fixtures/out/plumbing_fire_fixture.pdf
```

Implementation notes: reuse the HVAC generator's OCG-registration and text-insertion helpers; compute `length_pt` by summing Euclidean segment lengths of the exact polylines above (`450.0` and `350.0` and `450.0` are exact; cold main is `400 + √(60²+60²) ≈ 458.31` — assert with `pytest.approx(abs=0.01)`).

- [ ] **Step 3: Write the fixture sanity test**

Create `backend/tests/test_phase4_fixture_pdf.py`:

```python
"""The generated plumbing/fire fixture parses and hits ground truth."""

import subprocess
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
PDF = FIXTURE_DIR / "out" / "plumbing_fire_fixture.pdf"


def _ensure_fixture():
    if not PDF.exists():
        subprocess.run(
            [sys.executable, str(FIXTURE_DIR / "make_plumbing_fire_fixture.py")],
            check=True,
            cwd=str(FIXTURE_DIR.parent.parent),
        )


def test_fixture_builds_and_parses(tmp_path):
    _ensure_fixture()
    import pymupdf

    doc = pymupdf.open(PDF)
    page = doc[0]
    layers = {v["name"] for v in doc.get_ocgs().values()}
    assert {
        "P-SAN-MAIN", "P-DOM-CW", "FP-SPRK-BRANCH", "FA-DETECTOR"
    } <= layers
    drawings = page.get_drawings()
    per_layer = {}
    for d in drawings:
        if d.get("layer"):
            per_layer.setdefault(d["layer"], 0)
            per_layer[d["layer"]] += 1
    assert per_layer.get("FP-SPRK-HEADS", 0) >= 6
    assert per_layer.get("P-VENT", 0) == 1
    text = page.get_text()
    assert "SCALE 1:100" in text
    assert "DN150" in text
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase4_fixture_pdf.py -v`
Expected: PASS on second run (first run generates); deterministic regeneration produces identical parse results.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/fixtures/make_plumbing_fire_fixture.py backend/tests/test_phase4_fixture_pdf.py
git commit -m "test(phase4): deterministic plumbing+fire fixture generator"
```

---

### Task 7: E2E wiring + regression suite

**Files:**
- Modify: `backend/app/e2e/extraction.py` (assembly-set constants), `backend/app/e2e/router.py` (route-loop context)
- Test: `backend/tests/test_phase4_regression.py` (create)

**Interfaces:**
- Consumes: everything from T1–T6; existing `measure_routes`, `count_components`, `apply_assembly`, `resolve_route_size` signatures.
- Produces:
  - `ROUTE_ASSEMBLIES` extended with `{"sanitary_drainage", "water_supply", "vent", "sprinkler_branch", "standpipe"}`; `SIZED_ASSEMBLIES` extended with the same five (NOT `storm_downpipe` — counted kit, see Global Constraints refinement 1).
  - New helper in router.py: `resolve_route_context(assembly_type: str, route: Dict, cascade_spans: List[Dict], scale: str, schedule_rows: List[Dict], components: List[Dict], settings: Settings) -> Optional[Tuple[Dict, Optional[str], Optional[Dict]]]` returning `(variables, size_source, size)` or None when the route must be dropped. Variables always bind `length_m`, resolved size vars, `elbows_90`, `tees` (fittings default 0); for `water_supply` the size may come from the FU tier. `size` is the raw cascade dict (carrying `fu_total`/`ref` when FU-sourced) so `route_sizes[route_index] = {**size, "source": size_source}` works exactly as today. The route loop calls this instead of its current inline cascade block; response/persistence shapes are unchanged.

- [ ] **Step 1: Extract `resolve_route_context` (behavior-preserving refactor)**

Move the body of the current `if assembly_type in SIZED_ASSEMBLIES:` block (router.py ≈lines 365–400) into the new pure function. Behavior changes ONLY in that fittings vars and the FU tier join the context:

```python
def resolve_route_context(
    assembly_type: str,
    route: Dict,
    cascade_spans: List[Dict],
    scale: str,
    schedule_rows: List[Dict],
    components: List[Dict],
    settings: "Settings",
) -> Optional[Tuple[Dict, Optional[str], Optional[Dict]]]:
    """Cascade + fittings + FU for one sized route.

    Returns (variables, size_source, size) or None if the route must be
    dropped (fail-honest). `size` is the raw cascade dict including any
    fu_total/ref provenance keys.
    """
    from app.parsing.fittings import derive_fittings
    from app.parsing.fixture_units import accumulate_fixture_units, resolve_size_from_fixture_units

    mech_rule = load_assembly_rule(assembly_type) or {}
    fu_size = None
    if assembly_type == "water_supply":
        polyline = [(float(x), float(y)) for x, y in route.get("polyline") or []]
        # Adapt extraction rows (assembly_type/x/y + positional key) at the
        # boundary — never mutate the extraction dicts themselves.
        fu_comps = [
            {
                "key": f"{idx}@{c.get('source_path_ids', [''])[0] or idx}",
                "component_type": c.get("assembly_type"),
                "x": float(c.get("x", 0.0)),
                "y": float(c.get("y", 0.0)),
            }
            for idx, c in enumerate(components)
            if c.get("assembly_type")
        ]
        fu_total, breakdown = accumulate_fixture_units(
            polyline, fu_comps, corridor_pt=settings.fu_corridor_pt
        )
        gauge = mech_rule.get("fixture_unit_gauge") or {}
        if fu_total > 0.0 and gauge:
            size = resolve_size_from_fixture_units(fu_total, gauge.get("rows") or {})
            if size:
                fu_size = {
                    **size,
                    "fu_total": fu_total,
                    "ref": [f"{b['component_type']}@{b['key']}" for b in breakdown],
                }

    size = resolve_route_size(
        route,
        cascade_spans,
        scale,
        schedule_rows=schedule_rows,
        default_size=mech_rule.get("defaults") or None,
        fixture_unit_size=fu_size,
    )
    if size is None:
        return None
    size_source = size.get("source")
    required_size_vars = set(mech_rule.get("variables") or []) - {
        "length_m", "max_mm", "elbows_90", "tees",
    }
    if any(var not in size for var in required_size_vars):
        size_source = "assumed"

    fittings = derive_fittings(
        route,
        bend_angle_deg=settings.fitting_bend_angle_deg,
        min_segment_pt=settings.fitting_min_segment_pt,
        junction_tol_pt=settings.fitting_junction_tol_pt,
    )
    variables = {
        "length_m": route["length_m"],
        "elbows_90": float(fittings["elbows_90"]),
        "tees": float(fittings["tees"]),
        **{k: v for k, v in size.items() if k in ("width_mm", "height_mm", "diameter_mm")},
    }
    # Persisted-route parity: only stamp fitting counts onto the size dict
    # when the rule actually declares them (mechanical rules don't — their
    # size_json stays byte-compatible).
    if {"elbows_90", "tees"} <= set(mech_rule.get("variables") or []):
        size = {
            **size,
            "elbows_90": float(fittings["elbows_90"]),
            "tees": float(fittings["tees"]),
        }
    return variables, size_source, size
```

The route loop becomes:

```python
                variables = None
                size_source = None
                if assembly_type in SIZED_ASSEMBLIES:
                    ctx = resolve_route_context(
                        assembly_type, route, cascade_spans, scale,
                        schedule_rows, extraction_components, get_settings(),
                    )
                    if ctx is None:
                        logger.warning(
                            "dropping %s route (%.3f m): no resolvable "
                            "cross-section size and no configured default",
                            assembly_type, route["length_m"],
                        )
                        continue
                    variables, size_source, resolved_size = ctx
                    # Persist the EFFECTIVE tier exactly as before the
                    # refactor; FU provenance rides along inside size.
                    route_sizes[route_index] = {**resolved_size, "source": size_source}
```

Import `get_settings` from `app.core.config` alongside existing imports.

**Persisted-route parity (required — do not skip):** `_persist_route_boq` (`app/e2e/persistence.py:147-167`) rebuilds variables as `{"length_m": ..., **_size_variables(size_json)}`. Without a change, plumbing routes would drop at persist time with `FormulaValidationError` ("elbows_90 unbound") and the DB would silently diverge from the response math. Extend `_size_variables`:

```python
def _size_variables(size_json: dict | None) -> dict[str, float]:
    size = size_json or {}
    out = {
        k: float(size[k])
        for k in ("width_mm", "height_mm", "diameter_mm", "elbows_90", "tees")
        if k in size
    }
    return out
```

(Keep whatever the current function body does beyond the size keys — read it first; the change is additive: lift `elbows_90`/`tees` when present. Mechanical routes never carry those keys, so their persisted rows are unchanged.)

Replay of the fitting BOQ lines needs no new branch: `apply_assembly` snapshots `caller_vars` into each material's derivation `inputs`, which now include `elbows_90`/`tees`, so the existing formula branch replays them.

- [ ] **Step 2: Update constants**

`backend/app/e2e/extraction.py`:

```python
ROUTE_ASSEMBLIES = {
    "cable_tray",
    "conduit",
    "duct_rectangular",
    "duct_round",
    "pipe_insulated",
    "sanitary_drainage",
    "water_supply",
    "vent",
    "sprinkler_branch",
    "standpipe",
}
SIZED_ASSEMBLIES = {
    "duct_rectangular",
    "duct_round",
    "pipe_insulated",
    "sanitary_drainage",
    "water_supply",
    "vent",
    "sprinkler_branch",
    "standpipe",
}
```

- [ ] **Step 3: Write the failing regression suite**

Create `backend/tests/test_phase4_regression.py` with four tests (follow `test_hvac_fixture.py`'s TestClient/upload pattern):

```python
"""Phase 4 DoD gates: fixture e2e, MMC downpipes, FIRE ALARM honest-zero."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.fixtures.make_plumbing_fire_fixture import EXPECTED

client = TestClient(app)
SAMPLES = Path("data/samples")


def _run(pdf_path: Path, **params):
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        pytest.skip(f"sample missing: {pdf_path}")
    with open(pdf_path, "rb") as f:
        resp = client.post(
            "/api/e2e/run",
            files={"file": (pdf_path.name, f.read(), "application/pdf")},
            params=params,
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_plumbing_fire_fixture_end_to_end(tmp_path):
    from tests.test_phase4_fixture_pdf import _ensure_fixture, PDF

    _ensure_fixture()
    payload = _run(PDF)
    boq = payload["boq_items"]

    def qty(assembly, material):
        return sum(
            i["quantity"] for i in boq
            if i["assembly"] == assembly and i["material_name"] == material
        )

    # Counted devices
    assert qty("sprinkler_head", "sprinkler_head") == EXPECTED["heads"]
    for asm, n in EXPECTED["fa_devices"].items():
        got = qty(asm, {"smoke_detector": "smoke_detector",
                        "call_point": "manual_call_point",
                        "sounder": "sounder",
                        "facp": "fire_alarm_panel"}[asm])
        assert got == n
    # Storm/downpipe-style counted kits on the fixture: none drawn there
    assert qty("storm_downpipe", "downpipe_kit") == 0

    # Sized routes: lengths scale pt -> m at 1:100 (pt * 100 * 25.4/72 / 1000)
    PT_TO_M = 100 * 25.4 / 72 / 1000
    san = qty("sanitary_drainage", "drain_pipe_m")
    assert san == pytest.approx(EXPECTED["sanitary_main"]["length_pt"] * PT_TO_M * 1.05, rel=1e-6)

    # FU tier drove the CW main diameter (70 FU -> 32mm), not the 25mm default
    cw_rows = [i for i in boq if i["assembly"] == "water_supply"]
    assert cw_rows, "cold-water main produced no BOQ"
    assert all(i["size_source"] == "fixture_units" for i in cw_rows)
    # diameter proof via derivation inputs:
    inputs = [i["derivation"]["inputs"] for i in cw_rows if i.get("derivation")]
    assert inputs and all(inp["diameter_mm"] == 32.0 for inp in inputs)


    # Fittings derived: sanitary main has 2 elbows + 1 tee (branch junction)
    elb = [i for i in boq if i["assembly"] == "sanitary_drainage"
           and i["material_name"] == "bend_90_elbow"]
    assert elb and elb[0]["quantity"] == pytest.approx(2 * 1.05)
    tee = [i for i in boq if i["assembly"] == "sanitary_drainage"
           and i["material_name"] == "junction_tee"]
    assert tee and tee[0]["quantity"] == 1.0


def test_mmc_rain_downpipes_counted():
    payload = _run(SAMPLES / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf")
    boq = payload["boq_items"]
    kits = [i for i in boq if i["assembly"] == "storm_downpipe"
            and i["material_name"] == "downpipe_kit"]
    assert kits, "downpipe kit missing from MMC run"
    # Exact count pinned by probe in Step 4 — replace PIN with measured value
    assert kits[0]["quantity"] == pytest.approx(DOWNPIPE_PIN)


def test_mmc_fire_alarm_layer_honest_zero():
    payload = _run(SAMPLES / "MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf")
    # Layer classified fire_alarm...
    fa_layers = [l for l in payload["layers"]
                 if l["ocg_name"] == "FIRE ALARM"]
    assert fa_layers and fa_layers[0]["classified_discipline"] == "fire_alarm"
    # ...but zero paths -> zero components -> zero BOQ rows, ever
    alarm_assemblies = {"smoke_detector", "call_point", "sounder", "facp"}
    assert not any(i["assembly"] in alarm_assemblies for i in payload["boq_items"])
    unmapped_fa = [u for u in payload.get("unmapped_items", [])
                   if u.get("layer") == "FIRE ALARM"]
    assert not unmapped_fa
```

(`DOWNPIPE_PIN` is a module constant you set in Step 4.)

- [ ] **Step 4: Pin the MMC downpipe count with a probe**

Before running the regression, measure reality through the production counting path:

```bash
cd backend && .venv/Scripts/python.exe -c "
import pymupdf
from app.ingestion.vector import extract_paths, build_ocg_registry, cluster_paths_threshold
doc = pymupdf.open('../data/samples/MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf')
page = doc[0]
paths = extract_paths(page)
clusters = cluster_paths_threshold(paths, 'M_SAUDI_RAIN DOWNPIPE')
print('clusters:', len(clusters))
print('sizes:', [len(c['path_ids']) for c in clusters])
"
```

(Adapt call signature to the actual `extract_paths`/`cluster_paths_threshold` names in `app/ingestion/vector.py` — read that file first.) Record the cluster count as `DOWNPIPE_PIN` at the top of `test_phase4_regression.py`. Expected ≈ 11 (44 paths, ~4 per location, double/triple-drawn merge). If the count is wildly different, STOP and record why — do not tune clustering to reach 11.

Also assert stability: run the probe twice; counts must be identical (deterministic union-find).

Then run the whole regression file:

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase4_regression.py -v`
Expected: fixture e2e PASS; MMC downpipes PASS with pinned count; honest-zero PASS.

- [ ] **Step 5: Full suite + lint (regression locks must hold)**

Run: `cd backend && .venv/Scripts/python.exe -m ruff check app tests && .venv/Scripts/python.exe -m pytest -q`
Expected: ruff clean; suite green INCLUDING all prior phase locks (electrical counts, S101 equipment, HVAC fixture, exports byte-for-value, v3 integration). If a prior lock moved, investigate — never re-baseline silently.

- [ ] **Step 6: Commit**

```bash
git add backend/app/e2e/extraction.py backend/app/e2e/router.py backend/tests/test_phase4_regression.py
git commit -m "feat(phase4): e2e plumbing/fire branch + DoD regression suite"
```

---

### Task 8: Replay parity + docs sync

**Files:**
- Modify: `backend/app/estimates/router.py` (replay), `docs/Phases.md`
- Test: `backend/tests/test_phase4_replay.py` (create)

**Interfaces:**
- Consumes: persisted `Route.size_json` with `source=="fixture_units"` carrying `{diameter_mm, fu_total, ref:[...]}`; BoqItems whose `derivation_json.inputs.diameter_mm` came from that size; `load_assembly_rule("water_supply")["fixture_unit_gauge"]`; `resolve_size_from_fixture_units` (T3).
- Produces: `/api/estimates/{id}/replay` additionally verifies every `fixture_units`-sourced route on the estimate (coherence check, Global Constraint refinement 2); Phases.md Phase 4 section records implementation status + the two spec refinements.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_phase4_replay.py` (persist→replay pattern copied from `test_v3_integration.py` — read it first for the exact upload/persist/replay client calls):

```python
"""Replay parity for fixture_units-sourced routes (fail-closed coherence)."""

import json

from tests.test_phase4_regression import _run, client  # reuse upload helper
from tests.test_phase4_fixture_pdf import _ensure_fixture, PDF


def _persisted_estimate_id() -> str:
    _ensure_fixture()
    payload = _run(PDF, persist=True)
    assert payload.get("estimate_id")
    return payload["estimate_id"]


def test_replay_green_on_clean_fixture_run():
    est_id = _persisted_estimate_id()
    resp = client.get(f"/api/estimates/{est_id}/replay")
    assert resp.status_code == 200, resp.text
    assert resp.json()["mismatches"] == []
    assert resp.json()["checked"] > 0


def test_tampered_fu_total_fails_closed(est_id=None):
    est_id = _persisted_estimate_id()
    # Flip fu_total on the water_supply route's size_json directly in the DB
    from sqlalchemy import create_engine, text as sql_text
    from app.core.config import get_settings

    engine = create_engine(get_settings().database_url.replace("./aec.db", "./aec.db"))
    with engine.begin() as conn:
        row = conn.execute(sql_text(
            "SELECT id, size_json FROM routes WHERE size_json LIKE '%fixture_units%'"
        )).fetchone()
        assert row, "expected a fixture_units-sourced route"
        size = json.loads(row[1])
        size["fu_total"] = size["fu_total"] + 1000.0  # pushes past top threshold
        conn.execute(sql_text(
            "UPDATE routes SET size_json=:s WHERE id=:i"
        ), {"s": json.dumps(size), "i": row[0]})

    resp = client.get(f"/api/estimates/{est_id}/replay")
    assert resp.status_code == 409
```

DB access detail: use the app's session factory exactly as `test_persistence_spine.py` does (read it first and copy its engine/session setup — do not invent a parallel one; the sketch above shows the tamper intent only).

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase4_replay.py -v`
Expected: `test_replay_green_on_clean_fixture_run` PASSES only incidentally (BOQ formulas replay from recorded inputs) BUT the tamper test FAILS (replay returns 200 — no route-size verification exists yet).

- [ ] **Step 3: Implement route-size coherence verification**

In `backend/app/estimates/router.py`, inside `replay_estimate`, after the BOQ-item loop, add route-size coherence verification. Reach the routes through the BOQ items' measurements (BoqItem → Measurement.route, `app/db/models/estimate.py:18`) — no sheet walk needed:

```python
    # Phase 4: fixture_units-sourced route sizes must stay coherent with
    # their recorded FU totals, breakdown refs, and the rule's gauge table.
    seen_route_ids: set[uuid.UUID] = set()
    for item in estimate.boq_items:
        route_row = getattr(getattr(item, "measurement", None), "route", None)
        if route_row is None or route_row.id in seen_route_ids:
            continue
        seen_route_ids.add(route_row.id)
        size = _load_size_json(route_row.size_json)
        if not isinstance(size, dict) or size.get("source") != "fixture_units":
            continue
        checked += 1
        if not _verify_fu_size(size):
            mismatches.append(f"route:{route_row.id}")
```

With module-level helpers:

```python
def _load_size_json(raw) -> dict | None:
    import json as _json
    try:
        return _json.loads(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _verify_fu_size(size: dict) -> bool:
    gauge = (load_assembly_rule("water_supply") or {}).get("fixture_unit_gauge") or {}
    try:
        fu_total = float(size["fu_total"])
        diameter = float(size["diameter_mm"])
        breakdown = size["ref"]
    except (KeyError, TypeError, ValueError):
        return False
    if not isinstance(breakdown, list) or not breakdown:
        return False  # an FU-resolved size with no contributing fixtures is incoherent
    resolved = resolve_size_from_fixture_units(fu_total, gauge.get("rows") or {})
    if not resolved or abs(resolved["diameter_mm"] - diameter) > 1e-9:
        return False
    # Breakdown coherence: each "type@key" ref's rule YAML FU must exist,
    # and the recorded FUs must sum to the recorded total (T7 writes both).
    total = 0.0
    for token in breakdown:
        ctype = str(token).split("@", 1)[0]
        fu = fixture_units_for_type(ctype)
        if fu <= 0.0:
            return False
        total += fu
    return abs(total - fu_total) <= 1e-6
```

Top of file import: `from app.parsing.fixture_units import fixture_units_for_type, resolve_size_from_fixture_units` (module level, not inline). Corrupt/unparseable `size_json` on a `fixture_units` row returns None from `_load_size_json` and is skipped by the isinstance guard — tighten it: `if raw and not isinstance(size, dict): mismatches.append(...)` so present-but-corrupt fails honest (mirroring the derivation F2 rule).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest tests/test_phase4_replay.py tests/test_v3_integration.py -v`
Expected: BOTH PASS — clean run replays green; tampered fu_total 409s; existing v3 integration untouched.

- [ ] **Step 5: Sync docs**

In `docs/Phases.md`, under `## Phase 4 — Plumbing & Fire Protection`, append an implemented-notes subsection recording:
- what landed (classification disciplines, fittings module, fixture-units module + cascade tier, 18 rule files, e2e branch, replay coherence),
- the two spec refinements verbatim from Global Constraints,
- validation summary (fixture e2e, MMC downpipe pin = `<PINNED VALUE>` + determinism proof, honest-zero FIRE ALARM, replay 409 tamper case),
- the human-confirm gate: fixture-unit values (wc 3 / lavatory 1 / sink 2), gauge thresholds, ASSUMED defaults — owner-editable YAML pending ruling,
- real-sheet swap trigger clause.

Mark the section 🟦 in progress (DoD completes on human confirmation of YAML values + first real sheet).

- [ ] **Step 6: Full suite + lint, then commit**

Run: `cd backend && .venv/Scripts/python.exe -m ruff check app tests && .venv/Scripts/python.exe -m pytest -q`
Expected: ruff clean; suite green.

```bash
git add backend/app/estimates/router.py backend/tests/test_phase4_replay.py docs/Phases.md backend/app/e2e/router.py backend/tests/test_phase4_regression.py
git commit -m "feat(phase4): replay coherence for fixture-unit sizes + docs sync"
```

---

## Completion Checklist

- [ ] All 8 tasks committed on `feature/phase-4-plumbing-fire-protection`
- [ ] Full suite green (≥ baseline 238 + ~30 new), ruff clean
- [ ] Regression locks byte-identical (electrical, S101, HVAC, exports)
- [ ] `DOWNPIPE_PIN` recorded with probe evidence in test comment
- [ ] Phases.md amended; Memory.md updated at session end
- [ ] Human-confirm queue raised: FU values, gauge thresholds, ASSUMED defaults
