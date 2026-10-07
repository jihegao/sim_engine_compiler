"""Strict read-only native JSON decoder with bounded trailing-comma repair."""
from __future__ import annotations

import json
from pathlib import Path


def typed_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")

    def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ValueError(f"nonfinite JSON number: {value}")

    def decode(raw: str) -> dict:
        return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=invalid_constant)

    try:
        return decode(text)
    except json.JSONDecodeError:
        out: list[str] = []
        quote = escape = False
        for i, char in enumerate(text):
            if quote:
                out.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    quote = False
            elif char == '"':
                quote = True
                out.append(char)
            elif char == ',':
                j = i + 1
                while j < len(text) and text[j].isspace():
                    j += 1
                if j == len(text) or text[j] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        repaired = "".join(out)
        assert repaired != text, "native JSON malformed beyond trailing commas"
        return decode(repaired)
