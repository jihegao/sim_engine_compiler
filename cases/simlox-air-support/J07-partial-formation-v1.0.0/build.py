"""Freeze A03, strict one-aircraft shortage, and relaxed one-aircraft minimum."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
PARENT_SHA = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"


def table(doc, name):
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def freeze(path, raw):
    if path.exists():
        assert path.read_bytes() == raw, f"frozen {path.name} differs"
    else:
        path.write_bytes(raw)


def build():
    source = PARENT.read_bytes()
    assert hashlib.sha256(source).hexdigest() == PARENT_SHA
    full = json.loads(source)
    mission = table(full, "MissionType")["instances"][0]["rows"][0]
    deployment = table(full, "SystemDeployment")["instances"][0]["rows"][0]
    assert mission[:10] == ["BASIC-MISSION", "Two-hour generic mission", 2, 2, None, 2.0, None, 1, .25, .25]
    assert deployment == ["TEACH-AIR-01", "TEACH-UNIT", 2, 1, None, None, None]
    assert [row[2] for row in table(full, "OperationProfile")["instances"][0]["rows"]] == [8]
    strict = copy.deepcopy(full)
    table(strict, "SystemDeployment")["instances"][0]["rows"][0][2] = 1
    table(strict, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "J07 nominal two-aircraft wave, one deployed, MNOS two: strict shortage control"
    )
    partial = copy.deepcopy(strict)
    table(partial, "MissionType")["instances"][0]["rows"][0][3] = 1
    table(partial, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "J07 nominal two-aircraft wave, one deployed, MNOS one: partial formation"
    )
    return {
        "full-control": source,
        "strict-shortage": (json.dumps(strict, ensure_ascii=False, indent=2) + "\n").encode(),
        "partial-minimum": (json.dumps(partial, ensure_ascii=False, indent=2) + "\n").encode(),
    }


def main():
    inputs = build()
    for variant, raw in inputs.items():
        freeze(HERE / f"{variant}-input.json", raw)
        print(variant, hashlib.sha256(raw).hexdigest())
    parent = json.loads(inputs["full-control"])
    before = {t["name"]: t for t in parent["model"]["tables"]}
    diffs = {}
    for variant in ("strict-shortage", "partial-minimum"):
        child = json.loads(inputs[variant])
        after = {t["name"]: t for t in child["model"]["tables"]}
        changed = [name for name in before if before[name] != after[name]]
        expected = {"SystemDeployment", "ProblemDescription"}
        if variant == "partial-minimum":
            expected.add("MissionType")
        assert set(changed) == expected and len(before) == len(after) == 31
        diffs[variant] = {
            "child_input_sha256": hashlib.sha256(inputs[variant]).hexdigest(),
            "changed_tables": changed,
            "tables": {name: {"before": before[name]["instances"][0]["rows"],
                              "after": after[name]["instances"][0]["rows"]} for name in changed},
            "unchanged_table_count": len(before) - len(changed),
        }
    diff = {"schema": "simlox-j07-partial-formation-exact-diff/v1",
            "parent_publication_id": "A03.formation.1.0.1",
            "parent_input_sha256": PARENT_SHA,
            "variants": diffs}
    freeze(HERE / "exact-diffs.json", (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode())


if __name__ == "__main__":
    main()
