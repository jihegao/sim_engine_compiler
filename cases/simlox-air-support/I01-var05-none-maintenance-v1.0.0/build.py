"""Draft explicit <NONE> maintenance POINT contrast from accepted I01.var01."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I01-var01-two-stock-points-v1.0.0/stocked-input.json"
PARENT_SHA = "9e88c4bb95e1ca1ad4ec255c0fb9996fcbab8cd80b61972771574eb416233bfb"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1
    return found[0]


def rows(doc: dict, name: str) -> list[list]:
    instances = table(doc, name)["instances"]
    assert len(instances) == 1
    return instances[0]["rows"]


def new_table(name: str, columns: list[tuple[str, str, bool]], data: list[list]) -> dict:
    assert all(len(row) == len(columns) for row in data)
    return {"columns": [dict(datatype=kind, name=column, **({"key": True} if key else {}))
                        for column, kind, key in columns],
            "instances": [{"instance_name": "", "rows": data}], "name": name}


def main() -> None:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    parent = json.loads(raw)
    assert rows(parent, "StockAllocation") == [
        ["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 1, None, None, None, None, None],
        ["AIR_EMPTY", "TEACH-LRU-01", "BASE-01", 0, None, None, None, None, None]]
    assert rows(parent, "ItemRepair")[0][11] is None
    matching = copy.deepcopy(parent)
    rows(matching, "StockAllocation")[1][:4] = ["AIR_NONE", "TEACH-LRU-01", "BASE-01", 1]
    rows(matching, "ItemRepair")[0][11] = "I01-LRU-DIRP"
    rows(matching, "Tasks").append(
        ["I01-LRU-DIRP", "Direct failed-LRU repair", "LRU-CM", "BASE", None])
    added = [
        new_table("TaskCategory", [("TCID", "string", True), ("DESCR", "string", False),
                                   ("NOTE", "string", False)],
                  [["LRU-CM", "LRU corrective maintenance", None]]),
        new_table("TaskLevel", [("TLID", "string", True), ("LEVL", "integer", False),
                                ("NOTE", "string", False)], [["BASE", 1, None]]),
        new_table("MaintenanceAllocation", [("POINT", "string", True), ("TCID", "string", True),
                                             ("TLID", "string", True), ("STID", "string", True),
                                             ("NOTE", "string", False)],
                  [["AIR_BASIC", "LRU-CM", "BASE", "BASE-01", None],
                   ["AIR_NONE", "LRU-CM", "BASE", "<NONE>", None]])]
    matching["model"]["tables"].extend(added)
    rows(matching, "ProblemDescription")[0][0] = (
        "I01.var05 maintenance POINT repairs LRU at BASE-01")
    none = copy.deepcopy(matching)
    rows(none, "Control")[0][3] = "AIR_NONE"
    rows(none, "ProblemDescription")[0][0] = (
        "I01.var05 maintenance POINT selects LRU-CM at <NONE>")
    for name, doc in (("matching-input.json", matching), ("none-input.json", none)):
        out = HERE / name
        serialized = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        if out.exists() and out.read_bytes() != serialized:
            raise ValueError(f"frozen candidate differs: {name}")
        if not out.exists():
            out.write_bytes(serialized)
        print(name, sha(serialized))


if __name__ == "__main__":
    main()
