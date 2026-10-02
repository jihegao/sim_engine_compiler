"""Freeze two tightly linked subsystems from the accepted D03 calendar PM source."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
OUT = HERE / "native-input.json"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(name)
    return found[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D03 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    rows(doc, "ProblemDescription")[0][0] = "G12.var01 two linked subsystems with leaf calendar PM"
    systems = rows(doc, "System")
    if len(systems) != 1 or systems[0][0] != "TEACH-AIR-01" or systems[0][3] != 0:
        raise ValueError("parent system changed")
    for sid in ("TEACH-SUB-A", "TEACH-SUB-B"):
        child = copy.deepcopy(systems[0])
        child[0], child[1] = sid, f"Linked subsystem {sid[-1]}"
        systems.append(child)
    system_structure = {
        "name": "SystemStructure",
        "columns": [{"datatype": kind, **({"key": True} if name in ("SID", "MSID") else {}),
                     "name": name} for name, kind in
                    (("SID", "string"), ("MSID", "string"), ("QTYPM", "integer"),
                     ("ENVF", "double"), ("NOTE", "string"))],
        "instances": [{"instance_name": "", "rows": [
            ["TEACH-SUB-A", "TEACH-AIR-01", 1, 1.0, None],
            ["TEACH-SUB-B", "TEACH-AIR-01", 1, 1.0, None]]}],
    }
    model_tables = doc["model"]["tables"]
    model_tables.insert(model_tables.index(table(doc, "System")) + 1, system_structure)
    item_rows = rows(doc, "Item")
    if item_rows:
        raise ValueError("parent Item changed")
    item_columns = [c["name"] for c in table(doc, "Item")["columns"]]
    for suffix in ("A", "B"):
        values = {"IID": f"TEACH-LRU-{suffix}", "DESCR": f"Sub-{suffix} teaching LRU",
                  "FRT": 0, "OPID": "OPHOURS", "TYPE": "LRU", "CRIT": 1.0}
        item_rows.append([values.get(name) for name in item_columns])
    item_structure = rows(doc, "ItemStructure")
    if item_structure:
        raise ValueError("parent ItemStructure changed")
    item_structure.extend([
        ["TEACH-LRU-A", "TEACH-SUB-A", 1, 1.0, None, None, None, None, None],
        ["TEACH-LRU-B", "TEACH-SUB-B", 1, 1.0, None, None, None, None, None],
    ])
    pm = rows(doc, "MaterielPM")
    location = rows(doc, "PMLocation")
    if len(pm) != 1 or pm[0][2] != "TEACH-AIR-01" or len(location) != 1 or location[0][1] != "TEACH-AIR-01":
        raise ValueError("parent PM changed")
    pm[0][2] = "TEACH-SUB-A"
    location[0][1] = "TEACH-SUB-A"
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(data)
    elif OUT.read_bytes() != data:
        raise ValueError("frozen input differs")
    print(json.dumps({"variant_id": "G12.var01", "input_sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
