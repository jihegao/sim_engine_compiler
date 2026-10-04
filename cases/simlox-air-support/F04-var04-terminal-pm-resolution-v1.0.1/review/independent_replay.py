"""Independent read-only replay of F04.var04 v1.0.1 native evidence."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "F04-var01-deterministic-43day-v1.0.1"
DIAG = BASE / "F04-var04-terminal-pm-resolution-v1.0.0"
RUN = CASE / "runs/f04-var04-terminal-pm-v101-ssh-20261004-01"
PARENT_RUN = PARENT / "runs/f04-var01-repeat-a-v101-ssh-20261004-01"
DIAG_RUN = DIAG / "runs/f04-var04-terminal-pm-v100-ssh-20261004-01"
VERDICT = Path(__file__).with_name("independent-verdict.json")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, native_report=False):
    raw = path.read_text(encoding="utf-8-sig")
    if native_report:
        # One final trailing comma is produced by this native default exporter.
        raw = re.sub(r",(?=\s*\]\s*\}\s*\}\s*$)", "", raw)
    return json.loads(raw)


def tables(document, branch):
    return {table["name"]: table for table in document[branch]["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table):
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row, strict=True)) for row in rows(table)]


class Audit:
    def __init__(self):
        self.count = 0
        self.failures = []

    def check(self, condition, label):
        self.count += 1
        if not condition:
            self.failures.append(label)

    def equal(self, actual, expected, label):
        self.check(actual == expected, label)


def main():
    a = Audit()
    contract = read(CASE / "contract.json")
    closure = read(RUN / "closure.json")
    invocation = read(RUN / "invocation.json")
    steps = read(RUN / "steps.json")
    source = read(CASE / "native-input.json")
    parent_source = read(PARENT / "native-input.json")
    diagnostic_source = read(DIAG / "native-input.json")
    pp = contract["accepted_parent"]
    dd = contract["excluded_diagnostic"]

    pinned = {
        CASE / "native-input.json": contract["input_sha256"],
        CASE / "exact-diff.json": contract["exact_diff_sha256"],
        PARENT / "native-input.json": pp["input_sha256"],
        PARENT_RUN / "closure.json": pp["closure_sha256"],
        PARENT / "cli-scope-signoff-2026-10-04.md": pp["signoff_sha256"],
        PARENT_RUN / "report-raw.json": pp["default_report_sha256"],
        PARENT_RUN / "model.log": pp["event_log_sha256"],
        DIAG / "native-input.json": dd["input_sha256"],
        DIAG_RUN / "closure.json": dd["closure_sha256"],
    }
    for path, expected in pinned.items():
        a.equal(sha(path), expected, f"lineage SHA {path.parent.name}/{path.name}")
    a.equal(sha(CASE / "contract.json"), closure["source_hashes_before"]["contract"], "frozen contract SHA")
    a.equal(sha(RUN / "closure.json"), "f1a56fa36eae0f8b6f0d810f743980bdf430d7d8883781f8266dc0a1549886f0", "native closure SHA")
    for filename in ["build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1"]:
        a.equal(sha(CASE / filename), closure["source_hashes_before"][filename], f"current source SHA {filename}")

    ptab, ctab, dtab = (tables(doc, "model") for doc in [parent_source, source, diagnostic_source])
    a.equal(list(ctab), list(ptab), "32 source table names/order")
    a.equal(len(ctab), 32, "32 authored tables")
    changes = []
    old_changes = []
    for name in ptab:
        p, c, d = ptab[name], ctab[name], dtab[name]
        a.equal(c["columns"], p["columns"], f"source columns {name}")
        pr, cr, dr = rows(p), rows(c), rows(d)
        a.equal(len(cr), len(pr), f"source row count {name}")
        for i, (one, two, old) in enumerate(zip(pr, cr, dr), 1):
            for j, (before, after, prior) in enumerate(zip(one, two, old)):
                if before != after:
                    changes.append({"table": name, "row": i, "column": c["columns"][j]["name"], "from": before, "to": after})
                if prior != after:
                    old_changes.append((name, i, c["columns"][j]["name"]))
    a.equal(changes, read(CASE / "exact-diff.json")["changed_cells"], "exact parent-to-child five-cell delta")
    a.equal(len(changes), 5, "five changed cells")
    a.equal(old_changes, [("ProblemDescription", 1, "PDESC")], "v1.0.0 to v1.0.1 description only")
    a.equal(rows(ctab["Control"])[0][1], 1032.5, "continued simulation horizon")

    a.equal(closure["error"], None, "native closure error null")
    a.equal(closure["source_hashes_before"], closure["source_hashes_after"], "source seals before/after")
    a.equal(sha(RUN / "invocation.json"), closure["invocation_sha256"], "invocation seal")
    a.equal(invocation["source_hashes_before"], closure["source_hashes_before"], "invocation source seal")
    a.equal(invocation["session_id"], 0, "SSH session 0")
    a.equal(invocation["execution_mode"], "ssh_cli_v1", "SSH CLI mode")
    a.check("sshd.exe" in [name.lower() for name in invocation["ssh_ancestor_names"]], "sshd ancestor")
    a.equal(invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue", "global queue mutex")
    a.equal(invocation["gui"]["pid"], 13340, "GUI PID")
    a.check(invocation["gui"]["session_id"] > 0, "GUI interactive session")
    a.equal(len(closure["raw"]), 12, "twelve raw seals")
    for filename, seal in sorted(closure["raw"].items()):
        a.equal((RUN / filename).stat().st_size, seal["bytes"], f"raw size {filename}")
        a.equal(sha(RUN / filename), seal["sha256"], f"raw SHA {filename}")
    a.equal([step["name"] for step in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five completed steps")
    for step in steps:
        a.equal(step["exit_code"], 0, f"step exit {step['name']}")
        if step["name"] != "check_import_export":
            a.equal(step["gui_preserved"], True, f"GUI preservation {step['name']}")
    log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    a.check(bool(re.search(r"Input conversion completed\. Errors: 0, Warnings: 3, Notes: 0", log)), "converter totals")
    a.equal(re.findall(r"\(warning #(\d+)\)", log), ["108", "2053", "2053"], "converter warning IDs")
    a.check("(error #" not in log and "(notice #" not in log, "no unreviewed converter messages")

    exported = tables(read(RUN / "roundtrip-raw.json"), "model")
    populated = 0
    for name, table in ctab.items():
        if not rows(table):
            continue
        populated += 1
        a.check(name in exported, f"roundtrip table {name}")
        if name in exported:
            a.equal(exported[name]["columns"], table["columns"], f"roundtrip columns {name}")
            a.equal(exported[name]["instances"], table["instances"], f"roundtrip rows {name}")
    a.equal(populated, 30, "30 authored populated tables")
    a.equal(read(RUN / "roundtrip-validation.json")["passed"], True, "author roundtrip corroborated")

    old_lines = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
    new_lines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
    diag_lines = (DIAG_RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
    first_boundary = lambda lines: next(i for i, line in enumerate(lines) if line.startswith("Time: 1032 "))
    a.equal(new_lines[2:first_boundary(new_lines)], old_lines[2:first_boundary(old_lines)], "exact pre-h1032 event prefix")
    a.equal(new_lines[2:], diag_lines[2:], "fresh/diagnostic event log equality after horizon header")
    a.check(not any("system PM task 533" in line and "completed" in line for line in old_lines), "parent leaves PM533 uncompleted")
    boundary = new_lines[first_boundary(new_lines):]
    expected_events = [
        "subtask 533 seqno 1 within system PM task 533 on <TEACH-AIR-01,6> completed",
        "<P-MAINT at <BASE-02,0>> deallocated from  maintenance task: 1  available now: 1",
        "system PM task 533 on <TEACH-AIR-01,6> completed",
        "<TEACH-AIR-01,6> nbr ready increased at unit",
        "System ready <TEACH-AIR-01,6>",
    ]
    for phrase in expected_events:
        a.check(any(line.startswith("Time: 1032 ") and phrase in line for line in boundary), f"h1032 event {phrase}")

    parent_report = tables(read(PARENT_RUN / "report-raw.json", native_report=True), "report")
    current_report = tables(read(RUN / "report-raw.json", native_report=True), "report")
    diagnostic_report = tables(read(DIAG_RUN / "report-raw.json", native_report=True), "report")
    for name in current_report:
        if name == "ProblemDescription":
            continue
        a.equal(current_report[name]["columns"], diagnostic_report[name]["columns"], f"diagnostic report columns {name}")
        new_rows, diag_rows = rows(current_report[name]), rows(diagnostic_report[name])
        a.equal(len(new_rows), len(diag_rows), f"diagnostic report row count {name}")
        for i, (new, prior) in enumerate(zip(new_rows, diag_rows), 1):
            a.equal(new, prior, f"fresh/diagnostic report {name} row {i}")
    for name in ["StockTotalResults", "ResourceResults"]:
        parent_rows, new_rows = rows(parent_report[name]), rows(current_report[name])
        a.equal(len(parent_rows), 2064, f"parent {name} bins")
        a.equal(len(new_rows), 2065, f"continued {name} bins")
        for i, (before, after) in enumerate(zip(parent_rows, new_rows), 1):
            a.equal(after, before, f"exact {name} prefix row {i}")
    parent_system = records(parent_report["SystemResults"])
    new_system = records(current_report["SystemResults"])
    a.equal(len(parent_system), 2064, "parent System bins")
    a.equal(len(new_system), 2065, "continued System bins")
    exceptions = []
    for i, (before, after) in enumerate(zip(parent_system, new_system)):
        for field in before:
            if before[field] != after[field]:
                exceptions.append((i, field, before[field], after[field]))
            elif i != 2062:
                a.equal(after[field], before[field], f"System prefix {i}/{field}")
    a.equal(exceptions, [(2062, "SYDT", None, 1), (2062, "NSYDT", 0, 1)], "only finalized System downtime exception")
    a.equal((new_system[-1]["STINT"], new_system[-1]["ETINT"]), (1032, 1032.5), "one added half-hour System bin")
    a.check(7.99 <= new_system[-1]["NSYRY"] <= 8, "terminal near-eight ready")
    a.check(0 <= new_system[-1]["NSYPM"] <= .01, "terminal near-zero PM occupancy")
    resource_last = records(current_report["ResourceResults"])[-1]
    a.check(0 <= resource_last["NRUM"] <= .01, "terminal near-zero resource use")
    a.equal((resource_last["STINT"], resource_last["ETINT"]), (1032, 1032.5), "resource added bin horizon")

    summary_parent = records(parent_report["ResultSummary"])[0]
    summary_child = records(current_report["ResultSummary"])[0]
    summary_changes = [(k, summary_parent[k], summary_child[k]) for k in summary_parent if summary_parent[k] != summary_child[k]]
    a.equal(summary_changes, [("RTIUP", 1032, 1032.5)], "ResultSummary upper-bound-only change")
    a.equal(summary_child["MSUF"], 1, "mission success fraction unchanged")
    a.equal(summary_child["MTMF"], 1, "mission terminal fraction unchanged")
    a.check(all(row["NFAIL"] == 0 for row in new_system), "no System failure bins")
    stock = records(current_report["StockTotalResults"])
    a.check(all(row["NBO"] == 0 for row in stock), "no stock backorder bins")
    a.equal((stock[-1]["STINT"], stock[-1]["ETINT"]), (1032, 1032.5), "stock added bin horizon")

    output = {
        "schema": "f04-var04-independent-readonly-replay/v1",
        "passed": not a.failures,
        "verdict": "GO_BOUNDED" if not a.failures else "NO_GO",
        "checks_total": a.count,
        "checks_passed": a.count - len(a.failures),
        "failures": a.failures,
        "fingerprints": {
            "input_sha256": sha(CASE / "native-input.json"),
            "contract_sha256": sha(CASE / "contract.json"),
            "exact_diff_sha256": sha(CASE / "exact-diff.json"),
            "closure_sha256": sha(RUN / "closure.json"),
            "accepted_parent_closure_sha256": sha(PARENT_RUN / "closure.json"),
            "excluded_diagnostic_closure_sha256": sha(DIAG_RUN / "closure.json"),
        },
        "observations": {
            "system_prefix_exception": exceptions,
            "added_bin": {"NSYRY": new_system[-1]["NSYRY"], "NSYPM": new_system[-1]["NSYPM"], "NRUM": resource_last["NRUM"]},
            "system_bins": len(new_system),
            "stock_bins": len(stock),
            "resource_bins": len(records(current_report["ResourceResults"])),
            "summary_changes": summary_changes,
        },
        "limits": [
            "One deterministic CAL24 PM at the 1032 h boundary; parent does not establish positive remaining work duration.",
            "The event log establishes PM completion; the added-bin occupancy retains a small time-sampling smear.",
            "The preterminal System downtime counters are retrospectively finalized in the continuation.",
            "Unfinished repair, transit, reserved stock, alternate seeds, GUI visuals, and cross-engine results remain unverified.",
        ],
    }
    VERDICT.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{output['verdict']}: {output['checks_passed']}/{output['checks_total']} checks")
    for failure in a.failures[:20]:
        print("FAIL:", failure)
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
