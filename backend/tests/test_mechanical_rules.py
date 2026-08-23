"""Phase 3: mechanical YAML rules load and validate; layers map."""

from pathlib import Path

from app.assembly.rules import load_assembly_rule, validate_rule_file
from app.parsing.layer_map import layer_to_assembly, route_layers

_ASSEMBLIES = Path(__file__).resolve().parents[2] / "data" / "assemblies"


class TestMechanicalRulesExist:
    def test_all_four_rules_load(self):
        for name in ("duct_rectangular", "duct_round", "pipe_insulated", "hvac_equipment"):
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
