"""Freeze traditional Item.CRIT=0 and explicit FailureMode.CRITF=0 children."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENTS = {
    "traditional": (HERE.parent / "D01-installed-lru-direct-repair-v1.0.0/native-input.json", "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93", "Item", "CRIT"),
    "failure-mode": (HERE.parent / "D06-explicit-position-direct-repair-v1.0.0/native-input.json", "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78", "FailureMode", "CRITF"),
}
EXPECTED = {
    "traditional": "cd549962924b57f4db8ccc9de906f6abd86af5c5057e4c413c2f9824bf46a01e",
    "failure-mode": "36d20f6be3bcb877ff925542aa2a3f95324a7e1562ed57f18c1561fba27fe59e",
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    assert len(found) == 1
    return found[0]


def build(arm: str) -> bytes:
    parent, expected, name, field = PARENTS[arm]
    assert sha(parent.read_bytes()) == expected
    doc = json.loads(parent.read_text(encoding="utf-8-sig"))
    description = table(doc, "ProblemDescription")
    columns = [column["name"] for column in description["columns"]]
    description["instances"][0]["rows"][0][columns.index("PDESC")] = f"D08.var03 {arm} {field} zero noncritical mission continuation"
    target = table(doc, name)
    names = [column["name"] for column in target["columns"]]
    rows = [row for inst in target["instances"] for row in inst["rows"]]
    assert len(rows) == 1 and rows[0][names.index(field)] == 1.0
    rows[0][names.index(field)] = 0.0
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    result = {}
    for arm in PARENTS:
        raw = build(arm)
        path = HERE / f"native-input-{arm}.json"
        if write:
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw
            assert sha(raw) == EXPECTED[arm]
        result[arm] = sha(raw)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
