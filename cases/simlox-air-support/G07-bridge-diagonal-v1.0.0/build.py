"""Build matched five-position bridge and ordinary-route control models."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "G04-three-branch-threshold-v1.0.0" / "one-input.json"
PARENT_SHA = "cfdf287c4de93638e8117c71ad3de1846da3c62c24254bf7d2a3f0f7c7c0c4d7"
SCHEMA_DONOR = ROOT / "G04-nested-series-parallel-v1.0.0" / "and-input.json"
SCHEMA_DONOR_SHA = "658cdfcc374a13754c0980888137dd05bb0b94c4dfad5386bab5292fc414dd15"
ARMS = ("bridge", "routes")


def table(doc: dict, name: str) -> dict:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(f"table shape {name}")
    return hits[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def add_tables(doc: dict) -> None:
    raw = SCHEMA_DONOR.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SCHEMA_DONOR_SHA:
        raise ValueError("accepted series schema donor changed")
    donor = json.loads(raw)
    for name in ("RBDSeries", "RBDSeriesStructure"):
        new = copy.deepcopy(table(donor, name))
        new["instances"][0]["rows"] = []
        doc["model"]["tables"].append(new)
    names = ["RBID", "DESCR", "ULBID", "LLBID", "BRBID", "URBID", "LRBID",
             "ULOPM", "LLOPM", "BROPM", "UROPM", "LROPM", "NOTE"]
    columns = [{"datatype": "string", "name": name, **({"key": True} if name == "RBID" else {})} for name in names]
    doc["model"]["tables"].append({"columns": columns, "instances": [{"instance_name": "", "rows": []}], "name": "RBDBridge"})


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted parent changed")
    doc = copy.deepcopy(json.loads(raw))
    if rows(doc, "RBDParallel") != [["G04-PARALLEL", "Active 1-of-3 fixed-mission threshold", 1, 3, 0.0, "N", None]]:
        raise ValueError("parent RBD changed")
    if [r[0] for r in rows(doc, "MaterielPosition")] != ["POS-A", "POS-B", "POS-C"]:
        raise ValueError("parent positions changed")
    structure = rows(doc, "MaterielStructure")
    if [r[:2] for r in structure] != [[f"POS-{p}", "TEACH-AIR-01"] for p in "ABC"] + [["TEACH-LRU-01", f"POS-{p}"] for p in "ABC"]:
        raise ValueError("parent physical structure changed")
    add_tables(doc)
    rows(doc, "ProblemDescription")[0][0] = f"G07 bridge diagonal versus ordinary routes: {arm}"
    rows(doc, "MaterielPosition").extend([["POS-D", "Upper right healthy position", None],
                                          ["POS-E", "Healthy bridge position", None]])
    structure[3:3] = [[f"POS-{p}", "TEACH-AIR-01", 1, 1.0, None, None] for p in "DE"]
    structure.extend([["TEACH-LRU-01", f"POS-{p}", 1, 1.0, None, None] for p in "DE"])
    rows(doc, "MaterielOperationalModes").extend([[f"POS-{p}", "G04-OPS", None, None, 1.0, None] for p in "DE"])
    modes = rows(doc, "MaterielOperationalModes")
    if arm == "bridge":
        modes[0][2] = "G07-BRIDGE"
        rows(doc, "RBDParallel").clear()
        rows(doc, "RBDParallelStructure").clear()
        rows(doc, "RBDBridge").append([
            "G07-BRIDGE", "Five-position bridge; diagonal salvages B/A failures",
            "POS-B", "POS-C", "POS-E", "POS-D", "POS-A",
            "G04-OPS", "G04-OPS", "G04-OPS", "G04-OPS", "G04-OPS", None,
        ])
    else:
        modes[0][2] = "G07-SYS-ROOT"
        rows(doc, "RBDParallel")[0][:] = ["G07-PAR-ROUTES", "Upper or lower two-block route", 1, 2, 0.0, "N", None]
        rows(doc, "RBDParallelStructure")[:] = [
            ["G07-PAR-ROUTES", "G07-UP", None, 1, 1, None],
            ["G07-PAR-ROUTES", "G07-LOW", None, 1, 1, None],
        ]
        rows(doc, "RBDSeries").extend([
            ["G07-SYS-ROOT", "Healthy POS-E in series with two ordinary routes", None],
            ["G07-UP", "Upper POS-B and POS-D", None],
            ["G07-LOW", "Lower POS-C and POS-A", None],
        ])
        rows(doc, "RBDSeriesStructure").extend([
            ["G07-SYS-ROOT", "POS-E", "G04-OPS", 1, None],
            ["G07-SYS-ROOT", "G07-PAR-ROUTES", None, 1, None],
            ["G07-UP", "POS-B", "G04-OPS", 1, None],
            ["G07-UP", "POS-D", "G04-OPS", 1, None],
            ["G07-LOW", "POS-C", "G04-OPS", 1, None],
            ["G07-LOW", "POS-A", "G04-OPS", 1, None],
        ])
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    hashes = {}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} input differs")
        hashes[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(hashes))


if __name__ == "__main__":
    main()
