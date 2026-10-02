"""Build a quiet E01 control and certain primary-LRU damage candidate."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
E01 = ROOT / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json"
H02 = ROOT / "H02-var01-system-damage-direct-repair-v1.0.0/system-input.json"
E01_SHA = "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931"
H02_SHA = "67eb54c6148cd17c43e050eaf3d310bf7f66b96452526614ca1af416c16d9bcb"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1
    return found[0]


def row(doc: dict, name: str) -> list:
    instances = table(doc, name)["instances"]
    assert len(instances) == 1 and len(instances[0]["rows"]) == 1
    return instances[0]["rows"][0]


def main() -> None:
    assert sha(E01) == E01_SHA and sha(H02) == H02_SHA
    parent = json.loads(E01.read_text(encoding="utf-8-sig"))
    reference = json.loads(H02.read_text(encoding="utf-8-sig"))
    control = copy.deepcopy(parent)
    row(control, "ProblemDescription")[0] = "H02.var01 quiet E01 control for primary LRU damage"
    row(control, "System")[3] = 0
    row(control, "Item")[3] = 0
    child = copy.deepcopy(control)
    row(child, "ProblemDescription")[0] = "H02.var01 certain primary LRU damage, replacement and repair"
    for name in ("DamageType", "MissionDamage", "DamageItem"):
        child["model"]["tables"].append(copy.deepcopy(table(reference, name)))
    row(child, "DamageType")[:2] = ["BATTLE-HIT", "Certain primary LRU mission damage"]
    row(child, "MissionDamage")[:] = ["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-HIT", 1.0, None, None]
    row(child, "DamageItem")[:] = ["BATTLE-HIT", "TEACH-AIR-01", "TEACH-LRU-01", 1.0, 1.0, None, None]
    child["model"]["tables"].append({
        "name": "DamageReplacement",
        "columns": [
            {"name": "DAMID", "datatype": "string", "key": True},
            {"name": "STID", "datatype": "string", "key": True},
            {"name": "SID", "datatype": "string", "key": True},
            {"name": "IID", "datatype": "string", "key": True},
            {"name": "SURPT", "datatype": "double"},
            {"name": "SURPF", "datatype": "double"},
            {"name": "TID", "datatype": "string"},
            {"name": "SURPD", "datatype": "string"},
            {"name": "NOTE", "datatype": "string"},
        ],
        "instances": [{"instance_name": "", "rows": [[
            "BATTLE-HIT", "BASE-01", "TEACH-AIR-01", "TEACH-LRU-01",
            0.5, 1.0, "E01-SURP", None, None,
        ]]}],
    })
    for name, doc in (("control-input.json", control), ("lru-input.json", child)):
        path = HERE / name
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {name} differs")
        if not path.exists():
            path.write_bytes(raw)
        print(name, sha(path))


if __name__ == "__main__":
    main()
