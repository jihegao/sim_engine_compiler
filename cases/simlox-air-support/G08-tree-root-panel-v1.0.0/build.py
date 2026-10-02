"""Build two matched three-leaf trees with A or B as the common root."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G04-three-branch-threshold-v1.0.0" / "two-input.json"
PARENT_SHA = "38f85af4c121668eee3d31b07bb435b74571c5be6d63ddccff034549609ec319"
ARMS = ("roota", "rootb")
RBID = "G08-TREE"


def table(doc: dict, name: str) -> dict:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def column(source: dict, old: str, new: str | None = None, *, key: bool | None = None) -> dict:
    result = copy.deepcopy(next(c for c in source["columns"] if c["name"] == old))
    result["name"] = new or old
    if key is not None:
        if key:
            result["key"] = True
        else:
            result.pop("key", None)
    return result


def new_table(name: str, columns: list[dict], body: list[list]) -> dict:
    return {"name": name, "columns": columns, "instances": [{"instance_name": "", "rows": body}]}


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G04 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    parallel, parallel_structure = table(doc, "RBDParallel"), table(doc, "RBDParallelStructure")
    if rows(doc, "RBDParallel") != [["G04-PARALLEL", "Active 2-of-3 fixed-mission threshold", 2, 3, 0.0, "N", None]]:
        raise ValueError("accepted parallel row changed")
    if [r[1] for r in rows(doc, "RBDParallelStructure")] != ["POS-A", "POS-B", "POS-C"]:
        raise ValueError("accepted parallel links changed")
    positions = rows(doc, "MaterielPosition")
    if [r[0] for r in positions] != ["POS-A", "POS-B", "POS-C"]:
        raise ValueError("accepted positions changed")
    structure, modes = rows(doc, "MaterielStructure"), rows(doc, "MaterielOperationalModes")
    if len(structure) != 6 or len(modes) != 4:
        raise ValueError("accepted installation changed")
    if [r[2] for r in rows(doc, "FailureMode")] != ["POS-A", "POS-B"]:
        raise ValueError("accepted failure modes changed")
    root = "POS-A" if arm == "roota" else "POS-B"
    leaves = [f"POS-{letter}" for letter in "ABCD" if f"POS-{letter}" != root]
    rows(doc, "ProblemDescription")[0][0] = f"G08 three-leaf tree NBREQ2; common root {root}"
    positions.append(["POS-D", "Fourth healthy LRU position", None])
    structure.insert(3, ["POS-D", "TEACH-AIR-01", 1, 1.0, None, None])
    structure.append(["TEACH-LRU-01", "POS-D", 1, 1.0, None, None])
    modes.append(["POS-D", "G04-OPS", None, None, 1.0, None])
    modes[0][2] = RBID
    tree = new_table("RBDTree", [column(parallel, "RBID"), column(parallel, "DESCR"),
                                   column(parallel, "NBREQ"), column(parallel, "NOTE")],
                     [[RBID, f"Three leaf paths through common root {root}", 2, None]])
    structure_columns = [column(parallel_structure, "RBID"),
                         column(parallel_structure, "SRBID", "MRBID", key=True),
                         column(parallel_structure, "SRBID", key=True),
                         column(parallel_structure, "OPMID", "MBOPM"),
                         column(parallel_structure, "OPMID", "SBOPM"),
                         column(parallel_structure, "QTYPB", "QTYPM"),
                         column(parallel_structure, "NOTE")]
    tree_structure = new_table("RBDTreeStructure", structure_columns,
                               [[RBID, root, leaf, "G04-OPS", "G04-OPS", 1, None] for leaf in leaves])
    doc["model"]["tables"] = [t for t in doc["model"]["tables"]
                               if t["name"] not in {"RBDParallel", "RBDParallelStructure"}] + [tree, tree_structure]
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} differs")
        result[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
