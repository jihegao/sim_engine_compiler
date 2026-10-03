"""Extend accepted G10.var03 with two ACTIVE series items in each redundancy link."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var03-nrlrq-crossing-v1.0.0" / "native-input.json"
PARENT_SHA = "df9966f1bee58561b1bd54d05ced353abefc37efcd7559c47af5c63683aaa718"
OUTPUT = HERE / "native-input.json"
LINK_ID = "G10-SER-LINK"
AUX_ID = "TEACH-AUX-01"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"one {name} table required")
    return matches[0]


def columns_and_rows(model: dict, name: str) -> tuple[list[str], list[list]]:
    t = table(model, name)
    if len(t["instances"]) != 1:
        raise ValueError(f"one {name} instance required")
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def clone_row(model: dict, name: str, key: str, value: str) -> tuple[list[str], list]:
    cols, rows = columns_and_rows(model, name)
    hits = [r for r in rows if r[cols.index(key)] == value]
    if len(hits) != 1:
        raise ValueError(f"one {name}.{key}={value} donor required")
    clone = copy.deepcopy(hits[0])
    rows.append(clone)
    return cols, clone


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted G10.var03 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    cols, rows = columns_and_rows(model, "ProblemDescription")
    if len(rows) != 1:
        raise ValueError("one description required")
    rows[0][cols.index("PDESC")] = "G10.var01 ACTIVE 1-of-2 two-item series links"

    cols, rows = columns_and_rows(model, "System")
    if len(rows) != 1 or rows[0][cols.index("FRT")] != 1800000:
        raise ValueError("unexpected accepted System.FRT")
    rows[0][cols.index("FRT")] = 3600000

    cols, item = clone_row(model, "Item", "IID", "TEACH-LRU-01")
    item[cols.index("IID")] = AUX_ID
    item[cols.index("DESCR")] = "Direct-repair series companion in each link"
    if item[cols.index("FRT")] != 900000 or item[cols.index("TYPE")] != "LRU":
        raise ValueError("unexpected donor item")

    cols, structure = clone_row(model, "ItemStructure", "IID", "TEACH-LRU-01")
    structure[cols.index("IID")] = AUX_ID
    if structure[cols.index("MID")] != "TEACH-AIR-01" or structure[cols.index("QTYPM")] != 2:
        raise ValueError("unexpected donor structure")

    cols, repair = clone_row(model, "ItemRepair", "IID", "TEACH-SRU-01")
    repair[cols.index("IID")] = AUX_ID
    if repair[cols.index("STID")] != "BASE-01" or repair[cols.index("DIRPT")] != 1.0:
        raise ValueError("unexpected direct-repair donor")

    cols, stock = clone_row(model, "StockAllocation", "IID", "TEACH-LRU-01")
    stock[cols.index("IID")] = AUX_ID
    if stock[cols.index("STSIZ")] != 2:
        raise ValueError("unexpected donor stock")

    cols, redundancy = columns_and_rows(model, "Redundancy")
    if len(redundancy) != 1 or redundancy[0][cols.index("RLID")] != "TEACH-LRU-01" or redundancy[0][cols.index("NRL")] != 2 or redundancy[0][cols.index("NRLRQ")] != 1 or redundancy[0][cols.index("ACPA")] != "ACTIVE":
        raise ValueError("unexpected accepted redundancy")
    redundancy[0][cols.index("RLID")] = LINK_ID
    if any(t["name"] == "RedundancyLink" for t in model["tables"]):
        raise ValueError("parent already has RedundancyLink")
    model["tables"].append({
        "columns": [
            {"datatype": "string", "key": True, "name": "RLID"},
            {"datatype": "string", "key": True, "name": "IID"},
            {"datatype": "integer", "name": "QTYPL"},
            {"datatype": "string", "name": "NOTE"},
        ],
        "instances": [{"instance_name": "", "rows": [
            [LINK_ID, "TEACH-LRU-01", 1, None],
            [LINK_ID, AUX_ID, 1, None],
        ]}],
        "name": "RedundancyLink",
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
