"""Build a three-arm C09 primary-maintenance remote-resource matrix from C03."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "C03-shared-crew-formation-v1.0.2/inputs/staffing-2.json"
D01 = ROOT / "D01-installed-lru-direct-repair-v1.0.0/native-input.json"
PARENT_SHA = "83b454bd145621f36571a87cdf8abcbccc184f07ab8f9ad5f3111651c78881e0"
D01_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
VARIANTS = ("local", "remote", "remote-disabled")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def row(t: dict, index: int = 0) -> list:
    return [r for i in t["instances"] for r in i["rows"]][index]


def put(t: dict, r: list, field: str, value) -> None:
    r[[c["name"] for c in t["columns"]].index(field)] = value


def add(t: dict, r: list) -> None:
    assert len(t["instances"]) == 1
    assert len(r) == len(t["columns"])
    t["instances"][0]["rows"].append(r)


def empty_row(t: dict) -> list:
    return [None] * len(t["columns"])


def remote_support_table() -> dict:
    fields = (("RID", "string", True), ("STID", "string", True),
              ("RSTID", "string", True), ("TFRS", "double", False),
              ("TTRS", "double", False), ("TTRSS", "double", False),
              ("NOTE", "string", False))
    return {"columns": [{**{"datatype": kind}, **({"key": True} if key else {}), "name": name}
                        for name, kind, key in fields],
            "instances": [{"instance_name": "", "rows": []}],
            "name": "ResourceRemoteSupport"}


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    assert sha(PARENT) == PARENT_SHA and sha(D01) == D01_SHA
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    d01 = json.loads(D01.read_text(encoding="utf-8"))
    model = copy.deepcopy(parent)
    pd = table(model, "ProblemDescription")
    put(pd, row(pd), "PDESC", f"C09.var04 primary system maintenance remote resource {variant}")
    system = table(model, "System")
    put(system, row(system), "FRT", 2_000_000.0)
    # C03 is the direct parent; D01 supplies the accepted direct system repair
    # row shape. The new main task is the sole maintenance resource demand.
    repair = table(model, "SystemRepair")
    repair_row = copy.deepcopy(row(table(d01, "SystemRepair")))
    for field, value in (("DIRPT", 0.5), ("SURPT", 0.0),
                         ("DIRPF", 1.0), ("SURPF", 1.0),
                         ("DIRPTID", "C09-DIRP"), ("SURPTID", None)):
        put(repair, repair_row, field, value)
    add(repair, repair_row)
    tasks = table(model, "Tasks")
    task = empty_row(tasks)
    put(tasks, task, "TID", "C09-DIRP")
    put(tasks, task, "DESCR", "Direct system repair needing borrowed mechanic")
    add(tasks, task)
    breakdown = table(model, "TaskBreakDown")
    subtask = empty_row(breakdown)
    for field, value in (("TID", "C09-DIRP"), ("SEQ", 1),
                         ("SUTID", "<REPAIR>"), ("DURN", 0.5)):
        put(breakdown, subtask, field, value)
    add(breakdown, subtask)
    stations = table(model, "Station")
    remote_station = copy.deepcopy(row(stations))
    put(stations, remote_station, "STID", "BASE-02")
    put(stations, remote_station, "DESCR", "Remote lending base")
    add(stations, remote_station)
    resources = table(model, "Resource")
    mechanic = empty_row(resources)
    for field, value in (("RID", "P-MECH"), ("DESCR", "Primary system mechanic"),
                         ("TYPE", "SPECIAL")):
        put(resources, mechanic, field, value)
    add(resources, mechanic)
    allocation = table(model, "ResourceAllocation")
    allocated = empty_row(allocation)
    for field, value in (("POINT", "AIR_BASIC"), ("RID", "P-MECH"),
                         ("STID", "BASE-01" if variant == "local" else "BASE-02"),
                         ("RQTY", 1.0)):
        put(allocation, allocated, field, value)
    add(allocation, allocated)
    task_resources = table(model, "TaskResource")
    needed = empty_row(task_resources)
    for field, value in (("TID", "C09-DIRP"), ("RID", "P-MECH"),
                         ("QTY", 1), ("RPROB", 1.0),
                         ("ENRMS", "N" if variant == "remote-disabled" else "Y")):
        put(task_resources, needed, field, value)
    add(task_resources, needed)
    if variant != "local":
        route = remote_support_table()
        add(route, ["P-MECH", "BASE-01", "BASE-02", 0.25, 0.5, 0.125, None])
        model["model"]["tables"].append(route)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {}
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        dest = HERE / f"{variant}-input.json"
        if args.write:
            if dest.exists():
                raise FileExistsError(dest)
            dest.write_bytes(raw)
        elif dest.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {variant}")
        result[variant] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "d01_template_sha256": D01_SHA,
                      "inputs_sha256": result}))


if __name__ == "__main__":
    main()
