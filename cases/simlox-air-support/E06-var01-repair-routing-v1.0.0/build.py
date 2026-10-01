"""Freeze E06.var01 two-level cumulative direct-repair boundary inputs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E05-local-repair-reissue-v1.0.0" / "native-input.json"
PARENT_SHA = "ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca"
SUPPORT = HERE.parent / "E04-upstream-transport-fast-v1.0.0" / "native-input.json"
SUPPORT_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"
VARIANTS = {"local": 1.0, "upstream": 0.0}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"ambiguous {name} table")
    return matches[0]


def named_rows(doc: dict, name: str) -> list[dict]:
    t = table(doc, name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row, strict=True)) for row in t["instances"][0]["rows"]]


def append(t: dict, values: dict) -> None:
    names = [c["name"] for c in t["columns"]]
    if set(values) != set(names):
        raise ValueError(f"{t['name']} row schema differs")
    t["instances"][0]["rows"].append([values[name] for name in names])


def set_cell(t: dict, row: int, field: str, value: object) -> None:
    names = [c["name"] for c in t["columns"]]
    t["instances"][0]["rows"][row][names.index(field)] = value


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    parent_raw, support_raw = PARENT.read_bytes(), SUPPORT.read_bytes()
    if sha(parent_raw) != PARENT_SHA or sha(support_raw) != SUPPORT_SHA:
        raise ValueError("accepted parent/support fingerprint differs")
    doc, support = copy.deepcopy(json.loads(parent_raw)), json.loads(support_raw)
    set_cell(table(doc, "ProblemDescription"), 0, "PDESC", f"E06 cumulative direct-repair boundary {variant}")
    for name in ("Station", "StationStructure"):
        source_rows = named_rows(support, name)
        append(table(doc, name), source_rows[-1])
    base_repair = named_rows(doc, "ItemRepair")[0]
    set_cell(table(doc, "ItemRepair"), 0, "DIRPF", VARIANTS[variant])
    depot_repair = dict(base_repair, STID="DEPOT-01", DIRPF=1.0)
    append(table(doc, "ItemRepair"), depot_repair)
    depot_stock = dict(named_rows(doc, "StockAllocation")[0], STID="DEPOT-01", STSIZ=0)
    append(table(doc, "StockAllocation"), depot_stock)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"{variant}-input.json"
        if args.write:
            if path.exists():
                raise FileExistsError(f"refusing to overwrite {path}")
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {variant} input differs")
        print(json.dumps({"variant": variant, "parent_sha256": PARENT_SHA,
                          "support_sha256": SUPPORT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
