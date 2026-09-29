"""Derive a fixed-seed system failure probe from the accepted A05 continuous control."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-continuous-baseline-v1.0.1" / "native-continuous.json"
PARENT_SHA = "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea"
REPAIR_PARENT = HERE.parent / "D01-system-direct-repair-v1.0.0" / "native-input.json"
REPAIR_PARENT_SHA = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"
OUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return found[0]


def set_one(doc: dict, name: str, field: str, before: object, after: object) -> None:
    t = table(doc, name)
    names = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or field not in names or rows[0][names.index(field)] != before:
        raise ValueError(f"unexpected {name}.{field}")
    rows[0][names.index(field)] = after


def build() -> dict:
    parent_raw = PARENT.read_bytes()
    repair_raw = REPAIR_PARENT.read_bytes()
    if sha(parent_raw) != PARENT_SHA or sha(repair_raw) != REPAIR_PARENT_SHA:
        raise ValueError("accepted parent fingerprint differs")
    doc = copy.deepcopy(json.loads(parent_raw))
    repair = json.loads(repair_raw)
    set_one(doc, "ProblemDescription", "PDESC",
            "A05 continuous four-hour two-aircraft control",
            "A05 continuous four-hour two-aircraft seeded system-loss probe")
    set_one(doc, "System", "FRT", 0, 300000)
    own_repair = table(doc, "SystemRepair")
    source_repair = table(repair, "SystemRepair")
    if own_repair["instances"][0]["rows"] or len(source_repair["instances"][0]["rows"]) != 1:
        raise ValueError("unexpected repair rows")
    if own_repair["columns"] != source_repair["columns"]:
        raise ValueError("repair table schema differs")
    own_repair["instances"][0]["rows"] = copy.deepcopy(source_repair["instances"][0]["rows"])
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(json.dumps({"native_input_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
