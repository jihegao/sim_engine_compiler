"""Pure synthetic rejection probes for the reviewer-owned I03.var06 replay."""

from __future__ import annotations

import importlib.util
import json
import struct
from copy import deepcopy
from pathlib import Path


PKG = Path(__file__).resolve().parents[1]
METHOD = Path(__file__).with_name("independent_replay.py")
spec = importlib.util.spec_from_file_location("independent_i03_var06", METHOD)
assert spec and spec.loader
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def rejects(call, label: str) -> None:
    try:
        call()
    except (AssertionError, ValueError, KeyError, TypeError, UnicodeError):
        return
    raise AssertionError("accepted mutation: " + label)


def change_one(text: str, old: str, new: str) -> bytes:
    assert text.count(old) == 1, (old, text.count(old))
    return text.replace(old, new, 1).encode("utf-8")


def next_binary32(value: float) -> float:
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    return struct.unpack("<f", struct.pack("<I", bits + 1))[0]


def report_fixture(contract: dict, model: dict, expected: dict) -> dict:
    control = r.native_json((r.PARENT_RUN / "report-raw.json").read_bytes())
    meta = {t["name"]: t["columns"] for t in control["report"]["tables"]}
    out = []
    for spec in contract["report_gate"]["topology"]:
        name = spec["name"]
        out.append({"name": name, "columns": deepcopy(meta[name]),
                    "instances": [{"instance_name": spec["instance_name"],
                                   "rows": [[row[c] for c in spec["columns"]]
                                            for row in expected[name]]}]})
    return {"report": {"tables": out}}


