"""Isolate the Fixed role requirement of A13 START dependence."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A13-start-dependence-v1.0.0" / "dependent-input.json"
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
VARIANTS = ("fixed-fixed", "prec-cont-control", "prec-cont-dependency",
            "dep-cont-control", "dep-cont-dependency")


def table(doc: dict, name: str) -> dict:
    found = [tab for tab in doc["model"]["tables"] if tab["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def set_cell(tab: dict, row: list, field: str, before: object, after: object) -> None:
    index = [column["name"] for column in tab["columns"]].index(field)
    if row[index] != before:
        raise ValueError(f"unexpected {tab['name']}.{field} value {row[index]!r}")
    row[index] = after


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A13 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    pd = table(doc, "ProblemDescription")
    label = f"A13.var06 START Fixed role {variant}"
    set_cell(pd, pd["instances"][0]["rows"][0], "PDESC",
             "A13 paired two-aircraft START dependence; predecessor returns at 12", label)
    if variant.startswith("prec-cont") or variant.startswith("dep-cont"):
        mission = "RECON" if variant.startswith("prec-cont") else "FOLLOW"
        tab = table(doc, "MissionType")
        columns = [column["name"] for column in tab["columns"]]
        targets = [row for row in tab["instances"][0]["rows"]
                   if row[columns.index("MTID")] == mission]
        if len(targets) != 1:
            raise ValueError(f"unexpected {mission} row count")
        set_cell(tab, targets[0], "MPAT", None, "CONTINUOUS")
        # Accepted A05 proves that CONTINUOUS cannot retain fixed-mission
        # travel fractions: native converter error #335. Clear only these
        # two required fields in both matched dependency/control inputs.
        set_cell(tab, targets[0], "TFOUT", 0.25, None)
        set_cell(tab, targets[0], "TFRET", 0.25, None)
    if variant.endswith("control"):
        doc["model"]["tables"] = [tab for tab in doc["model"]["tables"]
                                   if tab["name"] != "MissionDependence"]
    return doc


def main() -> None:
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{variant}-input.json"
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError(f"frozen {variant} input differs")
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
