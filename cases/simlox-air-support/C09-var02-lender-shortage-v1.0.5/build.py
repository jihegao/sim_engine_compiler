"""Build the single v1.0.5 child from the pinned ordinary input; no SIMLOX call."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "contract.json"
CHILD = HERE / "shortage-input.json"
DIFF = HERE / "exact-diff.json"


def seal(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def only_row(t: dict) -> tuple[list[str], list]:
    assert len(t["instances"]) == 1 and t["instances"][0]["instance_name"] == ""
    rows = t["instances"][0]["rows"]
    assert len(rows) == 1, t["name"]
    columns = [c["name"] for c in t["columns"]]
    assert len(rows[0]) == len(columns)
    return columns, rows[0]


def changes(parent: dict, child: dict) -> list[dict]:
    assert list(parent) == list(child) == ["model"]
    assert parent["model"]["database_version"] == child["model"]["database_version"]
    a, b = parent["model"]["tables"], child["model"]["tables"]
    assert len(a) == len(b) == 32
    assert [t["name"] for t in a] == [t["name"] for t in b]
    out = []
    for left, right in zip(a, b):
        assert left["columns"] == right["columns"]
        assert len(left["instances"]) == len(right["instances"])
        cols = [c["name"] for c in left["columns"]]
        for li, ri in zip(left["instances"], right["instances"]):
            assert li["instance_name"] == ri["instance_name"]
            assert len(li["rows"]) == len(ri["rows"])
            for rowno, (lr, rr) in enumerate(zip(li["rows"], ri["rows"]), 1):
                assert len(lr) == len(rr) == len(cols)
                for column, before, after in zip(cols, lr, rr):
                    if before != after or type(before) is not type(after):
                        out.append({"table": left["name"], "instance_name": li["instance_name"],
                                    "row": rowno, "column": column, "before": before, "after": after})
    return out


def build() -> tuple[bytes, bytes]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema"] == "simlox-c09-var02-lender-shortage-v105-child-contract/v1"
    source_pin = contract["planned_child"]["input_parent"]
    source = (HERE / source_pin["path"]).resolve()
    assert seal(source) == {"bytes": source_pin["bytes"], "sha256": source_pin["sha256"]}
    parent = json.loads(source.read_text(encoding="utf-8"))
    assert len(parent["model"]["tables"]) == 32
    assert sum(any(i["rows"] for i in t["instances"]) for t in parent["model"]["tables"]) == 25
    child = copy.deepcopy(parent)
    route = table(child, "ResourceRemoteSupport")
    cols, row = only_row(route)
    assert (row[cols.index("RID")], row[cols.index("STID")], row[cols.index("RSTID")]) == ("P-MECH", "BASE-01", "BASE-02")
    assert (row[cols.index("TFRS")], row[cols.index("TTRS")], row[cols.index("TTRSS")]) == (0.25, 0.5, 0.5)
    row[cols.index("TTRSS")] = 0.125
    cols, row = only_row(table(child, "ProblemDescription"))
    assert row[cols.index("PDESC")] == "ordinary TTRSS equals TTRS"
    row[cols.index("PDESC")] = "shortage TTRSS 0.125 child test"
    delta = changes(parent, child)
    declared = contract["planned_child"]["exact_changed_cells"]
    assert len(delta) == len(declared) == 2
    assert {(x["table"], x["column"], x["before"], x["after"]) for x in delta} == {
        (x["table"], x["column"], x["from"], x["to"]) for x in declared}
    doc = {"schema": "c09-var02-v105-exact-diff/v1", "parent_sha256": source_pin["sha256"],
           "table_count": 32, "row_containing_authored_tables": 25,
           "metadata_and_unchanged_cells_equal": True, "changed_cell_count": 2, "changed_cells": delta}
    return encoded(child), encoded(doc)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    args = p.parse_args()
    files = {CHILD: build()[0], DIFF: build()[1]}
    for path, raw in files.items():
        if args.write:
            assert not path.exists(), path
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw, path
    print(json.dumps({path.name: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                      for path, raw in files.items()}, sort_keys=True))


if __name__ == "__main__":
    main()
