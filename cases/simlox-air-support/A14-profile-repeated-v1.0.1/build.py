"""Build corrected repeated A14 profile and explicit/profile contrasts."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A14-continuous-end-abort-v1.0.1" / "control-input.json"
PARENT_SHA = "f81445ad2daba09321e7a55ad67c5355b7e4a14ec3a58bbf10fbfcd18b343376"
DONOR = HERE.parent / "A09-hierarchical-operation-profile-v1.0.1" / "native-nested.json"
DONOR_SHA = "e795c5fcf563f8e42ab9e9cb161a925bec3b06157cbbecde7901e99bfec91d85"
VARIANTS = ("control", "explicit", "profile")


def load(path: Path, digest: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"source fingerprint differs: {path}")
    return json.loads(raw)


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def rows(tab: dict) -> list[list]:
    return tab["instances"][0]["rows"]


def put(tab: dict, record: list, field: str, before: object, after: object) -> None:
    idx = [c["name"] for c in tab["columns"]].index(field)
    if record[idx] != before:
        raise ValueError(f"unexpected {tab['name']}.{field}: {record[idx]!r}")
    record[idx] = after


def add_table(doc: dict, name: str, names: list[str], types: list[str], key_count: int, records: list[list]) -> None:
    if len(names) != len(types) or any(len(r) != len(names) for r in records):
        raise ValueError(f"invalid {name} shape")
    doc["model"]["tables"].append({
        "name": name,
        "columns": [{"name": n, "datatype": typ, **({"key": True} if i < key_count else {})}
                    for i, (n, typ) in enumerate(zip(names, types))],
        "instances": [{"instance_name": "", "rows": records}],
    })


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    doc = copy.deepcopy(load(PARENT, PARENT_SHA))
    donor = load(DONOR, DONOR_SHA)
    put(table(doc, "ProblemDescription"), rows(table(doc, "ProblemDescription"))[0],
        "PDESC", "A14 paired continuous missions control", f"A14 repeated dependency v101 {variant}")
    ct = table(doc, "Control")
    for field in ("SIMPE", "RCEND"):
        put(ct, rows(ct)[0], field, 16.0, 40.0)
    rc = table(doc, "ResultCollection")
    if len(rows(rc)) != 2:
        raise ValueError("A14 parent result collection rows differ")
    for record in rows(rc):
        put(rc, record, "RCEND", 16.0, 40.0)
    op = table(doc, "OperationProfile")
    donor_op = table(donor, "OperationProfile")
    if op["columns"] != donor_op["columns"]:
        raise ValueError("A09 OperationProfile schema differs")
    root = copy.deepcopy(rows(donor_op)[0])
    if root[:7] != ["BASIC-SCHEDULE", "A09-DAILY-TWO-WAVE", 0.0, "SCHEDULED", 2, None, 48.0]:
        raise ValueError("A09 accepted root recipe differs")
    put(op, root, "SPRID", "A09-DAILY-TWO-WAVE", "A14-WAVE")
    children = copy.deepcopy(rows(op))
    if len(children) != 2:
        raise ValueError("A14 parent mission rows differ")
    for child in children:
        put(op, child, "PRID", "BASIC-SCHEDULE", "A14-WAVE")
    op["instances"][0]["rows"] = [root, *children]
    if variant == "explicit":
        names = ["DUNID", "DMTID", "DSTIM", "PUNID", "PMTID", "PSTIM", "DTYPE", "MUTD", "DTTOL", "NOTE"]
        types = ["string", "string", "double", "string", "string", "double", "string", "string", "double", "string"]
        records = [["TEACH-UNIT", "EXECUTE", t, "TEACH-UNIT", "SUPPORT", t, "CONTINUOUS", "N", None, None]
                   for t in (8.0, 32.0)]
        add_table(doc, "MissionDependence", names, types, 6, records)
    elif variant == "profile":
        names = ["PRID", "DMTID", "DSTIM", "PMTID", "PSTIM", "DTYPE", "MUTD", "DTTOL", "NOTE"]
        types = ["string", "string", "double", "string", "double", "string", "string", "double", "string"]
        records = [["A14-WAVE", "EXECUTE", 8.0, "SUPPORT", 8.0, "CONTINUOUS", "N", None, None]]
        add_table(doc, "MissionDependenceProfile", names, types, 5, records)
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
