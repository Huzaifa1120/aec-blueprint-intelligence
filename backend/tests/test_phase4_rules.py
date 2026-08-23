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
