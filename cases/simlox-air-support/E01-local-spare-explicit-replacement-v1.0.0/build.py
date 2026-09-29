"""Derive explicit 10-minute removal and 20-minute fit from D01 LRU."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA256 = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected single {name} table/instance")
    return found[0]


def columns(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def update(t: dict, **values: object) -> None:
    names = columns(t)
    if len(rows(t)) != 1 or len(rows(t)[0]) != len(names) or set(values) - set(names):
        raise ValueError(f"unexpected {t['name']} rows/columns")
    for key, value in values.items():
        rows(t)[0][names.index(key)] = value


def add(t: dict, **values: object) -> None:
    names = columns(t)
    if set(values) - set(names):
        raise ValueError(f"unexpected {t['name']} columns")
    rows(t).append([values.get(name) for name in names])


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted D01 LRU parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    update(table(model, "ProblemDescription"), PDESC="E01 local spare: explicit 10-minute REMOVE and 20-minute REPLACE")
    update(table(model, "SystemRepair"), SURPTID="E01-SURP")
    tasks = table(model, "Tasks")
    breakdown = table(model, "TaskBreakDown")
    if rows(tasks) or rows(breakdown):
        raise ValueError("parent task tables are not empty")
    add(tasks, TID="E01-SURP", DESCR="Explicit local LRU system replacement")
    add(breakdown, TID="E01-SURP", SEQ=1, SUTID="<REMOVE>", DURN=1/6)
    add(breakdown, TID="E01-SURP", SEQ=2, SUTID="<REPLACE>", DURN=1/3)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(f"refusing to overwrite {OUTPUT}")
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen E01 input differs from generator")
    print(json.dumps({"case_id": "E01", "parent_sha256": PARENT_SHA256, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
