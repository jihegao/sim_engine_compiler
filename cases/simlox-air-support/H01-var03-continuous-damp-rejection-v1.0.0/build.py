"""Build a matched continuous-mission control and DAMP=1 rejection probe."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-continuous-baseline-v1.0.1/native-continuous.json"
PARENT_SHA = "997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea"
ARMS = ("control", "damp")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(name: str, fields: list[tuple[str, str, bool]], row: list) -> dict:
    if len(fields) != len(row):
        raise ValueError(name)
    return {"name": name,
            "columns": [{**{"name": field, "datatype": dtype}, **({"key": True} if key else {})}
                        for field, dtype, key in fields],
            "instances": [{"instance_name": "", "rows": [row]}]}


def build(arm: str) -> bytes:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted A05 parent fingerprint differs")
    if arm == "control":
        return raw
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    if {x["name"] for x in tables} & {"DamageType", "MissionDamage", "DamageItem"}:
        raise ValueError("parent unexpectedly contains damage tables")
    mission = next(x for x in tables if x["name"] == "MissionType")
    columns = [c["name"] for c in mission["columns"]]
    row = mission["instances"][0]["rows"][0]
    if row[columns.index("MTID")] != "BASIC-MISSION" or row[columns.index("MPAT")] != "CONTINUOUS":
        raise ValueError("parent is not the accepted continuous mission")
    description = next(x for x in tables if x["name"] == "ProblemDescription")
    if description["instances"][0]["rows"] != [["A05 continuous four-hour two-aircraft control"]]:
        raise ValueError("parent description differs")
    description["instances"][0]["rows"] = [["H01.var03 continuous DAMP=1 rejection probe"]]
    tables.extend([
        table("DamageType", [("DAMID", "string", True), ("DESCR", "string", False),
                              ("NOTE", "string", False)],
              ["BATTLE-LOSS", "Guaranteed mission attrition probe", None]),
        table("MissionDamage", [("MTID", "string", True), ("SID", "string", True),
                                 ("DAMID", "string", True), ("DAMP", "double", False),
                                 ("DAMRT", "double", False), ("NOTE", "string", False)],
              ["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-LOSS", 1.0, None, None]),
        table("DamageItem", [("DAMID", "string", True), ("SID", "string", True),
                              ("IID", "string", True), ("PROB", "double", False),
                              ("REPF", "double", False), ("OPID", "string", False),
                              ("NOTE", "string", False)],
              ["BATTLE-LOSS", "TEACH-AIR-01", "<ATTRITION>", 1.0, None, None, None]),
    ])
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {}
    for arm in ARMS:
        raw = build(arm)
        path = HERE / f"{arm}-input.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} input differs")
        result[arm] = {"sha256": sha(raw), "bytes": len(raw)}
    print(json.dumps({"parent_sha256": PARENT_SHA, "inputs": result}))


if __name__ == "__main__":
    main()
