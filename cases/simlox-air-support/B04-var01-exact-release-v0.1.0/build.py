"""Build the B04 exact-release child from accepted turnround source."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B04-cross-midnight-turnround-v1.0.1/turnround-input.json"
PARENT_SHA = "9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5"
OUTPUT = HERE / "native-input.json"


def cells(doc):
    return sum(len(row) for table in doc["model"]["tables"]
               for instance in table["instances"] for row in instance["rows"])


def build():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted B04 source SHA differs")
    doc = json.loads(raw)
    if cells(doc) != 204:
        raise ValueError("accepted B04 positional cell count differs")
    found = [t for t in doc["model"]["tables"] if t["name"] == "MissionTurnround"]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError("MissionTurnround shape differs")
    cols = [x["name"] for x in found[0]["columns"]]
    rows = found[0]["instances"][0]["rows"]
    if len(rows) != 1 or len(rows[0]) != len(cols):
        raise ValueError("MissionTurnround row shape differs")
    row = rows[0]
    for field, expected in (("MTID", "BASIC-MISSION"), ("SID", "TEACH-AIR-01"),
                            ("STID", "BASE-01"), ("DURN", 1.0), ("TID", None),
                            ("DURND", None)):
        if row[cols.index(field)] != expected:
            raise ValueError(f"accepted B04 MissionTurnround.{field} differs")
    row[cols.index("DURN")] = 0.75
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = build()
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(data)
    elif OUTPUT.read_bytes() != data:
        raise ValueError("frozen child differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA,
                      "input_sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data), "only_change": "MissionTurnround.DURN 1 to 0.75"}))


if __name__ == "__main__":
    main()
