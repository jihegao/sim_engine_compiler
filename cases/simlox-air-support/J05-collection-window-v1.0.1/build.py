"""Derive matched J05 global and per-type collection windows from accepted A01."""
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


def build() -> dict[str, dict]:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    baseline = json.loads(PARENT.read_bytes())
    control = table(baseline, "Control")
    assert [c["name"] for c in control["columns"]][:7] == ["NREPS", "SIMPE", "RSEED", "APID", "RCINT", "RCSTA", "RCEND"]
    assert control["instances"][0]["rows"][0][:7] == [1, 36.0, "1", "AIR_BASIC", 0.5, 0, 36.0]
    result = table(baseline, "ResultCollection")
    assert result["instances"][0]["rows"] == [["MISSION", 0.5, 0, 36.0, None, None], ["SYSTEM", 0.5, 0, 36.0, None, None]]
    assert table(baseline, "MissionType")["instances"][0]["rows"][0][5] == 2.0
    assert table(baseline, "OperationProfile")["instances"][0]["rows"][0][2] == 8.0
    global_window = copy.deepcopy(baseline)
    table(global_window, "Control")["instances"][0]["rows"][0][4:7] = [0.25, 7.5, 9.0]
    table(global_window, "ResultCollection")["instances"][0]["rows"] = []
    table(global_window, "ProblemDescription")["instances"][0]["rows"][0][0] = "J05 global collection 7.5-9 by quarter-hour; A01 mission continues"
    system_override = copy.deepcopy(global_window)
    table(system_override, "ResultCollection")["instances"][0]["rows"] = [["SYSTEM", 0.5, 0, 36.0, None, None]]
    table(system_override, "ProblemDescription")["instances"][0]["rows"][0][0] = "J05 system collection 0-36 override; mission global 7.5-9"
    return {"baseline": baseline, "global-window": global_window, "system-override": system_override}


def main() -> None:
    for variant, doc in build().items():
        raw = PARENT.read_bytes() if variant == "baseline" else (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"{variant}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {variant} differs"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
