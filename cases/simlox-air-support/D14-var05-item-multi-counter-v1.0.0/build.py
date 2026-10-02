"""Derive monitored-item two-counter PM and single-counter control from accepted D14.var03."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D14-var03-post-reinstallation-pm-v1.0.0" / "native-input-monitored.json"
PARENT_SHA = "48a3eea3f6f9c32fd79bcc9f544845e2e60f5767987b37605563b5bf2738c9dd"
ARMS = ("ophours-only", "missions-plus-ophours")


def table(tables: list[dict], name: str) -> dict:
    found = [t for t in tables if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def put(tables: list[dict], name: str, row: int, **values: object) -> None:
    t = table(tables, name)
    fields = [c["name"] for c in t["columns"]]
    target = t["instances"][0]["rows"][row]
    for key, value in values.items():
        target[fields.index(key)] = value


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    source = PARENT.read_bytes()
    if hashlib.sha256(source).hexdigest() != PARENT_SHA:
        raise ValueError("accepted parent input changed")
    doc = copy.deepcopy(json.loads(source))
    tables = doc["model"]["tables"]
    if any(t["name"] == "MaterielPMInterval" for t in tables):
        raise ValueError("parent unexpectedly contains interval table")
    put(tables, "ProblemDescription", 0,
        PDESC=f"D14.var05 monitored item PM {'OPHOURS5 only' if arm == 'ophours-only' else 'OPHOURS5 plus MISSIONS2'}")
    pm = table(tables, "MaterielPM")["instances"][0]["rows"]
    if len(pm) != 2 or pm[0][0] != "LRU-OP3" or pm[1][0] != "SYS-SWAP":
        raise ValueError("unexpected accepted PM topology")
    put(tables, "MaterielPM", 0, PMID="LRU-MIX", DESCR="Monitored item 5 operation hours", PMINT=5.0)
    for i in range(2):
        put(tables, "PMLocation", i, PMID="LRU-MIX")
    put(tables, "PMReplacement", 0, PMID="LRU-MIX")
    if arm == "missions-plus-ophours":
        interval = {
            "columns": [
                {"datatype": "string", "key": True, "name": "PMID"},
                {"datatype": "string", "key": True, "name": "OPID"},
                {"datatype": "double", "name": "PMINT"},
                {"datatype": "string", "name": "NOTE"},
            ],
            "instances": [{"instance_name": "", "rows": [["LRU-MIX", "MISSIONS", 2.0, None]]}],
            "name": "MaterielPMInterval",
        }
        at = next(i for i, t in enumerate(tables) if t["name"] == "MaterielPM")
        tables.insert(at + 1, interval)
    return doc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    shas = {}
    for arm in ARMS:
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"native-input-{arm}.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {arm}")
        shas[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"case_id": "D14", "variant_id": "D14.var05",
                      "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
