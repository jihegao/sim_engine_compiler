"""Build the ONLM=N direct-CM arm from the accepted G05 ONLM=Y source."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G05-unavailable-standby-v1.0.3/unavailable-input.json"
PARENT_SHA256 = "b0d79caeb71dbf991291b9122dff3139bc52c27e2c014b5bf624632539101f0d"
SOURCE = HERE / "deferred-input.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def row(document: dict, name: str, key: object) -> tuple[list, list[str]]:
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
    assert pdesc[cols.index("PDESC")] == "G05 unavailable preferred branch under online maintenance"
    pdesc[cols.index("PDESC")] = "G06 continuous passive direct CM deferred ONLM N"
    rbd, cols = row(document, "RBDParallel", "G05-PASSIVE")
    assert rbd[cols.index("ONLM")] == "Y"
    rbd[cols.index("ONLM")] = "N"
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
        raise ValueError("frozen G06 ONLM=N input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA256, "source_sha256": sha(data),
                      "bytes": len(data)}))


if __name__ == "__main__":
    main()
