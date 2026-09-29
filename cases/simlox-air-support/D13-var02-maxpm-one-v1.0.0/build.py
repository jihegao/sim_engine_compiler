"""Derive two-aircraft noncritical calendar PM with MAXPM=1 from D03."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
PARENT_SHA256 = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
OUTPUT = HERE / "native-input.json"


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table shape")
    return found[0]


def one(model: dict, name: str, **values: object) -> None:
    t = table(model, name)
    fields = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or set(values) - set(fields):
        raise ValueError(f"unexpected {name} rows")
    for field, value in values.items():
        rows[0][fields.index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("accepted D03 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    one(model, "ProblemDescription", PDESC="D13.var02 two calendar-PM aircraft, MAXPM one")
    one(model, "Control", SIMPE=36.0, RCEND=36.0)
    result = table(model, "ResultCollection")
    fields = [c["name"] for c in result["columns"]]
    rows = result["instances"][0]["rows"]
    if len(rows) != 2 or {r[0] for r in rows} != {"MISSION", "SYSTEM"}:
        raise ValueError("unexpected parent result windows")
    for row in rows:
        row[fields.index("RCEND")] = 36.0
    one(model, "SystemDeployment", QTYPS=2)
    one(model, "Unit", DESCR="Two-aircraft teaching unit", MAXPM=1)
    one(model, "MaterielPM", DTIM=0.5)
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
        raise ValueError("frozen D13 MAXPM one input differs from builder")
    print(json.dumps({"case_id": "D13.var02", "input_sha256": hashlib.sha256(raw).hexdigest(),
                      "parent_sha256": PARENT_SHA256, "bytes": len(raw)}))


if __name__ == "__main__":
    main()
