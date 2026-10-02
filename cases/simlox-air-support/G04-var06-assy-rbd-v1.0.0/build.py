"""Build matched assembly-owned parallel and series RBD inputs."""
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
SERIES_REFERENCE = ROOT / "G04-series-active-parallel-v1.0.1" / "series-input.json"
SERIES_REFERENCE_SHA = "3adc1cf0d75dd9418e816d0e06bdc502af5d37d975beafbba8f781c94d2763e8"
ARMS = ("parallel", "series")


def table(doc: dict, name: str) -> dict:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(f"table shape: {name}")
    return hits[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def add_series_tables(doc: dict) -> None:
    raw = SERIES_REFERENCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SERIES_REFERENCE_SHA:
        raise ValueError("accepted series schema donor changed")
    reference = json.loads(raw)
    for name in ("RBDSeries", "RBDSeriesStructure"):
        if any(t["name"] == name for t in doc["model"]["tables"]):
            raise ValueError(f"parent unexpectedly has {name}")
        new = copy.deepcopy(table(reference, name))
        new["instances"][0]["rows"] = []
        doc["model"]["tables"].append(new)


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
    if [r[:2] for r in structure] != [
        ["POS-A", "TEACH-AIR-01"], ["POS-B", "TEACH-AIR-01"], ["POS-C", "TEACH-AIR-01"],
        ["TEACH-LRU-01", "POS-A"], ["TEACH-LRU-01", "POS-B"], ["TEACH-LRU-01", "POS-C"]
    ]:
        raise ValueError("parent physical structure changed")
    if rows(doc, "MaterielOperationalModes") != [
        ["TEACH-AIR-01", "G04-OPS", "G04-PARALLEL", None, 1.0, None],
        *[[f"POS-{p}", "G04-OPS", None, None, 1.0, None] for p in "ABC"],
    ]:
        raise ValueError("parent operational modes changed")
    add_series_tables(doc)
    rows(doc, "ProblemDescription")[0][0] = f"G04.var06 assembly-owned {arm} RBD"
    item = ["TEACH-ASSY-01", "Structural assembly around three teaching positions"] + [None] * (len(table(doc, "Item")["columns"]) - 2)
    item[5] = "ASSY"
    rows(doc, "Item").append(item)
    structure.insert(0, ["TEACH-ASSY-01", "TEACH-AIR-01", 1, 1.0, None, None])
    for row in structure[1:4]:
        row[1] = "TEACH-ASSY-01"
    modes = rows(doc, "MaterielOperationalModes")
    modes[0][2] = "G04-SYS-ROOT"
    modes.insert(1, ["TEACH-ASSY-01", "G04-OPS", "G04-ASSY-PARALLEL" if arm == "parallel" else "G04-ASSY-SERIES", None, 1.0, None])
    rows(doc, "RBDSeries").append(["G04-SYS-ROOT", "System contains the assembly block", None])
    rows(doc, "RBDSeriesStructure").append(["G04-SYS-ROOT", "TEACH-ASSY-01", "G04-OPS", 1, None])
    if arm == "parallel":
        rows(doc, "RBDParallel")[0][0] = "G04-ASSY-PARALLEL"
        rows(doc, "RBDParallel")[0][1] = "Assembly active 1-of-3 position threshold"
        for row in rows(doc, "RBDParallelStructure"):
            row[0] = "G04-ASSY-PARALLEL"
    else:
        rows(doc, "RBDParallel").clear()
        rows(doc, "RBDParallelStructure").clear()
        rows(doc, "RBDSeries").append(["G04-ASSY-SERIES", "All three assembly positions required", None])
        rows(doc, "RBDSeriesStructure").extend(
            [["G04-ASSY-SERIES", f"POS-{p}", "G04-OPS", 1, None] for p in "ABC"]
        )
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
