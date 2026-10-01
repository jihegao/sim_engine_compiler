"""Build frozen G02.var04 position-bound PM inputs from published G02.var01.

This source is pre-native. Do not change it after running the pinned native matrix.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "G02-var01-position-modes-v1.0.0" / "native-input.json"
PM_TEMPLATE = ROOT / "D03-calendar-pm-v1.0.0" / "native-input.json"
PARENT_SHA = "5ef40eb302544e551282dd7dd3617a6ae160954f600dea605f26140ea551a19e"
PM_TEMPLATE_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
VARIANTS = ("no-pm", "pos-a-only", "pos-b-only", "both")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(document: dict, name: str) -> dict:
    return next(t for t in document["model"]["tables"] if t["name"] == name)


def row(t: dict, index: int = 0) -> list:
    populated = [r for instance in t["instances"] for r in instance["rows"]]
    return populated[index]


def put(t: dict, r: list, field: str, value) -> None:
    r[[c["name"] for c in t["columns"]].index(field)] = value


def add(t: dict, r: list) -> None:
    assert len(t["instances"]) == 1
    t["instances"][0]["rows"].append(r)


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    assert sha(PARENT) == PARENT_SHA and sha(PM_TEMPLATE) == PM_TEMPLATE_SHA
    source = json.loads(PARENT.read_text(encoding="utf-8"))
    template = json.loads(PM_TEMPLATE.read_text(encoding="utf-8"))
    model = copy.deepcopy(source)
    put(table(model, "ProblemDescription"), row(table(model, "ProblemDescription")),
        "PDESC", f"G02.var04 position-specific PM {variant}")
    control = table(model, "Control")
    put(control, row(control), "SIMPE", 60.0)
    put(control, row(control), "RCEND", 60.0)
    put(control, row(control), "ENPM", "Y")
    collections = table(model, "ResultCollection")
    for instance in collections["instances"]:
        for item in instance["rows"]:
            put(collections, item, "RCEND", 60.0)
    specs = []
    if variant in ("pos-a-only", "both"):
        specs.append(("PM-POS-A", "POS-A", 24.0, 1.0))
    if variant in ("pos-b-only", "both"):
        specs.append(("PM-POS-B", "POS-B", 36.0, 0.5))
    if specs:
        add(table(model, "SubTaskType"), copy.deepcopy(row(table(template, "SubTaskType"))))
    for pmid, mid, interval, duration in specs:
        task = copy.deepcopy(row(table(template, "Tasks")))
        tt = table(model, "Tasks")
        put(tt, task, "TID", pmid)
        put(tt, task, "DESCR", f"Calendar PM at {mid}")
        add(tt, task)
        pm = copy.deepcopy(row(table(template, "MaterielPM")))
        pt = table(model, "MaterielPM")
        for key, value in (("PMID", pmid), ("DESCR", f"Calendar PM at {mid}"),
                           ("MID", mid), ("PMINT", interval), ("OPID", "CALHOURS")):
            put(pt, pm, key, value)
        add(pt, pm)
        location = copy.deepcopy(row(table(template, "PMLocation")))
        lt = table(model, "PMLocation")
        for key, value in (("PMID", pmid), ("ID", "TEACH-AIR-01"),
                           ("STID", "BASE-01"), ("PMT", duration), ("TID", pmid)):
            put(lt, location, key, value)
        add(lt, location)
        subtask = copy.deepcopy(row(table(template, "TaskBreakDown")))
        st = table(model, "TaskBreakDown")
        put(st, subtask, "TID", pmid)
        put(st, subtask, "DURN", duration)
        add(st, subtask)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    hashes = {}
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        output = HERE / f"{variant}-input.json"
        if args.write:
            if output.exists():
                raise FileExistsError(output)
            output.write_bytes(raw)
        elif output.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {variant}")
        hashes[variant] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "pm_template_sha256": PM_TEMPLATE_SHA,
                      "inputs_sha256": hashes}))


if __name__ == "__main__":
    main()
