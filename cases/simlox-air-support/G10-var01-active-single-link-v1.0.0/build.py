"""Derive a two-link active redundancy from accepted G01.var05."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var05-qty-two-v1.0.0" / "native-input.json"
PARENT_SHA = "ef21268a1f4c024e0c5bea24136509446e356ea3214dedd694c67825f376f984"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return found[0]


def set_value(t: dict, field: str, value: object) -> None:
    rows = t["instances"][0]["rows"]
    if len(rows) != 1:
        raise ValueError(f"one {t['name']} row required")
    rows[0][[c["name"] for c in t["columns"]].index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted G01.var05 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    set_value(table(model, "ProblemDescription"), "PDESC", "G10.var01 active 1-of-2 single-item redundancy")
    set_value(table(model, "Control"), "RELOP", "REDUNDANCY")
    structure = table(model, "ItemStructure")
    cols = [c["name"] for c in structure["columns"]]
    aircraft_rows = [r for r in structure["instances"][0]["rows"] if r[cols.index("MID")] == "TEACH-AIR-01"]
    if len(aircraft_rows) != 1 or aircraft_rows[0][cols.index("IID")] != "TEACH-LRU-01" or aircraft_rows[0][cols.index("QTYPM")] != 2:
        raise ValueError("parent must have two installed LRU instances")
    model["tables"].append({
        "columns": [
            {"datatype": "string", "key": True, "name": "RLID"},
            {"datatype": "string", "key": True, "name": "SID"},
            {"datatype": "integer", "name": "NRL"},
            {"datatype": "integer", "name": "NRLRQ"},
            {"datatype": "string", "name": "ACPA"},
            {"datatype": "double", "name": "TSWOV"},
            {"datatype": "string", "name": "NOTE"},
        ],
        "instances": [{"instance_name": "", "rows": [["TEACH-LRU-01", "TEACH-AIR-01", 2, 1, "ACTIVE", 0.0, None]]}],
        "name": "Redundancy",
    })
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
        raise ValueError("frozen input differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
