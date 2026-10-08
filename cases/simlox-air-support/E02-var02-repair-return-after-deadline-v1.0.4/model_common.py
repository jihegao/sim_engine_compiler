"""Pure, strict byte and typed-model comparisons for E02.var02 v1.0.4."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUN_ID = "e02-var02-repair-deadline-v104-ssh-20261009-01"
NATIVE_DIR = REPO / "tmp/e02-var02-native-v104-20261009-01"
RECOVERED_DIR = REPO / "cases/simlox-air-support/E02-var02-repair-return-after-deadline-v1.0.4/runs" / RUN_ID
INPUT_PIN = {"bytes": 43701, "sha256": "fe9579fc77222196ffcd942fb5a09e98e8ebfca5208f7b954dcfcf1c6f05f98b"}
REPORT_PIN = {"bytes": 100409, "sha256": "910f3495d9217cb47e884f6a2adabee45b76add700c90c4340c636c1867af7a4"}
PATTERN_PIN = {"bytes": 16033, "sha256": "b11b963d2572af36b159326c606ae71f0e525edd0d0b1c3d985e19e96e87b332"}


def seal(path: Path) -> dict[str, object]:
    body = path.read_bytes()
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def exact(path: Path, pin: dict[str, object]) -> bytes:
    body = path.read_bytes()
    assert len(body) == pin["bytes"] and hashlib.sha256(body).hexdigest() == pin["sha256"], str(path)
    return body


def strict_json(body: bytes) -> object:
    assert not body.startswith(b"\xef\xbb\xbf"), "BOM"

    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        found: dict[str, object] = {}
        for key, value in items:
            assert key not in found, f"duplicate key: {key}"
            found[key] = value
        return found

    def constant(value: str) -> object:
        raise AssertionError(f"nonfinite JSON token: {value}")

    return json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def native_report_json(body: bytes) -> object:
    assert body.count(b"\n") == body.count(b"\r\n"), "report line endings"
    marker = b",\r\n      ]"
    assert body.count(marker) == 1, "approved native trailing-comma cardinality"
    return strict_json(body.replace(marker, b"\r\n      ]", 1))


def typed_value(expected: object, actual: object, datatype: str | None = None,
                tolerance: float = 0.0) -> bool:
    if expected is None or actual is None:
        return expected is None and actual is None
    if datatype == "integer":
        return type(expected) is type(actual) is int and expected == actual
    if datatype == "double":
        if type(expected) not in (int, float) or type(actual) not in (int, float):
            return False
        if not math.isfinite(expected) or not math.isfinite(actual):
            return False
        return abs(expected - actual) <= tolerance
    if datatype == "string":
        return type(expected) is type(actual) is str and expected == actual
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return set(expected) == set(actual) and all(
            typed_value(expected[k], actual[k], tolerance=tolerance) for k in expected)
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(
            typed_value(a, b, tolerance=tolerance) for a, b in zip(expected, actual, strict=True))
    return expected == actual


def compare_tables(expected: object, actual: object, tolerance: float = 0.0) -> int:
    assert type(expected) is type(actual) is list and len(expected) == len(actual)
    count = 0
    for et, at in zip(expected, actual, strict=True):
        assert type(et) is type(at) is dict and set(et) == set(at) == {"name", "columns", "instances"}
        assert et["name"] == at["name"]
        assert type(et["columns"]) is type(at["columns"]) is list
        assert type(et["instances"]) is type(at["instances"]) is list
        assert len(et["columns"]) == len(at["columns"])
        for ec, ac in zip(et["columns"], at["columns"], strict=True):
            assert type(ec) is type(ac) is dict and set(ec) == set(ac)
            assert {"name", "datatype"}.issubset(ec) and set(ec) in (
                {"name", "datatype"}, {"name", "datatype", "key"})
            if "key" in ec:
                assert type(ec["key"]) is type(ac["key"]) is bool
            assert typed_value(ec, ac)
        assert len(et["instances"]) == len(at["instances"])
        for ei, ai in zip(et["instances"], at["instances"], strict=True):
            assert type(ei) is type(ai) is dict and set(ei) == set(ai) == {"instance_name", "rows"}
            assert typed_value(ei["instance_name"], ai["instance_name"])
            assert type(ei["rows"]) is type(ai["rows"]) is list and len(ei["rows"]) == len(ai["rows"])
            for er, ar in zip(ei["rows"], ai["rows"], strict=True):
                assert type(er) is type(ar) is list and len(er) == len(ar) == len(et["columns"])
                for col, ev, av in zip(et["columns"], er, ar, strict=True):
                    assert typed_value(ev, av, col["datatype"], tolerance), (et["name"], col["name"], ev, av)
                    count += 1
    return count


def count_model(data: object, root: str) -> dict[str, int]:
    assert type(data) is dict and set(data) == {root}
    assert type(data[root]) is dict
    assert set(data[root]) == ({"database_version", "tables"} if root == "model" else {"tables"})
    tables = data[root]["tables"]
    assert type(tables) is list
    rows = [r for t in tables for i in t["instances"] for r in i["rows"]]
    return {"tables": len(tables), "rows": len(rows), "cells": sum(map(len, rows))}
