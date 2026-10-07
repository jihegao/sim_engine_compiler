"""Unsealed semantic probes for reviewer-owned I03.var11 pure fixture.

These inputs are synthetic and never substitute for original native child raw.
"""

from __future__ import annotations

import importlib.util
import json
import math
import pathlib
import struct
from copy import deepcopy

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("reviewer_var11", HERE / "independent_replay_candidate_v5.py")
assert spec and spec.loader
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
contract = json.loads((r.PKG / "contract.json").read_text(encoding="utf-8"))
parent, child = r.parent_and_prediction(contract, r.Audit())
parent_raw = (r.PARENT_RUN / "model.log").read_bytes()
fixture = r.pure_child_fixture(parent_raw)
timeline = r.child_physical(fixture, r.Audit(), role="child")
expected = r.expected_report(contract, child, "child", timeline)
template_doc = r.native_json((r.PARENT_RUN / "report-raw.json").read_bytes())


def reject(label, fn):
    try:
        fn()
    except (AssertionError, ValueError, KeyError, TypeError, IndexError):
        return label
    raise AssertionError("semantic mutation escaped: " + label)


def replace_once(raw, old, new):
    old, new = old.encode(), new.encode()
    assert raw.count(old) == 1, (old, raw.count(old))
    return raw.replace(old, new, 1)


def check_log(raw):
    r.child_physical(raw, r.Audit(), role="child")


def report_doc():
    doc = deepcopy(template_doc)
    for table in doc["report"]["tables"]:
        name = table["name"]
        fields = [c["name"] for c in table["columns"]]
        table["instances"][0]["rows"] = [[row[field] for field in fields]
                                                 for row in expected[name]]
    return doc


def check_report(doc):
    r.compare_report(contract, child, doc, "child", r.Audit(), timeline)


def change_cell(table, row, column, value):
    doc = report_doc()
    t = next(t for t in doc["report"]["tables"] if t["name"] == table)
    j = next(j for j, c in enumerate(t["columns"]) if c["name"] == column)
    t["instances"][0]["rows"][row][j] = value
    return doc


def check_source(doc):
    r.child_input_check(child, doc, r.Audit())


def adjacent_f32(value, sign):
    bits = struct.unpack("<I", struct.pack("<f", value))[0]
    assert value > 0 and sign in (-1, 1)
    return struct.unpack("<f", struct.pack("<I", bits + sign))[0]


# Positive baseline traverses the complete 5,210-cell comparator. Every later
# report mutation changes only one field in this already accepted pure fixture.
check_report(report_doc())


rejects = []
rejects.append(reject("printed40_to39", lambda: check_log(replace_once(
    fixture, "starts with 1 resources, transfer time: 40",
    "starts with 1 resources, transfer time: 39"))))
rejects.append(reject("printed40_to4", lambda: check_log(replace_once(
    fixture, "starts with 1 resources, transfer time: 40",
    "starts with 1 resources, transfer time: 4"))))
rejects.append(reject("wrong_out_quantity", lambda: check_log(replace_once(
    fixture, "starts with 1 resources, transfer time: 40",
    "starts with 2 resources, transfer time: 40"))))
rejects.append(reject("wrong_out_station", lambda: check_log(replace_once(
    fixture, "created: starting from  <P-CREW at <BASE-01,0>>",
    "created: starting from  <P-CREW at <BASE-02,0>>"))))
rejects.append(reject("missing_out_demand", lambda: check_log(replace_once(
    fixture, "Time: 6  <P-CREW at <BASE-01,0>> Resource transfer demand arrives from OUT-transfer \r\n",
    ""))))
rejects.append(reject("h10_linked_arrival", lambda: check_log(
    fixture.replace(b"Time: 19.5", b"Time: 10  resource transfer task 0 (OUT)  arrives with 1 resources\r\nTime: 19.5", 1))))
rejects.append(reject("h36_linked_arrival", lambda: check_log(
    fixture + b"\r\nTime: 36  resource transfer task 0 (OUT)  arrives with 1 resources\r\n")))
rejects.append(reject("duplicate_out_start", lambda: check_log(
    fixture.replace(b"Time: 6  resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 40",
                    b"Time: 6  resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 40\r\nTime: 6  resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 40", 1))))
rejects.append(reject("extra_backorder", lambda: check_log(
    fixture.replace(b"Time: 7.5", b"Time: 7  <P-CREW at <BASE-01,0>> Resource transfer backorder added\r\nTime: 7.5", 1))))
rejects.append(reject("wrong_booking_available", lambda: check_log(replace_once(
    fixture, "allocated to maintenance task: 1  available now: 0",
    "allocated to maintenance task: 1  available now: 1"))))
rejects.append(reject("orphan_queue_snapshot", lambda: check_log(
    fixture.replace(b"Time: 8  system preparation task 0", b"  Tasks waiting for resources at: <BASE-01,0> 1\r\nTime: 8  system preparation task 0", 1))))
rejects.append(reject("duplicate_ready_edge", lambda: check_log(
    fixture.replace(b"Time: 9.5 <TEACH-AIR-01,0> nbr ready increased",
                    b"Time: 9.5 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>\r\nTime: 9.5 <TEACH-AIR-01,0> nbr ready increased", 1))))
rejects.append(reject("wrong_mission_request", lambda: check_log(replace_once(
    fixture, "mission activated, systems requested: 2",
    "mission activated, systems requested: 3"))))
rejects.append(reject("missing_return_continuation", lambda: check_log(replace_once(
    fixture, "  no failures\r\n  no PMTasks", "  no PMTasks"))))

