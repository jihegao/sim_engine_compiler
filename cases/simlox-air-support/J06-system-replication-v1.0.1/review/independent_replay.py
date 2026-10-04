"""Independent read-only raw replay for J06.var02 System replication output."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
CASES = CASE.parent
RUN = CASE / "runs" / "j06-system-replication-v101-ssh-20261004-01"
PARENT = CASES / "J04-var01-fixed-replications-v1.0.0"
PARENT_RUN = PARENT / "runs" / "j04-var01-fixed-reps-accepted-20261001-03"
PRECEDENT = CASES / "J05-profile-snapshot-v1.0.1"
EXCLUDED = CASES / "J06-system-replication-percentile-v1.0.0"
EXCLUDED_RUN = EXCLUDED / "runs" / "j06-system-replication-v100-ssh-20261004-01"
DEFAULT_SETTINGS = Path(r"C:\Users\Public\Documents\Systecon\SIMLOX\Setup\Default.sxs")
ENABLED_SETTINGS = CASE / "runs" / "report-settings" / "replications-enabled.sxs"
OUTPUT = HERE / "independent-verdict.json"
checks = 0
failures: list[str] = []


def check(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def tables(document: dict, root: str) -> dict:
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


def columns(table: dict) -> list[str]:
    return [column["name"] for column in table["columns"]]


def value(table: dict, row: list, key: str):
    return row[columns(table).index(key)]


def close(a, b, tolerance=1e-5) -> bool:
    return isinstance(a, (int, float)) and math.isclose(a, b, rel_tol=0, abs_tol=tolerance)


contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
invocation = load(RUN / "invocation.json")
closure = load(RUN / "closure.json")
steps = load(RUN / "steps.json")
check(contract["case_id"] == "J06" and contract["variant_id"] == "J06.var02", "contract identity")
check(contract["parameters"]["nreps"] == 16 and contract["parameters"]["horizon_hours"] == 36, "16 replications, 36-hour horizon")
check(contract["parameters"]["snapshot_hours"] == [9, 11], "snapshot times 9 and 11")
check(contract["parameters"]["system_replication_flags"] == {"TOTAL": "Y", "TIME": "Y", "SNAPS": "Y"}, "system result switches")
source_paths = {
    "input": CASE / "replication-input.json",
    "parent": PARENT_RUN / "input.json",
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-10-01.md",
    "precedent_signoff": PRECEDENT / "cli-scope-signoff-2026-10-01.md",
    "contract": CASE / "contract.json",
    "exact_diff": CASE / "exact-diff.json",
    "default_settings": DEFAULT_SETTINGS,
    "report_settings": ENABLED_SETTINGS,
    "excluded_closure": EXCLUDED_RUN / "closure.json",
    "build.py": CASE / "build.py",
    "describe_diff.py": CASE / "describe_diff.py",
    "make_report_settings.py": CASE / "make_report_settings.py",
    "check_roundtrip.py": CASE / "check_roundtrip.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
for key, path in sorted(source_paths.items()):
    check(path.is_file(), f"source exists {key}")
    if path.is_file():
        check(sha(path) == closure["source_hashes_before"].get(key), f"frozen source SHA {key}")
check(sha(source_paths["parent"]) == contract["accepted_parent"]["input_sha256"], "accepted parent input")
check(sha(source_paths["parent_closure"]) == contract["accepted_parent"]["closure_sha256"], "accepted parent closure")
check(sha(source_paths["parent_signoff"]) == contract["accepted_parent"]["signoff_sha256"], "accepted parent signoff")
check(sha(source_paths["precedent_signoff"]) == contract["report_precedent"]["signoff_sha256"], "report precedent signoff")
check(sha(source_paths["excluded_closure"]) == contract["excluded_diagnostic"]["closure_sha256"], "excluded warning-502 diagnostic")
check(sha(EXCLUDED / "replication-input.json") == contract["excluded_diagnostic"]["input_sha256"], "excluded percentile source")
check(sha(source_paths["input"]) == contract["child_input_sha256"], "frozen child input")
check(sha(source_paths["exact_diff"]) == contract["exact_diff_sha256"], "frozen exact diff")
for source_key, contract_key in [("exe", "simlox_exe_sha256"), ("manual", "manual_pdf_sha256"), ("dictionary", "dictionary_sha256")]:
    check(closure["source_hashes_before"][source_key] == contract["source"][contract_key], f"installed {source_key} fingerprint")

parent = tables(load(source_paths["parent"]), "model")
child = tables(load(source_paths["input"]), "model")
check(len(parent) == 32 and len(child) == 34, "32 parent and 34 child tables")
check(set(child) == set(parent) | {"SnapshotResultTimes", "ReplicationResultControlSystem"}, "only two appended source tables")
for name in sorted(parent):
    check(child[name] == parent[name], f"unchanged parent source table {name}")
for appended in diff["appended_tables"]:
    check(child[appended["name"]] == appended, f"appended source table {appended['name']}")
check(diff["parent_input_sha256"] == sha(source_paths["parent"]) and diff["child_input_sha256"] == sha(source_paths["input"]), "exact diff lineage hashes")
check(diff["unchanged_parent_tables"] == 32 and diff["other_changes"] == [], "no additional source changes")
check(rows(child["SnapshotResultTimes"]) == [[9, None], [11, None]], "two authored snapshots")
check(rows(child["ReplicationResultControlSystem"]) == [["TEACH-AIR-01", "TEACH-UNIT", "Y", "Y", "Y", None]], "one system TOTAL/TIME/SNAPS control")
check("PercentileLevels" not in child, "no percentile source row")
check(sum(bool(rows(table)) for table in child.values()) == 16, "16 row-containing source tables")
control = {t["name"]: t for t in child.values()}
check(rows(control["Control"])[0][columns(control["Control"]).index("NREPS")] == 16, "authored NREPS16")

default = DEFAULT_SETTINGS.read_bytes()
enabled = ENABLED_SETTINGS.read_bytes()
check(sha(DEFAULT_SETTINGS) == contract["report_precedent"]["installed_default_settings_sha256"], "installed default report settings SHA")
check(sha(ENABLED_SETTINGS) == contract["report_precedent"]["one_byte_outpr_enabled_sha256"], "OUTRP-enabled report settings SHA")
different_offsets = [index for index, (left, right) in enumerate(zip(default, enabled)) if left != right]
check(len(default) == len(enabled) and len(different_offsets) == 1, "one-byte settings patch")
if len(different_offsets) == 1:
    pos = different_offsets[0]
    check(default[pos] == ord("N") and enabled[pos] == ord("Y"), "OUTRP N to Y byte")
    check(b"GeneralSettings\x00" in default[max(0, pos - 60):pos], "settings patch in GeneralSettings")

check(sha(RUN / "closure.json") == "516a38de676cafeba19bdf6d7c3c7ea1676b97b91dee561956b77bf6911f557b", "sealed native closure SHA")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation sealed")
check(invocation["run_id"] == RUN.name and closure["run_id"] == RUN.name, "run identity")
check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0, "SSH session zero")
check("sshd.exe" in invocation["ssh_ancestor_names"], "sshd ancestor")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI13340 separate session")
check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native mutex")
check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source stable before/after")
check(len(closure["raw"]) == 14, "fourteen raw file seals")
for filename, seal in sorted(closure["raw"].items()):
    path = RUN / filename
    check(path.is_file(), f"raw present {filename}")
    if path.is_file():
        check(path.stat().st_size == seal["bytes"], f"raw size {filename}")
        check(sha(path) == seal["sha256"], f"raw SHA {filename}")
check(closure["error"] is None, "native closure no error")
check(sha(RUN / "input.json") == sha(source_paths["input"]), "native input frozen source")
check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "replication_report", "check_import_export"], "six guarded steps")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None, f"step complete {step['name']}")
for step in steps[:5]:
    check(step["gui_preserved"] is True, f"GUI preserved {step['name']}")
for planned, actual in zip(invocation["planned_commands"], steps):
    check(planned["name"] == actual["name"] and planned["arguments"] == actual["arguments"], f"planned native command {actual['name']}")
check("-rpts " in steps[4]["arguments"] and str(ENABLED_SETTINGS) in steps[4]["arguments"], "report-only settings, no default fallback")
check((RUN / "model.sxo").stat().st_size > 100000, "usable simulation output")
log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check(re.search(r"Errors:\s*0,\s*Warnings:\s*3,\s*Notes:\s*0", log) is not None, "zero-error converter")
check(re.findall(r"warning #(\d+)", log) == ["108", "211", "126"], "only reviewed warnings #108/#211/#126")
check("warning #502" not in log and "notice #502" not in log, "no percentile warning 502")

exported = tables(load(RUN / "roundtrip-raw.json"), "model")
check(set(exported) == set(child), "native export all authored tables")
for name in sorted(child):
    original, back = child[name], exported[name]
    original_cols, back_cols = columns(original), columns(back)
    check(set(original_cols).issubset(back_cols), f"roundtrip columns {name}")
    if rows(original):
        projected = [[row[back_cols.index(column)] for column in original_cols] for row in rows(back)]
        check(projected == rows(original), f"roundtrip source rows {name}")
    else:
        check(not any(any(item is not None for item in row) for row in rows(back)), f"no substantive export rows {name}")

default_report = tables(load(RUN / "report-raw.json"), "report")
enabled_report = tables(load(RUN / "replication-report-raw.json"), "report")
check(set(default_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "default report tables")
check(set(enabled_report) == set(default_report) | {"Replications", "SystemResultsReplicationTotal", "SystemResultsReplication", "SystemResultsReplicationSnapshot"}, "OUTRP adds four replication tables")
for name in sorted(default_report):
    check(columns(default_report[name]) == columns(enabled_report[name]), f"common report columns {name}")
    check(rows(default_report[name]) == rows(enabled_report[name]), f"common report rows {name}")
check(sha(RUN / "model.log") == sha(PARENT_RUN / "model.log"), "first-rep log unchanged from accepted J04")
check(sha(RUN / "report-raw.json") == sha(PARENT_RUN / "report-raw.json"), "default report unchanged from accepted J04")

summary = dict(zip(columns(default_report["ResultSummary"]), rows(default_report["ResultSummary"])[0]))
check(summary["NREP"] == 16 and summary["MSTF"] == summary["MSUF"] == summary["MTMF"] == summary["STMF"] == 1, "summary sixteen successful replications")
stock_rows = rows(default_report["StockTotalResults"])
check(len(stock_rows) == 72, "72 default Stock bins")
for index, row in enumerate(stock_rows):
    check(row[0] == index * .5 and row[1] == (index + 1) * .5, f"Stock bin {index} interval")
    check(row[2] == 0 and row[9] == 1 and all(item == 0 for item in row[10:]), f"Stock bin {index} no demand or failure")

reps_table = enabled_report["Replications"]
reps = rows(reps_table)
check(len(reps) == 16 and [value(reps_table, row, "REPNO") for row in reps] == list(range(1, 17)), "sixteen ordered replication IDs")
check([value(reps_table, row, "RSEED") for row in reps][0] == "1", "first replication seed one")
check(len(set(value(reps_table, row, "RSEED") for row in reps)) == 16, "distinct listed replication seeds")
for index, row in enumerate(reps):
    check(all(value(reps_table, row, key) == 1 for key in ["FMTAC", "FMSTA", "FMSUC", "FSTAC"]), f"replication {index + 1} success factors")

time_table = enabled_report["SystemResultsReplication"]
times = rows(time_table)
total_table = enabled_report["SystemResultsReplicationTotal"]
totals = rows(total_table)
snapshot_table = enabled_report["SystemResultsReplicationSnapshot"]
snapshots = rows(snapshot_table)
aggregate_table = default_report["SystemResults"]
aggregate = rows(aggregate_table)
check(len(aggregate) == 72 and len(times) == 16 * 72 and len(totals) == 16 and len(snapshots) == 16 * 2, "aggregate/TIME/TOTAL/SNAPS row counts")
check([value(total_table, row, "REPLID") for row in totals] == list(range(1, 17)), "TOTAL replication IDs")
time_lookup: dict[tuple[int, float], list] = {}
for row in times:
    rid, start = value(time_table, row, "REPLID"), value(time_table, row, "STINT")
    check(rid in range(1, 17), f"TIME replication ID {rid}")
    check(start in [i / 2 for i in range(72)] and value(time_table, row, "ETINT") == start + .5, f"TIME replication {rid} interval {start}")
    check(value(time_table, row, "UNID") == "TEACH-UNIT" and value(time_table, row, "SID") == "TEACH-AIR-01", f"TIME entity {rid}/{start}")
    check((rid, start) not in time_lookup, f"TIME unique key {rid}/{start}")
    time_lookup[(rid, start)] = row
check(len(time_lookup) == 1152, "complete TIME key grid")

numeric_columns = [name for name in columns(aggregate_table) if name not in {"UNID", "SID", "STINT", "ETINT"}]
for index, row in enumerate(aggregate):
    start = index / 2
    check(value(aggregate_table, row, "STINT") == start and value(aggregate_table, row, "ETINT") == start + .5, f"aggregate bin {index} interval")
    for name in numeric_columns:
        actual = value(aggregate_table, row, name)
        per_rep = [value(time_table, time_lookup[(rid, start)], name) for rid in range(1, 17)]
        if actual is None:
            check(all(item is None for item in per_rep), f"aggregate bin {index} {name} null across replications")
        else:
            check(all(isinstance(item, (int, float)) for item in per_rep), f"aggregate bin {index} {name} numeric source")
            if all(isinstance(item, (int, float)) for item in per_rep):
                check(close(actual, sum(per_rep) / 16), f"aggregate bin {index} {name} equals per-rep mean")

total_columns = [name for name in columns(total_table) if name not in {"UNID", "SID", "REPLID"}]
for rid, row in enumerate(totals, start=1):
    check(value(total_table, row, "UNID") == "TEACH-UNIT" and value(total_table, row, "SID") == "TEACH-AIR-01", f"TOTAL entity {rid}")
    for name in total_columns:
        actual = value(total_table, row, name)
        per_bin = [value(time_table, time_lookup[(rid, index / 2)], name) for index in range(72)]
        if actual is None:
            check(all(item is None for item in per_bin), f"TOTAL {rid} {name} null across time")
        else:
            check(all(isinstance(item, (int, float)) for item in per_bin), f"TOTAL {rid} {name} numeric source")
            if all(isinstance(item, (int, float)) for item in per_bin):
                check(close(actual, sum(per_bin) / 72), f"TOTAL {rid} {name} equals 72-bin time mean")
    check(value(total_table, row, "NSYA") == 12 and value(total_table, row, "NFAIL") == 0, f"TOTAL {rid} available without failure")

snapshot_lookup: dict[tuple[int, float], list] = {}
for row in snapshots:
    rid, hour = value(snapshot_table, row, "REPLID"), value(snapshot_table, row, "SSTIM")
    check(rid in range(1, 17) and hour in {9, 11}, f"SNAPS key {rid}/{hour}")
    check((rid, hour) not in snapshot_lookup, f"SNAPS unique key {rid}/{hour}")
    snapshot_lookup[(rid, hour)] = row
    check(value(snapshot_table, row, "UNID") == "TEACH-UNIT" and value(snapshot_table, row, "SID") == "TEACH-AIR-01", f"SNAPS entity {rid}/{hour}")
    for name in columns(snapshot_table):
        if name not in {"UNID", "SID", "SSTIM", "REPLID"}:
            check(value(snapshot_table, row, name) == value(time_table, time_lookup[(rid, hour)], name), f"SNAPS {rid}/{hour} {name} equals TIME row")
check(len(snapshot_lookup) == 32, "complete 16 by 2 snapshot grid")
for rid in range(1, 17):
    snap9, snap11 = snapshot_lookup[(rid, 9)], snapshot_lookup[(rid, 11)]
    ready9, operating9 = value(snapshot_table, snap9, "NSYRY"), value(snapshot_table, snap9, "NSYMO")
    check(ready9 + operating9 == 12 and operating9 in {0, 2, 4, 6, 8}, f"replication {rid} h9 formation occupancy")
    check(value(snapshot_table, snap11, "NSYRY") == 12 and value(snapshot_table, snap11, "NSYMO") == 0, f"replication {rid} h11 all ready")
    check(value(time_table, time_lookup[(rid, 35.5)], "NSYRY") == 12, f"replication {rid} terminal ready12")
check(value(snapshot_table, snapshot_lookup[(1, 9)], "NSYRY") == 10 and value(snapshot_table, snapshot_lookup[(1, 9)], "NSYMO") == 2, "first-rep h9 two operating")
check(value(snapshot_table, snapshot_lookup[(1, 11)], "NSYRY") == 12, "first-rep h11 ready12")

events = []
for line in (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines():
    found = re.match(r"^Time:\s*([0-9.]+)\s+(.*)$", line)
    if found:
        events.append((float(found.group(1)), found.group(2)))


def times(fragment: str) -> list[float]:
    return [hour for hour, line in events if fragment in line]


check(times("mission ordered: BASIC-MISSION") == [7], "first-rep single mission order")
check(times("mission starting, duration: 2") == [8], "first-rep h8 mission starts")
check(times("mission success:") == [10] and times("mission completed:") == [10], "first-rep h10 successful completion")
check(times("mission allocates system:") == [7, 7], "first-rep two aircraft allocated")
check(times("nbr ready decreased at unit:") == [7, 7], "first-rep two readiness debits")
check(len(times("nbr ready increased at unit:")) == 14, "first-rep twelve initial and two return credits")
check(not any("mission aborted:" in line or "mission cancelled:" in line for _, line in events), "first-rep no mission abort/cancel")
for index in range(72):
    start = index / 2
    row = time_lookup[(1, start)]
    reserved = 2 if 7 <= start < 8 else 0
    operating = 2 if 8 <= start < 10 else 0
    for key, expected in [
        ("NSYRY", 12 - reserved - operating),
        ("NSYMA", reserved + operating),
        ("NSYMR", reserved),
        ("NSYMO", operating),
        ("NSYA", 12),
        ("STACC", operating),
        ("FTMO", operating / 12),
    ]:
        check(close(value(time_table, row, key), expected), f"first-rep bin {index} {key} event occupancy")
    check(value(time_table, row, "NFAIL") == 0 and value(time_table, row, "NSYPM") == 0, f"first-rep bin {index} no fault/PM")
check(close(sum(value(time_table, time_lookup[(1, i / 2)], "STACC") * .5 for i in range(72)), 4), "first-rep four aircraft flight-hours")

result = {
    "schema": "independent-j06-var02-system-replications-readonly/v1",
    "case": "J06.var02 System replication TOTAL/TIME/SNAPS",
    "passed": not failures,
    "verdict": "GO: bounded 16-replication System result exposure" if not failures else "NO-GO: independent replay failures",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "evidence": {
        "child_input_sha256": sha(CASE / "replication-input.json"),
        "closure_sha256": sha(RUN / "closure.json"),
        "default_report_sha256": sha(RUN / "report-raw.json"),
        "replication_report_sha256": sha(RUN / "replication-report-raw.json"),
        "settings_sha256": sha(ENABLED_SETTINGS),
        "replication_count": 16,
        "system_time_rows": 1152,
        "system_total_rows": 16,
        "snapshot_rows": 32,
        "snapshot_hours": [9, 11],
        "first_replication_mission_hours": [8, 10],
        "first_replication_terminal_ready": 12,
        "h9_operating_aircraft_frequency": dict(sorted(Counter(value(snapshot_table, snapshot_lookup[(rid, 9)], "NSYMO") for rid in range(1, 17)).items())),
    },
    "limits": [
        "One installed CLI engine, this 12-aircraft Poisson model, 16 fixed-seed replications, a 36-hour horizon, and System TOTAL/TIME/SNAPS report settings.",
        "ENLOG shows first-rep events only. Replications 2–16 are validated through their native result rows, not individual event logs.",
        "Numeric System aggregates equal means of corresponding per-rep rows; null fields remain null. No general formula is asserted for other report tables or metrics.",
        "The excluded v1.0.0 percentile probe stopped on warning #502. No percentile or STLOW distribution claim is accepted.",
        "No population distribution, GUI-only, or cross-engine conclusion follows from these sixteen replications.",
    ],
}
OUTPUT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
print(f"{result['verdict']}; {result['checks_passed']}/{result['checks_total']} checks")
for failure in failures[:20]:
    print("FAIL", failure)
if failures:
    raise SystemExit(1)
