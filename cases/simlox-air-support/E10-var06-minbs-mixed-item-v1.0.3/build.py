"""Add a second LRU type to accepted E10.var06 arms with frozen seed 2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT_DIR = HERE.parent / "E10-var06-minbs-same-item-v1.0.0"
PARENT_SHA = {
    "minbs1": "86a52bff52982382d7695ae0a24285b124754d1373fbcd7f3f9340557b31c1ea",
    "minbs2": "afff86d9f131ffdb4478fa8a519be3da987579689313a317e7373738dba43a24",
}
OLD_IID = "TEACH-LRU-01"
NEW_IID = "TEACH-LRU-02"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def clone_one(doc: dict, name: str) -> None:
    t = table(doc, name)
    assert len(t["instances"]) == 1
    rows = t["instances"][0]["rows"]
    assert len(rows) == 1 and rows[0][0] == OLD_IID
    new = rows[0].copy()
    new[0] = NEW_IID
    if name == "Item":
        new[[c["name"] for c in t["columns"]].index("DESCR")] = "Second replaceable teaching component"
    rows.append(new)


def build(arm: str) -> bytes:
    assert arm in PARENT_SHA
    parent = PARENT_DIR / f"native-input-{arm}.json"
    assert sha(parent) == PARENT_SHA[arm]
    doc = json.loads(parent.read_text(encoding="utf-8-sig"))
    desc = table(doc, "ProblemDescription")["instances"][0]["rows"]
    assert len(desc) == 1
    desc[0][0] = f"E10.var06 mixed-IID ONDEM batch threshold {arm}; seed 2; two types share general transport data"
    control = table(doc, "Control")
    control_rows = control["instances"][0]["rows"]
    seed_index = [c["name"] for c in control["columns"]].index("RSEED")
    assert len(control_rows) == 1 and control_rows[0][seed_index] == "1"
    control_rows[0][seed_index] = "2"
    for name in ("Item", "ItemStructure", "ItemRepair"):
        clone_one(doc, name)
    system = table(doc, "System")
    assert len(system["instances"]) == 1
    system_rows = system["instances"][0]["rows"]
    frt_index = [c["name"] for c in system["columns"]].index("FRT")
    assert len(system_rows) == 1 and system_rows[0][frt_index] == 3000000
    system_rows[0][frt_index] = 6000000
    stock = table(doc, "StockAllocation")
    assert len(stock["instances"]) == 1
    rows = stock["instances"][0]["rows"]
    names = [c["name"] for c in stock["columns"]]
    assert len(rows) == 2 and all(row[names.index("IID")] == OLD_IID for row in rows)
    assert {row[names.index("STID")] for row in rows} == {"BASE-01", "DEPOT-01"}
    for row in rows.copy():
        new = row.copy()
        new[names.index("IID")] = NEW_IID
        rows.append(new)
    policy = table(doc, "TransportPolicyProfile")["instances"][0]["rows"]
    assert len(policy) == 1 and policy[0][1] == "ONDEM" and policy[0][6] == int(arm[-1])
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    for arm in ("minbs1", "minbs2"):
        raw = build(arm)
        path = HERE / f"native-input-{arm}.json"
        if write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw
        print(json.dumps({"arm": arm, "parent_sha256": PARENT_SHA[arm], "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
