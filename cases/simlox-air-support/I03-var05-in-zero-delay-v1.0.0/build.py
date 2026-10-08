"""Deterministic I03.var05 source construction. Default invocation is read-only."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I03-var01-crew-out-in-v1.0.0" / "out_in-input.json"
PARENT_SHA = "81107e9713b9e21178de4d877a146963b693af7193d0663aa9e4d32871b44e84"
DESIGN_SHA = "95ba77bcac344e023f140a39b4f88b4f94160d07c2a4e94563ff84de592f7331"


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def typed_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def source_cells(model: dict) -> dict[str, object]:
    result = {}
    for t in model["tables"]:
        assert set(t) == {"name", "columns", "instances"}
        assert len(t["instances"]) == 1
        assert len({c["name"] for c in t["columns"]}) == len(t["columns"])
        for row_number, row in enumerate(t["instances"][0]["rows"]):
            assert len(row) == len(t["columns"])
            for column, value in zip(t["columns"], row):
                key = f"{t['name']}[0,{row_number}].{column['name']}"
                assert key not in result
                result[key] = value
    return result


def construct(parent: dict, design: dict) -> dict:
    source = design["source_delta"]
    assert set(parent) == {"model"} and set(parent["model"]) == {"database_version", "tables"}
    assert parent["model"]["database_version"] == source["parent_model_database_version"]
    assert [t["name"] for t in parent["model"]["tables"]] == source["table_names_ordered"]
    assert len(source_cells(parent["model"])) == source["full_cell_count_including_null_placeholders"] == 227
    assert sum(len(t["instances"][0]["rows"]) for t in parent["model"]["tables"]) == 25
    assert [t["name"] for t in parent["model"]["tables"] if not t["instances"][0]["rows"]] == source["zero_row_tables"]
    result = copy.deepcopy(parent)
    problem = table(result["model"], "ProblemDescription")
    assert [c["name"] for c in problem["columns"]] == ["PDESC"]
    assert problem["instances"][0]["rows"] == [[source["parent_description"]]]
    problem["instances"][0]["rows"][0][0] = source["child_description_predeclared"]
    transfer = table(result["model"], "ResourceTransfer")
    assert [c["name"] for c in transfer["columns"]] == ["STFID", "STTID", "RID", "TFTIME", "TFQTY", "TFDT", "NOTE"]
    assert transfer["instances"][0]["rows"] == [source["unchanged_OUT_row"], source["parent_IN_row"]]
    transfer["instances"][0]["rows"][1][5] = 0.0
    assert typed_equal(transfer["instances"][0]["rows"][1], source["child_IN_row_expected"])
    return result


def exact_diff(parent: dict, child: dict, design: dict) -> dict:
    assert typed_equal(child, construct(parent, design)), "source or metadata drift"
    before, after = source_cells(parent["model"]), source_cells(child["model"])
    assert before.keys() == after.keys() and len(before) == 227
    changes = [{"cell": key, "before": before[key], "after": after[key]}
               for key in before if not typed_equal(before[key], after[key])]
    source = design["source_delta"]
    assert changes == [
        {"cell": "ProblemDescription[0,0].PDESC", "before": source["parent_description"],
         "after": source["child_description_predeclared"]},
        {"cell": "ResourceTransfer[0,1].TFDT", "before": 0.5, "after": 0.0},
    ], changes
    return {"schema": "i03-var05-exact-source-diff/v1", "parent": PARENT_SHA,
            "table_count": 32, "authored_rows": 25, "authored_cells": 227,
            "changes": changes, "all_other_cells_and_metadata_type_exact": True}


def output(path: Path, body: bytes, write: bool) -> dict:
    if path.exists():
        assert path.read_bytes() == body, ("frozen output changed", str(path))
    else:
        assert write, ("output missing", str(path))
        path.write_bytes(body)
    return pin(body)


def main() -> None:
    write = sys.argv[1:] == ["--write"]
    assert not sys.argv[1:] or write
    design_bytes = (HERE / "contract.json").read_bytes()
    assert pin(design_bytes)["sha256"] == DESIGN_SHA
    design = json.loads(design_bytes)
    raw = PARENT.read_bytes()
    assert pin(raw)["sha256"] == PARENT_SHA
    parent = json.loads(raw)
    child = construct(parent, design)
    delta = exact_diff(parent, child, design)
    child_bytes = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    delta["child_input"] = pin(child_bytes)
    delta_bytes = (json.dumps(delta, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    result = {"schema": "i03-var05-build-result/v1", "input": output(HERE / "native-input.json", child_bytes, write),
              "diff": output(HERE / "exact-diff.json", delta_bytes, write), "native_calls": 0}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
