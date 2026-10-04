"""Derive D15 scheduled system-PM item-swap arms from accepted D14 geometry."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D14-var01-monitored-item-pm-v1.0.1" / "native-input-monitored.json"
PARENT_SHA = "29dd9638ecaf5980b7ecf90ef41644afbbcca3a9b15f88dceb8f2fe3e5c32903"


def get(tables: list[dict], name: str) -> dict:
    found = [table for table in tables if table["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table: {name}")
    return found[0]


def rows(tables: list[dict], name: str) -> list[list]:
    return get(tables, name)["instances"][0]["rows"]


def put(tables: list[dict], name: str, index: int, **values: object) -> None:
    table = get(tables, name)
    fields = [column["name"] for column in table["columns"]]
    for key, value in values.items():
        if key not in fields:
            raise KeyError((name, key))
        rows(tables, name)[index][fields.index(key)] = value


def make(arm: str) -> dict:
    if arm not in {"certain", "fractional"}:
        raise ValueError(arm)
    source = PARENT.read_bytes()
    if hashlib.sha256(source).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D14 source changed")
    doc = copy.deepcopy(json.loads(source))
    tables = doc["model"]["tables"]
    put(tables, "ProblemDescription", 0, PDESC=f"D15.var01 system CAL24 scheduled LRU PMRF {1.0 if arm == 'certain' else 0.5}")
    put(tables, "Control", 0, SIMPE=120.0, RCEND=120.0)
    for index in range(len(rows(tables, "ResultCollection"))):
        put(tables, "ResultCollection", index, RCEND=120.0)
    # Track item state even though a station selector is required for ItemResults export.
    put(tables, "Item", 0, TRACK="Y")
    rows(tables, "ResultCollection").append(["ITEM", 0.5, 0.0, 120.0, None, None])
    put(tables, "MaterielPM", 0, PMID="SYS-CAL24", DESCR="System calendar PM with scheduled LRU exchange", MID="TEACH-AIR-01", PMINT=24.0, OPID="CALHOURS", MONIT=None)
    put(tables, "PMLocation", 0, PMID="SYS-CAL24", PMT=0.5)
    put(tables, "PMLocation", 1, PMID="SYS-CAL24", PMT=1.0)
    put(tables, "PMReplacement", 0, PMID="SYS-CAL24", PMRF=1.0 if arm == "certain" else 0.5, PMRQ=1, SCHED="Y", OPID=None)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    outputs = {}
    for arm in ("certain", "fractional"):
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        target = HERE / f"{arm}-input.json"
        if args.write:
            if target.exists():
                raise FileExistsError(target)
            target.write_bytes(raw)
        elif target.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {arm}")
        outputs[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "inputs": outputs}))


if __name__ == "__main__":
    main()
