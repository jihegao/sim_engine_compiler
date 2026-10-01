"""Build a predeclared 48-seed E06 three-level cumulative DIRPF panel."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E06-var01-repair-routing-v1.0.0" / "upstream-input.json"
PARENT_SHA = "7febb8c32afaa24fbf3bad94ba240e53236d8967c6fe6df51b4cfb7686828b0d"
SUPPORT = HERE.parent / "E04-upstream-transport-fast-v1.0.0" / "native-input.json"
SUPPORT_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"
SEEDS = tuple(range(1, 49))


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"ambiguous {name} table")
    return found[0]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def col(t: dict, name: str) -> int:
    return [c["name"] for c in t["columns"]].index(name)


def build(seed: int) -> dict:
    if seed not in SEEDS:
        raise ValueError(f"seed {seed} outside predeclared panel")
    parent_raw = PARENT.read_bytes()
    if sha(parent_raw) != PARENT_SHA or sha(SUPPORT.read_bytes()) != SUPPORT_SHA:
        raise ValueError("accepted parent/support fingerprint differs")
    doc = copy.deepcopy(json.loads(parent_raw))
    pd = table(doc, "ProblemDescription")
    rows(pd)[0][col(pd, "PDESC")] = "E06 three-level cumulative direct repair fractions 0.2/0.7/1"
    control = table(doc, "Control")
    rows(control)[0][col(control, "RSEED")] = str(seed)
    rows(control)[0][col(control, "SIMPE")] = 60.0
    rows(control)[0][col(control, "RCEND")] = 60.0
    collection = table(doc, "ResultCollection")
    if {row[col(collection, "RTYPE")] for row in rows(collection)} != {"MISSION", "SYSTEM"}:
        raise ValueError("expected E06 parent mission/system result collections")
    for row in rows(collection):
        if row[col(collection, "RCEND")] != 36.0:
            raise ValueError("expected E06 parent 36-hour result horizon")
        row[col(collection, "RCEND")] = 60.0
    station = table(doc, "Station")
    if len(rows(station)) != 2:
        raise ValueError("expected E06 two-level parent stations")
    top = copy.deepcopy(rows(station)[1])
    top[col(station, "STID")] = "WORKSHOP-01"
    top[col(station, "DESCR")] = "Teaching final repair workshop"
    rows(station).append(top)
    structure = table(doc, "StationStructure")
    if len(rows(structure)) != 1:
        raise ValueError("expected E06 base/depot support link")
    link = copy.deepcopy(rows(structure)[0])
    link[col(structure, "STID")] = "DEPOT-01"
    link[col(structure, "MSTID")] = "WORKSHOP-01"
    rows(structure).append(link)
    repair = table(doc, "ItemRepair")
    if len(rows(repair)) != 2:
        raise ValueError("expected E06 base/depot repair rows")
    rows(repair)[0][col(repair, "DIRPF")] = 0.2
    rows(repair)[1][col(repair, "DIRPF")] = 0.7
    top_repair = copy.deepcopy(rows(repair)[1])
    top_repair[col(repair, "STID")] = "WORKSHOP-01"
    top_repair[col(repair, "DIRPF")] = 1.0
    rows(repair).append(top_repair)
    stock = table(doc, "StockAllocation")
    if len(rows(stock)) != 2:
        raise ValueError("expected E06 base/depot stock rows")
    top_stock = copy.deepcopy(rows(stock)[1])
    top_stock[col(stock, "STID")] = "WORKSHOP-01"
    rows(stock).append(top_stock)
    return doc


def raw(seed: int) -> bytes:
    return (json.dumps(build(seed), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def manifest() -> dict:
    return {"schema": "simlox-e06-var01-three-level-seed-manifest/v1",
            "parent_sha256": PARENT_SHA, "support_sha256": SUPPORT_SHA,
            "seeds": {str(seed): sha(raw(seed)) for seed in SEEDS}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-initial", action="store_true")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sha-only", action="store_true")
    args = parser.parse_args()
    manifest_path, sample_path = HERE / "seed-manifest.json", HERE / "seed-01-input.json"
    if args.write_initial:
        if manifest_path.exists() or sample_path.exists():
            raise FileExistsError("initial frozen sources already exist")
        sample_path.write_bytes(raw(1))
        manifest_path.write_bytes((json.dumps(manifest(), indent=2) + "\n").encode("utf-8"))
    elif args.seed is not None:
        data = raw(args.seed)
        if args.output:
            if args.output.exists():
                raise FileExistsError(args.output)
            args.output.write_bytes(data)
        print(json.dumps({"seed": args.seed, "input_sha256": sha(data), "bytes": len(data)}))
        if args.sha_only and args.output:
            raise ValueError("--sha-only and --output are mutually exclusive")
        return
    else:
        if sample_path.read_bytes() != raw(1) or json.loads(manifest_path.read_bytes()) != manifest():
            raise ValueError("frozen sample/manifest differs from builder")
    print(json.dumps({"seeds": len(SEEDS), "sample_sha256": sha(sample_path.read_bytes()),
                      "manifest_sha256": sha(manifest_path.read_bytes()), "parent_sha256": PARENT_SHA}))


if __name__ == "__main__":
    main()
