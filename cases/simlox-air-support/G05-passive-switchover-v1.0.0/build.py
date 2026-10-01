"""Build G05 passive one-operated-of-three RBD with zero/positive switchover time."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G04-three-branch-threshold-v1.0.0" / "one-input.json"
PARENT_SHA256 = "cfdf287c4de93638e8117c71ad3de1846da3c62c24254bf7d2a3f0f7c7c0c4d7"
ARMS = {"zero": 0.0, "half": 0.5}
ROOT = "G05-PASSIVE"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def rows(document: dict, name: str) -> list[list]:
    return table(document, name)["instances"][0]["rows"]


def set_cell(document: dict, name: str, field: str, value: object) -> None:
    item = table(document, name)
    values = rows(document, name)
    assert len(values) == 1, name
    columns = [column["name"] for column in item["columns"]]
    values[0][columns.index(field)] = value


def build(arm: str) -> dict:
    assert arm in ARMS
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA256
    document = copy.deepcopy(json.loads(raw))
    set_cell(document, "ProblemDescription", "PDESC", f"G05 passive standby, TSWOV={ARMS[arm]:g} h")
    modes = rows(document, "MaterielOperationalModes")
    assert modes[0][0:3] == ["TEACH-AIR-01", "G04-OPS", "G04-PARALLEL"]
    modes[0][2] = ROOT
    parallel = rows(document, "RBDParallel")
    assert len(parallel) == 1 and parallel[0][2:6] == [1, 3, 0.0, "N"]
    parallel[0][0:6] = [ROOT, "One operated of three with B/A/C priority", 1, 1, ARMS[arm], "N"]
    structure = rows(document, "RBDParallelStructure")
    assert [row[1] for row in structure] == ["POS-A", "POS-B", "POS-C"]
    by_position = {row[1]: row for row in structure}
    structure[:] = []
    for priority, position in enumerate(("POS-B", "POS-A", "POS-C"), start=1):
        row = by_position[position]
        row[0] = ROOT
        row[4] = priority
        structure.append(row)
    assert [row[1:5] for row in structure] == [
        ["POS-B", "G04-OPS", 1, 1], ["POS-A", "G04-OPS", 1, 2], ["POS-C", "G04-OPS", 1, 3]]
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        data = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(data)
        elif path.read_bytes() != data:
            raise ValueError(f"frozen {arm} input differs")
        result[arm] = {"sha256": sha(data), "bytes": len(data)}
    print(json.dumps({"parent_sha256": PARENT_SHA256, "arms": result}))


if __name__ == "__main__":
    main()
