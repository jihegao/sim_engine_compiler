"""Build a paired A13 START preparation-before-wait probe from accepted A13 and B01."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A13-start-dependence-v1.0.0" / "dependent-input.json"
PREPARATION = ROOT / "B01-fixed-preparation-v1.0.1" / "native-input.json"
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
PREPARATION_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"


def source(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"accepted source changed: {path}")
    return json.loads(raw)


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def column(t: dict, name: str) -> int:
    return [c["name"] for c in t["columns"]].index(name)


def build(dependent: bool) -> dict:
    doc = copy.deepcopy(source(PARENT, PARENT_SHA))
    prep = source(PREPARATION, PREPARATION_SHA)
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "A13.var03 prepare then START wait" if dependent else "A13.var03 prepare without START wait"
    )
    mission_prep = table(doc, "MissionPreparation")
    b01_prep = table(prep, "MissionPreparation")
    if mission_prep["columns"] != b01_prep["columns"] or mission_prep["instances"][0]["rows"]:
        raise ValueError("MissionPreparation source shape differs")
    prep_row = copy.deepcopy(b01_prep["instances"][0]["rows"][0])
    prep_row[column(mission_prep, "MTID")] = "FOLLOW"
    mission_prep["instances"][0]["rows"] = [prep_row]
    tasks = table(doc, "Tasks")
    b01_tasks = table(prep, "Tasks")
    if tasks["columns"] != b01_tasks["columns"] or tasks["instances"][0]["rows"]:
        raise ValueError("Tasks source shape differs")
    task_row = copy.deepcopy(b01_tasks["instances"][0]["rows"][0])
    task_row[column(tasks, "DESCR")] = "Fixed 30-minute FOLLOW preparation"
    tasks["instances"][0]["rows"] = [task_row]
    dependency = table(doc, "MissionDependence")
    if not dependent:
        doc["model"]["tables"].remove(dependency)
    return doc


def main() -> None:
    for label, dependent in (("control", False), ("dependency", True)):
        raw = (json.dumps(build(dependent), ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{label}-input.json"
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {label} input changed")
        path.write_bytes(raw)
        print(label, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
