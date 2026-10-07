"""In-memory semantic mutations after the original sealed replay passes.

No original source or raw file is modified. This imports only the independent
reviewer replay, never the author's implementation.
"""

import json
import pathlib
import runpy
import struct
from copy import deepcopy

ROOT = pathlib.Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT / "review/independent_replay.py"))
A = M["Audit"]
run = ROOT.parent / "I03-var06-out-ignored-duration-v1.0.0/runs/i03-var06-out-dt4-v100-ssh-20261008-01"
raw = (run / "model.log").read_bytes()
report = M["native_json"]((run / "report-raw.json").read_bytes())
contract = M["native_json"]((ROOT / "contract.json").read_bytes())
baseline = A()
parent, predicted = M["parent_and_prediction"](contract, baseline)
timeline = M["child_physical"](raw, baseline, role="child")
M["compare_report"](contract, predicted, report, "child", baseline, timeline)

rejected = []


def reject(name, action):
    try:
        action(A())
    except (AssertionError, ValueError, KeyError, IndexError) as exc:
        rejected.append({"name": name, "reason_type": type(exc).__name__})
    else:
        raise AssertionError("semantic mutation escaped: " + name)


def mutate_log(name, old, new):
    old = old.encode("utf-8")
    new = new.encode("utf-8")
    assert raw.count(old) == 1, (name, raw.count(old))
    mutated = raw.replace(old, new, 1)
    reject(name, lambda a: M["child_physical"](mutated, a, role="child"))


def mutate_report(name, table, row, column, value):
    mutated = deepcopy(report)
    target = next(t for t in mutated["report"]["tables"] if t["name"] == table)
    columns = [c["name"] for c in target["columns"]]
    target["instances"][0]["rows"][row][columns.index(column)] = value
    reject(name, lambda a: M["compare_report"](contract, predicted, mutated,
                                                 "child", a, timeline))


# Task duration and linked arrival are read directly from the original log.
mutate_log("printed4_to0", b"starts with 1 resources, transfer time: 4".decode(),
           "starts with 1 resources, transfer time: 0")
mutate_log("printed4_to3", "starts with 1 resources, transfer time: 4",
           "starts with 1 resources, transfer time: 3")
mutate_log("arrival10_to9point5", "Time: 10 resource transfer task 0 (OUT)  arrives with 1 resources",
           "Time: 9.5 resource transfer task 0 (OUT)  arrives with 1 resources")
mutate_log("arrival_wrong_task", "Time: 10 resource transfer task 0 (OUT)  arrives with 1 resources",
           "Time: 10 resource transfer task 1 (OUT)  arrives with 1 resources")
mutate_log("arrival_wrong_quantity", "Time: 10 resource transfer task 0 (OUT)  arrives with 1 resources",
           "Time: 10 resource transfer task 0 (OUT)  arrives with 2 resources")
mutate_log("booking_free_count", "allocated to maintenance task: 1  available now: 0",
           "allocated to maintenance task: 1  available now: 1")
mutate_log("mission_duration", "mission starting, duration: 1",
           "mission starting, duration: 2")
mutate_log("untimed_return_continuation", " no PMTasks", " no PMTasks changed")

line = b"Time: 10 resource transfer task 0 (OUT)  arrives with 1 resources"
assert raw.count(line) == 1
reject("duplicate_arrival", lambda a: M["child_physical"](raw.replace(line, line + b"\r\n" + line, 1), a,
                                                             role="child"))
start = b"Time: 6 resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 4"
assert raw.count(start) == 1
reject("double_local_decrement", lambda a: M["child_physical"](raw.replace(start, start + b"\r\n" + start, 1), a,
                                                                   role="child"))

# Exact report topology, nulls, whole bins, zeros and all five binary32 means.
mutate_report("whole_bin_nominal", "ResourceResults", 13, "NRN", 1.00001)
mutate_report("whole_zero_occupancy", "SystemResults", 0, "NSYMO", 1e-9)
stock = next(t for t in report["report"]["tables"] if t["name"] == "StockTotalResults")
stock_cols = [c["name"] for c in stock["columns"]]
null_col = next(c for c in stock_cols if stock["instances"][0]["rows"][0][stock_cols.index(c)] is None)
mutate_report("stock_null_to_zero", "StockTotalResults", 0, null_col, 0)

for field in ("NR", "NRA", "NRN", "NRUM", "NRW"):
    table = next(t for t in report["report"]["tables"] if t["name"] == "ResourceResultsTotal")
    cols = [c["name"] for c in table["columns"]]
    value = table["instances"][0]["rows"][0][cols.index(field)]
    bits = int.from_bytes(struct.pack("<f", value), "little")
    next_float = struct.unpack("<f", (bits + 1).to_bytes(4, "little"))[0]
    mutate_report("binary32_one_ulp_" + field, "ResourceResultsTotal", 0, field, next_float)

meta = deepcopy(report)
meta["report"]["tables"].append(deepcopy(meta["report"]["tables"][0]))
reject("duplicate_report_table", lambda a: M["compare_report"](contract, predicted, meta,
                                                                   "child", a, timeline))
meta = deepcopy(report)
meta["report"]["tables"][0]["instances"][0]["instance_name"] = "changed"
reject("instance_metadata", lambda a: M["compare_report"](contract, predicted, meta,
                                                              "child", a, timeline))
meta = deepcopy(report)
meta["report"]["tables"][2]["columns"][0]["datatype"] = True
reject("bool_column_metadata", lambda a: M["compare_report"](contract, predicted, meta,
                                                                 "child", a, timeline))

export = M["native_json"]((run / "roundtrip-raw.json").read_bytes())
bad = deepcopy(export)
bad["model"]["tables"].append(deepcopy(bad["model"]["tables"][0]))
reject("duplicate_source_table", lambda a: M["roundtrip"](predicted, bad, a, "mutated export"))
bad = deepcopy(export)
transfer = next(t for t in bad["model"]["tables"] if t["name"] == "ResourceTransfer")
transfer["instances"][0]["rows"][0][5] = 0
reject("export_TFDT4_to0", lambda a: M["roundtrip"](predicted, bad, a, "mutated export"))

print(json.dumps({"schema": "i03-var06-independent-retrospective-self-check/v1",
                  "passed": True, "baseline_semantic_checks": baseline.checks,
                  "negative_rejections": rejected}, sort_keys=True, indent=2))
