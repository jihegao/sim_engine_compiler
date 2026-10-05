"""Move the second mission into the accepted D03 PM window."""
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
        raise ValueError("accepted D03 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = [t for t in doc["model"]["tables"] if t["name"] == "OperationProfile"]
    if len(tables) != 1 or len(tables[0]["instances"]) != 1:
        raise ValueError("unexpected OperationProfile shape")
    table = tables[0]
    fields = [x["name"] for x in table["columns"]]
    rows = table["instances"][0]["rows"]
    if len(rows) != 3 or any(len(row) != len(fields) for row in rows):
        raise ValueError("unexpected OperationProfile rows")
    profile = [dict(zip(fields, row)) for row in rows]
    if [(row["PRID"], row["SPRID"], row["STIM"], row["ITYPE"], row["DTIM"])
        for row in profile] != [
            ("BASIC-SCHEDULE", "BASIC-MISSION", 8.0, "SCHEDULED", 0.3333333333333333),
            ("BASIC-SCHEDULE", "BASIC-MISSION", 20.0, "SCHEDULED", 0.3333333333333333),
            ("BASIC-SCHEDULE", "BASIC-MISSION", 32.0, "SCHEDULED", 0.3333333333333333),
        ]:
        raise ValueError("unexpected accepted mission schedule")
    rows[1][fields.index("STIM")] = 24.5
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
        raise ValueError("frozen D03.var02 source differs from generator")
    print(json.dumps({"variant_id": "D03.var02", "parent_sha256": PARENT_SHA,
                      "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
