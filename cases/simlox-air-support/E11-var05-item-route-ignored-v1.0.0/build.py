"""Freeze an item-specific transport-rule counterexample for AUTOM."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E11-autonomous-support-gap-v1.0.0/native-input.json"
PARENT_SHA = "d1fc66999c081acb6f29e58e5083cee58c317f0c3e0597587037efcb58a2cfd3"
TEMPLATE = HERE.parent / "E07-item-specific-transport-v1.0.1/native-input.json"
TEMPLATE_SHA = "d42832b9e17b9a0c968a8bba7bcb1419eba06313097604fc0041baab5d132bc0"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(TEMPLATE.read_bytes()).hexdigest() == TEMPLATE_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    support = json.loads(TEMPLATE.read_text(encoding="utf-8-sig"))
    assert not any(t["name"] == "ItemStationStructure" for t in doc["model"]["tables"])
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E11.var05 AUTOM item-specific SLOW route 5h from/7h to counterexample"
    )
    item = table(support, "ItemStationStructure")
    assert len(item["instances"]) == 1 and len(item["instances"][0]["rows"]) == 1
    names = [c["name"] for c in item["columns"]]
    row = item["instances"][0]["rows"][0]
    assert row[names.index("IID")] == "TEACH-LRU-01"
    assert row[names.index("STID")] == "BASE-01" and row[names.index("MSTID")] == "DEPOT-01"
    assert row[names.index("OPOL")] == "FAST" and row[names.index("PFRMS")] is None and row[names.index("PTOMS")] is None
    row[names.index("TFRMS")] = 5.0
    row[names.index("TTOMS")] = 7.0
    row[names.index("OPOL")] = "SLOW"
    doc["model"]["tables"].append(item)
    station = table(doc, "Station")
    snames = [c["name"] for c in station["columns"]]
    assert station["instances"][0]["rows"][0][snames.index("TYPE")] == "AUTOM"
    general = table(doc, "StationStructure")
    gnames = [c["name"] for c in general["columns"]]
    grow = general["instances"][0]["rows"][0]
    assert grow[gnames.index("PFRMS")] == grow[gnames.index("PTOMS")] == "DOWN-POLICY"
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


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
    print(json.dumps({"parent_sha256": PARENT_SHA, "template_sha256": TEMPLATE_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
