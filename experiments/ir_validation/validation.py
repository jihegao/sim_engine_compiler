"""Shared value checks and identity hashing; no domain vocabulary or dispatch."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

PROFILE = "ir-native-event-v1"
RULES = {"selection": "first_available", "acquisition": "atomic", "stock_abort": "consume"}
MAX_INTEGER = (1 << 63) - 1


class ValidationError(ValueError):
    pass


def _fail(message: str) -> None:
    raise ValidationError(message)


def _keys(value: Any, allowed: set[str], where: str) -> None:
    if not isinstance(value, dict):
        _fail(f"{where}: expected object")
    unknown = set(value) - allowed
    if unknown:
        _fail(f"{where}: unsupported fields {sorted(unknown)}")


def _integer(value: Any, where: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > MAX_INTEGER:
        _fail(f"{where}: expected integer in [{minimum},{MAX_INTEGER}]")
    return value


def _identity(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value or "|" in value:
        _fail(f"{where}: expected nonempty stable ID without '|'")
    return value


def _list(value: Any, where: str) -> list:
    if not isinstance(value, list):
        _fail(f"{where}: expected list")
    return value


def _fingerprint(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _duration(value: Any, where: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        _fail(f"{where}: duration must be [lo,hi] integer ticks")
    lo, hi = (_integer(v, where) for v in value)
    if lo > hi:
        _fail(f"{where}: duration lo exceeds hi")
    return [lo, hi]


def _unique(rows: list[dict], where: str) -> dict[str, dict]:
    found = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail(f"{where}/{i}: expected object")
        ident = _identity(row.get("id"), f"{where}/{i}/id")
        if ident in found:
            _fail(f"{where}: duplicate id {ident}")
        found[ident] = row
    return found


def _needs(raw: Any, resources: dict, where: str) -> dict:
    if not isinstance(raw, dict):
        _fail(f"{where}: needs must be object")
    result = {}
    for resource, quantity in raw.items():
        if resource not in resources:
            _fail(f"{where}: unknown resource {resource}")
        result[resource] = _integer(quantity, where, 1)
        if resources[resource]["kind"] == "capacity" and quantity > resources[resource]["initial"]:
            _fail(f"{where}: impossible capacity request {resource}")
    return result


def _dag(after: list[list[int]]) -> None:
    indegree = [len(a) for a in after]
    following = [[] for _ in after]
    for child, parents in enumerate(after):
        for parent in parents:
            following[parent].append(child)
    todo = [i for i, value in enumerate(indegree) if value == 0]
    count = 0
    while todo:
        node = todo.pop()
        count += 1
        for child in following[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                todo.append(child)
    if count != len(after):
        _fail("process predecessor graph contains a cycle")


