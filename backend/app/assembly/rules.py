"""YAML-driven assembly rules engine for access control takeoff.

Reads rule sets from data/assemblies/*.yaml and derives material/labor
quantities from measured components. Every derived quantity records its
rule_version for auditability.

Constraint: Rules are YAML-driven, NOT hardcoded in source code.
Adding a new assembly type requires YAML edit, not code change.
"""

from __future__ import annotations

import logging

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.assembly.formulas import (
    FormulaValidationError,
    evaluate_formula,
    lookup_gauge,
    validate_formula,
)
from app.db.models.catalog import Assembly, Material


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# YAML rule set loading
# ---------------------------------------------------------------------------

_ASSEMBLIES_DIR = Path(__file__).resolve().parents[3] / "data" / "assemblies"

# Cross-section variables derivable from other bound inputs. A rule may drive
# a gauge table with these without the caller supplying them explicitly.
_DERIVED_VARIABLE_SOURCES: Dict[str, tuple] = {
    "max_mm": ("width_mm", "height_mm", "diameter_mm"),
}


def _effective_variables(
    rule: Dict, variables: Optional[Dict[str, float]]
) -> Dict[str, float]:
    """Bind evaluation inputs: rule defaults < caller variables < derived."""
    effective: Dict[str, float] = {}
    for key, value in (rule.get("defaults") or {}).items():
        effective[key] = float(value)
    for key, value in (variables or {}).items():
        effective[key] = float(value)
    for derived, sources in _DERIVED_VARIABLE_SOURCES.items():
        if derived not in effective:
            candidates = [float(effective[s]) for s in sources if s in effective]
            if candidates:
                effective[derived] = max(candidates)
    return effective


def _validate_rule_data(data: Dict, source_name: str) -> List[str]:
    """Validate parsed rule data. Returns error strings; empty list = valid.

    Shared by ``validate_rule_file`` (catalog import gate) and
    ``load_assembly_rule`` (runtime load gate) so both fail closed on the
    same conditions.
    """
    errors: List[str] = []
    if not isinstance(data, dict):
        errors.append(f"{source_name}: rule root must be a mapping, got {type(data).__name__}")
        return errors
    name = data.get("name", Path(source_name).stem)
    declared = data.get("variables", []) or []
    for mat_name, entry in (data.get("bom") or {}).items():
        if not isinstance(entry, dict):
            continue
        formula = entry.get("formula")
        if formula is not None:
            try:
                validate_formula(formula, declared, rule_name=name)
            except FormulaValidationError as exc:
                errors.append(f"{source_name}: bom.{mat_name}: disallowed formula: {exc}")
        if "gauge_lookup" in entry:
            table = entry.get("gauge_lookup") or {}
            driver = table.get("by", "")
            if (
                driver
                and driver not in declared
                and driver not in _DERIVED_VARIABLE_SOURCES
            ):
                errors.append(
                    f"{source_name}: bom.{mat_name}: gauge driver "
                    f"'{driver}' not in declared variables"
                )
    return errors


def load_assembly_rule(name: str) -> Optional[Dict]:
    """Load a YAML rule set by assembly name.

    Returns dict with keys: name, rule_version, bom, labor, waste_factor,
    variables, defaults or None if not found. BOM entries may be plain
    numbers (legacy linear multipliers) or dicts with ``formula`` /
    ``gauge_lookup`` (optionally ``waste_factor``).

    Fail-closed gate: a rule file that fails the same validation as
    ``validate_rule_file`` is excluded (returns None) with a warning —
    the rest of the catalog keeps serving.
    """
    yaml_path = _ASSEMBLIES_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        return None

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        logger.warning("excluding unreadable assembly rule %s: %s", name, exc)
        return None

    data = data if isinstance(data, dict) else {}
    errors = _validate_rule_data(data, yaml_path.name)
    if errors:
        for error in errors:
            logger.warning("excluding invalid assembly rule: %s", error)
        return None

    return {
        "name": data.get("name", name),
        "rule_version": data.get("rule_version", "unknown"),
        "bom": data.get("bom", {}),
        "labor": data.get("labor", {}),
        "waste_factor": data.get("waste_factor", 0.10),
        "variables": data.get("variables", []) or [],
        "defaults": data.get("defaults", {}) or {},
    }


# ---------------------------------------------------------------------------
# Rule engine: apply assembly to a component type
# ---------------------------------------------------------------------------

