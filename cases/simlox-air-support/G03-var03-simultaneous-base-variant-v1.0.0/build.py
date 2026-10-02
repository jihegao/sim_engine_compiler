"""Deploy accepted G03 base and add variant concurrently in separate units."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G03-effective-item-contrast-v1.0.0" / "add-extra-input.json"
PARENT_SHA = "c12e1ae3ddb58e0daa4432e243e547b1fd4a174244dff93861ba86b84679f497"
OUT = HERE / "native-input.json"


def rows(doc: dict, name: str) -> list[list]:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(name)
    return matches[0]["instances"][0]["rows"]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G03 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    if rows(doc, "ProblemDescription") != [["G03 effective item contrast add-extra; fixed-seed D01 repair method"]]:
        raise ValueError("parent description changed")
    rows(doc, "ProblemDescription")[0][0] = "G03.var03 simultaneous base and BSID add variant"
    units, deployment, operations = (rows(doc, name) for name in ("Unit", "SystemDeployment", "Operations"))
    if units != [["TEACH-UNIT", "One aircraft fixed-seed item contrast", "BASE-01", None, None, None]]:
        raise ValueError("parent unit changed")
    if deployment != [["TEACH-VAR-ADD", "TEACH-UNIT", 1, 1, None, None, None]]:
        raise ValueError("parent deployment changed")
    if operations != [["TEACH-UNIT", "BASIC-SCHEDULE", None]]:
        raise ValueError("parent operations changed")
    units.append(["TEACH-BASE-UNIT", "Separately deployed base type", "BASE-01", None, None, None])
    deployment.append(["TEACH-AIR-01", "TEACH-BASE-UNIT", 1, 1, None, None, None])
    operations.append(["TEACH-BASE-UNIT", "BASIC-SCHEDULE", None])
    if [r[3] for r in rows(doc, "Item")] != [0, 300000]:
        raise ValueError("parent item rates changed")
    if rows(doc, "ItemStructure") != [["TEACH-LRU-BASE", "TEACH-AIR-01", 1, 1.0, None, None, None, None, None],
                                      ["TEACH-LRU-ADD", "TEACH-VAR-ADD", 1, 1.0, None, None, None, None, None]]:
        raise ValueError("parent inheritance structure changed")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(data)
    elif OUT.read_bytes() != data:
        raise ValueError("frozen input differs")
    print(json.dumps({"variant_id": "G03.var03", "input_sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
