"""Independent, read-only replay of the sealed J09.var04 native evidence.

Uses Python's standard library and raw source/run files; no author checker imports.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
CASES = CASE.parent
RUN_ID = "j09-var04-scpmi2-v100-ssh-20261004-01"
RUN = CASE / "runs" / RUN_ID
PARENT = CASES / "D03-calendar-pm-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d03-calendar-v100-ssh-20261001-02"
PRECEDENT = CASES / "J09-var06-transport-scale-v1.0.1"
VERDICT = HERE / "independent-verdict.json"
checks = 0
failures: list[str] = []


def check(ok: bool, description: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(description)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    data = path.read_text(encoding="utf-8-sig")
    # SIMLOX native JSON can put a comma immediately before a closing bracket.
    return json.loads(re.sub(r",\s*([}\]])", r"\1", data))


def table_map(document: dict, root: str) -> dict:
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


def names(table: dict) -> list[str]:
    return [column["name"] for column in table["columns"]]


def numeric_equal(actual, expected, tolerance: float = 0) -> bool:
    if actual is None or expected is None:
        return actual is expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return math.isclose(actual, expected, rel_tol=0, abs_tol=tolerance)
    return actual == expected


contract = read(CASE / "contract.json")
diff = read(CASE / "exact-diff.json")
invocation = read(RUN / "invocation.json")
closure = read(RUN / "closure.json")
steps = read(RUN / "steps.json")
parent_input_path = PARENT / "native-input.json"
precedent_input_path = PRECEDENT / "scaled-input.json"
source_paths = {
    "input": CASE / "scaled-input.json",
    "parent": parent_input_path,
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
    "precedent_input": precedent_input_path,
    "precedent_closure": PRECEDENT / "runs" / "j09-var06-sctrt2-v101-ssh-20261004-01" / "closure.json",
    "precedent_evidence_index": PRECEDENT / "evidence-index.json",
    "contract": CASE / "contract.json",
    "exact_diff": CASE / "exact-diff.json",
    "build.py": CASE / "build.py",
    "describe_diff.py": CASE / "describe_diff.py",
    "check_roundtrip.py": CASE / "check_roundtrip.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}

check(contract["case_id"] == "J09" and contract["variant_id"] == "J09.var04", "contract identity")
check(contract["parameters"]["expected_report_bins"] == 120, "60-hour, half-hour contract")
check(sha(parent_input_path) == contract["accepted_parent"]["input_sha256"], "accepted D03 input pin")
check(sha(PARENT_RUN / "closure.json") == contract["accepted_parent"]["closure_sha256"], "accepted D03 closure pin")
check(sha(source_paths["parent_signoff"]) == contract["accepted_parent"]["signoff_sha256"], "accepted D03 signoff pin")
check(sha(precedent_input_path) == contract["scale_schema_precedent"]["input_sha256"], "J09.var06 schema source pin")
check(sha(source_paths["precedent_closure"]) == contract["scale_schema_precedent"]["closure_sha256"], "J09.var06 closure pin")
check(sha(source_paths["precedent_evidence_index"]) == contract["scale_schema_precedent"]["evidence_index_sha256"], "J09.var06 index pin")
check(sha(source_paths["input"]) == contract["scaled_input_sha256"], "scaled input pin")
check(sha(source_paths["exact_diff"]) == contract["exact_diff_sha256"], "exact diff pin")
check(diff["parent_input_sha256"] == sha(parent_input_path), "diff parent source hash")
check(diff["scaled_input_sha256"] == sha(source_paths["input"]), "diff child source hash")

parent_tables = table_map(read(parent_input_path), "model")
child_tables = table_map(read(source_paths["input"]), "model")
check(len(parent_tables) == 31 and len(child_tables) == 32, "parent 31 and child 32 tables")
check(set(child_tables) == set(parent_tables) | {"ScaleFactors"}, "only ScaleFactors added")
for name in sorted(parent_tables):
    check(child_tables[name] == parent_tables[name], f"unchanged parent table {name}")
check(child_tables["ScaleFactors"] == diff["appended_table"], "exact appended ScaleFactors table")
check(diff["unchanged_existing_tables"] == 31 and diff["other_changes"] == [], "exact diff scope")
check(names(child_tables["ScaleFactors"]) == ["SCFRT", "SCRPT", "SCLDT", "SCPMI", "SCPMT", "SCTRT"], "scale columns")
check(rows(child_tables["ScaleFactors"]) == [[1, 1, 1, 2, 1, 1]], "SCPMI2 with all other scales one")
check(sum(bool(rows(t)) for t in parent_tables.values()) == 18, "parent 18 row-containing tables")
check(sum(bool(rows(t)) for t in child_tables.values()) == 19, "child 19 row-containing tables")

check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation closure hash")
check(invocation["run_id"] == RUN_ID and closure["run_id"] == RUN_ID, "run identity")
check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0, "SSH session 0")
check("sshd.exe" in invocation["ssh_ancestor_names"], "SSH ancestor")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI13340 separate session")
check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native queue mutex")
check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source hashes stable")
for key, path in sorted(source_paths.items()):
    check(path.is_file() and sha(path) == closure["source_hashes_before"].get(key), f"frozen source {key}")
for key, value in sorted(contract["source"].items()):
    source_key = {"simlox_exe_sha256": "exe", "manual_pdf_sha256": "manual", "dictionary_sha256": "dictionary"}[key]
    check(closure["source_hashes_before"][source_key] == value, f"frozen installed {source_key} fingerprint")
check(len(closure["raw"]) == 12, "twelve raw seals")
for filename, seal in sorted(closure["raw"].items()):
    path = RUN / filename
    check(path.is_file(), f"raw file present {filename}")
    if path.is_file():
        check(path.stat().st_size == seal["bytes"], f"raw byte count {filename}")
        check(sha(path) == seal["sha256"], f"raw SHA {filename}")
check(sha(RUN / "input.json") == sha(source_paths["input"]), "native input equals frozen source")
check(closure["error"] is None, "run closure no error")
check([x["name"] for x in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five native steps in order")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None, f"step completed {step['name']}")
for step in steps[:4]:
    check(step["gui_preserved"] is True, f"GUI preserved through {step['name']}")
for planned, actual in zip(invocation["planned_commands"], steps):
    check(planned["name"] == actual["name"] and planned["arguments"] == actual["arguments"], f"planned command {actual['name']}")
check((RUN / "model.sxo").stat().st_size > 100000, "usable simulation output")

export_tables = table_map(read(RUN / "roundtrip-raw.json"), "model")
check(set(export_tables) == set(child_tables), "native export all authored tables")
for name in sorted(child_tables):
    authored = child_tables[name]
    exported = export_tables[name]
    acols = names(authored)
    ecols = names(exported)
    check(set(acols).issubset(ecols), f"native export columns include authored {name}")
    if rows(authored):
        projected = [[r[ecols.index(col)] for col in acols] for r in rows(exported)]
        check(projected == rows(authored), f"lossless authored rows {name}")
    else:
        check(not any(any(value is not None for value in row) for row in rows(exported)), f"no substantive export rows {name}")
scale_export_columns = names(export_tables["ScaleFactors"])
scale_authored_columns = names(child_tables["ScaleFactors"])
check(all(all(row[scale_export_columns.index(col)] is None for row in rows(export_tables["ScaleFactors"])) for col in sorted(set(scale_export_columns) - set(scale_authored_columns))), "native-added scale columns null")

run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check(re.search(r"Errors:\s*0,\s*Warnings:\s*2,\s*Notes:\s*0", run_log) is not None, "zero converter errors, two warnings")
check(re.findall(r"warning #(\d+)", run_log) == ["108", "126"], "warnings 108 and 126 only")
check("Starting simulation" in run_log and "Saving results" in run_log, "calculation and result saving")


def event_lines(directory: Path) -> list[tuple[float, str]]:
    result = []
    for line in (directory / "model.log").read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"^Time:\s*([0-9.]+)\s+(.*)$", line)
        if match:
            result.append((float(match.group(1)), match.group(2)))
    return result


def exact_events(events: list[tuple[float, str]], phrase: str) -> list[float]:
    return [time for time, line in events if phrase in line]


def task_events(events: list[tuple[float, str]], phrase: str) -> list[float]:
    return [time for time, line in events if line.strip() == phrase]


parent_events = event_lines(PARENT_RUN)
child_events = event_lines(RUN)
for label, events, starts, ends in [
    ("parent", parent_events, [24, 49], [25, 50]),
    ("scaled", child_events, [48], [49]),
]:
    check(task_events(events, "system PM task 0 on <TEACH-AIR-01,0> started") == [starts[0]], f"{label} task0 starts")
    check(task_events(events, "system PM task 0 on <TEACH-AIR-01,0> completed") == [ends[0]], f"{label} task0 completes")
    if len(starts) == 2:
        check(task_events(events, "system PM task 1 on <TEACH-AIR-01,0> started") == [starts[1]], "parent task1 starts")
        check(task_events(events, "system PM task 1 on <TEACH-AIR-01,0> completed") == [ends[1]], "parent task1 completes")
    else:
        check(not any("system PM task 1" in line for _, line in events), "scaled no second PM task")
    check(exact_events(events, "PMID: CAL24") == starts, f"{label} CAL24 identity")
    check(exact_events(events, "starts performing, planned to last for 1 hours") == starts, f"{label} one-hour PM work")
    check(exact_events(events, "requests resources: no resources needed") == starts, f"{label} no PM resource demand")
    for event_name, expected in [
        ("mission ordered: BASIC-MISSION", [7, 19, 31]),
        ("mission starting, duration: 2", [8, 20, 32]),
        ("mission success:", [10, 22, 34]),
        ("mission completed:", [10, 22, 34]),
    ]:
        check(exact_events(events, event_name) == expected, f"{label} {event_name} timeline")
    check(not any("mission aborted:" in line or "mission cancelled:" in line for _, line in events), f"{label} no aborted/cancelled mission")
    check(exact_events(events, "nbr ready decreased at unit:") == [7, 19] + ([24] if label == "parent" else []) + [31] + ([49] if label == "parent" else [48]), f"{label} readiness debit chronology")
    check(exact_events(events, "nbr ready increased at unit:") == [0, 10, 22] + ([25] if label == "parent" else []) + [34] + ([50] if label == "parent" else [49]), f"{label} readiness credit chronology")
    check(events[-1][1].endswith("systems ready: 1 :<TEACH-AIR-01,0>"), f"{label} terminal ready aircraft")

parent_report = table_map(read(PARENT_RUN / "report-raw.json"), "report")
child_report = table_map(read(RUN / "report-raw.json"), "report")
check(set(parent_report) == set(child_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "default report tables")
check(rows(child_report["ResultSummary"]) == rows(parent_report["ResultSummary"]), "summary parity")
summary = dict(zip(names(child_report["ResultSummary"]), rows(child_report["ResultSummary"])[0]))
check(summary["NREP"] == 1 and summary["MSTF"] == 1 and summary["MSUF"] == 1, "one replication and full mission success factors")
check(summary["MTMF"] == 1 and summary["STMF"] == 1, "mission and system technical factors")

parent_stock = rows(parent_report["StockTotalResults"])
child_stock = rows(child_report["StockTotalResults"])
check(len(parent_stock) == len(child_stock) == 120, "120 stock bins in both runs")
for i, (pr, cr) in enumerate(zip(parent_stock, child_stock)):
    check(cr == pr, f"stock bin {i} parity")
    check(cr[0] == i / 2 and cr[1] == (i + 1) / 2, f"stock bin {i} interval")
    check(cr[2] == 0 and cr[9] == 1 and all(value == 0 for value in cr[10:]), f"stock bin {i} no backorder, damage, demand or movement")

parent_system = rows(parent_report["SystemResults"])
child_system = rows(child_report["SystemResults"])
system_columns = names(child_report["SystemResults"])
check(names(parent_report["SystemResults"]) == system_columns, "aligned SystemResults schema")
check(len(parent_system) == len(child_system) == 120, "120 system bins in both runs")


def span_occupancy(start: float, end: float, bin_start: float, bin_end: float) -> float:
    return max(0.0, min(end, bin_end) - max(start, bin_start)) / (bin_end - bin_start)


def field(row: list, key: str):
    return row[system_columns.index(key)]


changes = {"NSYRY", "NSYUA", "NSYA", "NSYPM", "NPMS", "NPMT", "SYDT", "NSYDT"}
for label, sr, pm_windows, starts, ends in [
    ("parent", parent_system, [(24, 25), (49, 50)], [24, 49], [25, 50]),
    ("scaled", child_system, [(48, 49)], [48], [49]),
]:
    for i, row in enumerate(sr):
        start, end = i / 2, (i + 1) / 2
        check(field(row, "STINT") == start and field(row, "ETINT") == end, f"{label} system bin {i} interval")
        mission_reserved = sum(span_occupancy(a, b, start, end) for a, b in [(7, 8), (19, 20), (31, 32)])
        mission_operating = sum(span_occupancy(a, b, start, end) for a, b in [(8, 10), (20, 22), (32, 34)])
        pm = sum(span_occupancy(a, b, start, end) for a, b in pm_windows)
        ready = 1 - mission_reserved - mission_operating - pm
        for key, expected in [
            ("NSYMR", mission_reserved), ("NSYMO", mission_operating),
            ("NSYMA", mission_reserved + mission_operating), ("FTMO", mission_operating),
            ("STACC", mission_operating), ("NSYPM", pm), ("NSYUA", pm),
            ("NSYRY", ready), ("NSYA", 1 - pm),
        ]:
            actual = field(row, key)
            check(numeric_equal(actual, expected, 2e-5), f"{label} system bin {i} {key} event occupancy")
        check(field(row, "NPMS") == (1 if start in starts else 0), f"{label} system bin {i} PM start marker")
        check(field(row, "NPMT") == (1 if start in ends else 0), f"{label} system bin {i} PM completion marker")
        check(field(row, "NSYDT") == (1 if start in starts else 0), f"{label} system bin {i} downtime-start marker")
        check(field(row, "SYDT") == (1 if start in starts else None), f"{label} system bin {i} downtime duration marker")

for i, (pr, cr) in enumerate(zip(parent_system, child_system)):
    for column, pv, cv in zip(system_columns, pr, cr):
        if column not in changes:
            check(cv == pv, f"system bin {i} unchanged field {column}")

check(math.isclose(sum(field(row, "NSYPM") * 0.5 for row in parent_system), 2, abs_tol=2e-5), "parent two PM system-hours")
check(math.isclose(sum(field(row, "NSYPM") * 0.5 for row in child_system), 1, abs_tol=2e-5), "scaled one PM system-hour")
check(math.isclose(sum(field(row, "STACC") * 0.5 for row in child_system), 6, abs_tol=2e-5), "scaled six mission aircraft-hours")
check(field(child_system[-1], "NSYRY") == 1 and field(child_system[-1], "NSYPM") == 0, "scaled final report bin ready")

result = {
    "schema": "independent-simlox-j09-var04-readonly/v1",
    "case": "J09.var04 SCPMI2",
    "run_id": RUN_ID,
    "passed": not failures,
    "verdict": "GO: bounded SCPMI2 calendar-PM interval observation" if not failures else "NO-GO: independent replay failures",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "evidence": {
        "child_input_sha256": sha(source_paths["input"]),
        "child_closure_sha256": sha(RUN / "closure.json"),
        "child_report_sha256": sha(RUN / "report-raw.json"),
        "parent_input_sha256": sha(parent_input_path),
        "parent_closure_sha256": sha(PARENT_RUN / "closure.json"),
        "parent_report_sha256": sha(PARENT_RUN / "report-raw.json"),
        "child_pm_intervals_hours": [[48, 49]],
        "parent_pm_intervals_hours": [[24, 25], [49, 50]],
        "mission_start_hours": [8, 20, 32],
        "mission_success_hours": [10, 22, 34],
        "report_bins_per_table": 120,
    },
    "limits": [
        "One installed CLI engine, one aircraft, seed 1, SCPMI=2, CAL24 one-hour PM and a 60-hour horizon.",
        "The log and report show the first PM at 48 and no later PM before hour 60; they do not expose the scheduler's internal renewal law.",
        "No claim for flight-hour PM, PM/mission conflict, nonzero ATIM/DTIM, resource shortage, GUI-only execution or cross-engine parity.",
        "SystemResults boundary values differ from ideal occupancy by less than 2e-5; this is report floating-point timing, not extra work.",
    ],
}
VERDICT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
print(f"{result['verdict']}; {result['checks_passed']}/{result['checks_total']} checks; {VERDICT}")
if failures:
    for failure in failures[:20]:
        print("FAIL:", failure)
    raise SystemExit(1)
