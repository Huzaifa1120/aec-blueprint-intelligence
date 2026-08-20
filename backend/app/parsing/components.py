"""Discrete component counting — clustered vector geometry → assembly instances.

For each DBSCAN cluster produced by the vector parser, resolve the cluster's
layer to an assembly type via the data-driven layer mapping, and emit one
component instance. Every instance carries its ``source_path_ids`` so the BOQ
row is clickable back to the PDF region.

Trap compliance:
- Counts are deterministic from vector geometry — no LLM/vision output.
- Layer→assembly resolution is YAML-driven (``data/layer_mapping.yaml``).
- Confidence tiering is discrete (MEASURED), never a blended percentage.
"""

from __future__ import annotations

from typing import Dict, List

from app.parsing.layer_map import layer_to_assembly


def count_components(
    clusters: List[Dict],
    raw_drawings: List[Dict],
) -> List[Dict]:
    """Count discrete component instances from clustered paths.

    Args:
        clusters: list of ClusterResult dicts from ``cluster_paths``.
        raw_drawings: list of DrawingPath dicts (for layer lookup by path id).

    Returns:
        List of component dicts:
        {
            "assembly_type": str,
            "count": 1,
            "layer": str,
            "source_path_ids": [str, ...],
            "confidence_status": "MEASURED",
            "confidence_score": 1.0,
        }
    """
    path_lookup: Dict[str, Dict] = {p["id"]: p for p in raw_drawings}
    components: List[Dict] = []

    for cluster in clusters:
        member_ids = cluster.get("member_path_ids", [])
        if not member_ids:
            continue

        first = path_lookup.get(member_ids[0], {})
        layer = first.get("layer") or ""
        assembly = layer_to_assembly(layer)
        if assembly is None:
            continue

        components.append(
            {
                "assembly_type": assembly,
                "count": 1,
                "layer": layer,
                "source_path_ids": member_ids,
                "confidence_status": "MEASURED",
                "confidence_score": 1.0,
            }
        )

    return components


def component_totals(components: List[Dict]) -> Dict[str, int]:
    """Aggregate component counts by assembly type (deterministic)."""
    totals: Dict[str, int] = {}
    for comp in components:
        totals[comp["assembly_type"]] = totals.get(comp["assembly_type"], 0) + 1
    return totals