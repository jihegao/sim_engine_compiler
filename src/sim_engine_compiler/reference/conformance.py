"""First-divergence reporting for legacy oracle and reference results."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class Divergence:
    path: str
    expected: Any
    actual: Any
    business_rule_id: str | None = None
    source_path: str | None = None


def first_divergence(
    expected: Any,
    actual: Any,
    *,
    path: str = "root",
    business_rule_id: str | None = None,
    source_path: str | None = None,
    float_rel_tol: float = 0.0,
    float_abs_tol: float = 0.0,
) -> Divergence | None:
    if type(expected) is not type(actual):
        return Divergence(path, expected, actual, business_rule_id, source_path)
    if isinstance(expected, dict):
        if expected.keys() != actual.keys():
            return Divergence(
                f"{path}.keys", sorted(expected), sorted(actual), business_rule_id, source_path
            )
        for key in expected:
            item = first_divergence(
                expected[key],
                actual[key],
                path=f"{path}.{key}",
                business_rule_id=business_rule_id,
                source_path=source_path,
                float_rel_tol=float_rel_tol,
                float_abs_tol=float_abs_tol,
            )
            if item:
                return item
        return None
    if isinstance(expected, list):
        if len(expected) != len(actual):
            return Divergence(f"{path}.length", len(expected), len(actual), business_rule_id, source_path)
        for index, (left, right) in enumerate(zip(expected, actual)):
            rule = business_rule_id
            source = source_path
            if isinstance(left, dict):
                rule = left.get("rule_id", rule)
                source = left.get("source_path", source)
            if isinstance(right, dict):
                rule = rule or right.get("rule_id")
                source = source or right.get("source_path")
            item = first_divergence(
                left,
                right,
                path=f"{path}[{index}]",
                business_rule_id=rule,
                source_path=source,
                float_rel_tol=float_rel_tol,
                float_abs_tol=float_abs_tol,
            )
            if item:
                return item
        return None
    if isinstance(expected, float) and math.isclose(
        expected,
        actual,
        rel_tol=float_rel_tol,
        abs_tol=float_abs_tol,
    ):
        return None
    if expected != actual:
        return Divergence(path, expected, actual, business_rule_id, source_path)
    return None


def normalize_trace(
    trace: list[dict[str, Any]], *, ignored_kinds: frozenset[str] = frozenset()
) -> list[dict[str, Any]]:
    return [
        {
            "time": item["time"],
            "phase": item["phase"],
            "kind": item["kind"],
            "entity": item["entity"],
            "rule_id": item.get("rule_id"),
            "source_path": item.get("source_path"),
            "details": item.get("details", {}),
        }
        for item in trace
        if item["kind"] not in ignored_kinds
    ]
