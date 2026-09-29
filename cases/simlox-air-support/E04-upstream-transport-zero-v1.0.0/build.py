"""Derive a zero-transit-time upstream support variant from accepted E04 FAST."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E04-upstream-transport-fast-v1.0.0" / "native-input.json"
PARENT_SHA256 = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table/instance")
    return found[0]


def update_one(t: dict, **values: object) -> None:
    names = [c["name"] for c in t["columns"]]
    data = t["instances"][0]["rows"]
    if len(data) != 1 or len(data[0]) != len(names) or set(values) - set(names):
        raise ValueError(f"unexpected {t['name']} shape")
    for name, value in values.items():
        data[0][names.index(name)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted E04 FAST parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    update_one(table(model, "ProblemDescription"), PDESC="E04.var03 zero-time upstream and return transport under FAST ordering")
    update_one(table(model, "StationStructure"), TFRMS=0.0, TTOMS=0.0)
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
        raise ValueError("frozen E04 zero-time input differs from generator")
    print(json.dumps({"case_id": "E04.var03", "parent_sha256": PARENT_SHA256, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
