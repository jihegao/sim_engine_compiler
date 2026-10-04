"""Freeze BASE-01 maintainer capacity 1→2 from accepted F04.var01."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F04-var01-deterministic-43day-v1.0.1" / "native-input.json"
PARENT_SHA = "7b9dfa927ba85c1260d9cbf6d58bae44914ad039a7b3b87b082e1ed04827cc4d"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def rows(doc: dict, name: str) -> list[list]:
    t = table(doc, name)
    assert len(t["instances"]) == 1
    return t["instances"][0]["rows"]


def build() -> dict:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    doc = json.loads(raw)
    assert len(doc["model"]["tables"]) == 32
    control = table(doc, "Control")
    cnames = [c["name"] for c in control["columns"]]
    crow = rows(doc, "Control")[0]
    assert (crow[cnames.index("NREPS")], crow[cnames.index("SIMPE")],
            crow[cnames.index("RSEED")], crow[cnames.index("RCEND")]) == (
                1, 1032.0, "1", 1032.0)
    allocation = table(doc, "ResourceAllocation")
    assert [c["name"] for c in allocation["columns"]] == [
        "POINT", "RID", "STID", "RQTY", "NOTE"]
    assert rows(doc, "ResourceAllocation") == [
        ["AIR_BASIC", "P-MAINT", "BASE-01", 1, None],
        ["AIR_BASIC", "P-CREW", "BASE-01", 1, None],
        ["AIR_BASIC", "P-MAINT", "BASE-02", 1, None],
        ["AIR_BASIC", "P-CREW", "BASE-02", 1, None]]
    rows(doc, "ProblemDescription")[0][0] = (
        "F04.var05 v1.0.0 43-day BASE-01 maintainer capacity 1 to 2")
    rows(doc, "ResourceAllocation")[0][3] = 2
    return doc


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "native-input.json"
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
