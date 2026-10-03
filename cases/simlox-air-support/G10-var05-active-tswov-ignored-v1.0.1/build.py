"""Set positive TSWOV on the accepted ACTIVE G10.var01 link group."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var01-active-single-link-v1.0.0" / "native-input.json"
PARENT_SHA = "7e990242656119f9424fcf390ae8c46eb23e4751dbe6fb44bd80b3bb4cf307d1"
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
        raise ValueError("accepted G10.var01 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    columns, values = row(model, "ProblemDescription")
    values[columns.index("PDESC")] = "G10.var05 ACTIVE 1-of-2 TSWOV=1 ignored"
    columns, values = row(model, "Redundancy")
    if values[columns.index("ACPA")] != "ACTIVE" or values[columns.index("TSWOV")] != 0 or values[columns.index("NRL")] != 2 or values[columns.index("NRLRQ")] != 1:
        raise ValueError("unexpected accepted parent redundancy")
    values[columns.index("TSWOV")] = 1.0
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
