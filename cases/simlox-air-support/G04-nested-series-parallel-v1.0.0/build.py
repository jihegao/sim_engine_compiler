"""Build paired nested RBDs: A OR (B AND C) versus A AND (B OR C)."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G04-three-branch-threshold-v1.0.0" / "one-input.json"
PARENT_SHA256 = "cfdf287c4de93638e8117c71ad3de1846da3c62c24254bf7d2a3f0f7c7c0c4d7"
ARMS = ("or", "and")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [entry for entry in document["model"]["tables"] if entry["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def rows(document: dict, name: str) -> list[list]:
    return table(document, name)["instances"][0]["rows"]


def set_cell(document: dict, name: str, field: str, value: object) -> None:
    item = table(document, name)
    values = rows(document, name)
    assert len(values) == 1, name
    columns = [column["name"] for column in item["columns"]]
    values[0][columns.index(field)] = value


def new_table(name: str, columns: list[tuple[str, str, bool]], values: list[list]) -> dict:
    cols = []
    for field, datatype, key in columns:
        col = {"datatype": datatype}
        if key:
            col["key"] = True
        col["name"] = field
        cols.append(col)
    assert all(len(row) == len(cols) for row in values), name
    return {"columns": cols, "instances": [{"instance_name": "", "rows": values}], "name": name}


def build(arm: str) -> dict:
    assert arm in ARMS
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA256
    document = copy.deepcopy(json.loads(raw))
    set_cell(document, "ProblemDescription", "PDESC", f"G04 nested {arm.upper()} three-position RBD")
    failures = rows(document, "FailureMode")
    assert [row[0] for row in failures] == ["FM-POS-A", "FM-POS-B"]
    failures[0][0:3] = ["FM-POS-C", "Position C direct repair", "POS-C"]
    # POS-A is reliable in this bounded contrast. B and C have distinct stochastic modes.
    assert [row[2] for row in failures] == ["POS-C", "POS-B"]
    locations = rows(document, "CMLocation")
    assert [row[0] for row in locations] == ["FM-POS-A", "FM-POS-B"]
    locations[0][0] = "FM-POS-C"

    parallel = rows(document, "RBDParallel")
    assert len(parallel) == 1 and parallel[0][2:6] == [1, 3, 0.0, "N"]
    parallel_rows = rows(document, "RBDParallelStructure")
    assert [row[1] for row in parallel_rows] == ["POS-A", "POS-B", "POS-C"]

    if arm == "or":
        root, inner = "G04-ROOT-OR", "G04-SER-BC"
        parallel[0][0:4] = [root, "A OR (B AND C)", 1, 2]
        parallel_rows[:] = [[root, "POS-A", "G04-OPS", 1, 1, None],
                            [root, inner, None, 1, 1, None]]
        series_rows = [[inner, "POS-B", "G04-OPS", 1, None],
                       [inner, "POS-C", "G04-OPS", 1, None]]
        series_blocks = [[inner, "B AND C subblock", None]]
    else:
        root, inner = "G04-ROOT-AND", "G04-PAR-BC"
        parallel[0][0:4] = [inner, "B OR C subblock", 1, 2]
        parallel_rows[:] = [[inner, "POS-B", "G04-OPS", 1, 1, None],
                            [inner, "POS-C", "G04-OPS", 1, 1, None]]
        series_rows = [[root, "POS-A", "G04-OPS", 1, None],
                       [root, inner, None, 1, None]]
        series_blocks = [[root, "A AND (B OR C)", None]]
    modes = rows(document, "MaterielOperationalModes")
    assert [row[0] for row in modes] == ["TEACH-AIR-01", "POS-A", "POS-B", "POS-C"]
    modes[0][2] = root
    document["model"]["tables"].extend([
        new_table("RBDSeries", [("RBID", "string", True), ("DESCR", "string", False),
                                ("NOTE", "string", False)], series_blocks),
        new_table("RBDSeriesStructure", [("RBID", "string", True), ("SRBID", "string", True),
                                         ("OPMID", "string", False), ("QTYPB", "integer", False),
                                         ("NOTE", "string", False)], series_rows),
    ])
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    summary = {}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        data = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(data)
        elif path.read_bytes() != data:
            raise ValueError(f"frozen {arm} input differs")
        summary[arm] = {"sha256": sha(data), "bytes": len(data)}
    print(json.dumps({"parent_sha256": PARENT_SHA256, "arms": summary}))


if __name__ == "__main__":
    main()
