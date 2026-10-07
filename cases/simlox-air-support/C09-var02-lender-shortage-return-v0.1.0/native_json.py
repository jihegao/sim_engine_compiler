"""Read SIMLOX JSON without changing the raw file on disk."""
from __future__ import annotations

import json
from pathlib import Path


def parse(path: Path) -> dict:
    source = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(source)
    except json.JSONDecodeError:
        # Native exports can contain commas immediately before a closing
        # bracket. Strip those only from an in-memory copy, outside strings.
        out = []
        quoted = escaped = False
        for index, char in enumerate(source):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == ",":
                next_index = index + 1
                while next_index < len(source) and source[next_index].isspace():
                    next_index += 1
                if next_index >= len(source) or source[next_index] not in "}]":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out))


def table_map(doc: dict) -> dict:
    found = {}
    for table in doc["model"]["tables"]:
        name = table["name"]
        assert name not in found, ("duplicate table", name)
        instances = []
        for instance in table["instances"]:
            rows = instance["rows"]
            assert all(len(row) == len(table["columns"]) for row in rows)
            instances.append((instance.get("instance_name"), rows))
        found[name] = (table["columns"], instances)
    return found
