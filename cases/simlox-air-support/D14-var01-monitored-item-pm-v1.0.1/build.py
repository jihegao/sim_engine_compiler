"""Derive a scheduled item-removal PM MONIT=Y/N contrast from accepted D06."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA256 = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"


def table(tables: list[dict], name: str) -> dict:
    found = [t for t in tables if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def fields(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def rows(tables: list[dict], name: str) -> list[list]:
    return table(tables, name)["instances"][0]["rows"]


def put(tables: list[dict], name: str, row: int, **values: object) -> None:
    t = table(tables, name)
    names = fields(t)
    if set(values) - set(names):
        raise ValueError((name, set(values) - set(names)))
    for key, value in values.items():
        rows(tables, name)[row][names.index(key)] = value


def new_table(name: str, spec: list[tuple[str, str, bool]], body: list[list]) -> dict:
    columns = []
    for field, datatype, key in spec:
        col = {"datatype": datatype}
        if key:
            col["key"] = True
        col["name"] = field
        columns.append(col)
    if any(len(row) != len(columns) for row in body):
        raise ValueError(f"nonrectangular {name}")
    return {"columns": columns, "instances": [{"instance_name": "", "rows": body}], "name": name}


def make(arm: str) -> dict:
    if arm not in ("monitored", "system-converted"):
        raise ValueError(arm)
    source = PARENT.read_bytes()
    if hashlib.sha256(source).hexdigest() != PARENT_SHA256:
        raise ValueError("accepted D06 parent changed")
    doc = copy.deepcopy(json.loads(source))
    tables = doc["model"]["tables"]
    put(tables, "ProblemDescription", 0, PDESC=f"D14.var01 scheduled item swap PM MONIT={'Y' if arm == 'monitored' else 'N'}")
    put(tables, "Control", 0, ENPM="Y")
    rows(tables, "MaterielPosition")[:] = rows(tables, "MaterielPosition")[:1]
    rows(tables, "MaterielStructure")[:] = [r for r in rows(tables, "MaterielStructure") if "POS-B" not in r]
    rows(tables, "FailureMode").clear()
    rows(tables, "CMLocation").clear()
    stock = rows(tables, "StockAllocation")
    stock.append(["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 1, None, None, None, None, None])
    pm = rows(tables, "MaterielPM")
    pm.append(["LRU-OP2", "Item operation-hour service", "TEACH-LRU-01", 2.0, "OPHOURS", None, 0.0, 0.0, "Y" if arm == "monitored" else "N", None, None, None, None, None])
    loc = rows(tables, "PMLocation")
    loc.append(["LRU-OP2", "TEACH-AIR-01", "BASE-01", 0.5, None, None, None, None, None])
    loc.append(["LRU-OP2", "TEACH-LRU-01", "BASE-01", 1.0, None, None, None, None, None])
    if any(t["name"] == "PMReplacement" for t in tables):
        raise ValueError("parent already contains PMReplacement")
    tables.append(new_table("PMReplacement", [
        ("PMID", "string", True), ("MID", "string", True), ("IID", "string", True),
        ("PMRF", "double", False), ("PMRQ", "integer", False), ("PMRQD", "string", False),
        ("DISC", "double", False), ("SCHED", "string", False),
        ("OPID", "string", False), ("NOTE", "string", False),
    ], [["LRU-OP2", "TEACH-AIR-01", "TEACH-LRU-01", 1.0, 1,
         None, None, "Y", "OPHOURS", None]]))
    return doc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    result = {}
    for arm in ("monitored", "system-converted"):
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode()
        output = HERE / f"native-input-{arm}.json"
        if args.write:
            if output.exists():
                raise FileExistsError(output)
            output.write_bytes(raw)
        elif output.read_bytes() != raw:
            raise ValueError(f"frozen {arm} input differs")
        result[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"case_id": "D14", "variant_id": "D14.var01", "parent_sha256": PARENT_SHA256, "inputs": result}))


if __name__ == "__main__":
    main()
