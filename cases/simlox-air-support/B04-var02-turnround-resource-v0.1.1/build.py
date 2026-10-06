"""Build the sufficient-resource arm of B04.var02 from accepted B04.var05."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B04-var05-turnround-breakdown-v0.1.0" / "native-input.json"
PARENT_SHA = "965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f"
OUTPUT = HERE / "native-input.json"


def build():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted B04.var05 parent bytes differ")
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    if set(tables) != {table["name"] for table in doc["model"]["tables"]}:
        raise ValueError("duplicate table")
    rows = lambda name: tables[name]["instances"][0]["rows"]
    if rows("Resource") or rows("ResourceAllocation") or rows("SubTaskResource"):
        raise ValueError("parent already has a resource")
    if rows("TaskBreakDown")[-2:] != [
        ["TURN-STEPS", 1, "INSPECT", 1 / 6, None, None],
        ["TURN-STEPS", 2, "SERVICE", 1 / 3, None, None],
    ]:
        raise ValueError("accepted turnround steps differ")
    control = tables["Control"]
    control_row = rows("Control")[0]
    if control_row[[c["name"] for c in control["columns"]].index("APID")] != "AIR_BASIC":
        raise ValueError("accepted allocation point differs")
    if rows("ResultCollection") != [
        ["MISSION", 0.5, 0, 36.0, None, None],
        ["SYSTEM", 0.5, 0, 36.0, None, None],
    ]:
        raise ValueError("accepted result collection differs")
    rows("Resource").append(["P-CREW", "Turnround crew", None, None, None, "SPECIAL", None, None])
    rows("ResourceAllocation").append(["AIR_BASIC", "P-CREW", "BASE-01", 1, None])
    rows("SubTaskResource").append(["TURN-STEPS", 1, "P-CREW", 1, 1, None, None, None, None])
    rows("ResultCollection").append(["RESOURCE", 0.5, 0, 36.0, None, None])
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    output = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(output)
    elif OUTPUT.read_bytes() != output:
        raise ValueError("frozen child differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA,
                      "child_sha256": hashlib.sha256(output).hexdigest(),
                      "bytes": len(output)}))


if __name__ == "__main__":
    main()
