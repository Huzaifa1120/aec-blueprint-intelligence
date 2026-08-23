"""Tests for the restricted-AST formula evaluator (Phase 3)."""
import pytest

from app.assembly.formulas import (
    FormulaValidationError,
    evaluate_formula,
    lookup_gauge,
    validate_formula,
)


class TestEvaluateFormula:
    def test_rectangular_duct_golden_case(self):
        # 10 m of 600x400 duct -> 2*(0.6+0.4)*10 = 20.0 m2
        result = evaluate_formula(
            "2 * (width_mm + height_mm) / 1000 * length_m",
            {"width_mm": 600, "height_mm": 400, "length_m": 10.0},
        )
        assert result == pytest.approx(20.0)

    def test_round_duct_golden_case(self):
        import math
        result = evaluate_formula(
            "3.141592653589793 * (diameter_mm / 1000) * length_m",
            {"diameter_mm": 250, "length_m": 8.0},
        )
        assert result == pytest.approx(math.pi * 0.25 * 8.0)

    def test_linear_multiplier_as_constant(self):
        # legacy rules: a bare number is a constant expression
        assert evaluate_formula("0.2", {}) == pytest.approx(0.2)

    def test_whitelisted_functions(self):
        assert evaluate_formula("max(width_mm, 300) / 1000", {"width_mm": 600}) == pytest.approx(0.6)
        assert evaluate_formula("round(length_m, 2)", {"length_m": 1.2345}) == pytest.approx(1.23)
        assert evaluate_formula("min(a, b) + abs(c)", {"a": 1, "b": 2, "c": -3}) == pytest.approx(4)

    def test_unknown_variable_raises(self):
        with pytest.raises(FormulaValidationError):
            evaluate_formula("width_mm + depth_mm", {"width_mm": 600})

    def test_division_by_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            evaluate_formula("length_m / 0", {"length_m": 1.0})

    def test_bad_call_raises_validation_error(self):
        # round() with no args -> TypeError inside the evaluator
        with pytest.raises(FormulaValidationError):
            evaluate_formula("round()", {})
        # min() needs at least two args
        with pytest.raises(FormulaValidationError):
            evaluate_formula("min(1)", {})

    def test_huge_exponent_rejected(self):
        with pytest.raises(FormulaValidationError):
            evaluate_formula("2 ** 99999", {})
        with pytest.raises(FormulaValidationError):
            evaluate_formula("2 ** -1001", {})
        assert evaluate_formula("2 ** 10", {}) == pytest.approx(1024)

    def test_deep_nesting_rejected(self):
        # Same-precedence operator chains parse iteratively (no parser
        # nesting cap) but build a left-leaning AST that recurses one frame
        # per term in the evaluator walker.
        expr = "+".join(["1"] * 5000)
        with pytest.raises(FormulaValidationError) as exc:
            evaluate_formula(expr, {})
        assert "nesting too deep" in str(exc.value)


class TestValidateFormula:
    def test_valid_formulas_pass(self):
        validate_formula("2 * (width_mm + height_mm) / 1000 * length_m",
                         ["width_mm", "height_mm", "length_m"])
        validate_formula("0.2", [])

    def test_unknown_name_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("width_mm + secret", ["width_mm"])

    def test_function_call_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("__import__('os').system('ls')", [])

    def test_attribute_access_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("width_mm.real", ["width_mm"])

    def test_subscript_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("width_mm['x']", ["width_mm"])

    def test_lambda_and_comprehension_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("(lambda: 1)()", [])
        with pytest.raises(FormulaValidationError):
            validate_formula("[x for x in range(3)]", [])

    def test_syntax_error_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("2 * +", [])

    def test_keyword_arguments_rejected(self):
        with pytest.raises(FormulaValidationError):
            validate_formula("round(x=1.234)", [])

    def test_error_carries_rule_context(self):
        with pytest.raises(FormulaValidationError) as exc:
            validate_formula("foo + 1", [], rule_name="duct_rectangular")
        assert "duct_rectangular" in str(exc.value)


class TestLookupGauge:
    TABLE = {
        "by": "max_mm",
        "rows": {300: "gauge_0.8mm", 750: "gauge_1.0mm", 999999: "gauge_1.2mm"},
    }

    def test_picks_first_threshold_met(self):
        assert lookup_gauge(self.TABLE, {"max_mm": 250}) == "gauge_0.8mm"
        assert lookup_gauge(self.TABLE, {"max_mm": 300}) == "gauge_0.8mm"   # boundary inclusive
        assert lookup_gauge(self.TABLE, {"max_mm": 301}) == "gauge_1.0mm"
        assert lookup_gauge(self.TABLE, {"max_mm": 5000}) == "gauge_1.2mm"

    def test_missing_driver_raises(self):
        with pytest.raises(FormulaValidationError):
            lookup_gauge(self.TABLE, {})

    def test_no_matching_row_raises(self):
        with pytest.raises(FormulaValidationError):
            lookup_gauge({"by": "max_mm", "rows": {300: "gauge_0.8mm"}}, {"max_mm": 999})
