"""Build fixed-seed G04 active one-of-three and two-of-three threshold inputs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G04-series-active-parallel-v1.0.1" / "parallel-input.json"
PARENT_SHA256 = "ea56a9daf8705189c9162529355b28636ef7db168987b17ee90cdedbe9bb4b6f"
ARMS = {"one": 1, "two": 2}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [entry for entry in document["model"]["tables"] if entry["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def rows(document: dict, name: str) -> list[list]:
    return table(document, name)["instances"][0]["rows"]


def set_cell(document: dict, name: str, field: str, value: object) -> None:
    item = table(document, name)
    assert len(rows(document, name)) == 1, name
    columns = [column["name"] for column in item["columns"]]
    rows(document, name)[0][columns.index(field)] = value


def build(arm: str) -> dict:
    assert arm in ARMS
    raw = PARENT.read_bytes()
    assert digest(raw) == PARENT_SHA256, "accepted parent changed"
    document = copy.deepcopy(json.loads(raw))
    set_cell(document, "ProblemDescription", "PDESC", f"G04 active {ARMS[arm]}-of-3 position threshold, long mission")
    set_cell(document, "MissionType", "DESCR", "26-hour fixed teaching mission")
    set_cell(document, "MissionType", "DURN", 26.0)
    profile = rows(document, "OperationProfile")
    assert len(profile) == 3 and [row[2] for row in profile] == [8.0, 20.0, 32.0]
    del profile[1:]

    positions = rows(document, "MaterielPosition")
    assert [row[0] for row in positions] == ["POS-A", "POS-B"]
    positions.append(["POS-C", "Third nonfailing LRU position", None])

    structure = rows(document, "MaterielStructure")
    assert len(structure) == 4
    structure.insert(2, ["POS-C", "TEACH-AIR-01", 1, 1.0, None, None])
    structure.append(["TEACH-LRU-01", "POS-C", 1, 1.0, None, None])

    modes = rows(document, "MaterielOperationalModes")
    assert len(modes) == 3
    modes.append(["POS-C", "G04-OPS", None, None, 1.0, None])

    rbd = rows(document, "RBDParallel")
    assert rbd[0][2:6] == [1, 2, 0.0, "N"]
    rbd[0][1] = f"Active {ARMS[arm]}-of-3 fixed-mission threshold"
    rbd[0][2] = ARMS[arm]
    rbd[0][3] = 3
    branches = rows(document, "RBDParallelStructure")
    assert [row[1] for row in branches] == ["POS-A", "POS-B"]
    branches.append(["G04-PARALLEL", "POS-C", "G04-OPS", 1, 1, None])

    assert [row[0] for row in rows(document, "FailureMode")] == ["FM-POS-A", "FM-POS-B"]
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    output = {}
    for arm in ARMS:
        source = HERE / f"{arm}-input.json"
        data = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.write:
            if source.exists():
                raise FileExistsError(source)
            source.write_bytes(data)
        elif source.read_bytes() != data:
            raise ValueError(f"{arm} input differs from builder")
        output[arm] = {"sha256": digest(data), "bytes": len(data)}
    print(json.dumps({"parent_sha256": PARENT_SHA256, "arms": output}))


if __name__ == "__main__":
    main()
