"""Build matched calendar and operational NCFTL probes from accepted D08.var03."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D08-var03-criticality-v1.0.0/native-input-traditional.json"
PARENT_SHA = "cd549962924b57f4db8ccc9de906f6abd86af5c5057e4c413c2f9824bf46a01e"
ARMS = {"calendar": "CALENDAR", "operational": "OPERATION"}


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
    change(doc, "ProblemDescription", "PDESC", "D08.var03 traditional CRIT zero noncritical mission continuation", f"D09.var01 NCFTL calendar-vs-operational {arm} zero-stock pending repair")
    change(doc, "StockAllocation", "STSIZ", 1, 0)
    change(doc, "Item", "NCFTL", None, 0.2)
    change(doc, "Item", "NCFTT", None, ARMS[arm])
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
