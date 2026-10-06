"""Build the minimum-one A03 child from its accepted one-of-two source."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-var01-one-of-two-v0.1.0/native-input.json"
PARENT_SHA = "6b5807f42006a85f63777529d258ea1b563e5747f527821ab704f05f1d696709"
OUTPUT = HERE / "native-input.json"


def cells(doc):
    return sum(len(row) for table in doc["model"]["tables"]
               for instance in table["instances"] for row in instance["rows"])


def build():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted one-of-two source SHA differs")
    doc = json.loads(raw)
    if cells(doc) != 155:
        raise ValueError("accepted A03 positional cell count differs")
    mission = [t for t in doc["model"]["tables"] if t["name"] == "MissionType"]
    if len(mission) != 1 or len(mission[0]["instances"]) != 1:
        raise ValueError("MissionType shape differs")
    fields = [x["name"] for x in mission[0]["columns"]]
    rows = mission[0]["instances"][0]["rows"]
    if len(rows) != 1 or len(rows[0]) != len(fields):
        raise ValueError("MissionType row shape differs")
    row = rows[0]
    for field, expected in (("MTID", "BASIC-MISSION"), ("NOS", 2),
                            ("MNOS", 2), ("DURN", 2.0), ("NOPER", 1.0)):
        if row[fields.index(field)] != expected:
            raise ValueError(f"accepted MissionType.{field} differs")
    deployment = [t for t in doc["model"]["tables"] if t["name"] == "SystemDeployment"]
    if len(deployment) != 1 or len(deployment[0]["instances"]) != 1:
        raise ValueError("SystemDeployment shape differs")
    dep_fields = [x["name"] for x in deployment[0]["columns"]]
    dep_rows = deployment[0]["instances"][0]["rows"]
    if len(dep_rows) != 1 or dep_rows[0][dep_fields.index("QTYPS")] != 1:
        raise ValueError("accepted one-aircraft deployment differs")
    row[fields.index("MNOS")] = 1
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
                      "bytes": len(data), "only_change": "MissionType.MNOS 2 to 1"}))


if __name__ == "__main__":
    main()
