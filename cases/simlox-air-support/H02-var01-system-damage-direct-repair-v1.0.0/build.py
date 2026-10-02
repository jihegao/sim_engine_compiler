"""Build an airframe-damage direct-repair probe from accepted H01 attrition."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H01-var01-certain-attrition-v1.0.0/certain-input.json"
PARENT_SHA = "f519cd4549db879505c16bd5d4affb7e34f1db6227e71bebc27738442489d4f0"
ARMS = ("attrition", "system")


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
        raise ValueError("accepted H01 attrition source fingerprint differs")
    if arm == "attrition":
        return raw
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    names = {t["name"] for t in tables}
    if "DamageRepair" in names:
        raise ValueError("parent unexpectedly contains DamageRepair")
    damage = next(t for t in tables if t["name"] == "DamageItem")
    columns = [c["name"] for c in damage["columns"]]
    row = damage["instances"][0]["rows"][0]
    if row[columns.index("IID")] != "<ATTRITION>" or row[columns.index("PROB")] != 1.0:
        raise ValueError("parent consequence differs")
    row[columns.index("IID")] = "<SYSTEM>"
    description = next(t for t in tables if t["name"] == "ProblemDescription")
    if description["instances"][0]["rows"] != [["H01 DAMP 1 certain attrition probe"]]:
        raise ValueError("parent description differs")
    description["instances"][0]["rows"] = [["H02.var01 certain airframe damage with local one-hour direct repair"]]
    tables.append(table("DamageRepair", [
        ("DAMID", "string", True), ("SID", "string", True), ("STID", "string", True),
        ("DIRPT", "double", False), ("SURPT", "double", False),
        ("DIRPF", "double", False), ("SURPF", "double", False),
        ("DIRPTID", "string", False), ("SURPTID", "string", False),
        ("DIRPD", "string", False), ("SURPD", "string", False), ("NOTE", "string", False)],
        ["BATTLE-LOSS", "TEACH-AIR-01", "BASE-01", 1.0, 0.0, 1.0, 1.0,
         None, None, None, None, None]))
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
