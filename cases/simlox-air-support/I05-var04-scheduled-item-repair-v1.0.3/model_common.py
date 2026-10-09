"""Strict byte and typed-model primitives for the bounded I05.var04 child."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUN_ID = "i05-var04-item-repair-v103-ssh-20261009-01"
NATIVE_DIR = REPO / "tmp/i05-var04-native-v103-20261009-01"
RECOVERED_DIR = REPO / "cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.3/runs" / RUN_ID
INPUT_PIN = {"bytes": 45095, "sha256": "f4157f818f9f7c00a18b01074fcde9d52ed81baa8f4d92d8e3c323f2bf2545c2"}
PATTERN_PIN = {"bytes": 87444, "sha256": "5cf823b0a1719a09e632fca16cbd6f1cc0798751dbe72e8ad29e25fb24cb7de3"}
REPORT_RULES_PIN = {"bytes": 1380881, "sha256": "84661b8f0675f91226d86623588d8c46011a7b81f05a8276666f2778b711436b"}

def seal(path: Path) -> dict[str, object]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

def no_reparse_ancestry(path: Path) -> None:
    assert path.is_absolute()
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor /= part
        assert not cursor.is_symlink() and not cursor.is_junction(), ("path alias", str(cursor))
        if cursor.exists():
            assert not (cursor.stat().st_file_attributes & 0x400), ("reparse ancestor", str(cursor))

def exact(path: Path, pin: dict[str, object]) -> bytes:
    no_reparse_ancestry(path)
    raw = path.read_bytes()
    assert len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"], str(path)
    return raw

def strict_json(raw: bytes) -> object:
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM"
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            assert key not in result, ("duplicate", key)
            result[key] = value
        return result
    def constant(token: str) -> object:
        raise AssertionError(("nonfinite", token))
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)

def native_report_json(raw: bytes) -> object:
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert raw.count(b"\n") == raw.count(b"\r\n")
    marker = b",\r\n      ]"
    assert raw.count(marker) == 1, "single approved terminal native comma"
    return strict_json(raw.replace(marker, b"\r\n      ]", 1))

def typed_equal(a: object, b: object, datatype: str | None = None) -> bool:
    if a is None or b is None:
        return a is b is None
    if datatype == "integer":
        return type(a) is type(b) is int and a == b
    if datatype == "double":
        return type(a) in (int, float) and type(b) in (int, float) and math.isfinite(a) and math.isfinite(b) and a == b
    if datatype == "string":
        return type(a) is type(b) is str and a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b, strict=True))
    return a == b

def compare_tables(expected: object, actual: object) -> int:
    assert type(expected) is type(actual) is list and len(expected) == len(actual)
    count = 0
    for et, at in zip(expected, actual, strict=True):
        assert type(et) is type(at) is dict and set(et) == set(at) == {"name", "columns", "instances"}
        assert typed_equal(et["name"], at["name"])
        assert type(et["columns"]) is type(at["columns"]) is list and len(et["columns"]) == len(at["columns"])
        for ec, ac in zip(et["columns"], at["columns"], strict=True):
            assert type(ec) is type(ac) is dict and set(ec) == set(ac)
            assert {"name", "datatype"}.issubset(ec) and set(ec) in ({"name", "datatype"}, {"name", "datatype", "key"})
            assert typed_equal(ec, ac)
        assert type(et["instances"]) is type(at["instances"]) is list and len(et["instances"]) == len(at["instances"])
        for ei, ai in zip(et["instances"], at["instances"], strict=True):
            assert type(ei) is type(ai) is dict and set(ei) == set(ai) == {"instance_name", "rows"}
            assert typed_equal(ei["instance_name"], ai["instance_name"])
            assert type(ei["rows"]) is type(ai["rows"]) is list and len(ei["rows"]) == len(ai["rows"])
            for er, ar in zip(ei["rows"], ai["rows"], strict=True):
                assert type(er) is type(ar) is list and len(er) == len(ar) == len(et["columns"])
                for column, ev, av in zip(et["columns"], er, ar, strict=True):
                    assert typed_equal(ev, av, column["datatype"]), (et["name"], column["name"], ev, av)
                    count += 1
    return count

def count_model(doc: object, root: str) -> dict[str, int]:
    assert type(doc) is dict and set(doc) == {root}
    body = doc[root]
    assert type(body) is dict and set(body) == ({"database_version", "tables"} if root == "model" else {"tables"})
    tables = body["tables"]
    assert type(tables) is list
    rows = [row for table in tables for instance in table["instances"] for row in instance["rows"]]
    return {"tables": len(tables), "rows": len(rows), "cells": sum(len(row) for row in rows)}
