"""Build explicit, repeated, and nested C07 shift-profile candidates."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-cross-day-v1.0.0" / "cross-day-input.json"
PARENT_SHA256 = "b3780ff767af1653372e8dbd3f367f1fef9829b5fbf324cf6f354a19df558046"
VARIANTS = ("explicit", "repeated", "nested")


def build(variant: str) -> dict:
    assert variant in VARIANTS
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    descr = tables["ProblemDescription"]["instances"][0]["rows"][0]
    assert descr == ["C07 two explicit crew shifts across elapsed hour 24; DRAOS=N"]
    descr[0] = f"C07 two equivalent crew shifts via {variant} profile; DRAOS=N"
    profile = tables["ShiftProfile"]["instances"][0]["rows"]
    assert profile == [["CREW-DAY", "DAY-OPEN", 23.0, 24.0, 1, None, None],
                       ["CREW-DAY", "DAY-OPEN", 25.0, 27.0, 1, None, None]]
    if variant == "explicit":
        profile[:] = [["CREW-DAY", "DAY-OPEN", 23.0, 25.0, 1, None, None],
                      ["CREW-DAY", "DAY-OPEN", 26.0, 28.0, 1, None, None]]
    elif variant == "repeated":
        profile[:] = [["CREW-DAY", "DAY-OPEN", 23.0, 25.0, 2, 3.0, None]]
    else:
        profile[:] = [["CREW-BLOCK", "DAY-OPEN", 1.0, 3.0, 1, None, None],
                      ["CREW-DAY", "CREW-BLOCK", 22.0, None, 2, 3.0, None]]
    assert tables["ResourceStationData"]["instances"][0]["rows"][0][9] == "CREW-DAY"
    assert tables["ShiftResource"]["instances"][0]["rows"][0][:4] == ["DAY-OPEN", "BASE-01", "P-CREW", 2]
    return doc


def main() -> None:
    for variant in VARIANTS:
        path = HERE / f"{variant}-input.json"
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen input differs: {variant}"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
