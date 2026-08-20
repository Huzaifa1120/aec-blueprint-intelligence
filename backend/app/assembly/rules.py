"""YAML-driven assembly rules engine for access control takeoff.

Reads rule sets from data/assemblies/*.yaml and derives material/labor
quantities from measured components. Every derived quantity records its
rule_version for auditability.

Constraint: Rules are YAML-driven, NOT hardcoded in source code.
Adding a new assembly type requires YAML edit, not code change.
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any

from app.db.models.catalog import Assembly, Material, Price
from app.db.base import Base, SessionLocal


# ---------------------------------------------------------------------------
# YAML rule set loading
# ---------------------------------------------------------------------------

_ASSEMBLIES_DIR = Path(__file__).resolve().parents[3] / "data" / "assemblies"


def load_assembly_rule(name: str) -> Optional[Dict]:
    """Load a YAML rule set by assembly name.

    Returns dict with keys: name, rule_version, bom, labor, waste_factor
    or None if not found.
    """
    yaml_path = _ASSEMBLIES_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        return None

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return {
        "name": data.get("name", name),
        "rule_version": data.get("rule_version", "unknown"),
        "bom": data.get("bom", {}),
        "labor": data.get("labor", {}),
        "waste_factor": data.get("waste_factor", 0.10),
    }


# ---------------------------------------------------------------------------
# Rule engine: apply assembly to a component type
# ---------------------------------------------------------------------------

def apply_assembly(
    component_type: str,
    rule_name: str = "access_control_door",
) -> Dict[str, Any]:
    """Apply an assembly rule set to a component type.

    Returns dict with derived quantities:
    - materials: List[Dict] with {material_name, quantity, unit}
    - labor_hours: float
    - waste_factor: float
    - rule_version: str

    Constraint: Rules loaded from YAML, never hardcoded.
    """
    rule = load_assembly_rule(rule_name)
    if rule is None:
        return {
            "materials": [],
            "labor_hours": 0.0,
            "waste_factor": 0.10,
            "rule_version": "unknown",
            "error": f"Assembly rule '{rule_name}' not found",
        }

    bom = rule["bom"]
    labor = rule["labor"]
    waste_factor = rule["waste_factor"]
    rule_version = rule["rule_version"]

    # Build materials list from BOM
    materials = []
    for mat_name, quantity in bom.items():
        materials.append({
            "material_name": mat_name,
            "quantity": quantity,
            "unit": _infer_unit(mat_name),
        })

    # Derive labor hours from rule
    inst_hours = labor.get("installation_hours", 0.0)

    return {
        "materials": materials,
        "labor_hours": float(inst_hours),
        "waste_factor": float(waste_factor),
        "rule_version": rule_version,
    }


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
    waste_factor = rule["waste_factor"]

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
    for mat_name, quantity in bom.items():
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