"""Derive one-time swap plus per-item PM from accepted D14.var01 arms."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D14-var01-monitored-item-pm-v1.0.1"
PARENT_SHA = {
    "monitored": "29dd9638ecaf5980b7ecf90ef41644afbbcca3a9b15f88dceb8f2fe3e5c32903",
    "system-converted": "9e6f77519511e72eb732dc5c67b19a8dab16a166ca9d33a50917bb04b88ae9f9",
}


def table(tables: list[dict], name: str) -> dict:
    found = [t for t in tables if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def rows(tables: list[dict], name: str) -> list[list]:
    return table(tables, name)["instances"][0]["rows"]


def put(tables: list[dict], name: str, row: int, **values: object) -> None:
    t = table(tables, name)
    fields = [c["name"] for c in t["columns"]]
    for key, value in values.items():
        if key not in fields:
            raise ValueError((name, key))
        rows(tables, name)[row][fields.index(key)] = value


def make(arm: str) -> dict:
    if arm not in PARENT_SHA:
        raise ValueError(arm)
    path = PARENT / f"native-input-{arm}.json"
    source = path.read_bytes()
    if hashlib.sha256(source).hexdigest() != PARENT_SHA[arm]:
        raise ValueError(f"accepted {arm} parent changed")
    doc = copy.deepcopy(json.loads(source))
    tables = doc["model"]["tables"]
    put(tables, "ProblemDescription", 0, PDESC=f"D14.var02+03 one swap then item age PM MONIT={'Y' if arm == 'monitored' else 'N'}")
    if len(rows(tables, "MaterielPM")) != 1 or len(rows(tables, "PMLocation")) != 2 or len(rows(tables, "PMReplacement")) != 1:
        raise ValueError("unexpected accepted D14.var01 PM topology")
    put(tables, "MaterielPM", 0, PMID="LRU-OP3", DESCR="Three item operation hours", PMINT=3.0)
    rows(tables, "MaterielPM").append([
        "SYS-SWAP", "One scheduled system swap after first mission", "TEACH-AIR-01",
        2.0, "OPHOURS", None, 0.0, 0.0, None, None, None, None, 1, None,
    ])
    put(tables, "PMLocation", 0, PMID="LRU-OP3")
    put(tables, "PMLocation", 1, PMID="LRU-OP3")
    rows(tables, "PMLocation").extend([
        ["SYS-SWAP", "TEACH-AIR-01", "BASE-01", 0.5, None, None, None, None, None],
        ["SYS-SWAP", "TEACH-LRU-01", "BASE-01", 1.0, None, None, None, None, None],
    ])
    put(tables, "PMReplacement", 0, PMID="LRU-OP3")
    rows(tables, "PMReplacement").append([
        "SYS-SWAP", "TEACH-AIR-01", "TEACH-LRU-01", 1.0, 1,
        None, None, "Y", "OPHOURS", None,
    ])
    return doc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    result = {}
    for arm in PARENT_SHA:
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"native-input-{arm}.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} differs")
        result[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"case_id": "D14", "variant_ids": ["D14.var02", "D14.var03"],
                      "parent_sha256": PARENT_SHA, "inputs": result}))


if __name__ == "__main__":
    main()
