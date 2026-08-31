"""Phase 3: formula-bearing assembly rules load + evaluate correctly."""
import pytest
import yaml

from app.assembly.rules import apply_assembly, load_assembly_rule, validate_rule_file
from app.assembly.formulas import FormulaValidationError


DUCT_RULE = {
    "name": "duct_rectangular",
    "rule_version": "1.0.0",
    "variables": ["length_m", "width_mm", "height_mm", "max_mm"],
    "bom": {
        "sheet_metal_m2": {
            "formula": "2 * (width_mm + height_mm) / 1000 * length_m",
            "waste_factor": 0.15,
        },
        "duct_fitting": 0.2,  # legacy linear multiplier
        "hanger_kit": {"gauge_lookup": {"by": "max_mm",
                                         "rows": {600: "hanger_kit_light", 999999: "hanger_kit_heavy"}}},
    },
    "labor": {"installation_hours": 2.0, "hourly_rate": 50.0, "category": "mechanical"},
}


@pytest.fixture
def duct_rule(tmp_path, monkeypatch):
    rules_dir = tmp_path / "assemblies"
    rules_dir.mkdir()
    (rules_dir / "duct_rectangular.yaml").write_text(yaml.safe_dump(DUCT_RULE))
    monkeypatch.setattr("app.assembly.rules._ASSEMBLIES_DIR", rules_dir)
    load_assembly_rule.cache_clear()
    yield rules_dir
    load_assembly_rule.cache_clear()


class TestLoadAssemblyRule:
    def test_variables_exposed(self, duct_rule):
        rule = load_assembly_rule("duct_rectangular")
        assert rule["variables"] == ["length_m", "width_mm", "height_mm", "max_mm"]

    def test_legacy_rule_has_empty_variables(self, duct_rule):
        # legacy rules without a variables key still load
        (duct_rule / "legacy.yaml").write_text(yaml.safe_dump(
            {"name": "legacy", "bom": {"part": 1.0}, "labor": {}}))
        assert load_assembly_rule("legacy")["variables"] == []


class TestApplyAssemblyFormulas:
    def test_golden_case_20m2_plus_waste(self, duct_rule):
        variables = {"length_m": 10.0, "width_mm": 600, "height_mm": 400}
        result = apply_assembly("duct_rectangular", variables=variables)
        by_name = {m["material_name"]: m for m in result["materials"]}
        # 2*(600+400)/1000*10 = 20.0 * 1.15 waste = 23.0
        assert by_name["sheet_metal_m2"]["quantity"] == pytest.approx(23.0)
        assert by_name["sheet_metal_m2"]["derivation"]["formula"] == \
            "2 * (width_mm + height_mm) / 1000 * length_m"
        assert by_name["sheet_metal_m2"]["derivation"]["inputs"] == variables
        # legacy line: constant 0.2 per unit length * 10 m
        assert by_name["duct_fitting"]["quantity"] == pytest.approx(2.0)
        assert by_name["duct_fitting"]["derivation"] is None
        # gauge lookup resolved to a material line
        assert by_name["hanger_kit_light"]["quantity"] == pytest.approx(1.0)
        assert by_name["hanger_kit_light"]["derivation"]["gauge_lookup"]["by"] == "max_mm"

    def test_gauge_boundary_selects_heavy(self, duct_rule):
        variables = {"length_m": 1.0, "width_mm": 800, "height_mm": 400}
        result = apply_assembly("duct_rectangular", variables=variables)
        names = {m["material_name"] for m in result["materials"]}
        assert "hanger_kit_heavy" in names

    def test_formula_without_variables_fails_closed(self, duct_rule):
        with pytest.raises(FormulaValidationError):
            apply_assembly("duct_rectangular", variables=None)

    def test_missing_variable_fails_closed(self, duct_rule):
        with pytest.raises(FormulaValidationError):
            apply_assembly("duct_rectangular", variables={"length_m": 10.0})


class TestValidateRuleFile:
    def test_valid_rule_no_errors(self, tmp_path):
        p = tmp_path / "ok.yaml"
        p.write_text(yaml.safe_dump(DUCT_RULE))
        assert validate_rule_file(p) == []

    def test_bad_formula_reported(self, tmp_path):
        bad = dict(DUCT_RULE)
        bad["bom"] = {"x": {"formula": "__import__('os')"}}
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.safe_dump(bad))
        errors = validate_rule_file(p)
        assert len(errors) == 1
        assert "disallowed" in errors[0]

    def test_formula_referencing_undeclared_variable_reported(self, tmp_path):
        bad = dict(DUCT_RULE)
        bad["variables"] = ["length_m"]  # width_mm/height_mm undeclared
        p = tmp_path / "bad2.yaml"
        p.write_text(yaml.safe_dump(bad))
        assert len(validate_rule_file(p)) == 1

    def test_validate_rule_file_list_root_is_invalid_not_crash(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("- just\n- a\n- list\n")
        errors = validate_rule_file(p)
        assert errors  # non-empty error list; no AttributeError
        assert "mapping" in errors[0]
