"""Freeze an accepted aborting-mission control and an earlier success point."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"


def table(doc, name):
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def build():
    source = PARENT.read_bytes()
    assert hashlib.sha256(source).hexdigest() == PARENT_SHA
    control = json.loads(source)
    mission = table(control, "MissionType")["instances"][0]["rows"][0]
    assert mission[:10] == ["BASIC-MISSION", "Two-hour generic mission", 1, 1, None, 2.0, None, 1, .25, .25]
    assert [row[2] for row in table(control, "OperationProfile")["instances"][0]["rows"]] == [8, 20, 32]
    early = copy.deepcopy(control)
    table(early, "MissionType")["instances"][0]["rows"][0][7] = .75
    table(early, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "J07 success-point probe: D06 aborting mission, MSUCPT 0.75"
    )
    return {"full-completion-control": source,
            "early-success-point": (json.dumps(early, ensure_ascii=False, indent=2) + "\n").encode()}


def main():
    inputs = build()
    for variant, raw in inputs.items():
        path = HERE / f"{variant}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {variant} differs"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())
    parent = json.loads(inputs["full-completion-control"])
    child = json.loads(inputs["early-success-point"])
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    changed = [name for name in before if before[name] != after[name]]
    assert changed == ["ProblemDescription", "MissionType"] or set(changed) == {"ProblemDescription", "MissionType"}
    diff = {
        "schema": "simlox-j07-success-point-exact-diff/v1",
        "parent_publication_id": "D06.position_direct_cm.1.0.0",
        "parent_input_sha256": PARENT_SHA,
        "child_input_sha256": hashlib.sha256(inputs["early-success-point"]).hexdigest(),
        "changed_tables": changed,
        "tables": {name: {"before": before[name]["instances"][0]["rows"],
                          "after": after[name]["instances"][0]["rows"]} for name in changed},
        "unchanged_table_count": len(before) - len(changed),
    }
    diff_path = HERE / "exact-diff.json"
    raw = (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode()
    if diff_path.exists():
        assert diff_path.read_bytes() == raw, "frozen exact diff differs"
    else:
        diff_path.write_bytes(raw)


if __name__ == "__main__":
    main()
