"""Build short and long two-operated four-branch G05 switchover inputs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G05-passive-threshold-v1.0.0" / "two-input.json"
PARENT_SHA256 = "f09cc7e9d8f1843148b537125760dc02adfb51bdc1c634e5e03e138af19bb8c4"
ARMS = {"short": 0.5, "long": 9.0}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def rows(document: dict, name: str) -> list:
    return table(document, name)["instances"][0]["rows"]


def build(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA256
    document = copy.deepcopy(json.loads(raw))
    assert rows(document, "ProblemDescription") == [["G05 passive NBOP=2, NBREQ=2, TSWOV=0.5 h"]]
    rows(document, "ProblemDescription")[0][0] = f"G05 two operated of four, {arm} TSWOV={ARMS[arm]} h"
    positions = rows(document, "MaterielPosition")
    assert [r[0] for r in positions] == ["POS-A", "POS-B", "POS-C"]
    positions.append(["POS-D", "Fourth nonfailing LRU position", None])
    structure = rows(document, "MaterielStructure")
    assert len(structure) == 6 and [r[0] for r in structure[:3]] == ["POS-A", "POS-B", "POS-C"]
    structure.insert(3, ["POS-D", "TEACH-AIR-01", 1, 1.0, None, None])
    structure.append(["TEACH-LRU-01", "POS-D", 1, 1.0, None, None])
    operational = rows(document, "MaterielOperationalModes")
    assert len(operational) == 4 and [r[0] for r in operational] == ["TEACH-AIR-01", "POS-A", "POS-B", "POS-C"]
    operational.append(["POS-D", "G04-OPS", None, None, 1.0, None])
    parallel = rows(document, "RBDParallel")
    assert parallel == [["G05-PASSIVE", "Two operated of three, NBREQ=2", 2, 2, 0.5, "N", None]]
    parallel[0][1] = "Two operated of four, two passive spares"
    parallel[0][4] = ARMS[arm]
    branches = rows(document, "RBDParallelStructure")
    assert [r[1] for r in branches] == ["POS-B", "POS-A", "POS-C"]
    branches.append(["G05-PASSIVE", "POS-D", "G04-OPS", 1, 4, None])
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {"parent_sha256": PARENT_SHA256, "arms": {}}
    for arm in ARMS:
        data = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode()
        target = HERE / f"{arm}-input.json"
        if args.write:
            if target.exists():
                raise FileExistsError(target)
            target.write_bytes(data)
        elif target.read_bytes() != data:
            raise ValueError(f"frozen {arm} input differs")
        result["arms"][arm] = {"sha256": sha(data), "bytes": len(data)}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
