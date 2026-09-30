"""Build the paired A13 START-dependency probe from the accepted A02 model."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def set_field(tab: dict, row: list, field: str, value: object) -> None:
    row[[c["name"] for c in tab["columns"]].index(field)] = value


def build(dependent: bool) -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A02 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    t = table(doc, "ProblemDescription")
    t["instances"][0]["rows"][0][0] = (
        "A13 paired two-aircraft START dependence; predecessor returns at 12"
        if dependent else "A13 two-aircraft no-dependence control"
    )
    t = table(doc, "Control")
    row = t["instances"][0]["rows"][0]
    set_field(t, row, "SIMPE", 24.0)
    set_field(t, row, "RCEND", 24.0)
    t = table(doc, "SystemDeployment")
    set_field(t, t["instances"][0]["rows"][0], "QTYPS", 2)
    t = table(doc, "Unit")
    set_field(t, t["instances"][0]["rows"][0], "DESCR", "Two-aircraft dependency unit")
    t = table(doc, "MissionType")
    first = t["instances"][0]["rows"][0]
    set_field(t, first, "MTID", "RECON")
    set_field(t, first, "DESCR", "Four-hour fixed predecessor")
    set_field(t, first, "DURN", 4.0)
    set_field(t, first, "MSUCPT", 0.25)
    second = copy.deepcopy(first)
    set_field(t, second, "MTID", "FOLLOW")
    set_field(t, second, "DESCR", "Two-hour fixed dependent")
    set_field(t, second, "DURN", 2.0)
    set_field(t, second, "MSUCPT", 1.0)
    t["instances"][0]["rows"] = [first, second]
    t = table(doc, "OperationProfile")
    first = t["instances"][0]["rows"][0]
    set_field(t, first, "SPRID", "RECON")
    set_field(t, first, "STIM", 8.0)
    set_field(t, first, "DTIM", 4.0)
    second = copy.deepcopy(first)
    set_field(t, second, "SPRID", "FOLLOW")
    set_field(t, second, "STIM", 10.0)
    t["instances"][0]["rows"] = [first, second]
    t = table(doc, "ResultCollection")
    for row in t["instances"][0]["rows"]:
        set_field(t, row, "RCEND", 24.0)
    if dependent:
        names = ["DUNID", "DMTID", "DSTIM", "PUNID", "PMTID", "PSTIM", "DTYPE", "MUTD", "DTTOL", "NOTE"]
        types = ["string", "string", "double", "string", "string", "double", "string", "string", "double", "string"]
        doc["model"]["tables"].append({
            "name": "MissionDependence",
            "columns": [{"name": n, "datatype": ty, **({"key": True} if i < 6 else {})} for i, (n, ty) in enumerate(zip(names, types))],
            "instances": [{"instance_name": "", "rows": [["TEACH-UNIT", "FOLLOW", 10.0, "TEACH-UNIT", "RECON", 8.0, "START", None, None, None]]}],
        })
    return doc


def main() -> None:
    for label, dep in (("dependent", True), ("control", False)):
        raw = (json.dumps(build(dep), ensure_ascii=False, indent=2) + "\n").encode()
        target = HERE / f"{label}-input.json"
        if target.exists():
            if target.read_bytes() != raw:
                raise ValueError(f"frozen {label} input differs")
        else:
            target.write_bytes(raw)
        print(label, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
