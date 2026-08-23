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


def deduplicate_components(components: List[Dict]) -> List[Dict]:
    """Deduplicate components by source_path_ids.

    Keeps only one representative per unique source_path_ids subset,
    preserving order of first appearance.
    """
    seen: set = set()
    unique: List[Dict] = []
    for comp in components:
        key = tuple(sorted(comp.get("source_path_ids", [])))
        if key not in seen:
            seen.add(key)
            unique.append(comp)
    return unique


def count_components(
    clusters: List[Dict],
    raw_drawings: List[Dict],
    include_unmapped: bool = False,
) -> List[Dict]:
    """Count discrete component instances from clustered paths.

    Args:
        clusters: list of ClusterResult dicts from ``cluster_paths_threshold``.
        raw_drawings: list of DrawingPath dicts (for layer lookup by path id).
        include_unmapped: when True, clusters whose layer maps to no assembly
            rule are ALSO returned with ``assembly_type=None`` — surfaced for
            the human-verified pipeline (persisted ``UNMAPPED``), never priced.

    Returns:
        List of component dicts:
        {
            "assembly_type": str | None,
            "count": 1,
            "layer": str,
            "x": float,
            "y": float,
            "source_path_ids": [str, ...],
            "confidence_status": "MEASURED" | "UNMAPPED",
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
            if include_unmapped:
                centroid = cluster.get("centroid")
                components.append(
                    {
                        "assembly_type": None,
                        "count": 1,
                        "layer": layer,
                        "x": float(centroid[0]) if centroid is not None else 0.0,
                        "y": float(centroid[1]) if centroid is not None else 0.0,
                        "source_path_ids": member_ids,
                        "confidence_status": "UNMAPPED",
                        "confidence_score": 1.0,
                    }
                )
            continue

        centroid = cluster.get("centroid")
        components.append(
            {
                "assembly_type": assembly,
                "count": 1,
                "layer": layer,
                "x": float(centroid[0]) if centroid is not None else 0.0,
                "y": float(centroid[1]) if centroid is not None else 0.0,
                "source_path_ids": member_ids,
                "confidence_status": "MEASURED",
                "confidence_score": 1.0,
            }
        )

    # Deduplicate components with identical source_path_ids
    components = deduplicate_components(components)
    return components


def component_totals(components: List[Dict]) -> Dict[str, int]:
    """Aggregate component counts by assembly type (deterministic).

    Unmapped entries (``assembly_type=None``) have no rule to total under and
    are skipped.
    """
    totals: Dict[str, int] = {}
    for comp in components:
        assembly = comp["assembly_type"]
        if assembly is None:
            continue
        totals[assembly] = totals.get(assembly, 0) + 1
    return totals