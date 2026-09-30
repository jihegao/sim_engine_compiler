"""Freeze the A01, accepted direct-profile, and nested-repetition J05 inputs."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
DIRECT = HERE.parent / "J05-profile-snapshot-v1.0.1" / "mixed-profile-input.json"
PARENT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
DIRECT_SHA = "0eaa2c466e196f471bde4054f278bd018bae5f3eea2e15b9d0f21dba96223e38"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def build() -> dict[str, bytes]:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(DIRECT.read_bytes()).hexdigest() == DIRECT_SHA
    baseline = PARENT.read_bytes()
    direct = DIRECT.read_bytes()
    nested = copy.deepcopy(json.loads(direct))
    table(nested, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "J05 nested repeated SYSTEM profile: J05SEG twice at 7.75 and 9.75"
    )
    collection = table(nested, "ResultCollection")["instances"][0]["rows"]
    assert collection[1] == ["SYSTEM", 1.0, 0, 36.0, "J05MIX", None]
    collection[1][4] = "J05TOP"
    profile = table(nested, "ResultCollectionProfile")
    assert [c["name"] for c in profile["columns"]] == [
        "RCPID", "SRCPID", "STIM", "IQTY", "IINT", "RCINT", "DURN", "NOTE"
    ]
    profile["instances"][0]["rows"] = [
        ["J05SEG", "CONTINUOUS", 0.0, 1, None, 0.5, 0.5, None],
        ["J05SEG", "SNAPSHOT", 0.5, 1, None, None, None, None],
        ["J05TOP", "J05SEG", 7.75, 2, 2.0, None, None, None],
    ]
    return {
        "baseline": baseline,
        "direct-control": direct,
        "nested-repeat": (json.dumps(nested, ensure_ascii=False, indent=2) + "\n").encode(),
    }


def main() -> None:
    for variant, raw in build().items():
        path = HERE / f"{variant}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {variant} differs"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
