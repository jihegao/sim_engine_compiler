"""Independent read-only native replay of I01.var02 selected versus blank APID.

Only Python's standard library and frozen source/raw evidence are used. The
author builder, checker, validator, and native SIMLOX executable are not run.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULT = pathlib.Path(__file__).with_name("independent-readonly-2026-10-02.json")
checks = 0
failures: list[str] = []
run_results: dict[str, dict] = {}


def read_json(path: pathlib.Path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_map(document: dict) -> dict[str, dict]:
    obj = document.get("report", document.get("model", document))
    return {table["name"]: table for table in obj["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def check(condition, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def near(actual: float, expected: float, tolerance: float = .0002) -> bool:
    return isinstance(actual, (int, float)) and abs(actual - expected) < tolerance


def share(a: float, b: float, start: float, finish: float) -> float:
    return max(0.0, min(b, finish) - max(a, start)) * 2


contract = read_json(ROOT / "contract.json")
delta = read_json(ROOT / "exact-diff.json")
parent_path = ROOT / contract["direct_parent"]["source"]
parent_package = parent_path.parent
parent_signoff = parent_package / "cli-scope-signoff-2026-10-02.md"
manual_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
exe_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
selected_path = ROOT / "selected-input.json"
blank_path = ROOT / "blank-input.json"
parent = table_map(read_json(parent_path))
selected = table_map(read_json(selected_path))
blank = table_map(read_json(blank_path))
check(sha(parent_path) == contract["direct_parent"]["sha256"], "accepted I01.var01 parent hash")
check(sha(parent_signoff) == contract["direct_parent"]["signoff_sha256"], "accepted parent signoff hash")
check(sha(selected_path) == sha(parent_path) == contract["sources_sha256"]["selected"], "selected byte-identical parent")
check(sha(blank_path) == contract["sources_sha256"]["blank"], "blank source hash")
check(sha(ROOT / "exact-diff.json") == contract["sources_sha256"]["exact_diff"], "exact-diff hash")
for key, path in (("manual_pdf", manual_path), ("table_dictionary", dictionary_path), ("simlox_exe", exe_path)):
    check(sha(path) == contract["installed_source_sha256"][key], "installed " + key)
check(parent == selected, "selected tables equal accepted parent")
check(set(selected) == set(blank), "blank preserves table set")
changed = {name for name in selected if selected[name] != blank[name]}
check(changed == {"Control", "ProblemDescription"}, "only APID table and description change")
check(set(delta["changed_tables"]) == changed, "declared diff topology")
check(delta["unchanged_table_count"] == len(selected) - 2, "unchanged table count")
for name in selected:
    if name in changed:
        check(delta["changed_tables"][name]["before"] == selected[name], "diff before " + name)
        check(delta["changed_tables"][name]["after"] == blank[name], "diff after " + name)
    else:
        check(selected[name] == blank[name], "unchanged " + name)
control_fields = [column["name"] for column in selected["Control"]["columns"]]
apid_index = control_fields.index("APID")
before = rows(selected["Control"])[0]
after = rows(blank["Control"])[0]
check(before[apid_index] == "AIR_BASIC" and after[apid_index] is None, "selected to null APID")
check(before[:apid_index] + before[apid_index + 1:] == after[:apid_index] + after[apid_index + 1:], "no other Control field delta")
point_rows = [
    ["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 1, None, None, None, None, None],
    ["AIR_EMPTY", "TEACH-LRU-01", "BASE-01", 0, None, None, None, None, None],
]
check(rows(blank["StockAllocation"]) == rows(selected["StockAllocation"]) == point_rows, "both POINT rows retained")
check(all(not rows(blank[name]) for name in ("ResourceAllocation", "MaintenanceAllocation") if name in blank), "stock-only source")

accepted_runs = {
    "selected": parent_package / "runs" / "i01-var01-stocked-v100-ssh-20261002-01",
    "blank": parent_package / "runs" / "i01-var01-empty-v100-ssh-20261002-01",
}
for arm, source_path, source in (("selected", selected_path, selected), ("blank", blank_path, blank)):
    run_id = f"i01-var02-{arm}-v100-ssh-20261002-01"
    run = ROOT / "runs" / run_id
    accepted = accepted_runs[arm]
    invocation = read_json(run / "invocation.json")
    closure = read_json(run / "closure.json")
    check(invocation["run_id"] == closure["run_id"] == run_id, arm + " run identity")
    check(sha(run / "invocation.json") == closure["invocation_sha256"], arm + " invocation seal")
    check(invocation["input_sha256"] == sha(source_path) == sha(run / "input.json"), arm + " native source binding")
    check(invocation["parent_sha256"] == sha(parent_path), arm + " invocation parent")
    check(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], arm + " session-zero SSH")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", arm + " queue mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, arm + " preserved GUI identity")
    check(closure["source_hashes_before"] == closure["source_hashes_after"], arm + " source stability")
    source_files = (
        ("input", source_path), ("parent", parent_path), ("contract", ROOT / "contract.json"),
        ("manual", manual_path), ("dictionary", dictionary_path), ("builder", ROOT / "build.py"),
        ("exact_diff", ROOT / "exact-diff.json"), ("diff_checker", ROOT / "describe_diff.py"),
        ("checker", ROOT / "check_roundtrip.py"), ("python", pathlib.Path(invocation["planned_check"]["executable"])),
        ("runner_script", ROOT / "run_native_ssh.ps1"), ("simlox_exe", exe_path),
    )
    for key, path in source_files:
        check(closure["source_hashes_before"][key] == sha(path), arm + " source seal " + key)
    check(len(closure["raw"]) == 12, arm + " twelve raw artifacts")
    for filename, metadata in closure["raw"].items():
        file = run / filename
        check(file.is_file() and file.stat().st_size == metadata["bytes"] and sha(file) == metadata["sha256"], arm + " raw seal " + filename)
    steps = read_json(run / "steps.json")
    check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], arm + " five native steps")
    for step in steps:
        check(step["exit_code"] == 0 and step["gui_preserved"] and step["status"] in ("completed", "calc_observed"), arm + " step " + step["name"])
    exported = table_map(read_json(run / "roundtrip-raw.json"))
    authored = {name: table for name, table in source.items() if rows(table)}
    check(len(authored) == 20, arm + " twenty populated tables")
    for name, table in authored.items():
        check(name in exported and table["columns"] == exported[name]["columns"] and table["instances"] == exported[name]["instances"], arm + " exact roundtrip " + name)
    calc = (run / "run.log").read_text(errors="replace")
    check("Input conversion completed. Errors: 0, Warnings: 1, Notes: " + ("0" if arm == "selected" else "1") in calc, arm + " converter counts")
    check("warning #108" in calc, arm + " warning 108")
    check(("notice #102) Simulation with no stock" in calc) == (arm == "blank"), arm + " blank-APID no-stock notice")
    check((run / "model.sxo").stat().st_size > 4, arm + " valid SXO")

    log = (run / "model.log").read_text(errors="replace")
    check(sha(run / "model.log") == sha(accepted / "model.log"), arm + " byte-identical accepted event log")
    report = table_map(read_json(run / "report-raw.json"))
    accepted_report = table_map(read_json(accepted / "report-raw.json"))
    check(set(report) == set(accepted_report), arm + " accepted report tables")
    for name, table in report.items():
        if name != "ProblemDescription":
            check(table == accepted_report[name], arm + " accepted report " + name)
    if arm == "selected":
        check(sha(run / "report-raw.json") == sha(accepted / "report-raw.json"), "selected byte-identical accepted report")

    check("Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in log, arm + " same failure sample")
    check("Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in log, arm + " first abort")
    check("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed" in log, arm + " first return")
    check("Time: 10  system SURP task 0 on <TEACH-AIR-01,0> started" in log, arm + " replacement starts")
    check("Time: 10.1667  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed" in log, arm + " removal completes")
    check("Time: 10.1667  item DIRP task 1 on <TEACH-LRU-01,0," in log, arm + " item repair starts")
    check("Time: 11.1667  item DIRP task 1 on <TEACH-LRU-01,0," in log, arm + " item repair ends")
    for i, ordered, launched, succeeded in ((1, 19, 20, 22), (2, 31, 32, 34)):
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>"
        check(f"Time: {ordered} {mission} mission allocates system: <TEACH-AIR-01,0>" in log, arm + f" allocation {i}")
        check(f"Time: {launched} {mission} mission starting" in log, arm + f" launch {i}")
        check(f"Time: {succeeded} {mission} mission success" in log, arm + f" success {i}")
    if arm == "selected":
        check("Time: 0 <TEACH-LRU-01,0,BASE-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log, "selected physical initial spare")
        check("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log, "selected h10 spare issue")
        check("Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready" in log, "selected ready h10.5")
        check("Backorder added" not in log, "selected no backorder")
    else:
        check("Time: 0 <TEACH-LRU-01,0,BASE-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in log, "blank physical initial stock zero")
        check("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in log, "blank h10 backorder")
        check("Time: 10.1667  fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem" in log, "blank fit waits")
        check("Time: 11.1667 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1.16667" in log, "blank backorder removal")
        check("Time: 11.1667  system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,0>" in log, "blank repaired original reused")
        check("Time: 11.5 <TEACH-AIR-01,BASE-01,0> System ready" in log, "blank ready h11.5")
        check("Take replacement item" not in log and "Put back replacement item" not in log, "blank no physical stock issue/return")

    system = report["SystemResults"]
    stock = report["StockTotalResults"]
    summary = report["ResultSummary"]
    sr = rows(system)
    st = rows(stock)
    sc = {column["name"]: i for i, column in enumerate(system["columns"])}
    ic = {column["name"]: i for i, column in enumerate(stock["columns"])}
    uc = {column["name"]: i for i, column in enumerate(summary["columns"])}
    check(len(sr) == len(st) == 72, arm + " 72 System/Stock bins")
    selected_arm = arm == "selected"
    nonzero_system = {"NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYUA", "NSYA", "FTMO", "NSYRP", "NSYWI", "NREPT", "NFAIL", "STACC", "NSYDT"}
    for index, (system_row, stock_row) in enumerate(zip(sr, st)):
        a = index / 2
        b = a + .5
        mission = sum(share(a, b, start, finish) for start, finish in ((7, 10), (19, 22), (31, 34)))
        flight = sum(share(a, b, start, finish) for start, finish in ((8, 10), (20, 22), (32, 34)))
        request = sum(share(a, b, start, finish) for start, finish in ((7, 8), (19, 20), (31, 32)))
        unavailable = share(a, b, 10, 10.5 if selected_arm else 11.5)
        repair = share(a, b, 10, 10.5) if selected_arm else share(a, b, 10, 10.166667) + share(a, b, 11.166667, 11.5)
        waiting = 0 if selected_arm else share(a, b, 10.166667, 11.166667)
        system_expected = {
            "NSYRY": 1 - mission - unavailable, "NSYMA": mission, "NSYMO": flight,
            "NSYMR": request, "NSYUA": unavailable, "NSYA": 1 - unavailable,
            "FTMO": flight, "NSYRP": repair, "NSYWI": waiting,
            "NREPT": int(a <= (10.5 if selected_arm else 11.5) < b),
            "NFAIL": int(a <= 9.8829 < b), "STACC": flight,
            "NSYDT": int(a <= 10 < b),
        }
        check(near(system_row[sc["STINT"]], a) and near(system_row[sc["ETINT"]], b), arm + f" System time {index}")
        check(near(stock_row[ic["STINT"]], a) and near(stock_row[ic["ETINT"]], b), arm + f" Stock time {index}")
        for field, expected in system_expected.items():
            check(near(system_row[sc[field]], expected), arm + f" {field} bin {index}")
        for field, column in sc.items():
            if field in nonzero_system or field in ("UNID", "SID", "STINT", "ETINT", "SYDT"):
                continue
            check(system_row[column] == 0, arm + f" zero {field} bin {index}")
        backorder = 0 if selected_arm else share(a, b, 10, 11.166667)
        for field, expected in (("NBO", backorder), ("PNB", 1 - backorder), ("NDF", int(a == 10)), ("NWT", int(a == 10))):
            check(near(stock_row[ic[field]], expected), arm + f" Stock {field} bin {index}")
        for field in ("NDD", "NDR", "NDP", "NLD"):
            check(stock_row[ic[field]] == 0, arm + f" zero Stock {field} bin {index}")
        check(stock_row[ic["NBOU"]] is None, arm + f" null NBOU bin {index}")
        for field in ("ROS", "ROST", "WT", "WTT", "WTS"):
            value = stock_row[ic[field]]
            if a != 10 or (field == "WTS" and selected_arm):
                check(value is None, arm + f" null {field} bin {index}")
            else:
                expected = (0 if selected_arm else 1) if field in ("ROS", "ROST") else (0 if selected_arm else 1.1666667)
                check(near(value, expected), arm + f" {field} bin {index}")

    flight_hours = sum(row[sc["NSYMO"]] * .5 for row in sr)
    repair_hours = sum(row[sc["NSYRP"]] * .5 for row in sr)
    wait_hours = sum(row[sc["NSYWI"]] * .5 for row in sr)
    backorder_hours = sum(row[ic["NBO"]] * .5 for row in st)
    check(near(flight_hours, 6) and near(repair_hours, .5), arm + " integrated flight and repair")
    check(near(wait_hours, 0 if selected_arm else 1) and near(backorder_hours, 0 if selected_arm else 1.166667), arm + " integrated waits")
    check(sr[-1][sc["NSYRY"]] == 1 and sr[-1][sc["NSYUA"]] == 0 and st[-1][ic["NBO"]] == 0, arm + " terminal state")
    summary_row = rows(summary)[0]
    check(summary_row[uc["NREP"]] == 1 and summary_row[uc["RTIUP"]] == 36, arm + " summary horizon")
    check(summary_row[uc["MTMF"]] == 1 and summary_row[uc["MSTF"]] == 1 and near(summary_row[uc["MSUF"]], 2 / 3) and summary_row[uc["STMF"]] == 1, arm + " summary factors")
    run_results[arm] = {
        "run_id": run_id,
        "closure_sha256": sha(run / "closure.json"),
        "report_sha256": sha(run / "report-raw.json"),
        "model_log_sha256": sha(run / "model.log"),
        "flight_aircraft_hours": flight_hours,
        "system_repair_occupancy_hours": repair_hours,
        "system_wait_for_item_hours": wait_hours,
        "stock_backorder_hours": backorder_hours,
        "terminal_ready_aircraft": sr[-1][sc["NSYRY"]],
    }

verdict = {
    "schema": "simlox-i01-var02-independent-readonly/v1",
    "passed": not failures,
    "verdict": "GO: bounded blank-APID stock-only outcome" if not failures else "NO-GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "runs": run_results,
    "scope": "In this fixed-seed two-POINT StockAllocation model, blank Control.APID converts with notice #102, initializes no physical spare, and reproduces the accepted AIR_EMPTY event and report outcome; AIR_BASIC reproduces the stocked outcome.",
    "limits": [
        "The native blank-APID outcome is observed for one station, one LRU, and two conflicting stock POINT rows; the internal POINT-selection algorithm is not directly exposed.",
        "ResourceAllocation and MaintenanceAllocation blank-APID behavior, task filtering, STID=<NONE>, StationVariant, procurement, GUI visual behavior, and cross-engine parity are not established.",
        "StockTotalResults.PNB is used only as a report field complementary to NBO here; physical initial stock and item issue/reuse are established by the event log.",
        "One seed and fixed mission schedule do not establish general stock or backorder behavior.",
    ],
}
RESULT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"verdict": verdict["verdict"], "checks_passed": verdict["checks_passed"], "checks_total": checks, "failures": failures, "result": str(RESULT)}))
sys.exit(0 if verdict["passed"] else 1)
