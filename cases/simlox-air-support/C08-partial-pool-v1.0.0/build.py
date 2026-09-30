"""Derive a staggered two-mission partial-pool pair from accepted shift cases."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
LIMITED = HERE.parent / "C08-shift-maxut-v1.0.0" / "maxut-one-input.json"
BASE_SHA = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"
LIMITED_SHA = "00e660275ace4d71d41cdafa725da2b552baeea9604756d94ad6b07de846e9d5"


def tables(doc: dict) -> dict:
    return {table["name"]: table for table in doc["model"]["tables"]}


def stagger(doc: dict, label: str) -> dict:
    result = copy.deepcopy(doc)
    t = tables(result)
    description = t["ProblemDescription"]["instances"][0]["rows"][0]
    assert len(description) == 1
    description[0] = label
    mission = t["MissionType"]["instances"][0]["rows"][0]
    assert mission[:4] == ["BASIC-MISSION", "One-hour two-aircraft shared-crew formation", 2, 2]
    mission[1] = "One-hour single-aircraft mission, staggered pair"
    mission[2:4] = [1, 1]
    profile = t["OperationProfile"]["instances"][0]["rows"]
    assert profile == [["BASIC-SCHEDULE", "BASIC-MISSION", 28.0, "SCHEDULED", 1, None, 0, None, 1.0, None, None, None]]
    second = copy.deepcopy(profile[0])
    second[2] = 28.5
    profile.append(second)
    assert t["SystemDeployment"]["instances"][0]["rows"][0][2] == 2
    assert t["ShiftResource"]["instances"][0]["rows"][0][3] == 2
    assert t["SubTaskResource"]["instances"][0]["rows"][0][3] == 1
    return result


def build() -> dict[str, dict]:
    base_raw = BASE.read_bytes()
    limited_raw = LIMITED.read_bytes()
    assert hashlib.sha256(base_raw).hexdigest() == BASE_SHA
    assert hashlib.sha256(limited_raw).hexdigest() == LIMITED_SHA
    base = json.loads(base_raw)
    limited = json.loads(limited_raw)
    a, b = tables(base), tables(limited)
    assert sorted(name for name in a if a[name] != b[name]) == ["ProblemDescription", "ShiftResource"]
    assert a["ShiftResource"]["instances"][0]["rows"] == [["DAY-OPEN", "BASE-01", "P-CREW", 2, None, None]]
    assert b["ShiftResource"]["instances"][0]["rows"] == [["DAY-OPEN", "BASE-01", "P-CREW", 2, 1.0, None]]
    control = stagger(base, "C08 staggered partial pool; MAXUT unset; DRAOS=N")
    finite = stagger(limited, "C08 staggered partial pool; MAXUT one hour per crew; DRAOS=N")
    c, f = tables(control), tables(finite)
    assert sorted(name for name in c if c[name] != f[name]) == ["ProblemDescription", "ShiftResource"]
    return {"stagger-unlimited": control, "stagger-maxut": finite}


def main() -> None:
    for variant, doc in build().items():
        path = HERE / f"{variant}-input.json"
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {variant} input differs"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
