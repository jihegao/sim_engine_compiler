"""Deploy one extra subsystem instance independently in a second unit."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G12-var01-two-subsystems-v1.0.0" / "native-input.json"
PARENT_SHA = "25490c7da29019183ddc25aaed7953741bfc67261d535419941d56fc59767c7b"
OUT = HERE / "native-input.json"


def rows(doc: dict, name: str) -> list[list]:
    tables = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(tables) != 1 or len(tables[0]["instances"]) != 1:
        raise ValueError(name)
    return tables[0]["instances"][0]["rows"]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G12.var01 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    rows(doc, "ProblemDescription")[0][0] = "G12.var05 extra child-B system independently deployed"
    units, deployment, operations = (rows(doc, name) for name in ("Unit", "SystemDeployment", "Operations"))
    if units != [["TEACH-UNIT", "One-aircraft teaching unit", "BASE-01", None, None, None]]:
        raise ValueError("parent unit changed")
    if deployment != [["TEACH-AIR-01", "TEACH-UNIT", 1, 1, None, None, None]]:
        raise ValueError("parent deployment changed")
    if operations != [["TEACH-UNIT", "BASIC-SCHEDULE", None]]:
        raise ValueError("parent operations changed")
    units.append(["SUB-B-UNIT", "Independently deployed child-B type", "BASE-01", None, None, None])
    deployment.append(["TEACH-SUB-B", "SUB-B-UNIT", 1, 1, None, None, None])
    operations.append(["SUB-B-UNIT", "BASIC-SCHEDULE", None])
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(data)
    elif OUT.read_bytes() != data:
        raise ValueError("frozen input differs")
    print(json.dumps({"variant_id": "G12.var05", "input_sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
