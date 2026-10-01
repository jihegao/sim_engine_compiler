"""Build a single-mission online-maintenance standby-selection probe."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G05-passive-switchover-v1.0.0" / "half-input.json"
PARENT_SHA256 = "d5a38dcb0006f3a2dc6447bdafdeb5c5e5a98b8eb2ccb49db57fa2801ae76c20"
SOURCE = HERE / "unavailable-input.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def row(document: dict, name: str, key: str) -> tuple[list, list[str]]:
    item = table(document, name)
    columns = [column["name"] for column in item["columns"]]
    found = [r for r in item["instances"][0]["rows"] if r[0] == key]
    assert len(found) == 1, (name, key)
    return found[0], columns


def build() -> dict:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA256
    document = copy.deepcopy(json.loads(raw))
    pdesc, cols = row(document, "ProblemDescription", "G05 passive standby, TSWOV=0.5 h")
    pdesc[cols.index("PDESC")] = "G05 unavailable preferred branch under online maintenance"
    cm, cols = row(document, "CMLocation", "FM-POS-B")
    assert cm[cols.index("CMT")] == 0.5
    cm[cols.index("CMT")] = 40.0
    rbd, cols = row(document, "RBDParallel", "G05-PASSIVE")
    assert rbd[cols.index("ONLM")] == "N"
    rbd[cols.index("ONLM")] = "Y"
    mission, cols = row(document, "MissionType", "BASIC-MISSION")
    assert mission[cols.index("MPAT")] is None
    assert mission[cols.index("DESCR")] == "26-hour fixed teaching mission"
    mission[cols.index("MPAT")] = "CONTINUOUS"
    mission[cols.index("DESCR")] = "26-hour continuous standby-selection diagnostic mission"
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
        raise ValueError("frozen unavailable input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA256, "source_sha256": sha(data), "bytes": len(data)}))


if __name__ == "__main__":
    main()
