"""Freeze one local spare at the accepted E11 autonomous base."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E11-autonomous-support-gap-v1.0.0/native-input.json"
PARENT_SHA = "d1fc66999c081acb6f29e58e5083cee58c317f0c3e0597587037efcb58a2cfd3"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E11.var01 one local spare at autonomous BASE-01; h9-11 isolation"
    )
    stock = table(doc, "StockAllocation")
    names = [c["name"] for c in stock["columns"]]
    rows = stock["instances"][0]["rows"]
    assert len(rows) == 2 and rows[0][names.index("STID")] == "BASE-01"
    assert rows[0][names.index("IID")] == "TEACH-LRU-01"
    assert rows[0][names.index("STSIZ")] == 0
    assert rows[1][names.index("STID")] == "DEPOT-01" and rows[1][names.index("STSIZ")] == 1
    rows[0][names.index("STSIZ")] = 1
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    path = HERE / "native-input.json"
    raw = build()
    if write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    else:
        assert path.read_bytes() == raw
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
