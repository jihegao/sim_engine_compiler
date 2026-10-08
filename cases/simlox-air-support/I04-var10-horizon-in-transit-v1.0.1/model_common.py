"""Strict, read-only JSON and byte helpers for this one SIMLOX case."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def constant(value):
    raise ValueError(f"nonfinite JSON constant: {value}")


def finite(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON number")
    elif isinstance(value, list):
        for item in value:
            finite(item)
    elif isinstance(value, dict):
        for item in value.values():
            finite(item)


def parse(data: bytes):
    value = json.loads(data.decode("utf-8-sig"), object_pairs_hook=pairs, parse_constant=constant)
    finite(value)
    return value


def read(path: Path):
    return parse(path.read_bytes())


def typed_equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return list(a) == list(b) and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def numeric_equal(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return False
    if a is None or b is None:
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isfinite(float(a)) and math.isfinite(float(b)) and a == b
    return type(a) is type(b) and a == b


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def verify_expected(path: Path, body: bytes, write: bool):
    if path.exists():
        if path.read_bytes() != body:
            raise AssertionError(f"existing file differs: {path}")
    elif write:
        with path.open("xb") as stream:
            stream.write(body)
    return {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "exists": path.exists()}
