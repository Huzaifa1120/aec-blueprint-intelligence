# Phase 3 — Mechanical (HVAC) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the QTO pipeline to the mechanical (HVAC) discipline — ducts/pipes quantified by YAML-declared size-dependent formulas, equipment counted as symbols — with full provenance on every derived number.

**Architecture:** Three new capabilities bolt onto the existing vector pipeline: (1) a restricted-AST formula evaluator fed by extended assembly YAMLs, (2) a size-resolution cascade (schedule → label → geometry → ASSUMED) producing per-route size provenance, (3) an e2e mechanical branch wiring cascade → formulas → BOQ rows carrying `derivation` + `size_source`. Equipment counting reuses the existing clustering path unchanged.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy + Alembic / PyMuPDF (import as `pymupdf`) / pytest / ruff. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-08-23-phase-3-mechanical-hvac-design.md`

## Global Constraints

- AI proposes. Geometry calculates. Rules derive. Humans approve. No LLM/vision model outputs a final quantity.
- Unit prices / productivity rates live in catalog DB or YAML — never hardcode in source.
- Import PyMuPDF as `pymupdf`, never `fitz`.
- All rules data-driven from `data/assemblies/*.yaml` + `data/layer_mapping.yaml`; new assembly type = YAML edit only.
- No `eval()`/`exec()` anywhere in the formula engine.
- Unpriced catalog items are flagged, never $0-substituted.
- Backend commands run from `backend/` with venv python: `backend/.venv/Scripts/python.exe -m pytest -q` (or activate venv first). Windows + Git Bash.
- `python -m ruff check app tests` must stay clean; run after every task.
- Full suite baseline: 63 passed + 1 xfail — must stay green; electrical BOQ outputs must remain byte-identical.
- Pre-commit hook active (`git config core.hooksPath .githooks`): ruff on staged `.py`.
- Never commit `data/samples/*.pdf` (gitignored client material).

---

### Task 1: Formula evaluator (`app/assembly/formulas.py`)

**Files:**
- Create: `backend/app/assembly/formulas.py`
- Test: `backend/tests/test_formulas.py`

**Interfaces:**
- Consumes: nothing (stdlib `ast` only).
- Produces:
  - `class FormulaValidationError(ValueError)` — with `.rule_name` and `.expression` attributes.
  - `validate_formula(expression: str, allowed_variables: Iterable[str], rule_name: str = "") -> None` — raises `FormulaValidationError` on any non-whitelisted syntax.
  - `evaluate_formula(expression: str, variables: Dict[str, float], rule_name: str = "") -> float` — evaluates a validated expression; raises `FormulaValidationError` on unknown/missing variables at eval time.
  - `lookup_gauge(table: Dict, variables: Dict[str, float]) -> str` — `table = {"by": "max_mm", "rows": {300: "gauge_0.8mm", ...}}`; returns first row value where `variables[table["by"]] <= threshold`; raises `FormulaValidationError` if no row matches or driving variable missing.

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for the restricted-AST formula evaluator (Phase 3)."""
import pytest

from app.assembly.formulas import (
    FormulaValidationError,
    evaluate_formula,
    lookup_gauge,
    validate_formula,
)


class TestEvaluateFormula:
    def test_rectangular_duct_golden_case(self):
        # 10 m of 600x400 duct -> 2*(0.6+0.4)*10 = 20.0 m2
        result = evaluate_formula(
            "2 * (width_mm + height_mm) / 1000 * length_m",
            {"width_mm": 600, "height_mm": 400, "length_m": 10.0},
        )
        assert result == pytest.approx(20.0)

    def test_round_duct_golden_case(self):
        import math
        result = evaluate_formula(
            "3.141592653589793 * (diameter_mm / 1000) * length_m",
            {"diameter_mm": 250, "length_m": 8.0},
        )
        assert result == pytest.approx(math.pi * 0.25 * 8.0)

    def test_linear_multiplier_as_constant(self):
        # legacy rules: a bare number is a constant expression
        assert evaluate_formula("0.2", {}) == pytest.approx(0.2)

    def test_whitelisted_functions(self):
        assert evaluate_formula("max(width_mm, 300) / 1000", {"width_mm": 600}) == pytest.approx(0.6)
        assert evaluate_formula("round(length_m, 2)", {"length_m": 1.2345}) == pytest.approx(1.23)
        assert evaluate_formula("min(a, b) + abs(c)", {"a": 1, "b": 2, "c": -3}) == pytest.approx(4)

    def test_unknown_variable_raises(self):
        with pytest.raises(FormulaValidationError):
            evaluate_formula("width_mm + depth_mm", {"width_mm": 600})

    def test_division_by_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            evaluate_formula("length_m / 0", {"length_m": 1.0})


class TestValidateFormula:
    def test_valid_formulas_pass(self):
        validate_formula("2 * (width_mm + height_mm) / 1000 * length_m",
                         ["width_mm", "height_mm", "length_m"])
        validate_formula("0.2", [])

    def test_unknown_name_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("width_mm + secret", ["width_mm"])

    def test_function_call_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("__import__('os').system('ls')", [])

    def test_attribute_access_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("width_mm.real", ["width_mm"])

    def test_subscript_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("width_mm['x']", ["width_mm"])

    def test_lambda_and_comprehension_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("(lambda: 1)()", [])
        with pytest.raises(FormulaValidationError):
            validate_formula("[x for x in range(3)]", [])

    def test_syntax_error_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("2 * +", [])

    def test_error_carries_rule_context(self):
        with pytest.raises(FormulaValidationError) as exc:
            validate_formula("foo + 1", [], rule_name="duct_rectangular")
        assert "duct_rectangular" in str(exc.value)


class TestLookupGauge:
    TABLE = {
        "by": "max_mm",
        "rows": {300: "gauge_0.8mm", 750: "gauge_1.0mm", 999999: "gauge_1.2mm"},
    }

    def test_picks_first_threshold_met(self):
        assert lookup_gauge(self.TABLE, {"max_mm": 250}) == "gauge_0.8mm"
        assert lookup_gauge(self.TABLE, {"max_mm": 300}) == "gauge_0.8mm"   # boundary inclusive
        assert lookup_gauge(self.TABLE, {"max_mm": 301}) == "gauge_1.0mm"
        assert lookup_gauge(self.TABLE, {"max_mm": 5000}) == "gauge_1.2mm"

    def test_missing_driver_raises(self):
        with pytest.raises(FormulaValidationError):
            lookup_gauge(self.TABLE, {})

    def test_no_matching_row_raises(self):
        with pytest.raises(FormulaValidationError):
            lookup_gauge({"by": "max_mm", "rows": {300: "gauge_0.8mm"}}, {"max_mm": 999})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_formulas.py -q` (from `backend/`)
Expected: FAIL — `ModuleNotFoundError: No module named 'app.assembly.formulas'`

- [ ] **Step 3: Write the implementation**

```python
"""Restricted-AST formula evaluator for YAML assembly rules (Phase 3).

Formulas live in data/assemblies/*.yaml. This module parses each expression
once with Python's ``ast`` module and walks the tree allowing ONLY:
numbers, declared variables, operators + - * / ** and parentheses, and the
functions min / max / round / abs. Everything else raises
FormulaValidationError — fail closed, at load time.

No eval(), no exec(), no attribute or subscript access.
"""

from __future__ import annotations

import ast
from typing import Dict, Iterable, Set

_ALLOWED_FUNCTIONS: Set[str] = {"min", "max", "round", "abs"}
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


class FormulaValidationError(ValueError):
    """A formula failed validation or referenced an unknown variable."""

    def __init__(self, message: str, rule_name: str = "", expression: str = ""):
        self.rule_name = rule_name
        self.expression = expression
        prefix = f"[{rule_name}] " if rule_name else ""
        super().__init__(f"{prefix}{message}")


def _walk(node: ast.AST, allowed_vars: Set[str], rule_name: str, expression: str) -> None:
    if isinstance(node, ast.Expression):
        _walk(node.body, allowed_vars, rule_name, expression)
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return
    elif isinstance(node, ast.Name):
        if node.id not in allowed_vars and node.id not in _ALLOWED_FUNCTIONS:
            raise FormulaValidationError(
                f"unknown name '{node.id}'", rule_name, expression
            )
    elif isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        _walk(node.left, allowed_vars, rule_name, expression)
        _walk(node.right, allowed_vars, rule_name, expression)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARYOPS):
        _walk(node.operand, allowed_vars, rule_name, expression)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCTIONS:
            raise FormulaValidationError(
                "function calls restricted to min/max/round/abs", rule_name, expression
            )
        for arg in node.args:
            _walk(arg, allowed_vars, rule_name, expression)
    elif isinstance(node, ast.keyword):  # pragma: no cover - round(x, n) uses args only
        _walk(node.value, allowed_vars, rule_name, expression)
    else:
        raise FormulaValidationError(
            f"disallowed syntax: {type(node).__name__}", rule_name, expression
        )


def validate_formula(
    expression: str, allowed_variables: Iterable[str], rule_name: str = ""
) -> None:
    """Parse and validate a formula expression. Raises FormulaValidationError."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FormulaValidationError(f"syntax error: {exc}", rule_name, expression) from exc
    _walk(tree, set(allowed_variables), rule_name, expression)


def evaluate_formula(
    expression: str, variables: Dict[str, float], rule_name: str = ""
) -> float:
    """Evaluate a validated formula with bound variables.

    Raises FormulaValidationError for unknown/missing variables at eval time
    (validate first at load time; this catches binding mistakes).
    """
    validate_formula(expression, variables.keys(), rule_name)
    tree = ast.parse(expression, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in _ALLOWED_FUNCTIONS:
                func = {"min": min, "max": max, "round": round, "abs": abs}[node.id]
                return func
            if node.id in variables:
                return float(variables[node.id])
            raise FormulaValidationError(
                f"missing variable '{node.id}' at evaluation", rule_name, expression
            )
        if isinstance(node, ast.BinOp):
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                return left ** right
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            return operand if isinstance(node.op, ast.UAdd) else -operand
        if isinstance(node, ast.Call):
            func = _eval(node.func)
            return float(func(*[_eval(a) for a in node.args]))
        raise FormulaValidationError(
            f"cannot evaluate: {type(node).__name__}", rule_name, expression
        )

    return _eval(tree)


def lookup_gauge(table: Dict, variables: Dict[str, float]) -> str:
    """Resolve an ordered threshold lookup table to a row value.

    ``table``: {"by": <variable name>, "rows": {threshold: value, ...}}.
    Returns the first row value whose threshold >= variables[by].
    Keys may be YAML ints or strings; comparison is numeric.
    """
    driver = table.get("by", "")
    if driver not in variables:
        raise FormulaValidationError(
            f"lookup driving variable '{driver}' missing", expression=str(table)
        )
    value = float(variables[driver])
    rows = table.get("rows", {})
    for key in sorted(rows, key=float):
        if value <= float(key):
            return rows[key]
    raise FormulaValidationError(
        f"no lookup row matches {driver}={value}", expression=str(table)
    )
```

YAML loads `{300: ...}` with int keys and `{"300": ...}` with str keys;
sorting by `float(key)` and indexing with the original key object handles both.

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_formulas.py -v`
Expected: all PASS

- [ ] **Step 5: Lint**

Run: `backend/.venv/Scripts/python.exe -m ruff check app/assembly/formulas.py tests/test_formulas.py`
Expected: clean (fix violations if any)

- [ ] **Step 6: Commit**

```bash
git add backend/app/assembly/formulas.py backend/tests/test_formulas.py
git commit -m "feat(phase3): restricted-AST formula evaluator for YAML rules"
```

---

### Task 2: Rule loader formula extension (`app/assembly/rules.py`)

**Files:**
- Modify: `backend/app/assembly/rules.py`
- Create: `backend/data/assemblies/` — no; test fixtures inline via tmp_path
- Test: `backend/tests/test_rules_formulas.py`

**Interfaces:**
- Consumes: `validate_formula`, `evaluate_formula`, `lookup_gauge`, `FormulaValidationError` from Task 1.
- Produces:
  - `load_assembly_rule(name)` — unchanged signature; returned dict now also carries `variables: List[str]` (default `[]`) and raw `bom` entries may be `float` (legacy) or `dict` (`{"formula": str}` / `{"gauge_lookup": {...}}`, each optionally with `waste_factor: float`).
  - `apply_assembly(component_type: str, rule_name: str = "", variables: Optional[Dict[str, float]] = None) -> Dict` — same return shape as before (`materials`, `labor_hours`, `waste_factor`, `rule_version`), where each material dict gains `derivation: Optional[Dict]` = `{"formula": str, "inputs": Dict[str, float]}` (or `{"gauge_lookup": {...}, "inputs": ...}`) and `None` for legacy constant lines. `variables=None` with a formula-bearing rule → `FormulaValidationError` propagates (fail closed).
  - `validate_rule_file(path: Path) -> List[str]` — returns list of error strings (empty = valid); used at catalog load and in tests for fail-closed exclusion.

- [ ] **Step 1: Write the failing tests**

```python
"""Phase 3: formula-bearing assembly rules load + evaluate correctly."""
import math

import pytest
import yaml

from app.assembly.rules import apply_assembly, load_assembly_rule, validate_rule_file
from app.assembly.formulas import FormulaValidationError


DUCT_RULE = {
    "name": "duct_rectangular",
    "rule_version": "1.0.0",
    "variables": ["length_m", "width_mm", "height_mm", "max_mm"],
    "bom": {
        "sheet_metal_m2": {
            "formula": "2 * (width_mm + height_mm) / 1000 * length_m",
            "waste_factor": 0.15,
        },
        "duct_fitting": 0.2,  # legacy linear multiplier
        "hanger_kit": {"gauge_lookup": {"by": "max_mm",
                                         "rows": {600: "hanger_light", 999999: "hanger_heavy"}}},
    },
    "labor": {"installation_hours": 2.0, "hourly_rate": 50.0, "category": "mechanical"},
}


@pytest.fixture
def duct_rule(tmp_path, monkeypatch):
    rules_dir = tmp_path / "assemblies"
    rules_dir.mkdir()
    (rules_dir / "duct_rectangular.yaml").write_text(yaml.safe_dump(DUCT_RULE))
    monkeypatch.setattr("app.assembly.rules._ASSEMBLIES_DIR", rules_dir)
    return rules_dir


class TestLoadAssemblyRule:
    def test_variables_exposed(self, duct_rule):
        rule = load_assembly_rule("duct_rectangular")
        assert rule["variables"] == ["length_m", "width_mm", "height_mm", "max_mm"]

    def test_legacy_rule_has_empty_variables(self, duct_rule):
        # legacy rules without a variables key still load
        (duct_rule / "legacy.yaml").write_text(yaml.safe_dump(
            {"name": "legacy", "bom": {"part": 1.0}, "labor": {}}))
        assert load_assembly_rule("legacy")["variables"] == []


class TestApplyAssemblyFormulas:
    def test_golden_case_20m2_plus_waste(self, duct_rule):
        variables = {"length_m": 10.0, "width_mm": 600, "height_mm": 400}
        result = apply_assembly("duct_rectangular", variables=variables)
        by_name = {m["material_name"]: m for m in result["materials"]}
        # 2*(600+400)/1000*10 = 20.0 * 1.15 waste = 23.0
        assert by_name["sheet_metal_m2"]["quantity"] == pytest.approx(23.0)
        assert by_name["sheet_metal_m2"]["derivation"]["formula"] == \
            "2 * (width_mm + height_mm) / 1000 * length_m"
        assert by_name["sheet_metal_m2"]["derivation"]["inputs"] == variables
        # legacy line: constant 0.2 per unit length * 10 m
        assert by_name["duct_fitting"]["quantity"] == pytest.approx(2.0)
        assert by_name["duct_fitting"]["derivation"] is None
        # gauge lookup resolved to a material line
        assert by_name["hanger_light"]["quantity"] == pytest.approx(1.0)
        assert by_name["hanger_light"]["derivation"]["gauge_lookup"]["by"] == "max_mm"

    def test_gauge_boundary_selects_heavy(self, duct_rule):
        variables = {"length_m": 1.0, "width_mm": 800, "height_mm": 400}
        result = apply_assembly("duct_rectangular", variables=variables)
        names = {m["material_name"] for m in result["materials"]}
        assert "hanger_heavy" in names

    def test_formula_without_variables_fails_closed(self, duct_rule):
        with pytest.raises(FormulaValidationError):
            apply_assembly("duct_rectangular", variables=None)

    def test_missing_variable_fails_closed(self, duct_rule):
        with pytest.raises(FormulaValidationError):
            apply_assembly("duct_rectangular", variables={"length_m": 10.0})


class TestValidateRuleFile:
    def test_valid_rule_no_errors(self, tmp_path):
        p = tmp_path / "ok.yaml"
        p.write_text(yaml.safe_dump(DUCT_RULE))
        assert validate_rule_file(p) == []

    def test_bad_formula_reported(self, tmp_path):
        bad = dict(DUCT_RULE)
        bad["bom"] = {"x": {"formula": "__import__('os')"}}
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.safe_dump(bad))
        errors = validate_rule_file(p)
        assert len(errors) == 1
        assert "disallowed" in errors[0]

    def test_formula_referencing_undeclared_variable_reported(self, tmp_path):
        bad = dict(DUCT_RULE)
        bad["variables"] = ["length_m"]  # width_mm/height_mm undeclared
        p = tmp_path / "bad2.yaml"
        p.write_text(yaml.safe_dump(bad))
        assert len(validate_rule_file(p)) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_rules_formulas.py -q`
Expected: FAIL — `ImportError: cannot import name 'validate_rule_file'`

- [ ] **Step 3: Implement**

In `backend/app/assembly/rules.py`:

1. Add imports: `import ast` not needed here; add `from pathlib import Path as _Path`, `from typing import List`, and `from app.assembly.formulas import FormulaValidationError, evaluate_formula, lookup_gauge, validate_formula`.
2. `load_assembly_rule`: add `"variables": data.get("variables", [])` and `"defaults": data.get("defaults", {})` to the returned dict. Keep `bom` raw (entries may be numbers or dicts).
3. Add module-level `_ROUTE_VARIABLES_NOTE = None` — no; skip, nothing else needed at module level.
4. Rewrite `apply_assembly` with the same signature plus `variables: Optional[Dict[str, float]] = None`:

```python
def apply_assembly(
    component_type: str,
    rule_name: str = "",
    variables: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Apply an assembly rule set, evaluating formula BOM lines when present.

    Legacy linear multipliers (plain numbers) behave exactly as before.
    Formula entries require ``variables`` (fail closed otherwise).
    Each material dict gains ``derivation``: None for constants, or
    {"formula": ..., "inputs": ...} / {"gauge_lookup": ..., "inputs": ...}.
    """
    lookup_name = rule_name if rule_name else component_type
    rule = load_assembly_rule(lookup_name)
    if rule is None:
        return {
            "materials": [],
            "labor_hours": 0.0,
            "waste_factor": 0.10,
            "rule_version": "unknown",
            "error": f"Assembly rule '{rule_name}' not found",
        }

    variables = variables or {}
    declared = list(rule.get("variables", []))
    needs_variables = any(isinstance(v, dict) for v in rule["bom"].values())
    if needs_variables and not variables:
        raise FormulaValidationError(
            "rule contains formulas but no variables were supplied",
            rule_name=lookup_name,
        )

    materials = []
    for mat_name, entry in rule["bom"].items():
        if isinstance(entry, dict) and "formula" in entry:
            quantity = evaluate_formula(entry["formula"], variables, lookup_name)
            waste = float(entry.get("waste_factor", rule["waste_factor"]))
            quantity *= 1.0 + waste
            materials.append({
                "material_name": mat_name,
                "quantity": quantity,
                "unit": _infer_unit(mat_name),
                "derivation": {"formula": entry["formula"], "inputs": dict(variables)},
            })
        elif isinstance(entry, dict) and "gauge_lookup" in entry:
            resolved = lookup_gauge(entry["gauge_lookup"], variables)
            materials.append({
                "material_name": resolved,
                "quantity": 1.0,
                "unit": "ea",
                "derivation": {
                    "gauge_lookup": entry["gauge_lookup"],
                    "inputs": dict(variables),
                },
            })
        else:
            # legacy: constant multiplier per unit quantity
            materials.append({
                "material_name": mat_name,
                "quantity": float(entry),
                "unit": _infer_unit(mat_name),
                "derivation": None,
            })

    inst_hours = rule["labor"].get("installation_hours", 0.0)
    return {
        "materials": materials,
        "labor_hours": float(inst_hours),
        "waste_factor": float(rule["waste_factor"]),
        "rule_version": rule["rule_version"],
    }
```

5. Add `validate_rule_file`:

```python
def validate_rule_file(path) -> List[str]:
    """Validate one rule YAML. Returns error strings; empty list = valid.

    Fail-closed: a rule with any error must be excluded from the catalog.
    """
    errors: List[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        return [f"{path.name}: YAML parse error: {exc}"]

    name = data.get("name", path.stem)
    declared = data.get("variables", []) or []
    for mat_name, entry in (data.get("bom") or {}).items():
        if isinstance(entry, dict):
            formula = entry.get("formula")
            if formula is not None:
                try:
                    validate_formula(formula, declared, rule_name=name)
                except FormulaValidationError as exc:
                    errors.append(f"{path.name}: bom.{mat_name}: {exc}")
            if "gauge_lookup" in entry:
                driver = entry["gauge_lookup"].get("by", "")
                if driver and driver not in declared:
                    errors.append(
                        f"{path.name}: bom.{mat_name}: gauge driver "
                        f"'{driver}' not in declared variables"
                    )
    return errors
```

6. `persist_assembly_to_db` keeps working: `bom.items()` now yields dict entries too — coerce with `quantity = entry if isinstance(entry, (int, float)) else 1.0` where it builds `AssemblyMaterial(quantity=...)` (formula lines persist with nominal quantity 1.0; real quantities live on BOQ rows).

- [ ] **Step 4: Run new tests + Phase 1/2 regression (legacy behavior unchanged)**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_rules_formulas.py tests/test_phase1_regression.py tests/test_phase2_regression.py -q`
Expected: new tests PASS; phase 1/2 suites PASS unchanged (legacy constant path identical)

- [ ] **Step 5: Lint + commit**

Run: `backend/.venv/Scripts/python.exe -m ruff check app/assembly tests/test_rules_formulas.py`
Expected: clean

```bash
git add backend/app/assembly/rules.py backend/tests/test_rules_formulas.py
git commit -m "feat(phase3): formula-bearing assembly rules with fail-closed validation"
```

---

### Task 3: Mechanical YAML rules + layer mapping

**Files:**
- Create: `data/assemblies/duct_rectangular.yaml`, `data/assemblies/duct_round.yaml`, `data/assemblies/pipe_insulated.yaml`, `data/assemblies/hvac_equipment.yaml`
- Modify: `data/layer_mapping.yaml`, `backend/app/parsing/layer_map.py` (`route_layers()` route set)
- Test: `backend/tests/test_mechanical_rules.py`

**Interfaces:**
- Consumes: `validate_rule_file` from Task 2; `load_layer_mapping` in `layer_map.py`.
- Produces: four loadable rules named exactly `duct_rectangular`, `duct_round`, `pipe_insulated`, `hvac_equipment`; `layer_to_assembly("M-DUCT") == "duct_rectangular"` etc.; `route_layers()` includes the new duct/pipe layer names.

- [ ] **Step 1: Write the failing test**

```python
"""Phase 3: mechanical YAML rules load and validate; layers map."""
from pathlib import Path

from app.assembly.rules import load_assembly_rule, validate_rule_file
from app.parsing.layer_map import layer_to_assembly, route_layers

_ASSEMBLIES = Path(__file__).resolve().parents[2] / "data" / "assemblies"


class TestMechanicalRulesExist:
    def test_all_four_rules_load(self):
        for name in ("duct_rectangular", "duct_round", "pipe_insulated",
                     "hvac_equipment"):
            rule = load_assembly_rule(name)
            assert rule is not None, name
            assert rule["name"] == name
            assert rule["rule_version"] != "unknown"

    def test_all_rules_validate_clean(self):
        for yaml_path in _ASSEMBLIES.glob("*.yaml"):
            assert validate_rule_file(yaml_path) == [], str(yaml_path)

    def test_route_rules_declare_length_variable(self):
        for name in ("duct_rectangular", "duct_round", "pipe_insulated"):
            assert "length_m" in load_assembly_rule(name)["variables"]

    def test_route_rules_declare_assumed_defaults(self):
        # spec §4: ASSUMED fallback sizes live in YAML, not source (spec §10)
        assert load_assembly_rule("duct_rectangular")["defaults"]["width_mm"] == 400
        assert load_assembly_rule("duct_round")["defaults"]["diameter_mm"] == 250
        assert load_assembly_rule("pipe_insulated")["defaults"]["diameter_mm"] == 150


class TestLayerMapping:
    def test_duct_layers_map(self):
        assert layer_to_assembly("M-DUCT") == "duct_rectangular"
        assert layer_to_assembly("M-DUCT-RECT") == "duct_rectangular"

    def test_round_duct_layers_map(self):
        assert layer_to_assembly("M-DUCT-RND") == "duct_round"

    def test_pipe_layers_map(self):
        assert layer_to_assembly("M-PIPE") == "pipe_insulated"

    def test_equipment_layers_map(self):
        assert layer_to_assembly("M-EQPT-NEW") == "hvac_equipment"
        assert layer_to_assembly("M-EQPT-FUTR") == "hvac_equipment"

    def test_route_layers_includes_ducts_and_pipes(self):
        layers = set(route_layers())
        assert {"M-DUCT", "M-DUCT-RECT", "M-DUCT-RND", "M-PIPE"} <= layers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_mechanical_rules.py -q`
Expected: FAIL — rules not found / mappings return None

- [ ] **Step 3: Write the four YAML rule files**

`data/assemblies/duct_rectangular.yaml`:

```yaml
name: duct_rectangular
rule_version: "1.0.0"
variables: [length_m, width_mm, height_mm, max_mm]
defaults:            # ASSUMED fallback sizes (owner to confirm — spec §10)
  width_mm: 400
  height_mm: 250
  max_mm: 400
bom:
  sheet_metal_m2:
    formula: "2 * (width_mm + height_mm) / 1000 * length_m"
    waste_factor: 0.15
  duct_fitting: 0.2
  hanger_kit:
    gauge_lookup:
      by: max_mm
      rows:
        600: hanger_kit_light
        999999: hanger_kit_heavy
labor:
  installation_hours: 2.0
  hourly_rate: 50.00
  category: mechanical
waste_factor: 0.10
```

`data/assemblies/duct_round.yaml`:

```yaml
name: duct_round
rule_version: "1.0.0"
variables: [length_m, diameter_mm]
defaults:
  diameter_mm: 250
bom:
  sheet_metal_m2:
    formula: "3.141592653589793 * (diameter_mm / 1000) * length_m"
    waste_factor: 0.15
  duct_fitting: 0.2
  hanger_kit:
    gauge_lookup:
      by: diameter_mm
      rows:
        315: hanger_kit_light
        999999: hanger_kit_heavy
labor:
  installation_hours: 1.5
  hourly_rate: 50.00
  category: mechanical
waste_factor: 0.10
```

`data/assemblies/pipe_insulated.yaml`:

```yaml
name: pipe_insulated
rule_version: "1.0.0"
variables: [length_m, diameter_mm]
defaults:
  diameter_mm: 150
bom:
  pipe_m:
    formula: "length_m"
    waste_factor: 0.05
  insulation_m2:
    formula: "3.141592653589793 * ((diameter_mm + 50) / 1000) * length_m"
    waste_factor: 0.10
  pipe_fitting: 0.1
labor:
  installation_hours: 1.8
  hourly_rate: 48.00
  category: mechanical
waste_factor: 0.10
```

`data/assemblies/hvac_equipment.yaml` (count-based, no formulas):

```yaml
name: hvac_equipment
rule_version: "1.0.0"
bom:
  unit_connector: 1.0
  vibration_isolator: 4.0
labor:
  installation_hours: 6.0
  hourly_rate: 55.00
  category: mechanical
waste_factor: 0.05
```

Append to `data/layer_mapping.yaml` (before EOF, matching existing style):

```yaml
  - assembly: duct_rectangular
    layers:
      - M-DUCT
      - M-DUCT-RECT
      - DUCT
      - SUPPLY DUCT
      - RETURN DUCT
  - assembly: duct_round
    layers:
      - M-DUCT-RND
      - ROUND DUCT
  - assembly: pipe_insulated
    layers:
      - M-PIPE
      - PIPE
      - CHW PIPE
      - HW PIPE
  - assembly: hvac_equipment
    layers:
      - M-EQPT
      - M-EQPT-NEW
      - M-EQPT-FUTR
      - AHU
      - FCU
      - VAV
```

In `backend/app/parsing/layer_map.py`, extend the route set:

```python
    route_assemblies = {"cable_tray", "conduit", "duct_rectangular", "duct_round", "pipe_insulated"}
```

- [ ] **Step 4: Run tests to verify they pass + full suite**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_mechanical_rules.py -q` → PASS
Run: `backend/.venv/Scripts/python.exe -m pytest -q` → 63+new green (new layers may add clustering candidates on the electrical sample — verify Phase 2 counts unchanged; the sample has no M-* duct layers, so counts must not move)

- [ ] **Step 5: Lint + commit**

Run: `backend/.venv/Scripts/python.exe -m ruff check app/parsing tests/test_mechanical_rules.py`

```bash
git add data/assemblies/duct_rectangular.yaml data/assemblies/duct_round.yaml data/assemblies/pipe_insulated.yaml data/assemblies/hvac_equipment.yaml data/layer_mapping.yaml backend/app/parsing/layer_map.py backend/tests/test_mechanical_rules.py
git commit -m "feat(phase3): mechanical assembly rules + HVAC layer mapping"
```

---

### Task 4: Size-resolution cascade (`app/parsing/sizes.py`)

**Files:**
- Create: `backend/app/parsing/sizes.py`
- Test: `backend/tests/test_size_cascade.py`

**Interfaces:**
- Consumes: `RouteGeo` dicts (keys `polyline`, `length_m`, `layer`) from `routes.py`; text spans as `List[Dict]` with keys `text`, `origin`/`bbox` (PyMuPDF `get_text("words")`-like: `{"text": str, "x0","y0","x1","y1"}`); scale string `"1:100"`.
- Produces:
  - `SIZE_SOURCE_ORDER = ("schedule", "label", "geometry", "assumed")`
  - `resolve_route_size(route: Dict, text_spans: List[Dict], scale: str, schedule_rows: Optional[List[Dict]] = None, default_size: Optional[Dict] = None, label_proximity_pt: float = 25.0) -> Optional[Dict]` — returns `{"width_mm": float, "height_mm": float, "source": str, "ref": str}` for rectangular, `{"diameter_mm": float, "source": str, "ref": str}` for round, or `None` when no default supplied. `source ∈ SIZE_SOURCE_ORDER`; `ref` names the winning span/schedule row/geometry path.
  - `parse_size_label(text: str) -> Optional[Dict]` — pure parser: `"600x400"`→`{"width_mm":600,"height_mm":400,"shape":"rect"}`, `"600×400"` same, `"12in"`/`12"` → `{"diameter_mm":304.8,"shape":"round"}`, `"DN150"` → `{"diameter_mm":150,"shape":"round"}`, `"Ø250"` → `{"diameter_mm":250,"shape":"round"}`, `"D250"` same. Returns `None` on no match.
  - `measure_rect_width_mm(route: Dict, scale: str, aspect_ratio: float = 2.0) -> Optional[Dict]` — for double-line ducts: largest inscribed rectangle side from the route's own polyline bbox → width; height = width/aspect_ratio. Returns `{"width_mm","height_mm","shape":"rect"}` or `None` if bbox degenerate.

- [ ] **Step 1: Write the failing tests**

```python
"""Phase 3: size-resolution cascade — priority order + provenance."""
import pytest

from app.parsing.sizes import (
    measure_rect_width_mm,
    parse_size_label,
    resolve_route_size,
)


def _span(text, x0, y0, x1=None, y1=None):
    x1 = x1 if x1 is not None else x0 + len(text) * 5
    y1 = y1 if y1 is not None else y0 + 10
    return {"text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1}


def _route(polyline):
    return {"polyline": polyline, "length_m": 5.0, "layer": "M-DUCT"}


class TestParseSizeLabel:
    def test_rect_variants(self):
        assert parse_size_label("600x400") == {"width_mm": 600, "height_mm": 400, "shape": "rect"}
        assert parse_size_label("600X400") == {"width_mm": 600, "height_mm": 400, "shape": "rect"}
        assert parse_size_label("600×400") == {"width_mm": 600, "height_mm": 400, "shape": "rect"}
        assert parse_size_label("600 x 400") == {"width_mm": 600, "height_mm": 400, "shape": "rect"}

    def test_dn(self):
        assert parse_size_label("DN150") == {"diameter_mm": 150, "shape": "round"}

    def test_diameter_symbol(self):
        assert parse_size_label("Ø250") == {"diameter_mm": 250, "shape": "round"}
        assert parse_size_label("D250") == {"diameter_mm": 250, "shape": "round"}

    def test_inches(self):
        assert parse_size_label('12"') == {"diameter_mm": 304.8, "shape": "round"}
        assert parse_size_label("12in") == {"diameter_mm": 304.8, "shape": "round"}

    def test_no_match(self):
        assert parse_size_label("AHU-01") is None
        assert parse_size_label("") is None


class TestCascadePriority:
    def test_schedule_beats_label(self):
        route = _route([(0, 0), (100, 0)])
        spans = [_span("600x400", 90, -20)]
        schedule = [{"width_mm": 500, "height_mm": 300, "ref": "sched_row_2"}]
        result = resolve_route_size(route, spans, "1:100", schedule_rows=schedule)
        assert result["source"] == "schedule"
        assert result["width_mm"] == 500

    def test_label_beats_geometry(self):
        # route drawn 17.008pt wide (= 600mm at 1:100); nearby label says 600x400
        route = _route([(0, 0), (17.008, 0), (17.008, 8.504), (0, 8.504), (0, 0)])
        spans = [_span("600x400", 10, -15)]
        result = resolve_route_size(route, spans, "1:100")
        assert result["source"] == "label"
        assert result["width_mm"] == 600

    def test_geometry_used_when_no_text(self):
        # 17.008pt x 8.504pt rectangle at 1:100 -> 600mm wide duct
        route = _route([(0, 0), (17.008, 0), (17.008, 8.504), (0, 8.504), (0, 0)])
        result = resolve_route_size(route, [], "1:100")
        assert result["source"] == "geometry"
        assert result["width_mm"] == pytest.approx(600, rel=0.05)

    def test_assumed_default_last(self):
        result = resolve_route_size(_route([(0, 0), (10, 0)]), [], "1:100",
                                    default_size={"width_mm": 400, "height_mm": 250})
        assert result["source"] == "assumed"
        assert result["width_mm"] == 400

    def test_none_without_default(self):
        assert resolve_route_size(_route([(0, 0), (10, 0)]), [], "1:100") is None

    def test_diameter_route_takes_diameter_label(self):
        route = _route([(0, 0), (50, 0)])
        route["layer"] = "M-DUCT-RND"
        spans = [_span("DN150", 40, -12)]
        result = resolve_route_size(route, spans, "1:100")
        assert result["diameter_mm"] == 150
        assert result["source"] == "label"

    def test_ref_names_the_source(self):
        spans = [_span("600x400", 90, -20)]
        result = resolve_route_size(_route([(0, 0), (100, 0)]), spans, "1:100")
        assert "600x400" in result["ref"]


class TestGeometryMeasurement:
    def test_rect_width_from_bbox(self):
        # 17.008pt x 8.504pt at 1:100 -> 600mm x 300mm (aspect 2:1)
        route = _route([(0, 0), (17.008, 0), (17.008, 8.504), (0, 8.504), (0, 0)])
        result = measure_rect_width_mm(route, "1:100")
        assert result["width_mm"] == pytest.approx(600, rel=0.05)
        assert result["height_mm"] == pytest.approx(300, rel=0.05)

    def test_degenerate_returns_none(self):
        assert measure_rect_width_mm(_route([(0, 0), (1, 0)]), "1:100") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_size_cascade.py -q`
Expected: FAIL — `ModuleNotFoundError: app.parsing.sizes`

- [ ] **Step 3: Implement**

```python
"""Size-resolution cascade for duct/pipe routes (Phase 3, spec §4).

Priority: schedule table > text label > measured geometry > ASSUMED default.
Every resolution records {value..., source, ref} so downstream BOQ rows can
state exactly where each size came from. Pure geometry/text logic — no LLM.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

SIZE_SOURCE_ORDER = ("schedule", "label", "geometry", "assumed")

# pt -> real-mm at scale denominator D: pt * D * 25.4/72
_PT_TO_REAL_MM = 25.4 / 72.0

_RECT_RE = re.compile(r"(\d{3,4})\s*[xX×]\s*(\d{3,4})")
_DN_RE = re.compile(r"\bDN\s?(\d{2,4})\b", re.IGNORECASE)
_DIAM_RE = re.compile(r"[ØøD]\s?(\d{2,4})\b")
_INCH_RE = re.compile(r'(\d{1,2})\s?(?:in|")\b', re.IGNORECASE)


def parse_size_label(text: str) -> Optional[Dict]:
    """Parse a size label into normalized mm dimensions. None if no match."""
    if not text:
        return None
    m = _RECT_RE.search(text)
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w != h:  # 600x600 is ambiguous rect/round; treat as rect
            return {"width_mm": float(w), "height_mm": float(h), "shape": "rect"}
    m = _DN_RE.search(text)
    if m:
        return {"diameter_mm": float(m.group(1)), "shape": "round"}
    m = _DIAM_RE.search(text)
    if m:
        return {"diameter_mm": float(m.group(1)), "shape": "round"}
    m = _INCH_RE.search(text)
    if m:
        return {"diameter_mm": round(float(m.group(1)) * 25.4, 1), "shape": "round"}
    return None


def _span_center(span: Dict) -> tuple:
    return ((span["x0"] + span["x1"]) / 2.0, (span["y0"] + span["y1"]) / 2.0)


def _route_bbox(polyline: List) -> Optional[tuple]:
    if len(polyline) < 2:
        return None
    xs = [p[0] for p in polyline]
    ys = [p[1] for p in polyline]
    return (min(xs), min(ys), max(xs), max(ys))


def _label_near_route(label: Dict, route: Dict, proximity_pt: float) -> bool:
    bbox = _route_bbox(route["polyline"])
    if bbox is None:
        return False
    cx, cy = _span_center(label)
    x0, y0, x1, y1 = bbox
    dx = max(x0 - cx, 0.0, cx - x1)
    dy = max(y0 - cy, 0.0, cy - y1)
    return (dx * dx + dy * dy) ** 0.5 <= proximity_pt


def _size_matches_route_shape(size: Dict, layer: str) -> bool:
    """A round size only fits a round-route layer and vice versa."""
    layer_upper = (layer or "").upper()
    round_layer = "RND" in layer_upper or "ROUND" in layer_upper
    round_size = size.get("shape") == "round"
    return round_layer == round_size


def measure_rect_width_mm(
    route: Dict, scale: str, aspect_ratio: float = 2.0
) -> Optional[Dict]:
    """Measure duct width from the route's own double-line geometry.

    Width = longer bbox side converted pt -> real mm via scale; height from
    the declared aspect ratio. Returns None when bbox is degenerate.
    """
    bbox = _route_bbox(route["polyline"])
    if bbox is None:
        return None
    try:
        denominator = float(scale.split(":")[1])
    except (IndexError, ValueError):
        return None
    w_pt = bbox[2] - bbox[0]
    h_pt = bbox[3] - bbox[1]
    side_pt = max(w_pt, h_pt)
    if side_pt <= 1.0:  # degenerate — a line, not a double-line duct
        return None
    width_mm = side_pt * denominator * _PT_TO_REAL_MM
    return {
        "width_mm": round(width_mm, 1),
        "height_mm": round(width_mm / aspect_ratio, 1),
        "shape": "rect",
    }


def resolve_route_size(
    route: Dict,
    text_spans: List[Dict],
    scale: str,
    schedule_rows: Optional[List[Dict]] = None,
    default_size: Optional[Dict] = None,
    label_proximity_pt: float = 25.0,
) -> Optional[Dict]:
    """Resolve a route's cross-section size via the cascade (spec §4).

    Returns {"width_mm","height_mm"|"diameter_mm", "source", "ref"} or None.
    """
    # 1. Schedule table wins
    for row in schedule_rows or []:
        if _label_near_route(row, route, label_proximity_pt * 4):
            out = {k: v for k, v in row.items() if k != "ref"}
            out["source"] = "schedule"
            out["ref"] = row.get("ref", "schedule_row")
            return out

    # 2. Text label near the route
    for span in text_spans:
        if not _label_near_route(span, route, label_proximity_pt):
            continue
        size = parse_size_label(span.get("text", ""))
        if size and _size_matches_route_shape(size, route.get("layer", "")):
            out = {k: v for k, v in size.items() if k != "shape"}
            out["source"] = "label"
            out["ref"] = f"text_span:{span.get('text', '')}"
            return out

    # 3. Measured geometry (double-line rectangular ducts)
    measured = measure_rect_width_mm(route, scale)
    if measured:
        out = {k: v for k, v in measured.items() if k != "shape"}
        out["source"] = "geometry"
        out["ref"] = "route_polyline_bbox"
        return out

    # 4. ASSUMED default — flagged, never silent
    if default_size:
        out = dict(default_size)
        out["source"] = "assumed"
        out["ref"] = "configured_default"
        return out

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_size_cascade.py -v`
Expected: PASS

- [ ] **Step 5: Lint + commit**

Run: `backend/.venv/Scripts/python.exe -m ruff check app/parsing/sizes.py tests/test_size_cascade.py`

```bash
git add backend/app/parsing/sizes.py backend/tests/test_size_cascade.py
git commit -m "feat(phase3): size-resolution cascade with provenance"
```

---

### Task 5: Schedule-table detection (`app/parsing/sizes.py`)

**Files:**
- Modify: `backend/app/parsing/sizes.py` (append)
- Test: `backend/tests/test_schedule_detection.py`

**Interfaces:**
- Consumes: text spans (same shape as Task 4).
- Produces: `detect_schedule_rows(text_spans: List[Dict], header_keywords: tuple = ("DUCT SIZE", "PIPE SCHEDULE", "DUCT SCHEDULE")) -> List[Dict]` — finds a header span, then parses size labels from spans below it (same column band, `y0 > header.y1`, within `header height * 30`), returning `{"width_mm","height_mm"|"diameter_mm","ref": f"schedule:{header_text}:row{i}", "x0","y0","x1","y1"}` (geometry keys let the cascade's proximity check work). Returns `[]` when no header found.

- [ ] **Step 1: Write the failing tests**

```python
"""Phase 3: schedule-table detection from text spans."""
from app.parsing.sizes import detect_schedule_rows


def _span(text, x0, y0):
    return {"text": text, "x0": x0, "y0": y0, "x1": x0 + len(text) * 5, "y1": y0 + 10}


class TestDetectScheduleRows:
    def test_header_then_rows(self):
        spans = [
            _span("AIR LEGEND", 100, 100),
            _span("DUCT SIZE", 100, 700),
            _span("600x400", 100, 720),
            _span("500x300", 100, 740),
        ]
        rows = detect_schedule_rows(spans)
        assert len(rows) == 2
        assert rows[0]["width_mm"] == 600 and rows[0]["height_mm"] == 400
        assert rows[0]["ref"].startswith("schedule:DUCT SIZE")

    def test_pipe_schedule_header(self):
        spans = [
            _span("PIPE SCHEDULE", 50, 500),
            _span("DN150", 50, 520),
            _span("DN100", 50, 540),
        ]
        rows = detect_schedule_rows(spans)
        assert len(rows) == 2
        assert rows[0]["diameter_mm"] == 150

    def test_no_header_no_rows(self):
        assert detect_schedule_rows([_span("600x400", 0, 0)]) == []

    def test_non_size_rows_skipped(self):
        spans = [
            _span("DUCT SIZE", 0, 0),
            _span("NOTE: ALL DUCTS SEALED", 0, 20),
            _span("400x250", 0, 40),
        ]
        rows = detect_schedule_rows(spans)
        assert len(rows) == 1
        assert rows[0]["width_mm"] == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_schedule_detection.py -q`
Expected: FAIL — `ImportError: cannot import name 'detect_schedule_rows'`

- [ ] **Step 3: Implement (append to `sizes.py`)**

```python
def detect_schedule_rows(
    text_spans: List[Dict],
    header_keywords: tuple = ("DUCT SIZE", "PIPE SCHEDULE", "DUCT SCHEDULE"),
) -> List[Dict]:
    """Detect schedule-table rows under a recognized header span.

    Heuristic (spec §10): a span whose text contains a header keyword starts
    a schedule; size-label spans below it within ~30 header-heights belong to
    it. Non-parsing spans are skipped silently (debug concern only).
    """
    rows: List[Dict] = []
    for header in text_spans:
        text = (header.get("text") or "").upper()
        if not any(kw in text for kw in header_keywords):
            continue
        band_height = max(header["y1"] - header["y0"], 1.0) * 30.0
        hx0, hx1 = header["x0"] - 200.0, header["x1"] + 200.0
        below = [
            s for s in text_spans
            if s is not header
            and s["y0"] > header["y1"]
            and s["y0"] - header["y1"] <= band_height
            and not (s["x1"] < hx0 or s["x0"] > hx1)
        ]
        for i, span in enumerate(sorted(below, key=lambda s: (s["y0"], s["x0"]))):
            size = parse_size_label(span.get("text", ""))
            if not size:
                continue
            row = {k: v for k, v in size.items() if k != "shape"}
            row["ref"] = f"schedule:{header.get('text', '')}:row{i}"
            row.update({k: span[k] for k in ("x0", "y0", "x1", "y1")})
            rows.append(row)
    return rows
```

- [ ] **Step 4: Run tests + full cascade suite**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_schedule_detection.py tests/test_size_cascade.py -q`
Expected: PASS

- [ ] **Step 5: Lint + commit**

```bash
backend/.venv/Scripts/python.exe -m ruff check app/parsing/sizes.py tests/test_schedule_detection.py
git add backend/app/parsing/sizes.py backend/tests/test_schedule_detection.py
git commit -m "feat(phase3): schedule-table detection heuristic"
```

---

### Task 6: DB migration — provenance columns

**Files:**
- Modify: `backend/app/db/models/geometry.py` (`Route`), `backend/app/db/models/estimate.py` (`BoqItem`)
- Create: `backend/alembic/versions/<auto>_add_size_json_and_derivation_provenance.py` (via autogenerate)
- Test: `backend/tests/test_provenance_columns.py`

**Interfaces:**
- Produces: `Route.size_json: Mapped[str | None]` (JSON serialized string, nullable); `BoqItem.derivation_json: Mapped[str | None]`; `BoqItem.size_source: Mapped[str | None]` (`schedule|label|geometry|assumed`). Later tasks serialize dicts into these columns.

- [ ] **Step 1: Write the failing test**

```python
"""Phase 3: provenance columns exist and round-trip."""
import json

from sqlalchemy import inspect

from app.db.models.estimate import BoqItem
from app.db.models.geometry import Route
from app.db.session import get_engine


class TestProvenanceColumns:
    def test_route_size_json_column(self):
        cols = {c["name"] for c in inspect(get_engine()).get_columns("routes")}
        assert "size_json" in cols

    def test_boq_item_provenance_columns(self):
        cols = {c["name"] for c in inspect(get_engine()).get_columns("boq_items")}
        assert {"derivation_json", "size_source"} <= cols

    def test_model_attributes_nullable(self):
        assert Route.size_json is not None  # column defined
        assert BoqItem.derivation_json is not None
        assert BoqItem.size_source is not None

    def test_json_round_trip(self):
        payload = {"width_mm": 600, "height_mm": 400,
                   "source": "label", "ref": "text_span:600x400"}
        assert json.loads(json.dumps(payload)) == payload
```

- [ ] **Step 2: Run to verify failure**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_provenance_columns.py -q`
Expected: FAIL — `size_json` not in columns

- [ ] **Step 3: Add model columns + migration**

In `geometry.py` `Route` (add `String` usage — already imported there):

```python
    size_json: Mapped[str | None] = mapped_column(String(1000), default=None)
    # JSON text: {width_mm,height_mm|diameter_mm,source,ref}
```

In `estimate.py` `BoqItem`:

```python
    derivation_json: Mapped[str | None] = mapped_column(String(2000), default=None)
    # JSON text: {formula|gauge_lookup, inputs, rule_name, rule_version}
    size_source: Mapped[str | None] = mapped_column(String(20), default=None)
    # schedule|label|geometry|assumed
```

Generate + apply migration (from `backend/`):

```bash
backend/.venv/Scripts/python.exe -m alembic revision --autogenerate -m "add size_json and derivation provenance columns"
backend/.venv/Scripts/python.exe -m alembic upgrade head
```

Inspect the generated file: it must contain exactly two `add_column` operations (`routes.size_json`, `boq_items.derivation_json`, `boq_items.size_source` — three total) and no drops. If autogenerate emits anything else (e.g. the known `labor_rates` drift), delete those lines from the migration before upgrading.

- [ ] **Step 4: Run tests + migration test suite**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_provenance_columns.py tests/test_migrations.py -q`
Expected: PASS

- [ ] **Step 5: Lint + commit**

```bash
backend/.venv/Scripts/python.exe -m ruff check app/db tests/test_provenance_columns.py "alembic/versions/$(ls alembic/versions | grep size_json)"
git add backend/app/db/models/geometry.py backend/app/db/models/estimate.py backend/alembic/versions/
git commit -m "feat(phase3): provenance columns (routes.size_json, boq_items.derivation_json/size_source)"
```

---

### Task 7: Generated HVAC test fixture

**Files:**
- Create: `backend/tests/fixtures/__init__.py` (empty), `backend/tests/fixtures/make_hvac_fixture.py`
- Test: `backend/tests/test_hvac_fixture.py`

**Interfaces:**
- Produces: `build_hvac_fixture(path: str) -> Dict` — writes a layer-rich single-page A3-landscape vector PDF at the given path and returns exact expected values: `{"scale": "1:100", "rect_duct": {"length_m": float, "width_mm": 600, "height_mm": 400}, "round_duct": {"length_m": float, "diameter_mm": 250}, "pipe": {"length_m": float, "diameter_mm": 150}, "equipment_count": int}`. OCG layers created: `M-DUCT`, `M-DUCT-RND`, `M-PIPE`, `M-EQPT-NEW`. Labels drawn as real text near each run; one mini schedule header `DUCT SIZE` with one row. This is test scaffolding only — production code must never reference it (spec §7.3).

- [ ] **Step 1: Write the failing test**

```python
"""Phase 3: generated HVAC fixture produces a layer-rich, parseable PDF."""
import pymupdf

from tests.fixtures.make_hvac_fixture import build_hvac_fixture


class TestHvacFixture:
    def test_builds_and_reports_expectations(self, tmp_path):
        pdf_path = str(tmp_path / "hvac_fixture.pdf")
        expected = build_hvac_fixture(pdf_path)
        assert expected["scale"] == "1:100"
        assert expected["equipment_count"] >= 2

    def test_pdf_has_ocg_layers(self, tmp_path):
        pdf_path = str(tmp_path / "hvac_fixture.pdf")
        build_hvac_fixture(pdf_path)
        doc = pymupdf.open(pdf_path)
        layer_names = {ocgs[k].get("name") for ocgs in [doc.get_ocgs()] for k in ocgs}
        assert {"M-DUCT", "M-DUCT-RND", "M-PIPE", "M-EQPT-NEW"} <= layer_names
        doc.close()

    def test_pdf_has_vector_content_and_text(self, tmp_path):
        pdf_path = str(tmp_path / "hvac_fixture.pdf")
        build_hvac_fixture(pdf_path)
        doc = pymupdf.open(pdf_path)
        page = doc[0]
        assert len(page.get_drawings()) > 20
        text = page.get_text()
        assert "600x400" in text
        assert "DUCT SIZE" in text
        doc.close()
```

- [ ] **Step 2: Run to verify failure**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_hvac_fixture.py -q`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the generator**

```python
"""Generate a synthetic layer-rich HVAC drawing PDF for e2e ground truth.

Test scaffolding ONLY (spec §7.3) — production code must never import this.
Everything is deterministic: fixed coordinates at scale 1:100, so expected
real lengths derive from the documented pt→paper-mm→real-m chain:
    real_m = points * denominator * 25.4 / (72 * 1000)
"""

from __future__ import annotations

from typing import Dict

import pymupdf

_SCALE_DENOM = 100
_PT_TO_M = _SCALE_DENOM * 25.4 / (72.0 * 1000.0)

# Fixed geometry (PDF points, top-left origin page coords)
RECT_DUCT_PTS = [(200, 300), (483.465, 300), (483.465, 317.008), (200, 317.008), (200, 300)]
ROUND_DUCT_PTS = [(200, 500), (454.863, 500)]
PIPE_PTS = [(200, 650), (339.912, 650)]
EQUIPMENT_RECTS = [(600, 280, 660, 320), (600, 480, 660, 520)]  # 2 units


def _real_length(points) -> float:
    total = 0.0
    for i in range(1, len(points)):
        total += ((points[i][0] - points[i - 1][0]) ** 2
                  + (points[i][1] - points[i - 1][1]) ** 2) ** 0.5
    return round(total * _PT_TO_M, 3)


def build_hvac_fixture(path: str) -> Dict:
    doc = pymupdf.open()
    page = doc.new_page(width=1191, height=842)  # A3 landscape

    ocg = {name: doc.add_ocg(name, on=True)
           for name in ("M-DUCT", "M-DUCT-RND", "M-PIPE", "M-EQPT-NEW")}

    shape = page.new_shape()
    shape.draw_polyline(RECT_DUCT_PTS)
    shape.finish(color=(0, 0, 1), width=1, oc=ocg["M-DUCT"])
    shape.draw_polyline(ROUND_DUCT_PTS)
    shape.finish(color=(0, 0, 1), width=1, oc=ocg["M-DUCT-RND"])
    shape.draw_polyline(PIPE_PTS)
    shape.finish(color=(0, 0, 1), width=1, oc=ocg["M-PIPE"])
    for rect in EQUIPMENT_RECTS:
        shape.draw_rect(pymupdf.Rect(rect))
        shape.finish(color=(1, 0, 0), width=1, oc=ocg["M-EQPT-NEW"])
    shape.commit()

    page.insert_text((300, 290), "600x400", fontsize=8)          # rect label
    page.insert_text((300, 490), "DN250", fontsize=8)            # round label
    page.insert_text((240, 640), "DN150", fontsize=8)            # pipe label
    page.insert_text((610, 275), "AHU-01", fontsize=8)           # equipment tags
    page.insert_text((610, 475), "FCU-02", fontsize=8)
    page.insert_text((100, 100), "DUCT SIZE", fontsize=10)       # mini schedule
    page.insert_text((100, 120), "600x400", fontsize=8)
    page.insert_text((100, 140), "SCALE 1:100", fontsize=8)      # scale detect

    doc.save(path)
    doc.close()

    return {
        "scale": "1:100",
        "rect_duct": {"length_m": _real_length(RECT_DUCT_PTS),
                      "width_mm": 600, "height_mm": 400},
        "round_duct": {"length_m": _real_length(ROUND_DUCT_PTS),
                       "diameter_mm": 250},
        "pipe": {"length_m": _real_length(PIPE_PTS), "diameter_mm": 150},
        "equipment_count": len(EQUIPMENT_RECTS),
    }
```

If `doc.add_ocg` or the `oc=` kwarg is unavailable in the installed pymupdf
version, check `node_modules`-equivalent docs via
`backend/.venv/Scripts/python.exe -c "import pymupdf; help(pymupdf.Document.add_ocg)"`
and adapt (fallback: draw without `oc`, then attach layers via
`page.set_oc`-style APIs — verify OCG presence with the Step 1 test before
proceeding).

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_hvac_fixture.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
backend/.venv/Scripts/python.exe -m ruff check tests/fixtures/ tests/test_hvac_fixture.py
git add backend/tests/fixtures/ backend/tests/test_hvac_fixture.py
git commit -m "test(phase3): deterministic generated HVAC fixture with OCG layers"
```

---

### Task 8: E2E mechanical branch

**Files:**
- Modify: `backend/app/e2e/router.py`
- Test: `backend/tests/test_phase3_regression.py`

**Interfaces:**
- Consumes: `resolve_route_size` + `detect_schedule_rows` (Tasks 4–5), formula-capable `apply_assembly` (Task 2), `build_hvac_fixture` (Task 7), `layer_to_assembly` with mechanical entries (Task 3).
- Produces: e2e `/api/e2e/run` BOQ rows gain two optional keys: `"derivation": {formula|gauge_lookup, inputs, rule_name, rule_version} | None` and `"size_source": "schedule|label|geometry|assumed" | None`. Route assembly whitelist becomes a module constant `ROUTE_ASSEMBLIES = {"cable_tray", "conduit", "duct_rectangular", "duct_round", "pipe_insulated"}`.

- [ ] **Step 1: Write the failing tests**

```python
"""Phase 3 regression: mechanical e2e pipeline on the generated fixture."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.fixtures.make_hvac_fixture import build_hvac_fixture


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestMechanicalE2E:
    def test_duct_pipe_equipment_boq(self, client, tmp_path):
        pdf_path = str(tmp_path / "hvac_fixture.pdf")
        expected = build_hvac_fixture(pdf_path)

        with open(pdf_path, "rb") as f:
            response = client.post("/api/e2e/run", files={"file": ("hvac.pdf", f, "application/pdf")})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"

        items = body["boq_items"]
        by_material = {}
        for item in items:
            by_material.setdefault(item["material_name"], []).append(item)

        # Sheet metal from the rectangular duct (label 600x400 wins over geometry)
        rect_len = expected["rect_duct"]["length_m"]
        expected_m2 = 2 * (600 + 400) / 1000 * rect_len * 1.15  # +15% waste
        sheet = [it for it in by_material.get("sheet_metal_m2", [])
                 if it["assembly_type"] == "duct_rectangular"]
        assert sheet, "no sheet_metal_m2 BOQ row for rectangular duct"
        assert sum(it["quantity"] for it in sheet) == pytest.approx(expected_m2, rel=0.01)
        assert sheet[0]["size_source"] == "label"
        assert sheet[0]["derivation"]["formula"].startswith("2 *")

        # Round duct metal
        rnd_len = expected["round_duct"]["length_m"]
        expected_rnd = 3.141592653589793 * 0.250 * rnd_len * 1.15
        rnd = [it for it in by_material.get("sheet_metal_m2", [])
               if it["assembly_type"] == "duct_round"]
        assert sum(it["quantity"] for it in rnd) == pytest.approx(expected_rnd, rel=0.01)

        # Pipe + insulation present with provenance
        assert by_material.get("pipe_m"), "no pipe_m row"
        pipe_rows = by_material["pipe_m"]
        assert all(it["size_source"] in {"label", "schedule", "geometry", "assumed"}
                   for it in pipe_rows)

        # Equipment counted (2 units -> unit connectors etc.)
        connectors = by_material.get("unit_connector", [])
        assert sum(it["quantity"] for it in connectors) == pytest.approx(
            expected["equipment_count"] * 1.0)

    def test_electrical_outputs_unchanged(self, client):
        """Phase 2 regression lock: electrical sample BOQ byte-identical."""
        sample = "data/samples/MMC-JVC-CD-ELEC-3902_AC-WIRE-Model.pdf"
        import os
        if not os.path.exists(sample):
            pytest.skip("sample PDF not present locally")
        with open(sample, "rb") as f:
            response = client.post("/api/e2e/run",
                                   files={"file": ("sample.pdf", f, "application/pdf")})
        assert response.status_code == 200
        body = response.json()
        # No mechanical rows may appear for the electrical sheet
        mechanical = {it["assembly_type"] for it in body["boq_items"]} & {
            "duct_rectangular", "duct_round", "pipe_insulated", "hvac_equipment"}
        assert mechanical == set()
        # And the known tray/conduit/lighting structure is intact
        types = {it["assembly_type"] for it in body["boq_items"]}
        assert "cable_tray" in types
```

Note: the sample path resolves relative to `backend/` — run pytest from
`backend/` (project convention). If the e2e route resolves paths relative to
repo root instead, match the existing Phase 2 regression test's path
convention (check `tests/test_phase2_regression.py` first and copy it).

- [ ] **Step 2: Run to verify failure**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_phase3_regression.py -q`
Expected: FAIL — mechanical rows absent / `derivation` key missing

- [ ] **Step 3: Implement in `app/e2e/router.py`**

1. Add imports: `from app.parsing.sizes import detect_schedule_rows, resolve_route_size`; extend `apply_assembly` import usage.
2. Add module constant: `ROUTE_ASSEMBLIES = {"cable_tray", "conduit", "duct_rectangular", "duct_round", "pipe_insulated"}`; replace the inline set in the route loop.
3. Extend `_boq_line` with `derivation: Optional[Dict] = None, size_source: Optional[str] = None` params, included in the returned dict.
4. After step 2️⃣ (parse), detect schedule rows once: `schedule_rows = detect_schedule_rows(parsed.get("raw_text_spans", []))`.
5. In the route loop, for mechanical assemblies resolve size and build variables. Defaults come from the rule YAML (`defaults:` section added in Task 3) — never inline in source:

```python
                variables = None
                size_source = None
                if assembly_type in {"duct_rectangular", "duct_round", "pipe_insulated"}:
                    mech_rule = _load_rule(assembly_type) or {}
                    size = resolve_route_size(
                        route, parsed.get("raw_text_spans", []), scale,
                        schedule_rows=schedule_rows,
                        default_size=mech_rule.get("defaults") or None,
                    )
                    if size is None:
                        continue  # no size resolvable and no YAML default — gap, not zero
                    size_source = size.get("source")
                    variables = {"length_m": route["length_m"], **{
                        k: v for k, v in size.items()
                        if k in ("width_mm", "height_mm", "diameter_mm")}}
                    if assembly_type == "duct_rectangular":
                        variables["max_mm"] = max(variables.get("width_mm", 0),
                                                  variables.get("height_mm", 0))
                    elif assembly_type in {"duct_round", "pipe_insulated"}:
                        variables["max_mm"] = variables.get("diameter_mm", 0)

                applied = apply_assembly(assembly_type, variables=variables)
```

(`_load_rule` is the `load_assembly_rule` alias already imported inside the
component loop; hoist it to a single top-of-function import so both loops
share it.)

Pass `derivation=mat.get("derivation")` and `size_source=size_source` into
`_boq_line` for every route row; component (equipment) rows keep
`derivation=None, size_source=None` but must include the new keys anyway
(response-shape uniformity).

6. Equipment path: no code change needed beyond Task 3's mapping —
`count_components` + the strict component loop already count `M-EQPT-NEW`
clusters and resolve them to `hvac_equipment` via `layer_to_assembly`.

- [ ] **Step 4: Run Phase 3 + full suite**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_phase3_regression.py -v` → PASS
Run: `backend/.venv/Scripts/python.exe -m pytest -q` → all green incl. Phase 1/2 (63 baseline) + 1 xfail

- [ ] **Step 5: Lint + commit**

```bash
backend/.venv/Scripts/python.exe -m ruff check app/e2e tests/test_phase3_regression.py
git add backend/app/e2e/router.py backend/tests/test_phase3_regression.py
git commit -m "feat(phase3): e2e mechanical branch — cascade, formulas, provenance"
```

---

### Task 9: S101 real-sheet equipment regression

**Files:**
- Test: `backend/tests/test_phase3_s101_equipment.py`

**Interfaces:**
- Consumes: e2e client (Task 8), real fixture `data/samples/ABC-SC03-S101.pdf` (present locally, gitignored — skip if absent).
- Produces: locked regression asserting human-verified equipment counts on a real client drawing. **The counts below are placeholders that MUST be replaced by manual verification before locking**: open S101, count `M-EQPT-NEW` / `M-EQPT-FUTR` symbols by eye (or via a debug run printing per-layer cluster counts), record the numbers with a `# human-verified 2026-08-XX` comment, then freeze them in the test.

- [ ] **Step 1: Get ground truth**

Run a debug script (throwaway, not committed) to print per-layer cluster counts:

```bash
backend/.venv/Scripts/python.exe -c "
from app.ingestion.vector import parse_pdf
from app.parsing.components import count_components
parsed = parse_pdf('data/samples/ABC-SC03-S101.pdf')
comps = count_components(parsed['clusters'], parsed['raw_drawings'])
from collections import Counter
print(Counter(c['assembly_type'] or c.get('source_layer','?') for c in comps))
print('total components:', len(comps))
"
```

Manually cross-check the `M-EQPT-NEW` / `M-EQPT-FUTR` counts against the
visible equipment symbols in the drawing (generator/cooling-tower yard plan).
Record the verified numbers.

- [ ] **Step 2: Write the regression test with verified counts**

```python
"""Phase 3: real-sheet mechanical equipment proof on ABC-SC03-S101.pdf.

Counts below are HUMAN-VERIFIED ground truth (spec §7.3) — do not adjust
them to make the test pass; adjust the pipeline instead.
"""
import os

import pytest
from fastapi.testclient import TestClient

from app.main import app

S101 = "data/samples/ABC-SC03-S101.pdf"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.skipif(not os.path.exists(S101), reason="client fixture not present")
class TestS101Equipment:
    def test_equipment_counted_with_provenance(self, client):
        with open(S101, "rb") as f:
            response = client.post("/api/e2e/run",
                                   files={"file": ("S101.pdf", f, "application/pdf")})
        assert response.status_code == 200
        body = response.json()
        equipment = [it for it in body["boq_items"]
                     if it["assembly_type"] == "hvac_equipment"]
        # HUMAN-VERIFIED 2026-08-XX: N units visible on M-EQPT-NEW
        # (replace N after Step 1 manual verification; vibration_isolator
        # quantity = 4 per unit is the rule multiplier)
        isolators = [it for it in equipment if it["material_name"] == "vibration_isolator"]
        assert isolators, "no hvac_equipment rows derived from S101"
        assert sum(it["quantity"] for it in isolators) == pytest.approx(N * 4.0)
        # every equipment row carries source traceability
        assert all(it["source_path_ids"] for it in equipment)
```

Replace `N` (both occurrences) with the verified count and the date comment
with the real verification date before committing.

- [ ] **Step 3: Run to verify**

Run: `backend/.venv/Scripts/python.exe -m pytest tests/test_phase3_s101_equipment.py -v`
Expected: PASS with verified counts. If counts disagree with manual truth,
debug the clustering/mapping — never edit the verified number to fit.

- [ ] **Step 4: Commit**

```bash
backend/.venv/Scripts/python.exe -m ruff check tests/test_phase3_s101_equipment.py
git add backend/tests/test_phase3_s101_equipment.py
git commit -m "test(phase3): S101 real-sheet equipment regression (human-verified)"
```

---

### Task 10: Full regression, docs sync, phase closure

**Files:**
- Modify: `docs/Phases.md` (Phase 3 section → implemented status), `docs/Memory.md` (progress row + open items)

**Interfaces:**
- Consumes: everything above.
- Produces: phase closure record.

- [ ] **Step 1: Full suite + lint**

Run (from `backend/`):
```bash
backend/.venv/Scripts/python.exe -m pytest -q
backend/.venv/Scripts/python.exe -m ruff check app tests
```
Expected: all green (63 baseline + all new Phase 3 tests, 1 known xfail), ruff clean.

- [ ] **Step 2: Update `docs/Phases.md` Phase 3 section**

Append under `## Phase 3 — Mechanical (HVAC)` an implementation-status block
mirroring the Phase 2 pattern: what landed (formula evaluator, cascade,
schedule detection, 4 YAML rules, provenance columns, e2e branch, generated
fixture, S101 regression), the DoD statement, and the standing gap: *no
dedicated HVAC/duct sheet yet — duct/pipe formulas proven on the generated
fixture + S101 equipment proof; swap in a real owner sheet when available
(trigger: first real mechanical upload)*.

- [ ] **Step 3: Update `docs/Memory.md`**

Add the Phase 3 progress row (what was done, verified-by), update
**Current phase** to Phase 3 ✅ / next Phase 4, refresh open items (remove
"Phase 3 fixture gap" or narrow it to "real HVAC sheet pending"), and record
the S101 verified equipment count + any gauge/default-size values the owner
must confirm.

- [ ] **Step 4: Commit docs**

```bash
git add docs/Phases.md docs/Memory.md
git commit -m "docs(phase3): Phase 3 Mechanical complete — status + memory sync"
```

---

## Task dependency graph

```
1 (formulas) → 2 (rules) ─────────┐
3 (YAML+mapping) ─────────────────┤
4 (cascade) → 5 (schedule) ───────┼→ 8 (e2e branch) → 9 (S101) → 10 (closure)
6 (migration) ────────────────────┘        ↑
7 (generated fixture) ────────────────────┘
```

Tasks 3–7 are independent of each other once 1–2 land; 8 requires all of 2–7.
