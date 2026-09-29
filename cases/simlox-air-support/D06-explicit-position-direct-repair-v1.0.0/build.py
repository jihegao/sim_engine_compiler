"""Derive a two-position, one-explicit-failure-mode D06 core slice."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA256 = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
OUTPUT = HERE / "native-input.json"


def new_table(name: str, spec: list[tuple[str, str, bool]], rows: list[list[object]]) -> dict:
    columns = []
    for field, datatype, key in spec:
        column = {"datatype": datatype}
        if key:
            column["key"] = True
        column["name"] = field
        columns.append(column)
    if any(len(row) != len(columns) for row in rows):
        raise ValueError(f"nonrectangular {name}")
    return {"columns": columns, "instances": [{"instance_name": "", "rows": rows}], "name": name}


def table(tables: list[dict], name: str) -> dict:
    matches = [t for t in tables if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return matches[0]


def update_one(tables: list[dict], name: str, **values: object) -> None:
    t = table(tables, name)
    names = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or set(values) - set(names):
        raise ValueError(f"unexpected {name} row or columns")
    for key, value in values.items():
        rows[0][names.index(key)] = value


def clear(tables: list[dict], name: str) -> None:
    t = table(tables, name)
    if len(t["instances"][0]["rows"]) != 1:
        raise ValueError(f"unexpected {name} parent rows")
    t["instances"][0]["rows"] = []


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("accepted D01 LRU parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    names = {t["name"] for t in tables}
    if names & {"MaterielPosition", "MaterielStructure", "FailureMode", "CMLocation"}:
        raise ValueError("parent already contains explicit-mode tables")
    update_one(tables, "ProblemDescription", PDESC="D06 two installed positions of one LRU, position A explicit failure mode, local direct CM")
    update_one(tables, "System", FRT=None)
    update_one(tables, "Item", FRT=None)
    for name in ("ItemStructure", "SystemRepair", "ItemRepair", "StockAllocation"):
        clear(tables, name)
    tables.append(new_table("MaterielPosition", [
        ("MPID", "string", True), ("DESCR", "string", False), ("NOTE", "string", False),
    ], [["POS-A", "Left LRU position", None], ["POS-B", "Right LRU position", None]]))
    tables.append(new_table("MaterielStructure", [
        ("MID", "string", True), ("MMID", "string", True),
        ("QTYPM", "integer", False), ("ENVF", "double", False),
        ("RUBM", "double", False), ("NOTE", "string", False),
    ], [["POS-A", "TEACH-AIR-01", 1, 1.0, None, None],
        ["POS-B", "TEACH-AIR-01", 1, 1.0, None, None],
        ["TEACH-LRU-01", "POS-A", 1, 1.0, None, None],
        ["TEACH-LRU-01", "POS-B", 1, 1.0, None, None]]))
    tables.append(new_table("FailureMode", [
        ("FMID", "string", True), ("DESCR", "string", False),
        ("MID", "string", False), ("FRQ", "double", False),
        ("OPID", "string", False), ("CRITF", "double", False),
        ("NCFTL", "double", False), ("NCFTT", "string", False),
        ("NOTE", "string", False),
    ], [["FM-POS-A", "Position A direct repair", "POS-A", 300000.0,
         "OPHOURS", 1.0, None, None, None]]))
    tables.append(new_table("CMLocation", [
        ("FMID", "string", True), ("ID", "string", True), ("STID", "string", True),
        ("CMT", "double", False), ("CMM", "double", False),
        ("CMC", "double", False), ("CMF", "double", False),
        ("TID", "string", False), ("CMTD", "string", False), ("NOTE", "string", False),
    ], [["FM-POS-A", "TEACH-AIR-01", "BASE-01", 0.5,
         None, None, 1.0, None, None, None]]))
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
        raise ValueError("frozen D06 input differs")
    print(json.dumps({"case_id": "D06", "variant": "position-a-direct-cm",
                      "parent_sha256": PARENT_SHA256,
                      "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
