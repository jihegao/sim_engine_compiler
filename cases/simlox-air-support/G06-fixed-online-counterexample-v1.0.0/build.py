"""Build a fixed ONLM=Y counterexample from accepted continuous ONLM=Y G05."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G05-unavailable-standby-v1.0.3/unavailable-input.json"
PARENT_SHA256 = "b0d79caeb71dbf991291b9122dff3139bc52c27e2c014b5bf624632539101f0d"
SOURCE = HERE / "fixed-input.json"
DEFERRED = HERE / "fixed-deferred-input.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def row(document: dict, name: str, key: str) -> tuple[list, list[str]]:
    found = [table for table in document["model"]["tables"] if table["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    table = found[0]
    columns = [column["name"] for column in table["columns"]]
    rows = [value for value in table["instances"][0]["rows"] if value[0] == key]
    assert len(rows) == 1, (name, key)
    return rows[0], columns


def build() -> dict:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA256
    document = copy.deepcopy(json.loads(raw))
    pdesc, cols = row(document, "ProblemDescription", "G05 unavailable preferred branch under online maintenance")
    pdesc[cols.index("PDESC")] = "G06 fixed mission ONLM Y direct CM counterexample"
    mission, cols = row(document, "MissionType", "BASIC-MISSION")
    assert mission[cols.index("MPAT")] == "CONTINUOUS"
    assert mission[cols.index("DESCR")] == "26-hour continuous standby-selection diagnostic mission"
    assert mission[cols.index("TFOUT")] is mission[cols.index("TFRET")] is None
    mission[cols.index("MPAT")] = None
    mission[cols.index("TFOUT")] = 0.25
    mission[cols.index("TFRET")] = 0.25
    mission[cols.index("DESCR")] = "26-hour fixed online direct CM counterexample mission"
    return document


def build_deferred() -> dict:
    document = build()
    pdesc, cols = row(document, "ProblemDescription", "G06 fixed mission ONLM Y direct CM counterexample")
    pdesc[cols.index("PDESC")] = "G06 fixed mission ONLM N direct CM control"
    rbd, cols = row(document, "RBDParallel", "G05-PASSIVE")
    assert rbd[cols.index("ONLM")] == "Y"
    rbd[cols.index("ONLM")] = "N"
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    sources = {SOURCE: build(), DEFERRED: build_deferred()}
    results = {}
    for path, document in sources.items():
        data = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if path.exists() and path.read_bytes() != data:
                raise ValueError(f"frozen G06 fixed input differs: {path}")
            if not path.exists():
                path.write_bytes(data)
        elif path.read_bytes() != data:
            raise ValueError(f"frozen G06 fixed input differs: {path}")
        results[path.name] = {"sha256": sha(data), "bytes": len(data)}
    print(json.dumps({"parent_sha256": PARENT_SHA256, "sources": results}))


if __name__ == "__main__":
    main()
