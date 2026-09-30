"""Build four A14 dependency contrasts from the accepted A05 continuous input."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-continuous-baseline-v1.0.1" / "native-continuous.json"
PARENT_SHA = "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea"
VARIANTS = ("control", "oneway", "mutual", "opposing")


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def row(tab: dict) -> list:
    rows = tab["instances"][0]["rows"]
    if len(rows) != 1:
        raise ValueError(f"expected one row in {tab['name']}")
    return rows[0]


def put(tab: dict, record: list, field: str, before: object, after: object) -> None:
    idx = [c["name"] for c in tab["columns"]].index(field)
    if record[idx] != before:
        raise ValueError(f"unexpected {tab['name']}.{field}: {record[idx]!r}")
    record[idx] = after


def dependence(dependent: str, precedent: str, mutual: bool) -> list:
    return ["TEACH-UNIT", dependent, 8.0, "TEACH-UNIT", precedent, 8.0,
            "CONTINUOUS", "Y" if mutual else "N", None, None]


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A05 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    put(table(doc, "ProblemDescription"), row(table(doc, "ProblemDescription")),
        "PDESC", "A05 continuous four-hour two-aircraft control", f"A14 paired continuous missions {variant}")
    mt = table(doc, "MissionType")
    first = row(mt)
    put(mt, first, "MTID", "BASIC-MISSION", "SUPPORT")
    put(mt, first, "DESCR", "Four-hour teaching mission", "Four-hour continuous support")
    put(mt, first, "NOS", 2, 1)
    put(mt, first, "MNOS", 2, 1)
    second = copy.deepcopy(first)
    put(mt, second, "MTID", "SUPPORT", "EXECUTE")
    put(mt, second, "DESCR", "Four-hour continuous support", "Four-hour continuous execution")
    mt["instances"][0]["rows"] = [first, second]
    op = table(doc, "OperationProfile")
    first = row(op)
    put(op, first, "SPRID", "BASIC-MISSION", "SUPPORT")
    second = copy.deepcopy(first)
    put(op, second, "SPRID", "SUPPORT", "EXECUTE")
    op["instances"][0]["rows"] = [first, second]
    if variant != "control":
        names = ["DUNID", "DMTID", "DSTIM", "PUNID", "PMTID", "PSTIM", "DTYPE", "MUTD", "DTTOL", "NOTE"]
        types = ["string", "string", "double", "string", "string", "double", "string", "string", "double", "string"]
        rows = [dependence("EXECUTE", "SUPPORT", variant == "mutual")]
        if variant == "opposing":
            rows.append(dependence("SUPPORT", "EXECUTE", False))
        doc["model"]["tables"].append({
            "name": "MissionDependence",
            "columns": [{"name": n, "datatype": typ, **({"key": True} if i < 6 else {})}
                        for i, (n, typ) in enumerate(zip(names, types))],
            "instances": [{"instance_name": "", "rows": rows}],
        })
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
