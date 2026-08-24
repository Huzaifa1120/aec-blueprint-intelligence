"""OCG layer registry & discipline classifier (spec v3 §7.3).

Classifies every OCG layer name on a sheet by regex against the
human-editable config ``data/layer_classification.yaml`` (ordered,
first-match-wins, terminal ``.*`` → unclassified).

Trap compliance: patterns live in YAML, never hardcoded in source. Output is
a frozen ``LayerRow`` per registry entry — deterministic, no model involved.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from app.e2e.extraction import LayerRow


_LAYER_CLASSIFICATION_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "layer_classification.yaml"
)


@lru_cache(maxsize=1)
def load_classification_rules() -> tuple[tuple[re.Pattern[str], str], ...]:
    """Load and compile the ordered classification rules from YAML once."""
    with open(_LAYER_CLASSIFICATION_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    compiled: list[tuple[re.Pattern[str], str]] = []
    for entry in data.get("layer_classification_rules", []):
        compiled.append((re.compile(entry["pattern"]), entry["discipline"]))
    return tuple(compiled)


@lru_cache(maxsize=4096)
def discipline_of(layer_name: str) -> str:
    """First-match discipline for one raw layer name ('unclassified' fallback).

    Cached helper for call sites that hold bare layer names but not the
    sheet's OCG registry (e.g. sibling-route discipline gating when deriving
    fittings). Same rules, same precedence as ``classify_layers``.
    """
    for pattern, candidate in load_classification_rules():
        if pattern.search(layer_name):
            return candidate
    return "unclassified"


def classify_layers(ocg_registry: dict[str, dict]) -> list[LayerRow]:
    """Classify each OCG name in the registry (shape from vector.build_ocg_registry).

    First matching rule wins; no match ⇒ terminal ``.*`` yields ``unclassified``
    (and if even that rule was removed by an editor, unclassified is forced).
    """
    return [
        LayerRow(ocg_name=name, classified_discipline=discipline_of(name)) for name in ocg_registry
    ]
