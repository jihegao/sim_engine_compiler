"""Derive a bounded PM activation off/on profile from accepted D03."""
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


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("accepted D03 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    if {t["name"] for t in tables} & {"PMActivation", "PMActivationProfile"}:
        raise ValueError("parent unexpectedly contains PM activation tables")
    description = next(t for t in tables if t["name"] == "ProblemDescription")
    if len(description["instances"][0]["rows"]) != 1:
        raise ValueError("unexpected parent description")
    description["instances"][0]["rows"][0][0] = "D13.var01 CAL24 PM disabled until hour 30 then enabled"
    tables.append(new_table("PMActivation", [
        ("USTID", "string", True), ("PMID", "string", True),
        ("ENPM", "string", False), ("CRIT", "string", False),
        ("PRID", "string", False), ("NOTE", "string", False),
    ], [["TEACH-UNIT", "CAL24", "Y", "Y", "PM-SWITCH", None]]))
    tables.append(new_table("PMActivationProfile", [
        ("PRID", "string", True), ("SPRID", "string", True),
        ("STIM", "double", True), ("ETIM", "double", False),
        ("IQTY", "integer", False), ("IINT", "double", False),
        ("ENPM", "string", False), ("CRIT", "string", False),
        ("NOTE", "string", False),
    ], [["PM-SWITCH", "<LIMIT>", 0.0, 30.0, 1, 0.0, "N", "Y", None],
        ["PM-SWITCH", "<LIMIT>", 30.0, 60.0, 1, 0.0, "Y", "Y", None]]))
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
        raise ValueError("frozen D13.var01 input differs")
    print(json.dumps({"case_id": "D13", "variant_id": "D13.var01",
                      "parent_sha256": PARENT_SHA256,
                      "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
