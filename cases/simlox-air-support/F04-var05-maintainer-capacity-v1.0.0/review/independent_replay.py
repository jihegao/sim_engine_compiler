"""Independent read-only replay for F04.var05 maintainer capacity."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
PARENT = CASE.parent / "F04-var01-deterministic-43day-v1.0.1"
RUN = CASE / "runs/f04-var05-maintainer-capacity-v100-ssh-20261004-01"
PARENT_RUN = PARENT / "runs/f04-var01-repeat-a-v101-ssh-20261004-01"
OUT = Path(__file__).with_name("independent-verdict.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, report=False):
    raw = path.read_text(encoding="utf-8-sig")
    if report:
        raw = re.sub(r",(?=\s*\]\s*\}\s*\}\s*$)", "", raw)
    return json.loads(raw)


def tables(doc, branch):
    return {table["name"]: table for table in doc[branch]["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table):
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row, strict=True)) for row in rows(table)]


class Audit:
    def __init__(self):
        self.total = 0
        self.failures = []

    def check(self, ok, label):
        self.total += 1
        if not ok:
            self.failures.append(label)

    def equal(self, actual, expected, label):
        self.check(actual == expected, label)

    def close(self, actual, expected, label, tol=1e-5):
        self.check(math.isclose(actual, expected, rel_tol=tol, abs_tol=tol), label)


def event_time(log, needle):
    matches = re.findall(r"^Time: ([0-9.]+)\s+" + re.escape(needle) + r"[^\n]*$", log, re.M)
    return [float(time) for time in matches]


def main():
    a = Audit()
    contract = load(CASE / "contract.json")
    closure = load(RUN / "closure.json")
    invocation = load(RUN / "invocation.json")
    steps = load(RUN / "steps.json")
    parent_pin = contract["accepted_parent"]
    pins = {
        CASE / "native-input.json": contract["input_sha256"],
        CASE / "exact-diff.json": contract["exact_diff_sha256"],
        PARENT / "native-input.json": parent_pin["input_sha256"],
        PARENT_RUN / "closure.json": parent_pin["closure_sha256"],
        PARENT / "cli-scope-signoff-2026-10-04.md": parent_pin["signoff_sha256"],
        PARENT_RUN / "report-raw.json": parent_pin["default_report_sha256"],
        PARENT_RUN / "model.log": parent_pin["event_log_sha256"],
    }
    for path, expected in pins.items():
        a.equal(sha(path), expected, f"frozen SHA {path.parent.name}/{path.name}")
    a.equal(sha(CASE / "contract.json"), closure["source_hashes_before"]["contract"], "contract SHA in native closure")
    a.equal(sha(RUN / "closure.json"), "4f70f8b874273313c500a09d6427ffd66dc3816a772bcfb106cfc1109564dcc8", "native closure SHA")
    for filename in ["build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1"]:
        a.equal(sha(CASE / filename), closure["source_hashes_before"][filename], f"current source SHA {filename}")

    parent = tables(load(PARENT / "native-input.json"), "model")
    child = tables(load(CASE / "native-input.json"), "model")
    a.equal(list(child), list(parent), "32 table names/order")
    a.equal(len(child), 32, "32 source tables")
    changes = []
    for name in parent:
        ptable, ctable = parent[name], child[name]
        a.equal(ctable["columns"], ptable["columns"], f"source columns {name}")
        before, after = rows(ptable), rows(ctable)
        a.equal(len(after), len(before), f"source rows {name}")
        for rowno, (old, new) in enumerate(zip(before, after), 1):
            for colno, (x, y) in enumerate(zip(old, new)):
                if x != y:
                    changes.append({"table": name, "row": rowno, "column": ctable["columns"][colno]["name"], "from": x, "to": y})
    a.equal(changes, load(CASE / "exact-diff.json")["changed_cells"], "exact parent-to-child two-cell diff")
    a.equal(len(changes), 2, "two changed cells")
    a.equal(records(child["ResourceAllocation"])[0]["RQTY"], 2, "BASE-01 maintainer capacity two")

    a.equal(closure["error"], None, "native closure error null")
    a.equal(closure["source_hashes_before"], closure["source_hashes_after"], "source seals before/after")
    a.equal(sha(RUN / "invocation.json"), closure["invocation_sha256"], "invocation seal")
    a.equal(invocation["source_hashes_before"], closure["source_hashes_before"], "invocation source seal")
    a.equal(invocation["session_id"], 0, "session zero")
    a.equal(invocation["execution_mode"], "ssh_cli_v1", "SSH CLI mode")
    a.check("sshd.exe" in [name.lower() for name in invocation["ssh_ancestor_names"]], "SSH daemon ancestor")
    a.equal(invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue", "serial native mutex")
    a.equal(invocation["gui"]["pid"], 13340, "GUI PID")
    a.check(invocation["gui"]["session_id"] > 0, "GUI interactive session")
    a.equal(len(closure["raw"]), 12, "twelve raw seals")
    for filename, seal in sorted(closure["raw"].items()):
        a.equal((RUN / filename).stat().st_size, seal["bytes"], f"raw size {filename}")
        a.equal(sha(RUN / filename), seal["sha256"], f"raw SHA {filename}")
    a.equal([step["name"] for step in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five steps")
    for step in steps:
        a.equal(step["exit_code"], 0, f"step exit {step['name']}")
        if step["name"] != "check_import_export":
            a.equal(step["gui_preserved"], True, f"GUI preserved {step['name']}")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    a.check("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in runlog, "converter totals")
    a.equal(re.findall(r"\(warning #(\d+)\)", runlog), ["108", "2053", "2053"], "reviewed warning sequence")
    a.check("(error #" not in runlog and "(notice #" not in runlog, "no unreviewed converter message")

    export = tables(load(RUN / "roundtrip-raw.json"), "model")
    populated = 0
    for name, table in child.items():
        if not rows(table):
            continue
        populated += 1
        a.check(name in export, f"roundtrip table {name}")
        if name in export:
            a.equal(export[name]["columns"], table["columns"], f"roundtrip columns {name}")
            a.equal(export[name]["instances"], table["instances"], f"roundtrip instances {name}")
    a.equal(populated, 30, "30 authored populated tables")
    a.equal(load(RUN / "roundtrip-validation.json")["passed"], True, "author checker corroboration")

    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    child_log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    a.equal(event_time(parent_log, "system PM task 8 on <TEACH-AIR-01,4> started"), [24.0], "parent first BASE-01 PM")
    a.equal(event_time(child_log, "system PM task 8 on <TEACH-AIR-01,4> started"), [24.0], "child first BASE-01 PM")
    a.equal(event_time(parent_log, "subtask 12 seqno 1 within system PM task 12 on <TEACH-AIR-01,0> books resources"), [25.0], "parent aircraft0 resource booking")
    a.equal(event_time(child_log, "subtask 12 seqno 1 within system PM task 12 on <TEACH-AIR-01,0> books resources"), [24.5], "child aircraft0 concurrent booking")
    a.equal(event_time(parent_log, "system PM task 12 on <TEACH-AIR-01,0> completed"), [26.0], "parent aircraft0 PM completion")
    a.equal(event_time(child_log, "system PM task 12 on <TEACH-AIR-01,0> completed"), [25.5], "child aircraft0 PM completion")
    a.equal(event_time(parent_log, "system PM task 13 on <TEACH-AIR-01,1> completed"), [27.0], "parent aircraft1 PM completion")
    a.equal(event_time(child_log, "system PM task 13 on <TEACH-AIR-01,1> completed"), [26.0], "child aircraft1 PM completion")
    a.check("Time: 24.5  subtask 12 seqno 1 within system PM task 12 on <TEACH-AIR-01,0> resource availability test\n  Availability test on  <P-MAINT at <BASE-01,0>> request for: 1 failed" in parent_log, "parent h24.5 failed availability")
    a.check("Time: 24.5  <P-MAINT at <BASE-01,0>> allocated to maintenance task: 1  available now: 0" in child_log, "child h24.5 second concurrent allocation")
    for label, text in [("parent", parent_log), ("child", child_log)]:
        a.equal(len(re.findall(r"^Time: [^\n]*  system PM task \d+ on <TEACH-AIR-01,\d+> started$", text, re.M)), 324, f"{label} PM starts")
        a.equal(len(re.findall(r"^Time: [^\n]*  system PM task \d+ on <TEACH-AIR-01,\d+> completed$", text, re.M)), 323, f"{label} PM completions before cutoff")
        for mission_type in ["BASE2-MISSION", "RISK-MISSION", "BASIC-MISSION"]:
            a.equal(len(re.findall(r"^Time: [^\n]*<" + mission_type + r",[^\n]*> mission success:\s*$", text, re.M)), 21, f"{label} 21 {mission_type} successes")
        a.equal(len(re.findall(r"^Time: [^\n]*System arrives <TEACH-AIR-01,\d+>, mission success,", text, re.M)), 105, f"{label} 105 successful aircraft sorties")
        a.check("mission aborted" not in text, f"{label} no mission abort")
        a.check("backorder" not in text.lower(), f"{label} no logged backorder")

    parent_report = tables(load(PARENT_RUN / "report-raw.json", report=True), "report")
    child_report = tables(load(RUN / "report-raw.json", report=True), "report")
    a.equal(rows(child_report["ResultSummary"]), rows(parent_report["ResultSummary"]), "mission ResultSummary exact equality")
    a.equal(records(child_report["ResultSummary"])[0]["MSUF"], 1, "mission success fraction one")
    for name in ["SystemResults", "StockTotalResults", "ResourceResults"]:
        before, after = records(parent_report[name]), records(child_report[name])
        a.equal(len(before), 2064, f"parent {name} 2064 bins")
        a.equal(len(after), 2064, f"child {name} 2064 bins")
        a.equal(child_report[name]["columns"], parent_report[name]["columns"], f"{name} column schema")
        for i, row in enumerate(after):
            a.equal((row["STINT"], row["ETINT"]), (i * .5, (i + 1) * .5), f"{name} half-hour bin {i}")
    stock_parent = records(parent_report["StockTotalResults"])
    stock_child = records(child_report["StockTotalResults"])
    for i, (before, after) in enumerate(zip(stock_parent, stock_child)):
        a.equal(after, before, f"Stock exact bin {i}")
        a.equal(after["NBO"], 0, f"Stock no-backorder bin {i}")
    system_parent = records(parent_report["SystemResults"])
    system_child = records(child_report["SystemResults"])
    resource_parent = records(parent_report["ResourceResults"])
    resource_child = records(child_report["ResourceResults"])
    for i, (system, resource) in enumerate(zip(system_child, resource_child)):
        a.equal(system["NFAIL"], 0, f"System no-failure bin {i}")
        a.equal(resource["NR"], 5, f"five allocated resources bin {i}")
        a.equal(resource["NRA"], 5, f"five available resource capacity bin {i}")
        a.check(0 <= system["NSYRY"] <= 8, f"bounded ready aircraft bin {i}")
    for i, resource in enumerate(resource_parent):
        a.equal(resource["NR"], 4, f"parent four resources bin {i}")
    total = records(child_report["ResourceResultsTotal"])[0]
    parent_total = records(parent_report["ResourceResultsTotal"])[0]
    child_wait = sum(.5 * row["NRW"] for row in resource_child)
    parent_wait = sum(.5 * row["NRW"] for row in resource_parent)
    child_work = sum(.5 * row["NRUM"] for row in resource_child)
    parent_work = sum(.5 * row["NRUM"] for row in resource_parent)
    a.close(child_wait, 21.0, "child queued resource-hours")
    a.close(parent_wait, 27.24975824356079, "parent queued resource-hours")
    a.check(child_wait < parent_wait, "queue reduced under extra maintainer")
    a.close(child_work, parent_work, "same aggregate PM work-hours", tol=.01)
    a.close(total["NRW"] * 1032, child_wait, "child Resource TOTAL wait normalization")
    a.close(parent_total["NRW"] * 1032, parent_wait, "parent Resource TOTAL wait normalization")
    a.close(total["NRUM"] * 1032, child_work, "child Resource TOTAL use normalization")
    a.close(parent_total["NRUM"] * 1032, parent_work, "parent Resource TOTAL use normalization")
    a.equal((total["NR"], parent_total["NR"]), (5, 4), "one extra total resource")
    a.equal(system_child[-1]["NSYRY"], system_parent[-1]["NSYRY"], "terminal ready aircraft")
    a.equal(system_child[-1]["NSYPM"], system_parent[-1]["NSYPM"], "terminal PM occupancy")
    a.equal(stock_child[-1], stock_parent[-1], "terminal stock state")
    for field in ["NPMT", "NPMS", "NPSTA", "NPSUC", "NFAIL"]:
        a.equal(sum(row[field] for row in system_child), sum(row[field] for row in system_parent), f"System event-count integral {field}")

    result = {
        "schema": "f04-var05-independent-readonly-replay/v1",
        "passed": not a.failures,
        "verdict": "GO_BOUNDED" if not a.failures else "NO_GO",
        "checks_total": a.total,
        "checks_passed": a.total - len(a.failures),
        "failures": a.failures,
        "fingerprints": {"input_sha256": sha(CASE / "native-input.json"), "contract_sha256": sha(CASE / "contract.json"), "exact_diff_sha256": sha(CASE / "exact-diff.json"), "closure_sha256": sha(RUN / "closure.json"), "parent_closure_sha256": sha(PARENT_RUN / "closure.json")},
        "observations": {"bins_per_series": 2064, "parent_wait_hours": parent_wait, "child_wait_hours": child_wait, "parent_work_hours": parent_work, "child_work_hours": child_work, "aircraft0_parent_pm_completed_h": 26.0, "aircraft0_child_pm_completed_h": 25.5, "mission_successes": 63, "aircraft_sorties": 105, "terminal_ready_aircraft": system_child[-1]["NSYRY"]},
        "limits": ["One deterministic, fixed-seed, two-base 43-day contrast; not a general staffing or stochastic availability estimate.", "Later PM and mission timing can diverge as whole-model consequences; only first-wave concurrent booking is directly isolated.", "One PM remains open at the 1032 h terminal cutoff in both arms.", "Other resource classes, stock settings, random failures, GUI visuals and cross-engine behavior remain unverified."],
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{result['verdict']}: {result['checks_passed']}/{result['checks_total']} checks")
    for failure in a.failures[:20]:
        print("FAIL:", failure)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
