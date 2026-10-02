"""Build a high-rate mission-damage probe without an attrition consequence."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions/native-input.json"
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
ARMS = ("control", "rate")


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
        raise ValueError("accepted A02 parent differs")
    if arm == "control":
        return raw
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    if {t["name"] for t in tables} & {"DamageType", "MissionDamage", "DamageItem"}:
        raise ValueError("parent unexpectedly contains damage tables")
    description = next(t for t in tables if t["name"] == "ProblemDescription")
    if description["instances"][0]["rows"] != [["A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence"]]:
        raise ValueError("parent description differs")
    description["instances"][0]["rows"] = [["H01.var02 fixed-mission DAMRT high-rate probe, no consequence"]]
    tables.extend([
        table("DamageType", [("DAMID", "string", True), ("DESCR", "string", False),
                              ("NOTE", "string", False)],
              ["BATTLE-HIT", "Repeated mission hit probe", None]),
        table("MissionDamage", [("MTID", "string", True), ("SID", "string", True),
                                 ("DAMID", "string", True), ("DAMP", "double", False),
                                 ("DAMRT", "double", False), ("NOTE", "string", False)],
              ["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-HIT", 0.0, 3000000.0, None]),
        table("DamageItem", [("DAMID", "string", True), ("SID", "string", True),
                              ("IID", "string", True), ("PROB", "double", False),
                              ("REPF", "double", False), ("OPID", "string", False),
                              ("NOTE", "string", False)],
              ["BATTLE-HIT", "TEACH-AIR-01", "<ATTRITION>", 0.0, None, None, None]),
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
            raise ValueError(f"frozen {arm} source differs")
        result[arm] = {"sha256": sha(raw), "bytes": len(raw)}
    print(json.dumps({"parent_sha256": PARENT_SHA, "inputs": result}))


if __name__ == "__main__":
    main()
