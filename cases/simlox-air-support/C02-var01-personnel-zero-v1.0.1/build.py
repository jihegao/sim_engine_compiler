"""Deterministically construct the sole C02.var01 child from sealed C02 input."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C02-joint-resources-v1.0.2" / "inputs" / "single-both.json"
PARENT_SHA = "0bf522cd4c4387f110ceae34d7c1e4b4c8b40c8e495e7e27920a48e47bb5f937"
CONTRACT_SHA = "e8cce2aeae398f8e725365ab7472b0a7a92b9681cc63299e581d642e76ef9d12"
PDESC = "C02.var01 one-step joint request: P-CREW capacity zero, E-GSE capacity one; fixed-seed prospective child"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def instance(doc: dict, name: str) -> tuple[dict, dict]:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1, name
    return matches[0], matches[0]["instances"][0]


def build(parent: dict) -> dict:
    child = copy.deepcopy(parent)
    desc_table, desc = instance(child, "ProblemDescription")
    assert len(desc["rows"]) == 1
    dcol = [c["name"] for c in desc_table["columns"]].index("PDESC")
    assert desc["rows"][0][dcol] == "A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence"
    desc["rows"][0][dcol] = PDESC
    table, alloc = instance(child, "ResourceAllocation")
    columns = [c["name"] for c in table["columns"]]
    key = [columns.index(x) for x in ("POINT", "RID", "STID")]
    qty = columns.index("RQTY")
    rows = [r for r in alloc["rows"] if tuple(r[i] for i in key) == ("AIR_BASIC", "P-CREW", "BASE-01")]
    assert len(rows) == 1 and rows[0][qty] == 1
    rows[0][qty] = 0
    return child


def flattened(doc: dict) -> dict[str, object]:
    result = {}
    for table in doc["model"]["tables"]:
        for i, ins in enumerate(table["instances"]):
            for j, row in enumerate(ins["rows"]):
                assert len(row) == len(table["columns"])
                for col, value in zip(table["columns"], row):
                    result[f"{table['name']}[{i},{j}].{col['name']}"] = value
    return result


def verify_isolation(parent: dict, child: dict) -> tuple[int, list[dict]]:
    assert len(parent["model"]["tables"]) == len(child["model"]["tables"]) == 31
    assert child == build(parent), "table, instance, metadata, or value drift"
    a, b = flattened(parent), flattened(child)
    assert a.keys() == b.keys()
    changes = [{"cell": k, "before": a[k], "after": b[k]} for k in a if a[k] != b[k]]
    assert changes == [
        {"cell": "ProblemDescription[0,0].PDESC", "before": "A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence", "after": PDESC},
        {"cell": "ResourceAllocation[0,0].RQTY", "before": 1, "after": 0},
    ], changes
    return len(a), changes


def frozen_write(path: Path, data: bytes) -> None:
    if path.exists():
        assert path.read_bytes() == data, f"frozen output differs: {path}"
    else:
        assert "--write" in sys.argv, f"missing frozen output: {path}"
        path.write_bytes(data)


def main() -> None:
    assert digest((HERE / "contract.json").read_bytes()) == CONTRACT_SHA
    raw = PARENT.read_bytes()
    assert digest(raw) == PARENT_SHA
    parent = json.loads(raw)
    child = build(parent)
    cells, changes = verify_isolation(parent, child)
    data = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    frozen_write(HERE / "native-input.json", data)
    record = {"schema": "c02-var01-v101-exact-diff/v1", "parent_sha256": PARENT_SHA,
              "child_sha256": digest(data), "flattened_cells": cells, "changes": changes,
              "table_objects": 31, "all_other_parsed_values_and_metadata_equal": True}
    frozen_write(HERE / "exact-diff.json", (json.dumps(record, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"input_sha256": digest(data), "input_bytes": len(data), "changes": len(changes), "flattened_cells": cells}))


if __name__ == "__main__":
    main()
