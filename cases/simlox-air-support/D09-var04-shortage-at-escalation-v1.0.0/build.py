"""Build a three-arm shortage-at-escalation diagnostic from accepted D09.var01."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D09-var01-calendar-vs-operational-v1.0.0/native-input-calendar.json"
PARENT_SHA = "c9645fcb8a567c89077e830916839a33dd63574b9249893f469a2ae47e5e6cce"
RESOURCE_DONOR = HERE.parent / "I01-var03-three-allocation-joint-v1.0.0/one-base-input.json"
RESOURCE_DONOR_SHA = "fd2fc5714d805cd6808e4da726e2a56b214022ec589593ec521240d974f1ae29"
ARMS = {"part-short": (0, 1), "crew-short": (1, 0), "supplied": (1, 1)}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1
    return found[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def append(doc: dict, name: str, values: dict) -> None:
    columns = [column["name"] for column in table(doc, name)["columns"]]
    assert set(values) <= set(columns)
    rows(doc, name).append([values.get(column) for column in columns])


def set_one(doc: dict, name: str, column: str, old: object, new: object) -> None:
    columns = [item["name"] for item in table(doc, name)["columns"]]
    selected = rows(doc, name)
    assert len(selected) == 1 and selected[0][columns.index(column)] == old
    selected[0][columns.index(column)] = new


def build(arm: str) -> bytes:
    assert arm in ARMS and sha(PARENT.read_bytes()) == PARENT_SHA
    assert sha(RESOURCE_DONOR.read_bytes()) == RESOURCE_DONOR_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    donor = json.loads(RESOURCE_DONOR.read_text(encoding="utf-8-sig"))
    for name in ("Tasks", "TaskBreakDown", "SubTaskResource", "Resource", "ResourceAllocation"):
        assert rows(doc, name) == []
        assert table(doc, name)["columns"] == table(donor, name)["columns"]
    stock, crew = ARMS[arm]
    set_one(doc, "ProblemDescription", "PDESC", "D09.var01 NCFTL calendar-vs-operational calendar zero-stock pending repair", f"D09.var04 {arm} at NCFTL escalation")
    set_one(doc, "SystemRepair", "SURPTID", None, "D09-SURP")
    set_one(doc, "StockAllocation", "STSIZ", 0, stock)
    append(doc, "Tasks", {"TID": "D09-SURP", "DESCR": "Explicit half-hour LRU system replacement"})
    append(doc, "TaskBreakDown", {"TID": "D09-SURP", "SEQ": 1, "SUTID": "<REMOVE>", "DURN": 0.25})
    append(doc, "TaskBreakDown", {"TID": "D09-SURP", "SEQ": 2, "SUTID": "<REPLACE>", "DURN": 0.25})
    donor_crew = next(r for r in rows(donor, "Resource") if r[[c["name"] for c in table(donor, "Resource")["columns"]].index("RID")] == "P-CREW")
    rows(doc, "Resource").append(copy.deepcopy(donor_crew))
    append(doc, "ResourceAllocation", {"POINT": "AIR_BASIC", "RID": "P-CREW", "STID": "BASE-01", "RQTY": crew})
    append(doc, "SubTaskResource", {"TID": "D09-SURP", "SEQ": 1, "RID": "P-CREW", "QTY": 1, "RPROB": 1})
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    hashes = {}
    for arm in ARMS:
        raw = build(arm)
        path = HERE / f"native-input-{arm}.json"
        if write:
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw
        hashes[arm] = sha(raw)
    print(json.dumps(hashes))


if __name__ == "__main__":
    main()
