"""Build a two-arm DAMP 0/1 attrition probe from accepted A02."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions/native-input.json"
PARENT_SHA256 = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
SOURCES = {"zero": HERE / "zero-input.json", "certain": HERE / "certain-input.json"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_table(name: str, fields: list[tuple[str, str, bool]], row: list) -> dict:
    assert len(fields) == len(row)
    return {
        "name": name,
        "columns": [{**{"name": field, "datatype": datatype}, **({"key": True} if key else {})}
                    for field, datatype, key in fields],
        "instances": [{"instance_name": "", "rows": [row]}],
    }


def build(arm: str) -> dict:
    assert arm in SOURCES
    parent_raw = PARENT.read_bytes()
    assert sha(parent_raw) == PARENT_SHA256
    document = copy.deepcopy(json.loads(parent_raw))
    tables = document["model"]["tables"]
    assert not {"DamageType", "MissionDamage", "DamageItem"} & {t["name"] for t in tables}
    description = next(t for t in tables if t["name"] == "ProblemDescription")
    assert description["instances"][0]["rows"] == [
        ["A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence"]]
    description["instances"][0]["rows"] = [[
        f"H01 DAMP {'1 certain' if arm == 'certain' else '0 control'} attrition probe"]]
    tables.extend([
        make_table("DamageType", [
            ("DAMID", "string", True), ("DESCR", "string", False), ("NOTE", "string", False)],
            ["BATTLE-LOSS", "One observable mission attrition consequence", None]),
        make_table("MissionDamage", [
            ("MTID", "string", True), ("SID", "string", True), ("DAMID", "string", True),
            ("DAMP", "double", False), ("DAMRT", "double", False), ("NOTE", "string", False)],
            ["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-LOSS", 1.0 if arm == "certain" else 0.0,
             None, None]),
        make_table("DamageItem", [
            ("DAMID", "string", True), ("SID", "string", True), ("IID", "string", True),
            ("PROB", "double", False), ("REPF", "double", False), ("OPID", "string", False),
            ("NOTE", "string", False)],
            ["BATTLE-LOSS", "TEACH-AIR-01", "<ATTRITION>", 1.0, None, None, None]),
    ])
    return document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    results = {}
    for arm, path in SOURCES.items():
        data = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(data)
        elif path.read_bytes() != data:
            raise ValueError(f"frozen H01 source differs: {arm}")
        results[arm] = {"sha256": sha(data), "bytes": len(data)}
    print(json.dumps({"parent_sha256": PARENT_SHA256, "sources": results}))


if __name__ == "__main__":
    main()
