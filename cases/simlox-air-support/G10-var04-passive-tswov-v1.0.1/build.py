"""Derive a 0.05-hour PASSIVE switchover from accepted G10.var02 zero delay."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var02-passive-zero-v1.0.0" / "native-input.json"
PARENT_SHA = "adb405c385f27778a35ad444aaa4e04e35eea9c20e2f206a06a36fb8c8c28ea5"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def row(model: dict, name: str) -> tuple[list[str], list]:
    tables = [t for t in model["tables"] if t["name"] == name]
    if len(tables) != 1 or len(tables[0]["instances"]) != 1 or len(tables[0]["instances"][0]["rows"]) != 1:
        raise ValueError(f"one {name} row required")
    table = tables[0]
    return [c["name"] for c in table["columns"]], table["instances"][0]["rows"][0]


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted G10.var02 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    cols, values = row(model, "ProblemDescription")
    values[cols.index("PDESC")] = "G10.var04 PASSIVE 1-of-2 TSWOV=0.05"
    cols, values = row(model, "Redundancy")
    if values[cols.index("ACPA")] != "PASSIVE" or values[cols.index("TSWOV")] != 0 or values[cols.index("NRL")] != 2 or values[cols.index("NRLRQ")] != 1:
        raise ValueError("unexpected accepted parent redundancy")
    values[cols.index("TSWOV")] = 0.05
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen input differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
