"""Independent read-only replay of I01.var01 APID stock POINT native evidence.

This standard-library checker parses authored JSON, sealed native raw files,
event logs, and reports. It never imports author scripts or executes SIMLOX.
Displayed event times are rounded, so bin comparisons allow 0.0002 hour.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT = pathlib.Path(__file__).with_name("independent-readonly-2026-10-02.json")
checks = 0
failures: list[str] = []
results: dict[str, dict] = {}


def read_json(path: pathlib.Path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def digest(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(document: dict) -> dict[str, dict]:
    payload = document.get("report", document.get("model", document))
    return {table["name"]: table for table in payload["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def assert_that(condition, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def close(actual: float, expected: float, tolerance: float = .0002) -> bool:
    return isinstance(actual, (int, float)) and abs(actual - expected) < tolerance


def occupancy(a: float, b: float, start: float, finish: float) -> float:
    return max(0.0, min(b, finish) - max(a, start)) * 2


contract = read_json(ROOT / "contract.json")
diff = read_json(ROOT / "exact-diff.json")
parent_path = ROOT / contract["direct_parent"]["source"]
manual_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
exe_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
parent = tables(read_json(parent_path))
stocked_path = ROOT / "stocked-input.json"
empty_path = ROOT / "empty-input.json"
stocked = tables(read_json(stocked_path))
empty = tables(read_json(empty_path))
assert_that(digest(parent_path) == contract["direct_parent"]["sha256"], "accepted E01 parent hash")
assert_that(digest(ROOT / "exact-diff.json") == contract["sources_sha256"]["exact_diff"], "frozen exact-diff hash")
assert_that(digest(stocked_path) == contract["sources_sha256"]["stocked"], "stocked input hash")
assert_that(digest(empty_path) == contract["sources_sha256"]["empty"], "empty input hash")
for key, path in (("manual_pdf", manual_path), ("table_dictionary", dictionary_path), ("simlox_exe", exe_path)):
    assert_that(digest(path) == contract["installed_source_sha256"][key], "installed " + key)

for before, after, specification, expected in (
    (parent, stocked, diff["parent_to_stocked"], {"ProblemDescription", "StockAllocation"}),
    (stocked, empty, diff["stocked_to_empty"], {"ProblemDescription", "Control"}),
):
    assert_that(set(before) == set(after), "source table set")
    changed = {name for name in before if before[name] != after[name]}
    assert_that(changed == expected, "exact changed tables " + ",".join(sorted(expected)))
    assert_that(not specification["added_tables"] and not specification["removed_tables"] and set(specification["changed_tables"]) == changed, "declared diff topology")
    assert_that(specification["unchanged_table_count"] == len(before) - len(changed), "unchanged table count")
    for name in before:
        if name in changed:
            assert_that(specification["changed_tables"][name]["before"] == before[name], "diff before " + name)
            assert_that(specification["changed_tables"][name]["after"] == after[name], "diff after " + name)
        else:
            assert_that(before[name] == after[name], "unchanged " + name)

expected_points = [
    ["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 1, None, None, None, None, None],
    ["AIR_EMPTY", "TEACH-LRU-01", "BASE-01", 0, None, None, None, None, None],
]
assert_that(rows(stocked["StockAllocation"]) == rows(empty["StockAllocation"]) == expected_points, "two stock POINT rows")
assert_that(rows(parent["StockAllocation"]) == expected_points[:1], "parent single stock POINT")
control_columns = [column["name"] for column in stocked["Control"]["columns"]]
apid_index = control_columns.index("APID")
assert_that(rows(stocked["Control"])[0][apid_index] == "AIR_BASIC", "stocked APID")
assert_that(rows(empty["Control"])[0][apid_index] == "AIR_EMPTY", "empty APID")
assert_that(all(rows(stocked[name]) == rows(empty[name]) == [] for name in ("ResourceAllocation", "MaintenanceAllocation") if name in stocked), "no resource or maintenance allocation")

e01_run = ROOT.parent / "E01-local-spare-explicit-replacement-v1.0.0" / "runs" / "e01-v100-ssh-20260929-01"
for variant, input_path, source in (("stocked", stocked_path, stocked), ("empty", empty_path, empty)):
    run_id = f"i01-var01-{variant}-v100-ssh-20261002-01"
    run = ROOT / "runs" / run_id
    invocation = read_json(run / "invocation.json")
    closure = read_json(run / "closure.json")
    assert_that(invocation["run_id"] == closure["run_id"] == run_id, variant + " run identity")
    assert_that(digest(run / "invocation.json") == closure["invocation_sha256"], variant + " invocation seal")
    assert_that(invocation["input_sha256"] == digest(input_path) == digest(run / "input.json"), variant + " native input")
    assert_that(invocation["parent_sha256"] == digest(parent_path), variant + " invocation parent")
    assert_that(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], variant + " SSH session zero")
    assert_that(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", variant + " mutex")
    assert_that(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, variant + " GUI identity")
    assert_that(closure["source_hashes_before"] == closure["source_hashes_after"], variant + " source stability")
    source_paths = (
        ("input", input_path), ("parent", parent_path), ("contract", ROOT / "contract.json"),
        ("manual", manual_path), ("dictionary", dictionary_path), ("builder", ROOT / "build.py"),
        ("exact_diff", ROOT / "exact-diff.json"), ("diff_checker", ROOT / "describe_diff.py"),
        ("checker", ROOT / "check_roundtrip.py"), ("python", pathlib.Path(invocation["planned_check"]["executable"])),
        ("runner_script", ROOT / "run_native_ssh.ps1"), ("simlox_exe", exe_path),
    )
    for key, path in source_paths:
        assert_that(closure["source_hashes_before"][key] == digest(path), variant + " source seal " + key)
    assert_that(len(closure["raw"]) == 12, variant + " 12 raw artifacts")
    for filename, metadata in closure["raw"].items():
        path = run / filename
        assert_that(path.is_file() and path.stat().st_size == metadata["bytes"] and digest(path) == metadata["sha256"], variant + " raw seal " + filename)
    steps = read_json(run / "steps.json")
    assert_that([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], variant + " five guarded steps")
    for step in steps:
        assert_that(step["exit_code"] == 0 and step["gui_preserved"] and step["status"] in ("completed", "calc_observed"), variant + " step " + step["name"])
    exported = tables(read_json(run / "roundtrip-raw.json"))
    authored = {name: table for name, table in source.items() if rows(table)}
    assert_that(len(authored) == 20, variant + " 20 populated business tables")
    for name, table in authored.items():
        assert_that(name in exported and table["columns"] == exported[name]["columns"] and table["instances"] == exported[name]["instances"], variant + " exact roundtrip " + name)
    calc = (run / "run.log").read_text(errors="replace")
    assert_that("Input conversion completed. Errors: 0" in calc and (run / "model.sxo").stat().st_size > 4, variant + " converter and SXO")

    log = (run / "model.log").read_text(errors="replace")
    assert_that("Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in log, variant + " shared failure draw")
    assert_that("Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in log, variant + " first mission abort")
    assert_that("Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed" in log, variant + " first return")
    assert_that("Time: 10  system SURP task 0 on <TEACH-AIR-01,0> started" in log, variant + " system replacement starts")
    assert_that("Time: 10.1667  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed" in log, variant + " remove work")
    assert_that("Time: 10.1667  item DIRP task 1 on <TEACH-LRU-01,0," in log, variant + " damaged item repair starts")
    assert_that("Time: 11.1667  item DIRP task 1 on <TEACH-LRU-01,0," in log, variant + " item repair completes")
    for mission_number, allocation, launch, success in ((1, 19, 20, 22), (2, 31, 32, 34)):
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission_number}>"
        assert_that(f"Time: {allocation} {mission} mission allocates system: <TEACH-AIR-01,0>" in log, variant + f" later allocation {mission_number}")
        assert_that(f"Time: {launch} {mission} mission starting" in log, variant + f" later launch {mission_number}")
        assert_that(f"Time: {success} {mission} mission success" in log, variant + f" later success {mission_number}")
    if variant == "stocked":
        assert_that(digest(run / "model.log") == digest(e01_run / "model.log"), "stocked log equals accepted E01")
        e01_report = tables(read_json(e01_run / "report-raw.json"))
        current_report = tables(read_json(run / "report-raw.json"))
        assert_that(all(current_report[name] == e01_report[name] for name in current_report if name != "ProblemDescription"), "stocked report equals E01 except description")
        assert_that("Time: 0 <TEACH-LRU-01,0,BASE-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log, "stocked initial physical spare")
        assert_that("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log, "stocked spare issued")
        assert_that("Time: 10.5  system SURP task 0 on <TEACH-AIR-01,0> completed" in log and "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready" in log, "stocked ready h10.5")
        assert_that("Time: 11.1667 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock" in log, "stocked repaired LRU stocked")
        assert_that("Backorder added" not in log, "stocked no backorder")
    else:
        assert_that("Time: 0 <TEACH-LRU-01,0,BASE-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in log, "empty physical initial stock")
        assert_that("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in log, "empty backorder at h10")
        assert_that("Time: 10.1667  fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> wait for subitem" in log, "fit waits for LRU")
        assert_that("Time: 11.1667 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1.16667" in log, "backorder clears by repaired item")
        assert_that("Time: 11.1667  system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,0>" in log, "repaired original reused")
        assert_that("Time: 11.5  system SURP task 0 on <TEACH-AIR-01,0> completed" in log and "Time: 11.5 <TEACH-AIR-01,BASE-01,0> System ready" in log, "empty ready h11.5")
        assert_that("Take replacement item" not in log and "Put back replacement item" not in log, "no physical spare issue or stock return")

    report = tables(read_json(run / "report-raw.json"))
    system = report["SystemResults"]
    stock = report["StockTotalResults"]
    summary = report["ResultSummary"]
    sr = rows(system)
    st = rows(stock)
    sc = {column["name"]: index for index, column in enumerate(system["columns"])}
    ic = {column["name"]: index for index, column in enumerate(stock["columns"])}
    uc = {column["name"]: index for index, column in enumerate(summary["columns"])}
    assert_that(len(sr) == len(st) == 72, variant + " 72 System/Stock bins")
    nonzero_system = {"NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYUA", "NSYA", "FTMO", "NSYRP", "NSYWI", "NREPT", "NFAIL", "STACC", "NSYDT"}
    stocked_arm = variant == "stocked"
    for index, (system_row, stock_row) in enumerate(zip(sr, st)):
        a = index / 2
        b = a + .5
        ma = sum(occupancy(a, b, start, end) for start, end in ((7, 10), (19, 22), (31, 34)))
        mo = sum(occupancy(a, b, start, end) for start, end in ((8, 10), (20, 22), (32, 34)))
        mr = sum(occupancy(a, b, start, end) for start, end in ((7, 8), (19, 20), (31, 32)))
        unavailable = occupancy(a, b, 10, 10.5 if stocked_arm else 11.5)
        repair = occupancy(a, b, 10, 10.5) if stocked_arm else occupancy(a, b, 10, 10.166667) + occupancy(a, b, 11.166667, 11.5)
        wait = 0 if stocked_arm else occupancy(a, b, 10.166667, 11.166667)
        expected_system = {
            "NSYRY": 1 - ma - unavailable, "NSYMA": ma, "NSYMO": mo,
            "NSYMR": mr, "NSYUA": unavailable, "NSYA": 1 - unavailable,
            "FTMO": mo, "NSYRP": repair, "NSYWI": wait,
            "NREPT": int(a <= (10.5 if stocked_arm else 11.5) < b),
            "NFAIL": int(a <= 9.8829 < b), "STACC": mo,
            "NSYDT": int(a <= 10 < b),
        }
        assert_that(close(system_row[sc["STINT"]], a) and close(system_row[sc["ETINT"]], b), variant + f" System time {index}")
        assert_that(close(stock_row[ic["STINT"]], a) and close(stock_row[ic["ETINT"]], b), variant + f" Stock time {index}")
        for field, expected in expected_system.items():
            assert_that(close(system_row[sc[field]], expected), variant + f" {field} bin {index}")
        for field, column in sc.items():
            if field in nonzero_system or field in ("UNID", "SID", "STINT", "ETINT", "SYDT"):
                continue
            assert_that(system_row[column] == 0, variant + f" zero {field} bin {index}")
        backorder = 0 if stocked_arm else occupancy(a, b, 10, 11.166667)
        for field, expected in (("NBO", backorder), ("PNB", 1 - backorder), ("NDF", int(a == 10)), ("NWT", int(a == 10))):
            assert_that(close(stock_row[ic[field]], expected), variant + f" Stock {field} bin {index}")
        for field in ("NDD", "NDR", "NDP", "NLD"):
            assert_that(stock_row[ic[field]] == 0, variant + f" zero Stock {field} bin {index}")
        assert_that(stock_row[ic["NBOU"]] is None, variant + f" null NBOU bin {index}")
        for field in ("ROS", "ROST", "WT", "WTT", "WTS"):
            actual = stock_row[ic[field]]
            if a != 10 or (field == "WTS" and stocked_arm):
                assert_that(actual is None, variant + f" null {field} bin {index}")
            else:
                expected = (0 if stocked_arm else 1) if field in ("ROS", "ROST") else (0 if stocked_arm else 1.1666667)
                assert_that(close(actual, expected), variant + f" {field} bin {index}")

    flight_hours = sum(row[sc["NSYMO"]] * .5 for row in sr)
    repair_hours = sum(row[sc["NSYRP"]] * .5 for row in sr)
    wait_hours = sum(row[sc["NSYWI"]] * .5 for row in sr)
    backorder_hours = sum(row[ic["NBO"]] * .5 for row in st)
    assert_that(close(flight_hours, 6) and close(repair_hours, .5), variant + " flight and repair hours")
    assert_that(close(wait_hours, 0 if stocked_arm else 1) and close(backorder_hours, 0 if stocked_arm else 1.166667), variant + " wait and backorder integrals")
    assert_that(sr[-1][sc["NSYRY"]] == 1 and sr[-1][sc["NSYUA"]] == 0 and st[-1][ic["NBO"]] == 0, variant + " terminal state")
    summary_row = rows(summary)[0]
    assert_that(summary_row[uc["NREP"]] == 1 and summary_row[uc["RTIUP"]] == 36, variant + " summary horizon")
    assert_that(summary_row[uc["MTMF"]] == 1 and summary_row[uc["MSTF"]] == 1 and close(summary_row[uc["MSUF"]], 2 / 3) and summary_row[uc["STMF"]] == 1, variant + " summary factors")
    results[variant] = {
        "run_id": run_id,
        "closure_sha256": digest(run / "closure.json"),
        "report_sha256": digest(run / "report-raw.json"),
        "model_log_sha256": digest(run / "model.log"),
        "flight_aircraft_hours": flight_hours,
        "system_repair_occupancy_hours": repair_hours,
        "system_wait_for_item_hours": wait_hours,
        "stock_backorder_hours": backorder_hours,
        "terminal_ready_aircraft": sr[-1][sc["NSYRY"]],
    }

verdict = {
    "schema": "simlox-i01-var01-independent-readonly/v1",
    "passed": not failures,
    "verdict": "GO: bounded stock-only APID POINT selection" if not failures else "NO-GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "runs": results,
    "scope": "Same E01 LRU failure in two fixed-seed sources differing only in Control.APID after adding a zero-stock AIR_EMPTY POINT; AIR_BASIC issues the spare and AIR_EMPTY backorders until the failed LRU is repaired and reused.",
    "limits": [
        "Only StockAllocation POINT selection is tested; ResourceAllocation and MaintenanceAllocation selection is not established.",
        "StockTotalResults.PNB is reconciled as a report field complementary to NBO here, not used as a physical stock-level count; physical initial levels and item issue/reuse are taken from native model.log.",
        "The observed backorder clears using the repaired original item, without a stock-return log; this does not establish procurement, reorder behavior, or other station configurations.",
        "One aircraft, station, LRU, and seed do not prove general shortage timing, task filtering, GUI visual behavior, or cross-engine parity.",
    ],
}
OUTPUT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"verdict": verdict["verdict"], "checks_passed": verdict["checks_passed"], "checks_total": checks, "failures": failures, "result": str(OUTPUT)}))
sys.exit(0 if verdict["passed"] else 1)
