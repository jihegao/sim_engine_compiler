"""Build the B01 exact-notice child from frozen accepted B01 input."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B01-fixed-preparation-v1.0.1/native-input.json"
PARENT_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
OUTPUT = HERE / "native-input.json"


def build():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted B01 source SHA differs")
    doc = copy.deepcopy(json.loads(raw))
    found = [table for table in doc["model"]["tables"] if table["name"] == "MissionType"]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError("MissionType shape differs")
    columns = [field["name"] for field in found[0]["columns"]]
    rows = found[0]["instances"][0]["rows"]
    if len(rows) != 1 or len(rows[0]) != len(columns):
        raise ValueError("MissionType row shape differs")
    row = rows[0]
    for field, expected in (("MTID", "BASIC-MISSION"), ("NOPER", 1.0), ("DURN", 2.0)):
        if row[columns.index(field)] != expected:
            raise ValueError(f"accepted B01 MissionType.{field} differs")
    prep = [table for table in doc["model"]["tables"] if table["name"] == "MissionPreparation"]
    if len(prep) != 1 or len(prep[0]["instances"]) != 1 or len(prep[0]["instances"][0]["rows"]) != 1:
        raise ValueError("MissionPreparation shape differs")
    pcols = [field["name"] for field in prep[0]["columns"]]
    if prep[0]["instances"][0]["rows"][0][pcols.index("DURN")] != 0.5:
        raise ValueError("accepted B01 preparation DURN differs")
    row[columns.index("NOPER")] = 0.5
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
    print(json.dumps({"parent_sha256": PARENT_SHA,
                      "input_sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data), "only_change": "MissionType.NOPER 1 to 0.5"}))


if __name__ == "__main__":
    main()
