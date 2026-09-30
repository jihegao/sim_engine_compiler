"""Freeze A01 and one-field collection-end/simulation-period children."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
PARENT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def build() -> dict[str, bytes]:
    baseline_raw = PARENT.read_bytes()
    assert hashlib.sha256(baseline_raw).hexdigest() == PARENT_SHA
    baseline = json.loads(baseline_raw)
    assert table(baseline, "Control")["instances"][0]["rows"][0][:7] == [
        1, 36.0, "1", "AIR_BASIC", .5, 0, 36.0
    ]
    assert table(baseline, "ResultCollection")["instances"][0]["rows"] == [
        ["MISSION", .5, 0, 36.0, None, None],
        ["SYSTEM", .5, 0, 36.0, None, None],
    ]

    collection_end = copy.deepcopy(baseline)
    table(collection_end, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "J05 SYSTEM result collection ends at 9; simulation continues to 36"
    )
    table(collection_end, "ResultCollection")["instances"][0]["rows"][1][3] = 9.0

    simulation_end = copy.deepcopy(baseline)
    table(simulation_end, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "J05 simulation period ends at 48; result collection ends at 36"
    )
    table(simulation_end, "Control")["instances"][0]["rows"][0][1] = 48.0

    simulation_cutoff = copy.deepcopy(baseline)
    table(simulation_cutoff, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "J05 simulation period ends at 9 during mission; collection end remains 36"
    )
    table(simulation_cutoff, "Control")["instances"][0]["rows"][0][1] = 9.0

    return {
        "baseline": baseline_raw,
        "rcend9": (json.dumps(collection_end, ensure_ascii=False, indent=2) + "\n").encode(),
        "simpe48": (json.dumps(simulation_end, ensure_ascii=False, indent=2) + "\n").encode(),
        "simpe9": (json.dumps(simulation_cutoff, ensure_ascii=False, indent=2) + "\n").encode(),
    }


def main() -> None:
    for name, raw in build().items():
        path = HERE / f"{name}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {name} differs"
        else:
            path.write_bytes(raw)
        print(name, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
