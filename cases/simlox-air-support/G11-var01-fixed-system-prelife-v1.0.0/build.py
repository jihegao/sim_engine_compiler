"""Build the fixed system-prelife pair from the accepted D03 calendar PM input."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
ARMS = ("zero-age", "fixed-ages")


def table(tables: list[dict], name: str) -> dict:
    found = [t for t in tables if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def put(tables: list[dict], name: str, row: int, **values: object) -> None:
    t = table(tables, name)
    columns = [c["name"] for c in t["columns"]]
    target = t["instances"][0]["rows"][row]
    for key, value in values.items():
        target[columns.index(key)] = value


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    source = PARENT.read_bytes()
    if hashlib.sha256(source).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D03 input changed")
    doc = copy.deepcopy(json.loads(source))
    tables = doc["model"]["tables"]
    if any(t["name"].startswith("Prelife") for t in tables):
        raise ValueError("D03 unexpectedly has prelife tables")
    put(tables, "ProblemDescription", 0, PDESC="G11.var01 three-aircraft 100-hour calendar PM; " + arm)
    put(tables, "Control", 0, SIMPE=104.0, RCEND=104.0)
    put(tables, "SystemDeployment", 0, QTYPS=3, PLID="PL-SYS" if arm == "fixed-ages" else None)
    put(tables, "MaterielPM", 0, PMID="CAL100", DESCR="100-hour calendar service", PMINT=100.0)
    put(tables, "PMLocation", 0, PMID="CAL100", TID="PM-CAL100")
    put(tables, "Tasks", 0, TID="PM-CAL100")
    put(tables, "TaskBreakDown", 0, TID="PM-CAL100")
    for i in range(2):
        put(tables, "ResultCollection", i, RCEND=104.0)
    if arm == "fixed-ages":
        prelife = {
            "columns": [
                {"datatype": "string", "key": True, "name": "PLID"},
                {"datatype": "string", "name": "DESCR"},
                {"datatype": "string", "name": "MID"},
                {"datatype": "string", "name": "NOTE"},
            ],
            "instances": [{"instance_name": "", "rows": [["PL-SYS", "Three fixed aircraft ages", "TEACH-AIR-01", None]]}],
            "name": "Prelife",
        }
        data = {
            "columns": [
                {"datatype": "string", "key": True, "name": "PLID"},
                {"datatype": "string", "key": True, "name": "PLIND"},
                {"datatype": "integer", "name": "QTY"},
                {"datatype": "double", "name": "AGE"},
                {"datatype": "double", "name": "AGEMIN"},
                {"datatype": "string", "name": "OPID"},
                {"datatype": "string", "name": "TYPE"},
                {"datatype": "string", "name": "NOTE"},
            ],
            "instances": [{"instance_name": "", "rows": [
                ["PL-SYS", "AGE0", 1, 0.0, 0.0, "CALHOURS", "FIXED", None],
                ["PL-SYS", "AGE60", 1, 60.0, 0.0, "CALHOURS", "FIXED", None],
                ["PL-SYS", "AGE120", 1, 120.0, 0.0, "CALHOURS", "FIXED", None],
            ]}],
            "name": "PrelifeData",
        }
        at = next(i for i, t in enumerate(tables) if t["name"] == "SystemDeployment")
        tables[at + 1:at + 1] = [prelife, data]
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    shas = {}
    for arm in ARMS:
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"native-input-{arm}.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {arm}")
        shas[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"case_id": "G11", "variant_id": "G11.var01", "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
