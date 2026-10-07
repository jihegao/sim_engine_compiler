"""Deterministic, read-only-by-default construction of the sole v102 child."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I03-var01-crew-out-in-v1.0.0" / "out-input.json"
PARENT_SHA = "7f07e30d95f88228d9551cda93c0cf53e196f7473258096a86d2fa06949c262e"
CONTRACT_SHA = "1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29"
DESCRIPTION = "I03.var02 idle crew OUT h6 versus accepted busy OUT h7.75"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1, name
    return matches[0]


def construct(parent: dict) -> dict:
    assert set(parent) == {"model"}
    assert parent["model"]["database_version"] == 20160627
    assert len(parent["model"]["tables"]) == 32
    child = copy.deepcopy(parent)
    pd = unique_table(child["model"], "ProblemDescription")
    assert [c["name"] for c in pd["columns"]] == ["PDESC"]
    assert pd["instances"][0]["instance_name"] == ""
    assert pd["instances"][0]["rows"] == [["I03.var01 out: second formation at h20; crew transfer comparison"]]
    pd["instances"][0]["rows"][0][0] = DESCRIPTION
    transfer = unique_table(child["model"], "ResourceTransfer")
    names = [c["name"] for c in transfer["columns"]]
    assert names == ["STFID", "STTID", "RID", "TFTIME", "TFQTY", "TFDT", "NOTE"]
    rows = transfer["instances"][0]["rows"]
    assert rows == [["BASE-01", "<OUTSIDE>", "P-CREW", 7.75, 1, 0.0, None]]
    rows[0][3] = 6.0
    return child


def typed_equal(a: object, b: object) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def all_cells(model: dict) -> dict[str, object]:
    cells = {}
    for table in model["tables"]:
        for i, inst in enumerate(table["instances"]):
            for j, row in enumerate(inst["rows"]):
                assert len(row) == len(table["columns"])
                for column, value in zip(table["columns"], row):
                    cells[f"{table['name']}[{i},{j}].{column['name']}"] = value
    return cells


def verify(parent: dict, child: dict) -> dict:
    assert typed_equal(child, construct(parent)), "child has additional source/metadata drift"
    a, b = all_cells(parent["model"]), all_cells(child["model"])
    assert a.keys() == b.keys()
    changes = [{"cell": key, "before": a[key], "after": b[key]} for key in a if not typed_equal(a[key], b[key])]
    assert changes == [
        {"cell": "ProblemDescription[0,0].PDESC", "before": "I03.var01 out: second formation at h20; crew transfer comparison", "after": DESCRIPTION},
        {"cell": "ResourceTransfer[0,0].TFTIME", "before": 7.75, "after": 6.0},
    ], changes
    return {"schema": "i03-var02-v102-source-diff/v1", "parent_sha256": PARENT_SHA,
            "flattened_cells": len(a), "changes": changes, "table_objects": 32,
            "all_other_parsed_values_and_metadata_equal": True}


def frozen_write(path: Path, data: bytes, write: bool) -> None:
    if path.exists():
        assert path.read_bytes() == data, f"frozen output differs: {path}"
    else:
        assert write, f"missing frozen output: {path}"
        path.write_bytes(data)


def main() -> None:
    write = sys.argv[1:] == ["--write"]
    assert not sys.argv[1:] or write
    assert sha((HERE / "contract.json").read_bytes()) == CONTRACT_SHA
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    parent = json.loads(raw)
    child = construct(parent)
    diff = verify(parent, child)
    output = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    diff["child_sha256"] = sha(output)
    frozen_write(HERE / "native-input.json", output, write)
    frozen_write(HERE / "exact-diff.json", (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), write)
    print(json.dumps({"schema": "i03-var02-v102-build-result/v1", "input_sha256": sha(output),
                      "input_bytes": len(output), "changes": 2, "flattened_cells": diff["flattened_cells"]}, separators=(",", ":")))


if __name__ == "__main__":
    main()
