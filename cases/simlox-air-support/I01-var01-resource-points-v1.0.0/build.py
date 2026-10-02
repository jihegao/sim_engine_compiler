"""Derive a two-POINT resource allocation contrast from accepted C01."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C01-personnel-capacity-v1.0.2/inputs/capacity-2.json"
PARENT_SHA = "a0d81fcfd065aa393b7ea9dace2b089e4779077e99cb242a2eae0299318c216c"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rows(doc: dict, name: str) -> list[list]:
    tables = [table for table in doc["model"]["tables"] if table["name"] == name]
    assert len(tables) == 1 and len(tables[0]["instances"]) == 1
    return tables[0]["instances"][0]["rows"]


def main() -> None:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    parent = json.loads(raw)
    assert rows(parent, "Control")[0][3] == "AIR_BASIC"
    assert rows(parent, "ResourceAllocation") == [
        ["AIR_BASIC", "P-CREW", "BASE-01", 2, None],
        ["AIR_BASIC", "P-OTHER", "BASE-01", 0, None],
    ]
    assert rows(parent, "SubTaskResource") == [
        ["PREP-FIXED", 1, "P-CREW", 2, 1, None, None, None, None]
    ]
    selected = copy.deepcopy(parent)
    rows(selected, "ResourceAllocation").extend([
        ["AIR_ZERO", "P-CREW", "BASE-01", 0, None],
        ["AIR_ZERO", "P-OTHER", "BASE-01", 0, None],
    ])
    rows(selected, "ProblemDescription")[0][0] = (
        "I01.var01 ResourceAllocation AIR_BASIC two P-CREW")
    zero = copy.deepcopy(selected)
    rows(zero, "Control")[0][3] = "AIR_ZERO"
    rows(zero, "ProblemDescription")[0][0] = (
        "I01.var01 ResourceAllocation AIR_ZERO zero P-CREW")
    for name, doc in (("selected-input.json", selected), ("zero-input.json", zero)):
        data = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        out = HERE / name
        if out.exists() and out.read_bytes() != data:
            raise ValueError(f"frozen candidate differs: {name}")
        if not out.exists():
            out.write_bytes(data)
        print(name, sha(data))


if __name__ == "__main__":
    main()
