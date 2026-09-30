"""Build a matched A13 pair stopped while the precedent remains on mission."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A13-start-dependence-v1.0.0" / "dependent-input.json"
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def write(doc: dict, path: Path) -> None:
    path.write_bytes((json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def main() -> None:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    child = copy.deepcopy(parent)
    control = table(child, "Control")
    indices = {c["name"]: i for i, c in enumerate(control["columns"])}
    row, = control["instances"][0]["rows"]
    assert (row[indices["SIMPE"]], row[indices["RCEND"]], row[indices["RCINT"]]) == (24.0, 24.0, .5)
    row[indices["SIMPE"]] = row[indices["RCEND"]] = 11.0
    table(child, "ProblemDescription")["instances"][0]["rows"][0][0] = "A13 unfinished RECON at hour 11; FOLLOW START row"
    write(child, HERE / "unfinished-dependency-input.json")
    paired = copy.deepcopy(child)
    dependence = table(paired, "MissionDependence")
    assert len(dependence["instances"][0]["rows"]) == 1
    dependence["instances"][0]["rows"] = []
    table(paired, "ProblemDescription")["instances"][0]["rows"][0][0] = "A13 unfinished RECON at hour 11; FOLLOW no row"
    write(paired, HERE / "unfinished-control-input.json")
    for variant in ("unfinished-control", "unfinished-dependency"):
        path = HERE / f"{variant}-input.json"
        print(variant, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
