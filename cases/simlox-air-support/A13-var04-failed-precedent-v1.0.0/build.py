"""Derive the A13 failed-precedent pair from its accepted dependent input."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A13-start-dependence-v1.0.0" / "dependent-input.json"
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1, name
    return matches[0]


def field(tab: dict, field_name: str) -> int:
    return [c["name"] for c in tab["columns"]].index(field_name)


def write(doc: dict, path: Path) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main() -> None:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    failure = copy.deepcopy(parent)
    sys = table(failure, "System")
    assert sys["instances"][0]["rows"][0][field(sys, "FRT")] == 0
    sys["instances"][0]["rows"][0][field(sys, "FRT")] = 300000
    repair = table(failure, "SystemRepair")
    assert not repair["instances"][0]["rows"]
    repair["instances"][0]["rows"] = [["TEACH-AIR-01", "BASE-01", 0.5, 0.0, 1.0, 1.0] + [None] * 9]
    mt = table(failure, "MissionType")
    follow = next(r for r in mt["instances"][0]["rows"] if r[field(mt, "MTID")] == "FOLLOW")
    assert follow[field(mt, "MFF")] is None
    follow[field(mt, "MFF")] = 1e-6
    failure_desc = "A13 failed fixed RECON predecessor with START-dependent FOLLOW"
    table(failure, "ProblemDescription")["instances"][0]["rows"][0][0] = failure_desc
    write(failure, HERE / "failure-dependency-input.json")
    control = copy.deepcopy(failure)
    dep = table(control, "MissionDependence")
    assert len(dep["instances"][0]["rows"]) == 1
    dep["instances"][0]["rows"] = []
    table(control, "ProblemDescription")["instances"][0]["rows"][0][0] = "A13 failed fixed RECON predecessor without START row"
    write(control, HERE / "failure-control-input.json")
    for name in ("failure-control", "failure-dependency"):
        p = HERE / f"{name}-input.json"
        print(name, hashlib.sha256(p.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