def apply_assembly(
    component_type: str,
    rule_name: str = "",
    variables: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Apply an assembly rule set, evaluating formula BOM lines when present.

    Legacy linear multipliers (plain numbers) behave exactly as before —
    except on rules that declare ``length_m`` as a driver variable, where a
    constant line is per-unit-length and scales by the bound length (route
    rules). Formula entries require bindable variables (fail closed
    otherwise). Each material dict gains ``derivation``: None for constants,
    or {"formula": ..., "inputs": ...} / {"gauge_lookup": ..., "inputs": ...}
    where ``inputs`` snapshots the caller-supplied variables exactly.

    Constraint: Rules loaded from YAML, never hardcoded.
    """
    # Use component_type as the rule name if rule_name is not specified
    # This allows the function to be called with just the assembly type
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

    caller_vars = dict(variables or {})
    effective = _effective_variables(rule, caller_vars)
    declared = set(rule.get("variables") or [])
    needs_variables = any(isinstance(entry, dict) for entry in rule["bom"].values())
    if needs_variables and not effective:
        raise FormulaValidationError(
            "rule contains formulas but no variables were supplied",
            rule_name=lookup_name,
        )

    materials = []
    for mat_name, entry in rule["bom"].items():
        if isinstance(entry, dict) and "formula" in entry:
            quantity = evaluate_formula(entry["formula"], effective, lookup_name)
            waste = float(entry.get("waste_factor", rule["waste_factor"]))
            quantity *= 1.0 + waste
            materials.append({
                "material_name": mat_name,
                "quantity": quantity,
                "unit": _infer_unit(mat_name),
                "derivation": {"formula": entry["formula"], "inputs": caller_vars},
            })
        elif isinstance(entry, dict) and "gauge_lookup" in entry:
            resolved = lookup_gauge(entry["gauge_lookup"], effective)
            materials.append({
                "material_name": resolved,
                "quantity": 1.0,
                "unit": "ea",
                "derivation": {
                    "gauge_lookup": entry["gauge_lookup"],
                    "inputs": caller_vars,
                },
            })
        else:
            # legacy: constant multiplier per unit quantity (per unit length
            # when the rule declares length_m as a driver variable)
            quantity = float(entry)
            if "length_m" in declared and "length_m" in effective:
                quantity *= float(effective["length_m"])
            materials.append({
                "material_name": mat_name,
                "quantity": quantity,
                "unit": _infer_unit(mat_name),
                "derivation": None,
            })

    # Derive labor hours from rule
    inst_hours = rule["labor"].get("installation_hours", 0.0)

    return {
        "materials": materials,
        "labor_hours": float(inst_hours),
        "waste_factor": float(rule["waste_factor"]),
        "rule_version": rule["rule_version"],
    }


# ---------------------------------------------------------------------------
# Fail-closed rule validation (catalog load gate)
# ---------------------------------------------------------------------------

def validate_rule_file(path: Path) -> List[str]:
    """Validate one rule YAML. Returns error strings; empty list = valid.

    Fail-closed: a rule with any error must be excluded from the catalog.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        return [f"{path.name}: YAML parse error: {exc}"]

    return _validate_rule_data(data, path.name)


# ---------------------------------------------------------------------------
# Helper: infer unit from material name
# ---------------------------------------------------------------------------

def _infer_unit(mat_name: str) -> str:
    """Infer unit of measure from material name (lowercase keywords)."""
    name_lower = mat_name.lower()
    if "cable" in name_lower or "conduit" in name_lower:
        return "m"
    if "lock" in name_lower or "reader" in name_lower:
        return "ea"  # each
    if "door" in name_lower:
        return "ea"
    return "ea"  # default to each


# ---------------------------------------------------------------------------
# DB integration: persist assembly + materials to DB
# ---------------------------------------------------------------------------

def persist_assembly_to_db(
    rule_name: str,
    project_id,
    session,
) -> Optional[Assembly]:
    """Persist an assembly and its material-price links to the DB.

    Returns the Assembly record, or None if rule not found.
    """
    rule = load_assembly_rule(rule_name)
    if rule is None:
        return None

    assembly_name = rule["name"]
    rule_version = rule["rule_version"]
    bom = rule["bom"]
    labor = rule["labor"]

    # Create or retrieve Assembly record
    assembly = session.query(Assembly).filter_by(name=assembly_name).first()
    if assembly is None:
        assembly = Assembly(
            name=assembly_name,
            rule_version=rule_version,
            formula_or_bom=bom,
        )
        session.add(assembly)
        session.flush()  # assign ID without committing

    # Update rule version if changed
    if assembly.rule_version != rule_version:
        assembly.rule_version = rule_version
        assembly.formula_or_bom = bom

    # Link materials via assembly_materials junction table
    for mat_name, entry in bom.items():
        # Formula/gauge lines persist at nominal quantity 1.0; real
        # quantities live on BOQ rows (derived per component/route).
        quantity = entry if isinstance(entry, (int, float)) else 1.0
        # Find or create Material record
        material = (
            session.query(Material)
            .filter_by(name=mat_name)
            .first()
        )
        if material is None:
            material = Material(name=mat_name, unit=_infer_unit(mat_name))
            session.add(material)
            session.flush()

        # Link via assembly_materials
        from app.db.models.catalog import AssemblyMaterial

        # Check if already linked
        existing = (
            session.query(AssemblyMaterial)
            .filter_by(assembly_id=assembly.id, material_id=material.id)
            .first()
        )
        if existing is None:
            link = AssemblyMaterial(
                assembly_id=assembly.id,
                material_id=material.id,
                quantity=quantity,
            )
            session.add(link)

    # Link labor price if available
    hourly_rate = labor.get("hourly_rate")
    if hourly_rate is not None:
        # Try to find or create a labor-rate material
        labor_mat = (
            session.query(Material)
            .filter_by(name="Labor")
            .first()
        )
        if labor_mat is None:
            labor_mat = Material(name="Labor", unit="hr")
            session.add(labor_mat)
            session.flush()

        existing_link = (
            session.query(AssemblyMaterial)
            .filter_by(assembly_id=assembly.id, material_id=labor_mat.id)
            .first()
        )
        if existing_link is None:
            link = AssemblyMaterial(
                assembly_id=assembly.id,
                material_id=labor_mat.id,
                quantity=labor.get("installation_hours", 0.0),
            )
            session.add(link)

    return assembly