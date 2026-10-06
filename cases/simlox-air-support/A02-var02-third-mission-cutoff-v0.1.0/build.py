"""Build one-cell A02 SYSTEM collection cutoff child from accepted source."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions/native-input.json"
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
OUTPUT = HERE / "native-input.json"


def build():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A02 input SHA differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = [t for t in doc["model"]["tables"] if t["name"] == "ResultCollection"]
    if len(tables) != 1 or len(tables[0]["instances"]) != 1:
        raise ValueError("unexpected ResultCollection shape")
    table = tables[0]
    columns = [c["name"] for c in table["columns"]]
    rows = table["instances"][0]["rows"]
    if len(rows) != 2 or any(len(row) != len(columns) for row in rows):
        raise ValueError("unexpected ResultCollection rows")
    rtype, rcend = columns.index("RTYPE"), columns.index("RCEND")
    if [(r[rtype], r[rcend]) for r in rows] != [("MISSION", 36.0), ("SYSTEM", 36.0)]:
        raise ValueError("accepted result collection differs")
    control = [t for t in doc["model"]["tables"] if t["name"] == "Control"]
    if len(control) != 1 or len(control[0]["instances"]) != 1 or len(control[0]["instances"][0]["rows"]) != 1:
        raise ValueError("unexpected Control shape")
    cc = [c["name"] for c in control[0]["columns"]]
    cr = control[0]["instances"][0]["rows"][0]
    if cr[cc.index("SIMPE")] != 36.0 or cr[cc.index("RCEND")] != 36.0:
        raise ValueError("accepted Control horizon differs")
    rows[1][rcend] = 33.0
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(data)
    elif OUTPUT.read_bytes() != data:
        raise ValueError("frozen child differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data), "only_change": "SYSTEM ResultCollection.RCEND 36 to 33"}))


if __name__ == "__main__":
    main()
