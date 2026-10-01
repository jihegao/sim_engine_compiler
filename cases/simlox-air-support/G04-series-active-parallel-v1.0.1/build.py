"""Freeze a G02-derived two-position explicit series versus active 1-of-2 RBD pair."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G02-var01-position-modes-v1.0.0" / "native-input.json"
PARENT_SHA = "5ef40eb302544e551282dd7dd3617a6ae160954f600dea605f26140ea551a19e"
ARMS = ("series", "parallel")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def row_set(doc: dict, name: str, column: str, value: object) -> None:
    t = table(doc, name)
    assert len(t["instances"][0]["rows"]) == 1, name
    columns = [c["name"] for c in t["columns"]]
    t["instances"][0]["rows"][0][columns.index(column)] = value


def new_table(name: str, columns: list[tuple[str, str, bool]], rows: list[list]) -> dict:
    cols = []
    for field, datatype, key in columns:
        col = {"datatype": datatype}
        if key:
            col["key"] = True
        col["name"] = field
        cols.append(col)
    assert all(len(row) == len(cols) for row in rows), name
    return {"columns": cols, "instances": [{"instance_name": "", "rows": rows}], "name": name}


def build(arm: str) -> dict:
    assert arm in ARMS
    parent_raw = PARENT.read_bytes()
    assert sha(parent_raw) == PARENT_SHA
    doc = copy.deepcopy(json.loads(parent_raw))
    row_set(doc, "ProblemDescription", "PDESC", f"G04 explicit {arm} two-position reliability block")
    row_set(doc, "Control", "RELOP", "RBD")
    root = "G04-SERIES" if arm == "series" else "G04-PARALLEL"
    common = [
        new_table("OperationalModes", [("OPMID", "string", True), ("DESCR", "string", False), ("NOTE", "string", False)],
                  [["G04-OPS", "Two-position mission RBD", None]]),
        new_table("MissionOperationalModes", [("MTID", "string", True), ("SID", "string", True),
                                                ("OPMID", "string", False), ("NOTE", "string", False)],
                  [["BASIC-MISSION", "TEACH-AIR-01", "G04-OPS", None]]),
        new_table("MaterielOperationalModes", [("MID", "string", True), ("OPMID", "string", True),
                                                 ("RBID", "string", False), ("NCID", "string", False),
                                                 ("USERT", "double", False), ("NOTE", "string", False)],
                  [["TEACH-AIR-01", "G04-OPS", root, None, 1.0, None],
                   ["POS-A", "G04-OPS", None, None, 1.0, None],
                   ["POS-B", "G04-OPS", None, None, 1.0, None]]),
    ]
    if arm == "series":
        common += [
            new_table("RBDSeries", [("RBID", "string", True), ("DESCR", "string", False),
                                     ("NOTE", "string", False)],
                      [[root, "Both installed positions required", None]]),
            new_table("RBDSeriesStructure", [("RBID", "string", True), ("SRBID", "string", True),
                                              ("OPMID", "string", False), ("QTYPB", "integer", False),
                                              ("NOTE", "string", False)],
                      [[root, position, "G04-OPS", 1, None] for position in ("POS-A", "POS-B")]),
        ]
    else:
        common += [
            new_table("RBDParallel", [("RBID", "string", True), ("DESCR", "string", False),
                                       ("NBREQ", "integer", False), ("NBOP", "integer", False),
                                       ("TSWOV", "double", False), ("ONLM", "string", False),
                                       ("NOTE", "string", False)],
                      [[root, "One of two active positions required", 1, 2, 0.0, "N", None]]),
            new_table("RBDParallelStructure", [("RBID", "string", True), ("SRBID", "string", True),
                                                ("OPMID", "string", False), ("QTYPB", "integer", False),
                                                ("PRIO", "integer", False), ("NOTE", "string", False)],
                      [[root, position, "G04-OPS", 1, 1, None] for position in ("POS-A", "POS-B")]),
        ]
    doc["model"]["tables"].extend(common)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    hashes = {}
    for arm in ARMS:
        output = HERE / f"{arm}-input.json"
        data = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.write:
            if output.exists():
                raise FileExistsError(output)
            output.write_bytes(data)
        elif output.read_bytes() != data:
            raise ValueError(f"frozen {arm} source differs")
        hashes[arm] = {"sha256": sha(data), "bytes": len(data)}
    print(json.dumps({"parent_sha256": PARENT_SHA, "arms": hashes}))


if __name__ == "__main__":
    main()
