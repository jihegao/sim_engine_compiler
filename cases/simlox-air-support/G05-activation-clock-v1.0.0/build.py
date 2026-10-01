"""Build a long-switchover probe from the accepted G05 half-hour source."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G05-passive-switchover-v1.0.0" / "half-input.json"
PARENT_SHA256 = "d5a38dcb0006f3a2dc6447bdafdeb5c5e5a98b8eb2ccb49db57fa2801ae76c20"
SOURCE = HERE / "long-input.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def set_cell(document: dict, name: str, field: str, value: object) -> None:
    item = table(document, name)
    rows = item["instances"][0]["rows"]
    assert len(rows) == 1, name
    columns = [column["name"] for column in item["columns"]]
    rows[0][columns.index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA256
    document = copy.deepcopy(json.loads(raw))
    parallel = table(document, "RBDParallel")["instances"][0]["rows"]
    assert len(parallel) == 1 and parallel[0][0:6] == [
        "G05-PASSIVE", "One operated of three with B/A/C priority", 1, 1, 0.5, "N"]
    set_cell(document, "ProblemDescription", "PDESC", "G05 activated-branch failure clock, TSWOV=8.3 h")
    set_cell(document, "RBDParallel", "TSWOV", 8.3)
    assert parallel[0][0:6] == [
        "G05-PASSIVE", "One operated of three with B/A/C priority", 1, 1, 8.3, "N"]
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if SOURCE.exists():
            raise FileExistsError(SOURCE)
        SOURCE.write_bytes(data)
    elif SOURCE.read_bytes() != data:
        raise ValueError("frozen long input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA256, "long_sha256": sha(data), "bytes": len(data)}))


if __name__ == "__main__":
    main()
