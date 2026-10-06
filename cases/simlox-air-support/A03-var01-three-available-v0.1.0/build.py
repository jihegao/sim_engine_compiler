"""Build the three-available A03 child from its accepted v1.0.1 source."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-two-aircraft-formation-v1.0.1/native-input.json"
PARENT_SHA = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
OUTPUT = HERE / "native-input.json"


def cells(doc):
    return sum(len(row) for table in doc["model"]["tables"]
               for instance in table["instances"] for row in instance["rows"])


def build():
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A03 source SHA differs")
    doc = json.loads(raw)
    if cells(doc) != 155:
        raise ValueError("accepted A03 positional cell count differs")
    found = [t for t in doc["model"]["tables"] if t["name"] == "SystemDeployment"]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError("SystemDeployment shape differs")
    columns = [x["name"] for x in found[0]["columns"]]
    rows = found[0]["instances"][0]["rows"]
    if len(rows) != 1 or len(rows[0]) != len(columns):
        raise ValueError("SystemDeployment row shape differs")
    row = rows[0]
    for field, expected in (("SID", "TEACH-AIR-01"), ("USTID", "TEACH-UNIT"),
                            ("QTYPS", 2), ("UTIL", 1)):
        if row[columns.index(field)] != expected:
            raise ValueError(f"accepted SystemDeployment.{field} differs")
    row[columns.index("QTYPS")] = 3
    mission = [t for t in doc["model"]["tables"] if t["name"] == "MissionType"]
    if len(mission) != 1 or len(mission[0]["instances"]) != 1:
        raise ValueError("MissionType shape differs")
    fields = [x["name"] for x in mission[0]["columns"]]
    missions = mission[0]["instances"][0]["rows"]
    if len(missions) != 1 or missions[0][fields.index("NOS")] != 2 or missions[0][fields.index("MNOS")] != 2:
        raise ValueError("accepted MissionType minimum differs")
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
                      "bytes": len(data), "only_change": "SystemDeployment.QTYPS 2 to 3"}))


if __name__ == "__main__":
    main()
