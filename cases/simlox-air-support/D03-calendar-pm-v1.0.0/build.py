"""Derive the bounded 24-hour calendar-PM case from accepted A02."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
PARENT_SHA256 = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
OUTPUT = HERE / "native-input.json"


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    return matches[0]


def set_fields(model: dict, name: str, **values: object) -> None:
    target = table(model, name)
    columns = [c["name"] for c in target["columns"]]
    rows = target["instances"][0]["rows"]
    if len(rows) != 1 or set(values) - set(columns):
        raise ValueError(f"unexpected {name} shape")
    for field, value in values.items():
        rows[0][columns.index(field)] = value


def add_row(model: dict, name: str, **values: object) -> None:
    target = table(model, name)
    columns = [c["name"] for c in target["columns"]]
    rows = target["instances"][0]["rows"]
    if rows or set(values) - set(columns):
        raise ValueError(f"unexpected {name} shape")
    rows.append([values.get(c) for c in columns])


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("A02 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    set_fields(model, "Control", SIMPE=60.0, RCEND=60.0, ENPM="Y")
    result_collection = table(model, "ResultCollection")
    rc_columns = [c["name"] for c in result_collection["columns"]]
    rc_rows = result_collection["instances"][0]["rows"]
    if len(rc_rows) != 2 or {row[0] for row in rc_rows} != {"MISSION", "SYSTEM"}:
        raise ValueError("unexpected A02 result collection")
    for row in rc_rows:
        row[rc_columns.index("RCEND")] = 60.0
    add_row(model, "MaterielPM", PMID="CAL24", DESCR="24-hour calendar service",
            MID="TEACH-AIR-01", PMINT=24.0, OPID="CALHOURS", ATIM=0.0, DTIM=0.0)
    add_row(model, "PMLocation", PMID="CAL24", ID="TEACH-AIR-01", STID="BASE-01",
            PMT=1.0, TID="PM-CAL24")
    add_row(model, "Tasks", TID="PM-CAL24", DESCR="One-hour calendar service")
    add_row(model, "SubTaskType", SUTID="INSPECT", DESCR="Inspection")
    add_row(model, "TaskBreakDown", TID="PM-CAL24", SEQ=1, SUTID="INSPECT", DURN=1.0)
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
        raise ValueError("frozen D03 input differs from builder")
    print(json.dumps({"case_id": "D03", "input_sha256": hashlib.sha256(raw).hexdigest(),
                      "parent_sha256": PARENT_SHA256, "bytes": len(raw)}))


if __name__ == "__main__":
    main()
