"""Build the unset NCFTL control for accepted D09.var01 finite calendar arm."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D09-var01-calendar-vs-operational-v1.0.0/native-input-calendar.json"
PARENT_SHA = "c9645fcb8a567c89077e830916839a33dd63574b9249893f469a2ae47e5e6cce"


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


def build() -> bytes:
    assert sha(PARENT.read_bytes()) == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    change(doc, "ProblemDescription", "PDESC", "D09.var01 NCFTL calendar-vs-operational calendar zero-stock pending repair", "D09.var02 unset NCFTL zero-stock pending noncritical repair")
    change(doc, "Item", "NCFTL", 0.2, None)
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    raw = build()
    path = HERE / "native-input-unset.json"
    if write:
        path.write_bytes(raw)
    else:
        assert path.read_bytes() == raw
    print(json.dumps({"input_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
