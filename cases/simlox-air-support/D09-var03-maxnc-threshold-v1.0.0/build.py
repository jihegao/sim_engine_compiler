"""Build matched MAXNC=2 and MAXNC=3 children from accepted D09.var02."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D09-var02-unset-vs-finite-v1.0.0/native-input-unset.json"
PARENT_SHA = "6303f1fd3013c43f7a6c5584a324d1fe0f32befc34548c906a11233bcb269f84"
ARMS = {"limit-2": 2, "limit-3": 3}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    assert len(found) == 1
    return found[0]


def change(doc: dict, name: str, column: str, before: object, after: object) -> None:
    target = table(doc, name)
    names = [item["name"] for item in target["columns"]]
    rows = [row for instance in target["instances"] for row in instance["rows"]]
    assert len(rows) == 1
    pos = names.index(column)
    assert rows[0][pos] == before
    rows[0][pos] = after


def build(arm: str) -> bytes:
    assert arm in ARMS and sha(PARENT.read_bytes()) == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    change(doc, "ProblemDescription", "PDESC", "D09.var02 unset NCFTL zero-stock pending noncritical repair", f"D09.var03 three installed LRUs MAXNC {ARMS[arm]} threshold")
    change(doc, "Item", "FRT", 300000, 3000000)
    change(doc, "ItemStructure", "QTYPM", 1, 3)
    change(doc, "System", "FRT", 300000, 9000000)
    change(doc, "System", "MAXNC", None, ARMS[arm])
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    result = {}
    for arm in ARMS:
        raw = build(arm)
        path = HERE / f"native-input-{arm}.json"
        if write:
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw
        result[arm] = sha(raw)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
