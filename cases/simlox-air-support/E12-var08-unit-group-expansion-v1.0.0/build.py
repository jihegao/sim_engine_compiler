"""Freeze group-owned operations over two explicit physical member units."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E12-var05-base02-zero-opening-stock-v1.0.0/native-input.json"
PARENT_SHA = "940592a6e27a84549e57656921ca111c1fc3c16e0bf233b90259866afb81071b"
A17 = HERE.parent / "A17-multi-unit-group-v1.0.0/native-input.json"
A17_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def rows(doc: dict, name: str) -> tuple[list[str], list[list]]:
    t = table(doc, name)
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(A17.read_bytes()).hexdigest() == A17_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    reference = json.loads(A17.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E12.var08 group-owned paired missions across two physical units"
    )
    un, units = rows(doc, "Unit")
    assert {r[un.index("UNID")]: r[un.index("STID")] for r in units} == {
        "TEACH-UNIT": "BASE-01", "TEACH-UNIT-2": "BASE-02"
    }
    dn, deployment = rows(doc, "SystemDeployment")
    assert {r[dn.index("USTID")]: r[dn.index("QTYPS")] for r in deployment} == {
        "TEACH-UNIT": 1, "TEACH-UNIT-2": 1
    }
    for name in ("UnitGroup", "UnitGroupMember"):
        assert not any(t["name"] == name for t in doc["model"]["tables"])
        doc["model"]["tables"].append(json.loads(json.dumps(table(reference, name))))
    _, groups = rows(doc, "UnitGroup")
    assert groups == [["TEACH-GROUP", "Two-unit teaching group", "N", None]]
    _, members = rows(doc, "UnitGroupMember")
    assert len(members) == 2 and {r[1] for r in members} == {"TEACH-UNIT", "TEACH-UNIT-2"}
    for member in members:
        member[2] = 1  # Equal search priority; no priority experiment here.
        assert member[3] == 0.0
    on, operations = rows(doc, "Operations")
    assert on == ["USTID", "PRID", "NOTE"] and operations == [
        ["TEACH-UNIT", "BASIC-SCHEDULE", None],
        ["TEACH-UNIT-2", "BASIC-SCHEDULE", None],
    ]
    operations[:] = [["TEACH-GROUP", "BASIC-SCHEDULE", None]]
    pn, profile = rows(doc, "OperationProfile")
    assert len(profile) == 3 and [r[pn.index("STIM")] for r in profile] == [8.0, 20.0, 32.0]
    for row in profile:
        assert row[pn.index("IQTY")] == 1 and row[pn.index("IPER")] == 0
        row[pn.index("IQTY")] = 2
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


if __name__ == "__main__":
    output = HERE / "native-input.json"
    raw = build()
    if sys.argv[1:] == ["--write"]:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    elif sys.argv[1:]:
        raise SystemExit("usage: build.py [--write]")
    else:
        assert output.read_bytes() == raw
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))