def main() -> None:
    contract = json.loads((PKG / "contract.json").read_text(encoding="utf-8"))
    a = r.Audit()
    parent, child = r.parent_and_prediction(contract, a)
    authored = r.native_json((PKG / "native-input.json").read_bytes())
    r.child_input_check(child, authored, a)
    timeline = r.source_prediction()
    log_raw = (r.PARENT_RUN / "model.log").read_bytes()
    log = log_raw.decode("utf-8-sig")
    assert r.child_physical(log_raw, r.Audit()) == timeline
    expected = r.expected_report(contract, child, "child", timeline)
    fixture = report_fixture(contract, child, expected)
    r.compare_report(contract, child, fixture, "child", r.Audit(), timeline)
    rejected = 0

    log_mutations = [
        ("transfer time: 0", "transfer time: 4", "OUT annotation4"),
        ("starts with 1 resources", "starts with 2 resources", "OUT quantity2"),
        ("arrives with 1 resources", "arrives with 0 resources", "OUT arrival0"),
        ("Resource transfer demand arrives from OUT-transfer", "Resource transfer backorder added", "backorder"),
        ("Time: 7.5  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
         "Time: 7.5  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 1", "wrong booked free"),
        ("Time: 8.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1",
         "Time: 8.5 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2", "wrong flight duration"),
        ("resource shift 0 ended at", "resource shift 1 ended at", "wrong terminal shift"),
    ]
    for old, new, label in log_mutations:
        raw = change_one(log, old, new)
        rejects(lambda raw=raw: r.child_physical(raw, r.Audit()), label)
        rejected += 1
    arrival = next(x for x in log.splitlines(keepends=True)
                   if "Time: 6" in x and "resource transfer task 0 (OUT)" in x and "arrives with 1 resources" in x)
    rejects(lambda: r.child_physical(log.replace(arrival, arrival + arrival, 1).encode("utf-8"), r.Audit()),
            "duplicate arrival")
    rejected += 1
    delayed = log.replace(arrival, "", 1)
    delayed = delayed.replace("Time: 19.5", arrival.replace("Time: 6", "Time: 10") + "Time: 19.5", 1)
    rejects(lambda: r.child_physical(delayed.encode("utf-8"), r.Audit()), "h10 delayed OUT arrival")
    rejected += 1
    departure = next(x for x in log.splitlines(keepends=True)
                     if "Time: 6" in x and "resource transfer task 0 (OUT)" in x and "starts with 1 resources" in x)
    rejects(lambda: r.child_physical(log.replace(departure, departure + departure, 1).encode("utf-8"), r.Audit()),
            "double OUT decrement")
    rejected += 1
    ready = next(x for x in log.splitlines(keepends=True)
                 if "Time: 7.5" in x and "nbr ready" in x)
    rejects(lambda: r.child_physical(log.replace(ready, ready + ready, 1).encode("utf-8"), r.Audit()),
            "extra ready edge")
    rejected += 1
    no_fail = next(x for x in log.splitlines(keepends=True) if x.strip() == "no failures")
    moved = log.replace(no_fail, "", 1) + no_fail
    rejects(lambda: r.child_physical(moved.encode("utf-8"), r.Audit()), "return continuation moved")
    rejected += 1

    table_by_name = {t["name"]: t for t in fixture["report"]["tables"]}
    total = table_by_name["ResourceResultsTotal"]
    for field in ("NR", "NRA", "NRN", "NRUM", "NRW"):
        altered = deepcopy(fixture)
        t = next(x for x in altered["report"]["tables"] if x["name"] == "ResourceResultsTotal")
        col = [x["name"] for x in t["columns"]].index(field)
        value = t["instances"][0]["rows"][0][col]
        t["instances"][0]["rows"][0][col] = next_binary32(value)
        rejects(lambda altered=altered: r.compare_report(contract, child, altered, "child", r.Audit(), timeline),
                field + " total one representable-float step")
        rejected += 1
    for name, field, value, label in [
        ("SystemResults", "NSYWR", 1e-9, "exact zero residue"),
        ("SystemResults", "NPSTA", True, "bool count"),
        ("StockTotalResults", "WTS", 0, "null to zero"),
        ("ResourceResults", "NR", 2, "resource availability"),
    ]:
        altered = deepcopy(fixture)
        t = next(x for x in altered["report"]["tables"] if x["name"] == name)
        col = [x["name"] for x in t["columns"]].index(field)
        row = 12 if name == "ResourceResults" else 0
        t["instances"][0]["rows"][row][col] = value
        rejects(lambda altered=altered: r.compare_report(contract, child, altered, "child", r.Audit(), timeline), label)
        rejected += 1
    for label, mutate in [
        ("duplicate report table", lambda x: x["report"]["tables"].append(deepcopy(x["report"]["tables"][-1]))),
        ("duplicate report instance", lambda x: x["report"]["tables"][2]["instances"].append(
            deepcopy(x["report"]["tables"][2]["instances"][0]))),
        ("extra table metadata", lambda x: x["report"]["tables"][0].__setitem__("extra", 0)),
        ("bool metadata key", lambda x: x["report"]["tables"][0]["columns"][0].__setitem__("key", True)),
        ("wrong instance", lambda x: x["report"]["tables"][2]["instances"][0].__setitem__("instance_name", "wrong")),
    ]:
        altered = deepcopy(fixture)
        mutate(altered)
        rejects(lambda altered=altered: r.compare_report(contract, child, altered, "child", r.Audit(), timeline), label)
        rejected += 1
    changed = deepcopy(child)
    next(x for x in changed["model"]["tables"] if x["name"] == "ResourceTransfer")["instances"][0]["rows"][0][5] = 0.0
    rejects(lambda: r.child_input_check(child, changed, r.Audit()), "export normalized TFDT0")
    rejected += 1
    rejects(lambda: r.native_json(b'{"model":{},"model":{}}'), "duplicate JSON key")
    rejected += 1
    rejects(lambda: r.native_json(b'{"model":{"value":NaN}}'), "nonfinite JSON number")
    rejected += 1
    commands, checkers = r.expected_stage_plan()
    plan = commands[:2] + checkers[:1] + commands[2:] + checkers[1:]
    invocation = {"created_utc": "2026-10-08T00:00:00Z",
                  "planned_commands": commands, "planned_checkers": checkers}
    stages = [{"sequence": i, "name": item["name"], "program": item["program"],
               "arguments": item["arguments"],
               "started_utc": f"2026-10-08T00:0{i}:00Z",
               "completed_utc": f"2026-10-08T00:0{i}:30Z"}
              for i, item in enumerate(plan)]
    r.check_step_metadata(invocation, stages, r.Audit())
    for label, change in [
        ("executed program", lambda x: x[2].__setitem__("program", "wrong.exe")),
        ("executed arguments", lambda x: x[3].__setitem__("arguments", "-calc-wrong")),
        ("stage sequence", lambda x: x[4].__setitem__("sequence", 3)),
        ("overlapping UTC stages", lambda x: x[2].__setitem__("started_utc", "2026-10-08T00:01:20Z")),
    ]:
        changed = deepcopy(stages)
        change(changed)
        rejects(lambda changed=changed: r.check_step_metadata(invocation, changed, r.Audit()), label)
        rejected += 1
    print(json.dumps({"schema": "i03-var06-independent-self-check/v1", "status": "STATIC_ONLY",
                      "predicted_report_cells": 5210, "semantic_rejections": rejected}, sort_keys=True))


if __name__ == "__main__":
    main()
