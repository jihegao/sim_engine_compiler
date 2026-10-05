"""Derive the one-cycle horizon from accepted D03 source bytes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
OUTPUT = HERE / "native-input.json"


def build():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D03 source fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    if len(tables) != len(doc["model"]["tables"]):
        raise ValueError("duplicate table")

    def set_cell(name, row_index, field, old, new):
        table = tables[name]
        columns = [x["name"] for x in table["columns"]]
        if len(table["instances"]) != 1 or columns.count(field) != 1:
            raise ValueError(f"unexpected {name} shape")
        rows = table["instances"][0]["rows"]
        if row_index >= len(rows) or len(rows[row_index]) != len(columns):
            raise ValueError(f"unexpected {name} row")
        row = rows[row_index]
        pos = columns.index(field)
        if row[pos] != old:
            raise ValueError(f"unexpected {name}.{field} parent value: {row[pos]!r}")
        row[pos] = new

    set_cell("ProblemDescription", 0, "PDESC",
             "A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence",
             "D03.var01 one calendar-PM cycle through hour 36; no J35/F35 equivalence")
    set_cell("Control", 0, "SIMPE", 60.0, 36.0)
    set_cell("Control", 0, "RCEND", 60.0, 36.0)
    rc = tables["ResultCollection"]
    names = [c["name"] for c in rc["columns"]]
    rows = rc["instances"][0]["rows"]
    if len(rows) != 2 or {r[names.index("RTYPE")] for r in rows} != {"MISSION", "SYSTEM"}:
        raise ValueError("unexpected result collection rows")
    for row_index in (0, 1):
        set_cell("ResultCollection", row_index, "RCEND", 60.0, 36.0)
    return doc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen D03.var01 source differs from builder")
    print(json.dumps({"variant_id": "D03.var01", "parent_sha256": PARENT_SHA,
                      "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
