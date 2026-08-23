"""Restricted-AST formula evaluator for YAML assembly rules (Phase 3).

Formulas live in data/assemblies/*.yaml. This module parses each expression
once with Python's ``ast`` module and walks the tree allowing ONLY:
numbers, declared variables, operators + - * / ** and parentheses, and the
functions min / max / round / abs. Everything else raises
FormulaValidationError — fail closed, at load time.

No eval(), no exec(), no attribute or subscript access.
"""

from __future__ import annotations

import ast
from typing import Dict, Iterable, Set

_ALLOWED_FUNCTIONS: Set[str] = {"min", "max", "round", "abs"}
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub)


class FormulaValidationError(ValueError):
    """A formula failed validation or referenced an unknown variable."""

    def __init__(self, message: str, rule_name: str = "", expression: str = ""):
        self.rule_name = rule_name
        self.expression = expression
        prefix = f"[{rule_name}] " if rule_name else ""
        super().__init__(f"{prefix}{message}")


def _walk(node: ast.AST, allowed_vars: Set[str], rule_name: str, expression: str) -> None:
    if isinstance(node, ast.Expression):
        _walk(node.body, allowed_vars, rule_name, expression)
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return
    elif isinstance(node, ast.Name):
        if node.id not in allowed_vars and node.id not in _ALLOWED_FUNCTIONS:
            raise FormulaValidationError(
                f"unknown name '{node.id}'", rule_name, expression
            )
    elif isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
        _walk(node.left, allowed_vars, rule_name, expression)
        _walk(node.right, allowed_vars, rule_name, expression)
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, _ALLOWED_UNARYOPS):
        _walk(node.operand, allowed_vars, rule_name, expression)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCTIONS:
            raise FormulaValidationError(
                "function calls restricted to min/max/round/abs", rule_name, expression
            )
        if node.keywords:  # ast.keyword nodes are rejected outright
            raise FormulaValidationError(
                f"disallowed syntax: {type(node.keywords[0]).__name__}",
                rule_name,
                expression,
            )
        for arg in node.args:
            _walk(arg, allowed_vars, rule_name, expression)
    else:
        raise FormulaValidationError(
            f"disallowed syntax: {type(node).__name__}", rule_name, expression
        )


def validate_formula(
    expression: str, allowed_variables: Iterable[str], rule_name: str = ""
) -> None:
    """Parse and validate a formula expression. Raises FormulaValidationError."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise FormulaValidationError(f"syntax error: {exc}", rule_name, expression) from exc
    _walk(tree, set(allowed_variables), rule_name, expression)


def evaluate_formula(
    expression: str, variables: Dict[str, float], rule_name: str = ""
) -> float:
    """Evaluate a validated formula with bound variables.

    Raises FormulaValidationError for unknown/missing variables at eval time
    (validate first at load time; this catches binding mistakes), for
    pathological expressions (huge exponents, nesting beyond Python's
    recursion limit) and for ill-formed function calls.
    """
    try:
        return _evaluate_formula(expression, variables, rule_name)
    except RecursionError as exc:
        raise FormulaValidationError(
            f"expression nesting too deep: {exc}", rule_name, expression
        ) from exc


def _evaluate_formula(
    expression: str, variables: Dict[str, float], rule_name: str
) -> float:
    validate_formula(expression, variables.keys(), rule_name)
    tree = ast.parse(expression, mode="eval")

    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in _ALLOWED_FUNCTIONS:
                func = {"min": min, "max": max, "round": round, "abs": abs}[node.id]
                return func
            if node.id in variables:
                return float(variables[node.id])
            raise FormulaValidationError(
                f"missing variable '{node.id}' at evaluation", rule_name, expression
            )
        if isinstance(node, ast.BinOp):
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Pow):
                exponent = node.right
                if isinstance(exponent, ast.UnaryOp) and isinstance(
                    exponent.op, _ALLOWED_UNARYOPS
                ):
                    exponent = exponent.operand
                if (
                    isinstance(exponent, ast.Constant)
                    and isinstance(exponent.value, (int, float))
                    and abs(exponent.value) > 1000
                ):
                    raise FormulaValidationError(
                        f"exponent magnitude {exponent.value} rejected (>1000)",
                        rule_name,
                        expression,
                    )
                return left ** right
        if isinstance(node, ast.UnaryOp):
            operand = _eval(node.operand)
            return operand if isinstance(node.op, ast.UAdd) else -operand
        if isinstance(node, ast.Call):
            func = _eval(node.func)
            args = [_eval(a) for a in node.args]
            try:
                return float(func(*args))
            except TypeError as exc:
                raise FormulaValidationError(
                    f"invalid function call: {exc}", rule_name, expression
                ) from exc
        raise FormulaValidationError(
            f"cannot evaluate: {type(node).__name__}", rule_name, expression
        )

    return _eval(tree)


def lookup_gauge(table: Dict, variables: Dict[str, float]) -> str:
    """Resolve an ordered threshold lookup table to a row value.

    ``table``: {"by": <variable name>, "rows": {threshold: value, ...}}.
    Returns the first row value whose threshold >= variables[by].
    Keys may be YAML ints or strings; comparison is numeric.
    """
    driver = table.get("by", "")
    if driver not in variables:
        raise FormulaValidationError(
            f"lookup driving variable '{driver}' missing", expression=str(table)
        )
    value = float(variables[driver])
    rows = table.get("rows", {})
    for key in sorted(rows, key=float):
        if value <= float(key):
            return rows[key]
    raise FormulaValidationError(
        f"no lookup row matches {driver}={value}", expression=str(table)
    )
