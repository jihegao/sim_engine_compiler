"""Contrast accepted position-FM damage with certain whole-aircraft loss."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H03-var01-position-fm-damage-v1.0.0/mode-input.json"
PARENT_SHA = "5297d5224b3a2086c26c663aa92cd51be7c349a24f7957428f47c21fcdc4ee7c"
ATTRITION_REFERENCE = HERE.parent / "H01-var01-certain-attrition-v1.0.0/certain-input.json"
ATTRITION_REFERENCE_SHA = "f519cd4549db879505c16bd5d4affb7e34f1db6227e71bebc27738442489d4f0"


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
    assert sha(PARENT) == PARENT_SHA and sha(ATTRITION_REFERENCE) == ATTRITION_REFERENCE_SHA
    control_raw = PARENT.read_bytes()
    control = json.loads(control_raw)
    reference = json.loads(ATTRITION_REFERENCE.read_bytes())
    assert not any(t["name"] == "DamageItem" for t in control["model"]["tables"])
    assert row(control, "DamageFailureMode")[:4] == ["BATTLE-HIT", "TEACH-AIR-01", "FM-POS-A", 1]
    assert row(control, "MissionDamage")[:4] == ["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-HIT", 1]
    child = copy.deepcopy(control)
    row(child, "DamageFailureMode")[3] = 0.0
    row(child, "DamageType")[1] = "Certain in-flight whole-aircraft attrition damage"
    damage_item = copy.deepcopy(table(reference, "DamageItem"))
    assert row(reference, "DamageItem")[:4] == ["BATTLE-LOSS", "TEACH-AIR-01", "<ATTRITION>", 1]
    damage_item["instances"][0]["rows"][0][0] = "BATTLE-HIT"
    child["model"]["tables"].append(damage_item)
    row(child, "ProblemDescription")[0] = (
        "H03.var03 FM-POS-A consequence PROB0 and BATTLE-HIT ATTRITION PROB1")
    child_raw = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode()
    for path, raw in ((HERE / "control-input.json", control_raw),
                      (HERE / "attrition-input.json", child_raw)):
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen source differs: {path.name}")
        if not path.exists():
            path.write_bytes(raw)
        print(path.name, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
