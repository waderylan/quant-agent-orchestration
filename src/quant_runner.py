"""Isolated, bounded interpreter for generated arithmetic Python; no eval/exec."""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal, DecimalException, localcontext


@dataclass(frozen=True)
class Number:
    value: Decimal
    sources: frozenset[str] = frozenset()


def interpret(code, values):
    if not isinstance(code, str) or len(code) > 12000:
        raise ValueError("Analysis code must be at most 12000 characters")
    tree = ast.parse(code)
    if len(list(ast.walk(tree))) > 1000 or len(tree.body) > 40:
        raise ValueError("Analysis exceeds 1000 AST nodes or 40 assignments")
    environment = {}
    steps = 0

    def evaluate(node, depth=0):
        nonlocal steps
        steps += 1
        if steps > 2000 or depth > 40:
            raise ValueError("Analysis expression budget exceeded")
        if isinstance(node, ast.Constant):
            if type(node.value) in (int, float):
                value = Decimal(ast.get_source_segment(code, node))
                if not value.is_finite() or abs(value) > Decimal("1e18"):
                    raise ValueError("Numeric literal exceeds analysis bounds")
                return Number(value)
            if isinstance(node.value, str) and len(node.value) <= 160:
                return node.value
        elif isinstance(node, ast.Name) and node.id in environment:
            return environment[node.id]
        elif (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "values"
        ):
            if not isinstance(node.slice, ast.Constant) or not isinstance(
                node.slice.value, str
            ):
                raise ValueError("Use values['F1'] with an explicit registered input")
            source = node.slice.value
            if source not in values:
                raise ValueError(f"Missing financial input: {source}")
            value = Decimal(str(values[source]))
            if not value.is_finite() or abs(value) > Decimal("1e18"):
                raise ValueError("Source value exceeds numeric analysis bounds")
            return Number(value, frozenset({source}))
        elif isinstance(node, ast.UnaryOp) and isinstance(
            node.op, (ast.UAdd, ast.USub)
        ):
            number = evaluate(node.operand, depth + 1)
            if not isinstance(number, Number):
                raise ValueError("Unary arithmetic requires numbers")
            return Number(
                number.value if isinstance(node.op, ast.UAdd) else -number.value,
                number.sources,
            )
        elif isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)
        ):
            left, right = (
                evaluate(node.left, depth + 1),
                evaluate(node.right, depth + 1),
            )
            if not isinstance(left, Number) or not isinstance(right, Number):
                raise ValueError("Arithmetic requires numeric source values")
            if isinstance(node.op, ast.Div) and right.value == 0:
                raise ValueError("Zero denominator in generated analysis")
            if isinstance(node.op, ast.Add):
                value = left.value + right.value
            elif isinstance(node.op, ast.Sub):
                value = left.value - right.value
            elif isinstance(node.op, ast.Mult):
                value = left.value * right.value
            else:
                value = left.value / right.value
            if not value.is_finite() or abs(value) > Decimal("1e18"):
                raise ValueError("Arithmetic result exceeds analysis bounds")
            return Number(value, left.sources | right.sources)
        elif isinstance(node, ast.List) and len(node.elts) <= 64:
            return [evaluate(item, depth + 1) for item in node.elts]
        elif isinstance(node, ast.Dict) and len(node.keys) <= 8:
            keys = [evaluate(key, depth + 1) for key in node.keys]
            if any(not isinstance(k, str) for k in keys) or len(set(keys)) != len(keys):
                raise ValueError("Dictionary keys must be distinct literal strings")
            return {
                key: evaluate(value, depth + 1) for key, value in zip(keys, node.values)
            }
        raise ValueError(f"Unsupported Python syntax: {type(node).__name__}")

    with localcontext() as context:
        context.prec = 28
        for statement in tree.body:
            if (
                not isinstance(statement, ast.Assign)
                or len(statement.targets) != 1
                or not isinstance(statement.targets[0], ast.Name)
            ):
                raise ValueError("Only simple variable assignments are allowed")
            name = statement.targets[0].id
            if (
                not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", name)
                or name == "values"
            ):
                raise ValueError("Unsupported or reserved variable name")
            environment[name] = evaluate(statement.value)
    results = environment.get("results")
    if not isinstance(results, list) or not 1 <= len(results) <= 64:
        raise ValueError(
            "Assign results to a list containing 1-64 calculation dictionaries"
        )
    normalized = []
    for row in results:
        if (
            not isinstance(row, dict)
            or set(row) != {"label", "kind", "inputs", "value"}
            or not isinstance(row["value"], Number)
        ):
            raise ValueError(
                "Each result needs label, kind, inputs, and an arithmetic value"
            )
        number = row["value"]
        if (
            not isinstance(row["label"], str)
            or not isinstance(row["kind"], str)
            or not isinstance(row["inputs"], list)
            or not 1 <= len(row["inputs"]) <= 5
            or any(not isinstance(s, str) for s in row["inputs"])
        ):
            raise ValueError(
                "Result metadata must contain scalar labels and 1-2 input identifiers"
            )
        normalized.append(
            {**row, "value": str(number.value), "used_inputs": sorted(number.sources)}
        )
    return normalized


def main():
    if sys.platform != "win32":
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    try:
        payload = json.loads(sys.stdin.buffer.read(262145))
        rows = interpret(payload["code"], payload["values"])
        print(json.dumps({"results": rows}))
    except (
        ValueError,
        SyntaxError,
        KeyError,
        TypeError,
        DecimalException,
        RecursionError,
    ) as error:
        print(json.dumps({"error": str(error)[:500]}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
