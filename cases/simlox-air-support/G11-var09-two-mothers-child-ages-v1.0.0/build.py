"""Freeze two same-type mothers with swapped installed child ages."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var04-inherit-item-prelife-v1.0.1" / "native-input-inherited.json"
PARENT_SHA = "473efed447d08808d565d08956b659574596be8e2a8457f451b4816bf50251ae"
ARMS = ("age20-then60", "age60-then20")


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return matches[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G11.var04 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    rows(doc, "ProblemDescription")[0][0] = "G11.var09 same-type mothers distinct LRU ages; " + arm
    deployment = table(doc, "SystemDeployment")
    names = [c["name"] for c in deployment["columns"]]
    drows = rows(doc, "SystemDeployment")
    if len(drows) != 1 or drows[0][names.index("QTYPS")] != 1 or drows[0][names.index("PLID")] != "PL-SYS":
        raise ValueError("accepted deployment differs")
    drows[0][names.index("QTYPS")] = 2
    if rows(doc, "Prelife") != [
        ["PL-SYS", "System initial calendar age", "TEACH-AIR-01", None],
        ["PL-POS", "Position inherits system", "POS-A", None],
        ["PL-LRU", "Installed monitored item age", "TEACH-LRU-01", None],
    ]:
        raise ValueError("accepted Prelife differs")
    if rows(doc, "PrelifeData") != [
        ["PL-SYS", "SYS-60", 1, 60.0, None, "CALHOURS", "FIXED", None],
        ["PL-POS", "POS-INH", 1, 0.0, None, "CALHOURS", "INHERIT", None],
        ["PL-LRU", "LRU-20", 1, 20.0, None, "CALHOURS", "INHERIT", None],
    ]:
        raise ValueError("accepted PrelifeData differs")
    if rows(doc, "PrelifeStructure") != [
        ["PL-POS", "PL-SYS", "SYS-60", None],
        ["PL-LRU", "PL-POS", "POS-INH", None],
    ]:
        raise ValueError("accepted PrelifeStructure differs")
    table(doc, "Prelife")["instances"][0]["rows"] = [
        ["PL-SYS", "Two same-type parent systems", "TEACH-AIR-01", None],
        ["PL-POS-A", "Position under parent SYS-A", "POS-A", None],
        ["PL-POS-B", "Position under parent SYS-B", "POS-A", None],
        ["PL-LRU-A", "Installed item under SYS-A", "TEACH-LRU-01", None],
        ["PL-LRU-B", "Installed item under SYS-B", "TEACH-LRU-01", None],
    ]
    age_a, age_b = (20.0, 60.0) if arm == "age20-then60" else (60.0, 20.0)
    table(doc, "PrelifeData")["instances"][0]["rows"] = [
        ["PL-SYS", "SYS-A", 1, 60.0, None, "CALHOURS", "FIXED", None],
        ["PL-SYS", "SYS-B", 1, 60.0, None, "CALHOURS", "FIXED", None],
        ["PL-POS-A", "POS-INH-A", 1, 0.0, None, "CALHOURS", "INHERIT", None],
        ["PL-POS-B", "POS-INH-B", 1, 0.0, None, "CALHOURS", "INHERIT", None],
        ["PL-LRU-A", "LRU-A", 1, age_a, None, "CALHOURS", "FIXED", None],
        ["PL-LRU-B", "LRU-B", 1, age_b, None, "CALHOURS", "FIXED", None],
    ]
    table(doc, "PrelifeStructure")["instances"][0]["rows"] = [
        ["PL-POS-A", "PL-SYS", "SYS-A", None],
        ["PL-POS-B", "PL-SYS", "SYS-B", None],
        ["PL-LRU-A", "PL-POS-A", "POS-INH-A", None],
        ["PL-LRU-B", "PL-POS-B", "POS-INH-B", None],
    ]
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    shas = {}
    for arm in ARMS:
        encoded = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"native-input-{arm}.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(encoded)
        elif path.read_bytes() != encoded:
            raise ValueError(f"frozen input differs: {arm}")
        shas[arm] = hashlib.sha256(encoded).hexdigest()
    print(json.dumps({"case_id": "G11", "variant_id": "G11.var09", "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
