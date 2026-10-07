"""Construct and verify the single prospective OUT-TFDT child, read-only by default."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I03-var02-idle-crew-out-v1.0.2" / "native-input.json"
CONTRACT = HERE / "contract.json"
INPUT = HERE / "native-input.json"
DIFF = HERE / "exact-diff.json"
RUN_ID = "i03-var06-out-dt4-v100-ssh-20261008-01"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def typed_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def table(model: dict, name: str) -> dict:
    matches = [entry for entry in model["tables"] if entry["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1, name
    return matches[0]


def flatten(model: dict) -> dict[str, object]:
    result: dict[str, object] = {}
    for item in model["tables"]:
        for instance_index, instance in enumerate(item["instances"]):
            for row_index, row in enumerate(instance["rows"]):
                assert len(row) == len(item["columns"])
                for column, value in zip(item["columns"], row):
                    key = f"{item['name']}[{instance_index},{row_index}].{column['name']}"
                    assert key not in result, key
                    result[key] = value
    return result


def construct(parent: dict, contract: dict) -> dict:
    assert set(parent) == {"model"}
    assert parent["model"]["database_version"] == 20160627
    assert len(parent["model"]["tables"]) == 32
    assert contract["run_id"] == RUN_ID
    changes = contract["source_delta"]["allowed_changes_exactly"]
    assert len(changes) == 2
    child = copy.deepcopy(parent)
    description = table(child["model"], "ProblemDescription")
    assert description["instances"][0]["instance_name"] == ""
    assert [column["name"] for column in description["columns"]] == ["PDESC"]
    assert description["instances"][0]["rows"] == [[changes[0]["from"]]]
    description["instances"][0]["rows"][0][0] = changes[0]["to"]
    transfer = table(child["model"], "ResourceTransfer")
    assert transfer["instances"][0]["instance_name"] == ""
    assert [column["name"] for column in transfer["columns"]] == [
        "STFID", "STTID", "RID", "TFTIME", "TFQTY", "TFDT", "NOTE"]
    assert transfer["instances"][0]["rows"] == [["BASE-01", "<OUTSIDE>", "P-CREW", 6.0, 1, 0.0, None]]
    transfer["instances"][0]["rows"][0][5] = 4.0
    assert transfer["instances"][0]["rows"] == [contract["source_delta"]["child_transfer_row"]]
    return child


def verify(parent: dict, child: dict, contract: dict) -> dict:
    assert typed_equal(child, construct(parent, contract)), "source or metadata drift"
    before = flatten(parent["model"])
    after = flatten(child["model"])
    assert before.keys() == after.keys()
    changes = [{"cell": key, "before": before[key], "after": after[key]}
               for key in before if not typed_equal(before[key], after[key])]
    assert changes == [
        {"cell": "ProblemDescription[0,0].PDESC",
         "before": contract["source_delta"]["allowed_changes_exactly"][0]["from"],
         "after": contract["source_delta"]["allowed_changes_exactly"][0]["to"]},
        {"cell": "ResourceTransfer[0,0].TFDT", "before": 0.0, "after": 4.0},
    ], changes
    return {"schema": "i03-var06-out-dt4-source-diff/v1", "run_id": RUN_ID,
            "parent_sha256": sha(PARENT.read_bytes()), "flattened_cells": len(before),
            "table_objects": 32, "changes": changes,
            "all_other_source_and_metadata_type_exact": True}


def frozen_output(path: Path, data: bytes, write: bool) -> None:
    if path.exists():
        assert path.read_bytes() == data, f"frozen bytes differ: {path}"
    else:
        assert write, f"missing generated file: {path}; use explicit --write once"
        path.write_bytes(data)


def main() -> None:
    write = sys.argv[1:] == ["--write"]
    assert not sys.argv[1:] or write
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    expected = contract["source_delta"]["parent_input"]
    parent_bytes = PARENT.read_bytes()
    assert {"bytes": len(parent_bytes), "sha256": sha(parent_bytes)} == {
        "bytes": expected["bytes"], "sha256": expected["sha256"]}
    parent = json.loads(parent_bytes)
    child = construct(parent, contract)
    diff = verify(parent, child, contract)
    input_bytes = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    diff["child_sha256"] = sha(input_bytes)
    frozen_output(INPUT, input_bytes, write)
    frozen_output(DIFF, (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), write)
    print(json.dumps({"schema": "i03-var06-out-dt4-build/v1", "run_id": RUN_ID,
                      "input_sha256": sha(input_bytes), "input_bytes": len(input_bytes),
                      "changes": 2, "flattened_cells": diff["flattened_cells"]}, separators=(",", ":")))


if __name__ == "__main__":
    main()
