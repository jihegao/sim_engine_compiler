"""Build the zero-capacity turnround crew arm from accepted B04.var02 v0.1.1."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B04-var02-turnround-resource-v0.1.1" / "native-input.json"
PARENT_SHA = "0d799bc6b2d4f8184db0bc33ddbffcaa51a822478b746fab3d4be9d942ee34d5"
OUTPUT = HERE / "native-input.json"


def build():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted sufficient-crew parent bytes differ")
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    rows = tables["ResourceAllocation"]["instances"][0]["rows"]
    if rows != [["AIR_BASIC", "P-CREW", "BASE-01", 1, None]]:
        raise ValueError("accepted parent capacity differs")
    rows[0][3] = 0
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
