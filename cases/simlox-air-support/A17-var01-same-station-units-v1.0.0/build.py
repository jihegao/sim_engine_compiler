"""Build the two-cell A17.var01 child source and full roundtrip hypothesis.

This reads accepted originals. It does not call SIMLOX or accepted checkers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PARENT = REPO / "cases/simlox-air-support/A17-multi-unit-group-v1.0.0"
PARENT_INPUT = PARENT / "native-input.json"
PARENT_EXPORT = PARENT / "runs/a17-v100-ssh-20260929-01/roundtrip-raw.json"
PARENT_INPUT_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"
PARENT_EXPORT_SHA = "819bbdd65799d20441191f41ca4a5d4df9aaf658466dd49dd952707d96943a42"
OLD_DESC = "A17 two explicit units at two bases serving one group mission; no transfer"
NEW_DESC = "A17.var01 two explicit units at BASE-01 serving one group mission; no transfer"


def load_pinned(path: Path, digest: str) -> dict:
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest, str(path)
    return json.loads(raw.decode("utf-8-sig"))


def table(model: dict, name: str) -> dict:
    rows = [item for item in model["model"]["tables"] if item["name"] == name]
    assert len(rows) == 1
    return rows[0]


def row(table_: dict, key_column: str, key: str) -> tuple[list[str], list]:
    columns = [c["name"] for c in table_["columns"]]
    assert key_column in columns
    found = [r for ins in table_["instances"] for r in ins["rows"] if r[columns.index(key_column)] == key]
    assert len(found) == 1
    return columns, found[0]


def count(model: dict) -> dict:
    tables = model["model"]["tables"]
    rows = [r for t in tables for i in t["instances"] for r in i["rows"]]
    return {"tables": len(tables), "rows": len(rows), "cells": sum(len(r) for r in rows)}


def change(model: dict) -> None:
    columns, unit = row(table(model, "Unit"), "UNID", "TEACH-UNIT-2")
    assert unit[columns.index("STID")] == "BASE-02"
    unit[columns.index("STID")] = "BASE-01"
    desc = table(model, "ProblemDescription")
    assert [c["name"] for c in desc["columns"]] == ["PDESC"]
    rows = [r for i in desc["instances"] for r in i["rows"]]
    assert rows == [[OLD_DESC]]
    rows[0][0] = NEW_DESC


def encoded(model: dict) -> bytes:
    return (json.dumps(model, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def write_absent(path: Path, raw: bytes) -> None:
    with path.open("xb") as f:
        f.write(raw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    authored = load_pinned(PARENT_INPUT, PARENT_INPUT_SHA)
    exported = load_pinned(PARENT_EXPORT, PARENT_EXPORT_SHA)
    assert count(authored) == {"tables": 33, "rows": 20, "cells": 203}
    assert count(exported) == {"tables": 33, "rows": 38, "cells": 387}
    change(authored)
    change(exported)
    diff = {
        "schema": "a17-var01-exact-two-cell-source-delta/v1",
        "parent_authored_sha256": PARENT_INPUT_SHA,
        "parent_export_sha256": PARENT_EXPORT_SHA,
        "changed_cells": [
            {"table": "Unit", "key": "TEACH-UNIT-2", "field": "STID", "before": "BASE-02", "after": "BASE-01", "role": "business"},
            {"table": "ProblemDescription", "field": "PDESC", "before": OLD_DESC, "after": NEW_DESC, "role": "editorial"},
        ],
        "authored_topology": count(authored),
        "export_topology": count(exported),
        "export_interpretation": "All 38 exported rows and 387 cells are a frozen hypothesis. Built-in default rows are not reinterpreted or relaxed after native observation.",
    }
    outputs = {
        "native-input.json": encoded(authored),
        "child-roundtrip-oracle.json": encoded(exported),
        "exact-diff.json": encoded(diff),
    }
    if args.write:
        for name, raw in outputs.items():
            write_absent(HERE / name, raw)
    else:
        for name, raw in outputs.items():
            path = HERE / name
            assert path.read_bytes() == raw, name
    print(json.dumps({"schema": "a17-var01-source-build/v1", "mode": "write" if args.write else "verify", "outputs": {k: {"bytes": len(v), "sha256": hashlib.sha256(v).hexdigest()} for k, v in outputs.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
