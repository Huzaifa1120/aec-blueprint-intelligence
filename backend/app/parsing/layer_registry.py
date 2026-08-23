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


def classify_layers(ocg_registry: dict[str, dict]) -> list[LayerRow]:
    """Classify each OCG name in the registry (shape from vector.build_ocg_registry).

    First matching rule wins; no match ⇒ terminal ``.*`` yields ``unclassified``
    (and if even that rule was removed by an editor, unclassified is forced).
    """
    rows: list[LayerRow] = []
    for name in ocg_registry:
        discipline = "unclassified"
        for pattern, candidate in load_classification_rules():
            if pattern.search(name):
                discipline = candidate
                break
        rows.append(LayerRow(ocg_name=name, classified_discipline=discipline))
    return rows
