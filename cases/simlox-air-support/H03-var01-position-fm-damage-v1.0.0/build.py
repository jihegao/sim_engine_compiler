"""Freeze an FM-model damage consequence on accepted D06 position CM route."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0/native-input.json"
PARENT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
DAMAGE_REFERENCE = HERE.parent / "H02-var01-primary-lru-damage-v1.0.0/lru-input.json"
DAMAGE_REFERENCE_SHA = "82564db9cd0d3f916a87264d16d390a42bf886f5748c843070bea20e6b1c4a92"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1
    return found[0]


def row(doc: dict, name: str) -> list:
    rows = table(doc, name)["instances"][0]["rows"]
    assert len(rows) == 1
    return rows[0]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA and sha(DAMAGE_REFERENCE) == DAMAGE_REFERENCE_SHA
    parent = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    reference = json.loads(DAMAGE_REFERENCE.read_text(encoding="utf-8-sig"))
    assert not any(t["name"] in ("DamageType", "MissionDamage", "DamageFailureMode")
                   for t in parent["model"]["tables"])
    control = copy.deepcopy(parent)
    assert row(control, "FailureMode")[:5] == [
        "FM-POS-A", "Position A direct repair", "POS-A", 300000, "OPHOURS"]
    row(control, "FailureMode")[3] = 1e-9
    damage_type = copy.deepcopy(table(reference, "DamageType"))
    row_template = damage_type["instances"][0]["rows"][0]
    assert row_template[0] == "BATTLE-HIT"
    row_template[1] = "Certain in-flight position failure-mode damage"
    mission_damage = copy.deepcopy(table(reference, "MissionDamage"))
    assert mission_damage["instances"][0]["rows"][0][:4] == [
        "BASIC-MISSION", "TEACH-AIR-01", "BATTLE-HIT", 1]
    damage_mode = {"name": "DamageFailureMode",
                   "columns": [
                       {"name": "DAMID", "datatype": "string", "key": True},
                       {"name": "SID", "datatype": "string", "key": True},
                       {"name": "FMID", "datatype": "string", "key": True},
                       {"name": "PROB", "datatype": "double"},
                       {"name": "NOTE", "datatype": "string"}],
                   "instances": [{"instance_name": "", "rows": [
                       ["BATTLE-HIT", "TEACH-AIR-01", "FM-POS-A", 0.0, None]]}]}
    control["model"]["tables"].extend([damage_type, mission_damage, damage_mode])
    row(control, "ProblemDescription")[0] = (
        "H03.var01 accepted D06 CM model with BATTLE-HIT, FM consequence PROB0")
    mode = copy.deepcopy(control)
    row(mode, "DamageFailureMode")[3] = 1.0
    row(mode, "ProblemDescription")[0] = (
        "H03.var01 accepted D06 CM model with BATTLE-HIT, FM consequence PROB1")
    for name, doc in (("control-input.json", control), ("mode-input.json", mode)):
        path = HERE / name
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {name} differs")
        if not path.exists():
            path.write_bytes(raw)
        print(name, sha(path))


if __name__ == "__main__":
    main()
