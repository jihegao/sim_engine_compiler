"""Derive a long-idle traditional OPHOURS branch from accepted D01 LRU."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
OUTPUT = HERE / "native-input.json"


def table(tables: list[dict], name: str) -> dict:
    matches = [t for t in tables if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return matches[0]


def rows(t: dict) -> tuple[list[str], list[list]]:
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def set_one(tables: list[dict], name: str, field: str, value: object) -> None:
    names, values = rows(table(tables, name))
    if len(values) != 1 or field not in names:
        raise ValueError(f"unexpected {name}.{field} shape")
    values[0][names.index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D01 LRU parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    set_one(tables, "ProblemDescription", "PDESC",
            "D02.var01 traditional LRU OPHOURS across 30-hour no-flight gap")
    set_one(tables, "Control", "SIMPE", 60.0)
    set_one(tables, "Control", "RCEND", 60.0)
    names, values = rows(table(tables, "ResultCollection"))
    if len(values) != 2 or "RCEND" not in names:
        raise ValueError("unexpected ResultCollection shape")
    for record in values:
        record[names.index("RCEND")] = 60.0
    names, values = rows(table(tables, "OperationProfile"))
    if len(values) != 3 or [r[names.index("STIM")] for r in values] != [8, 20, 32]:
        raise ValueError("unexpected parent mission schedule")
    values[2][names.index("STIM")] = 52.0
    for name in ("System", "Item"):
        names, values = rows(table(tables, name))
        if len(values) != 1 or values[0][names.index("OPID")] != "OPHOURS":
            raise ValueError(f"traditional {name}.OPID differs")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen D02.var01 input differs")
    print(json.dumps({"case_id": "D02", "variant_id": "D02.var01",
                      "parent_sha256": PARENT_SHA,
                      "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
