"""Strict pure JSON and schema comparisons for the A17.var06 child."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "a17-var06-xtime-v100-ssh-20261009-01"
RUN_DIR = HERE / "runs" / RUN_ID
NATIVE_DIR = str(RUN_DIR)
INPUT_SHA = "21a88bfe7eb34c42e2f11f541f624c42c3530ffc849af475c6fd31909350d22a"
EXPORT_SHA = "92c83e28dbdd44be0f89c4355b693bd7df4099a96b577161a7839cf4a4b2213e"
J07_CONTROL_SHA = "2c0894b74bab55c1d6cb239089e66980c7cd3d214bbab8b2b334bd89f7525474"
LOG_SHA = "ae6c8430c26490c16e98f7ea66a0137ea7bcd1e309c1f2ba46a44940a0e7f33e"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read_pinned_json(path: Path, sha: str) -> dict:
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == sha, str(path)
    return json.loads(data.decode("utf-8-sig"))


def strict_json(raw: bytes) -> dict:
    assert not raw.startswith(b"\xef\xbb\xbf")
    def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            assert key not in result, f"duplicate JSON key: {key}"
            result[key] = value
        return result
    def reject_constant(value: str) -> None:
        raise AssertionError(f"nonfinite JSON constant: {value}")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs,
                      parse_constant=reject_constant)


def read_native_report(raw: bytes) -> dict:
    assert raw.count(b"\n") == raw.count(b"\r\n") and not raw.startswith(b"\xef\xbb\xbf")
    return strict_json(raw)


def count_model(model: dict) -> dict:
    assert type(model) is dict and set(model) == {"model"}
    assert type(model["model"]) is dict and set(model["model"]) == {"database_version", "tables"}
    tables = model["model"]["tables"]
    assert type(tables) is list
    for table in tables:
        assert type(table) is dict and set(table) == {"name", "columns", "instances"}
        assert type(table["columns"]) is list and type(table["instances"]) is list
        for column in table["columns"]:
            assert type(column) is dict and set(column) in ({"name", "datatype"},
                                                            {"name", "datatype", "key"})
            if "key" in column:
                assert type(column["key"]) is bool
        for instance in table["instances"]:
            assert type(instance) is dict and set(instance) == {"instance_name", "rows"}
            assert type(instance["rows"]) is list
            assert all(type(row) is list and len(row) == len(table["columns"]) for row in instance["rows"])
    rows = [r for t in tables for ins in t["instances"] for r in ins["rows"]]
    return {"tables": len(tables), "rows": len(rows), "cells": sum(len(r) for r in rows)}


def compare_typed(expected: object, actual: object, datatype: str | None = None) -> bool:
    if expected is None or actual is None:
        return expected is None and actual is None
    if datatype == "double":
        return (
            type(expected) in (int, float) and type(actual) in (int, float)
            and math.isfinite(expected) and math.isfinite(actual) and expected == actual
        )
    if datatype == "integer":
        return type(expected) is int and type(actual) is int and expected == actual
    if datatype == "string":
        return type(expected) is str and type(actual) is str and expected == actual
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, dict):
        return set(expected) == set(actual) and all(compare_typed(expected[k], actual[k]) for k in expected)
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(compare_typed(x, y) for x, y in zip(expected, actual, strict=True))
    return expected == actual


def compare_tables(expected: list[dict], actual: list[dict]) -> int:
    assert type(expected) is type(actual) is list and len(expected) == len(actual)
    cells = 0
    for e, a in zip(expected, actual, strict=True):
        assert type(e) is type(a) is dict and set(e) == set(a) == {"name", "columns", "instances"}
        assert e["name"] == a["name"]
        assert type(e["columns"]) is type(a["columns"]) is list
        assert type(e["instances"]) is type(a["instances"]) is list
        for ec, ac in zip(e["columns"], a["columns"], strict=True):
            assert type(ec) is type(ac) is dict
            assert set(ec) == set(ac) and set(ec) in ({"name", "datatype"},
                                                      {"name", "datatype", "key"})
            if "key" in ec:
                assert type(ec["key"]) is type(ac["key"]) is bool
        assert compare_typed(e["columns"], a["columns"]), e["name"]
        assert len(e["instances"]) == len(a["instances"])
        for ei, ai in zip(e["instances"], a["instances"], strict=True):
            assert type(ei) is type(ai) is dict and set(ei) == set(ai) == {"instance_name", "rows"}
            assert ei["instance_name"] == ai["instance_name"]
            assert type(ei["rows"]) is type(ai["rows"]) is list
            assert len(ei["rows"]) == len(ai["rows"])
            for er, ar in zip(ei["rows"], ai["rows"], strict=True):
                assert type(er) is type(ar) is list
                assert len(er) == len(ar) == len(e["columns"])
                for col, expected_value, actual_value in zip(e["columns"], er, ar, strict=True):
                    assert compare_typed(expected_value, actual_value, col["datatype"]), (e["name"], col["name"], expected_value, actual_value)
                    cells += 1
    return cells
