"""JSON-only, deterministic helpers for offline public identity contracts."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any


def json_value(value: Any) -> Any:
    """Copy JSON data without coercing keys, booleans, numbers or custom objects."""
    active: set[int] = set()

    def copy_json(item: Any, depth: int) -> Any:
        if depth > 128:
            raise ValueError("JSON nesting exceeds identity contract limit of 128")
        if item is None or type(item) in (str, bool, int):
            return item
        if type(item) is float:
            if not math.isfinite(item):
                raise ValueError("non-finite JSON number")
            return item
        if isinstance(item, Mapping) or type(item) is list:
            if id(item) in active:
                raise ValueError("cyclic value is not JSON")
            active.add(id(item))
            try:
                if isinstance(item, Mapping):
                    if any(type(key) is not str for key in item):
                        raise ValueError("JSON object keys must be strings")
                    return {key: copy_json(child, depth + 1) for key, child in item.items()}
                return [copy_json(child, depth + 1) for child in item]
            finally:
                active.remove(id(item))
        raise ValueError(f"not a JSON value: {type(item).__name__}")

    return copy_json(value, 0)


def content_digest(value: Any) -> str:
    """SHA-256 of exact canonical JSON content, never a layout-insensitive ID."""
    raw = json.dumps(json_value(value), ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def diagnostic(code: str, message: str, *, stage: str = "identity",
               path: str | None = None, element_id: str | None = None,
               severity: str = "error") -> dict[str, Any]:
    return {"code": code, "severity": severity, "stage": stage,
            "path": path, "element_id": element_id, "message": message}
