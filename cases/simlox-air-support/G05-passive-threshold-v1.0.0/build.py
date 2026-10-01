"""Build a paired passive NBOP=2 RBD with NBREQ=1 versus 2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G05-passive-switchover-v1.0.0" / "half-input.json"
PARENT_SHA256 = "d5a38dcb0006f3a2dc6447bdafdeb5c5e5a98b8eb2ccb49db57fa2801ae76c20"
ARMS = {"one": 1, "two": 2}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def row(document: dict, name: str) -> tuple[list, list[str]]:
    item = table(document, name)
    rows = item["instances"][0]["rows"]
    assert len(rows) == 1, name
    return rows[0], [column["name"] for column in item["columns"]]


def set_cell(document: dict, name: str, field: str, value: object) -> None:
    values, columns = row(document, name)
    values[columns.index(field)] = value


def build(arm: str) -> dict:
    assert arm in ARMS
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA256
    document = copy.deepcopy(json.loads(raw))
    rbd, cols = row(document, "RBDParallel")
    assert [rbd[cols.index(name)] for name in ("RBID", "NBREQ", "NBOP", "TSWOV", "ONLM")] == [
        "G05-PASSIVE", 1, 1, 0.5, "N"]
    set_cell(document, "ProblemDescription", "PDESC", f"G05 passive NBOP=2, NBREQ={ARMS[arm]}, TSWOV=0.5 h")
    set_cell(document, "RBDParallel", "DESCR", f"Two operated of three, NBREQ={ARMS[arm]}")
    set_cell(document, "RBDParallel", "NBREQ", ARMS[arm])
    set_cell(document, "RBDParallel", "NBOP", 2)
    rbd, cols = row(document, "RBDParallel")
    assert [rbd[cols.index(name)] for name in ("RBID", "NBREQ", "NBOP", "TSWOV", "ONLM")] == [
        "G05-PASSIVE", ARMS[arm], 2, 0.5, "N"]
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
