"""Build isolated C07 overlap and shift-capacity counterexamples."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
PARENT_SHA256 = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"
REPEATED_PARENT = HERE.parent / "C07-repeat-nested-v1.0.0" / "repeated-input.json"
REPEATED_PARENT_SHA256 = "32f79158605a426edc80052f1188ec0c65f91d468d10a07ab748b7f0839c053e"
VARIANTS = ("overlap", "repeated-overlap", "over-capacity")


def build(variant: str) -> dict:
    assert variant in VARIANTS
    parent = REPEATED_PARENT if variant == "repeated-overlap" else PARENT
    expected_sha = REPEATED_PARENT_SHA256 if variant == "repeated-overlap" else PARENT_SHA256
    raw = parent.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected_sha
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    description = tables["ProblemDescription"]["instances"][0]["rows"][0]
    expected_descr = f"C07 two equivalent crew shifts via {'repeated' if variant == 'repeated-overlap' else 'explicit'} profile; DRAOS=N"
    assert description == [expected_descr]
    description[0] = f"C07 invalid {variant} crew shift diagnostic; DRAOS=N"
    if variant == "overlap":
        rows = tables["ShiftProfile"]["instances"][0]["rows"]
        assert rows == [["CREW-DAY", "DAY-OPEN", 23.0, 25.0, 1, None, None],
                        ["CREW-DAY", "DAY-OPEN", 26.0, 28.0, 1, None, None]]
        rows[1][2] = 24.5
    elif variant == "repeated-overlap":
        rows = tables["ShiftProfile"]["instances"][0]["rows"]
        assert rows == [["CREW-DAY", "DAY-OPEN", 23.0, 25.0, 2, 3.0, None]]
        rows[0][5] = 1.5
    else:
        row = tables["ShiftResource"]["instances"][0]["rows"][0]
        assert row == ["DAY-OPEN", "BASE-01", "P-CREW", 2, None, None]
        row[3] = 3
        assert tables["ResourceAllocation"]["instances"][0]["rows"][0][3] == 2
    return doc


def main() -> None:
    for variant in VARIANTS:
        path = HERE / f"{variant}-input.json"
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen source differs: {variant}"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
