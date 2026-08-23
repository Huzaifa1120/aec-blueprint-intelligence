"""Layer-name → assembly-type mapping (data-driven from YAML).

Reads ``data/layer_mapping.yaml`` and resolves a sheet's OCG/layer name to the
canonical assembly rule name used by ``app/assembly/rules.py``.

Trap compliance: the mapping is a rule and lives in YAML, never hardcoded in
source. Adding a new layer naming convention is a data edit, not a code change.
"""

from __future__ import annotations

import yaml
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional


_LAYER_MAP_PATH = Path(__file__).resolve().parents[3] / "data" / "layer_mapping.yaml"


@lru_cache(maxsize=1)
def load_layer_mapping() -> List[Dict]:
    """Load the layer→assembly mapping list from YAML.

    Returns list of ``{"assembly": str, "layers": [str, ...]}`` entries.
    """
    with open(_LAYER_MAP_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("layer_mapping", [])


def layer_to_assembly(layer: str) -> Optional[str]:
    """Resolve a sheet layer name to an assembly rule name.

    Returns the assembly name, or None if the layer is not mapped.
    """
    if not layer:
        return None
    for entry in load_layer_mapping():
        if layer in entry.get("layers", []):
            return entry.get("assembly")
    return None


def all_mapped_layers() -> List[str]:
    """Return every layer name known to the mapping (for clustering)."""
    layers: List[str] = []
    for entry in load_layer_mapping():
        layers.extend(entry.get("layers", []))
    return layers


def route_layers() -> List[str]:
    """Return mapped layer names whose assembly is a measured route.

    Route assemblies (cable_tray, conduit, ducts, pipes) are measured by
    length rather than counted per instance. The list is data-driven from the
    same YAML mapping.
    """
    route_assemblies = {
        "cable_tray",
        "conduit",
        "duct_rectangular",
        "duct_round",
        "pipe_insulated",
    }
    layers: List[str] = []
    for entry in load_layer_mapping():
        if entry.get("assembly") in route_assemblies:
            layers.extend(entry.get("layers", []))
    return layers