rejects.append(reject("report_exact_zero_residue", lambda: check_report(change_cell(
    "SystemResults", 0, "NSYAL", 1e-9))))
rejects.append(reject("report_integer_whole_bin", lambda: check_report(change_cell(
    "ResourceResults", 0, "NR", 2.00001))))
rejects.append(reject("report_null_to_zero", lambda: check_report(change_cell(
    "StockTotalResults", 0, "ROS", 0))))
rejects.append(reject("report_bool_numeric", lambda: check_report(change_cell(
    "SystemResults", 0, "NSYA", True))))
rejects.append(reject("report_description_wrong", lambda: check_report(change_cell(
    "ProblemDescription", 0, "PDESC", "wrong"))))
rejects.append(reject("report_duplicate_table", lambda: check_report(
    {"report": {"tables": report_doc()["report"]["tables"] +
                 [deepcopy(report_doc()["report"]["tables"][0])]}})))
for field in ("NR", "NRA", "NRN", "NRUM", "NRW"):
    old = expected["ResourceResultsTotal"][0][field]
    for direction in (1, -1):
        changed = adjacent_f32(old, direction)
        rejects.append(reject(f"total_{field}_{direction:+d}_f32ulp", lambda changed=changed, field=field:
                              check_report(change_cell("ResourceResultsTotal", 0, field, changed))))

source = deepcopy(child)
next(t for t in source["model"]["tables"] if t["name"] == "ResourceTransfer")["instances"][0]["rows"][0][5] = 4
rejects.append(reject("source_tfdt4", lambda: check_source(source)))
source = deepcopy(child)
next(t for t in source["model"]["tables"] if t["name"] == "ResourceTransfer")["instances"][0]["rows"][0][5] = True
rejects.append(reject("source_tfdt_bool", lambda: check_source(source)))
source = deepcopy(child)
source["model"]["tables"].append(deepcopy(source["model"]["tables"][0]))
rejects.append(reject("duplicate_source_table", lambda: check_source(source)))
source = deepcopy(child)
next(t for t in source["model"]["tables"] if t["name"] == "ResourceTransfer")["columns"][0]["key"] = 1
rejects.append(reject("bool_source_metadata", lambda: check_source(source)))

# The planned argv and UTC order gates are exercised on unsealed objects, so a
# raw SHA failure cannot mask an incorrectly accepted step transition.
commands, checkers = r.expected_stage_plan(r.CHILD_RUN)
planned = {x["name"]: x for x in commands + checkers}
names = ("import", "export", "check_import_export", "calc", "jsonreport", "check_behavior")
invocation = {"created_utc": "2026-10-08T00:00:00Z",
              "planned_commands": commands, "planned_checkers": checkers}
steps = []
for index, name in enumerate(names):
    steps.append({"sequence": index, **planned[name],
                  "started_utc": f"2026-10-08T00:00:{2 * index + 1:02d}Z",
                  "completed_utc": f"2026-10-08T00:00:{2 * index + 2:02d}Z"})
r.check_step_metadata(invocation, steps, r.Audit(), run_dir=r.CHILD_RUN)
wrong = deepcopy(steps)
wrong[3]["arguments"] += " -unexpected"
rejects.append(reject("executed_calc_argv", lambda: r.check_step_metadata(
    invocation, wrong, r.Audit(), run_dir=r.CHILD_RUN)))
wrong = deepcopy(steps)
wrong[5]["program"] = "another-python.exe"
rejects.append(reject("executed_checker_program", lambda: r.check_step_metadata(
    invocation, wrong, r.Audit(), run_dir=r.CHILD_RUN)))
wrong = deepcopy(steps)
wrong[4]["started_utc"] = "2026-10-08T00:00:07Z"
rejects.append(reject("overlapping_native_stage", lambda: r.check_step_metadata(
    invocation, wrong, r.Audit(), run_dir=r.CHILD_RUN)))

# A future catalog append keeps the immutable 492-entry proof active. Corrupt
# prefix, metadata types and duplicate IDs are semantic failures in memory.
archive = r.native_json((r.PKG / "preserved-catalog/catalog-at-selection-492.bytes").read_bytes())
appended = deepcopy(archive)
extra = deepcopy(appended["entries"][-1])
extra["publication_id"] = "PURE-FUTURE-ENTRY-UNPUBLISHED"
appended["entries"].append(extra)
r.check_catalog_archive(archive, appended, r.Audit())
bad = deepcopy(appended)
bad["entries"][0]["publication_id"] += "-changed"
rejects.append(reject("catalog_prefix_change", lambda: r.check_catalog_archive(
    archive, bad, r.Audit())))
bad = deepcopy(appended)
meta = next(k for k in bad if k != "entries")
bad[meta] = [bad[meta]]
rejects.append(reject("catalog_metadata_type", lambda: r.check_catalog_archive(
    archive, bad, r.Audit())))
bad = deepcopy(appended)
bad["entries"][-1]["publication_id"] = bad["entries"][0]["publication_id"]
rejects.append(reject("catalog_duplicate_id", lambda: r.check_catalog_archive(
    archive, bad, r.Audit())))

print(json.dumps({"schema": "i03-var11-independent-self-check/v1",
                  "status": "PASS_PURE_FIXTURE_ONLY", "semantic_rejections": len(rejects),
                  "rejected": rejects, "parent_report_cells": 5210,
                  "predicted_child_report_cells": 5210}, sort_keys=True))
