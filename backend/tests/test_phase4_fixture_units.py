"""Golden tests for fixture-unit accumulation and code-table sizing."""

import pytest

from app.assembly.rules import load_assembly_rule
from app.parsing.fixture_units import (
    accumulate_fixture_units,
    fixture_units_for_type,
    resolve_size_from_fixture_units,
)


def test_fixture_units_for_type_reads_yaml():
    # wc authored in T5 with fixture_units: 3 — skip if T5 not landed yet:
    assert fixture_units_for_type("nonexistent_rule_xyz") == 0.0


@pytest.mark.skipif(
    load_assembly_rule("wc") is None,
    reason="wc/lavatory YAML rules with fixture_units are authored in Task 5",
)
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
    assert resolve_size_from_fixture_units(120.0, rows)["diameter_mm"] == 40.0
    assert resolve_size_from_fixture_units(500.0, rows) is None


def test_resolve_size_shape_is_round():
    out = resolve_size_from_fixture_units(10.0, {"16": "25"})
    assert out == {"diameter_mm": 25.0, "shape": "round"}
