"""Independent, standard-library replay of the H03.var02 sealed native pair.

Reads original source and native artifacts only. No author implementation is
imported or called, and no native SIMLOX command is executed. Native model.log
times are printed to five or fewer decimals, so report occupancy comparisons
allow 0.0002 hour for display rounding.
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
    data = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", data))


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(document: dict) -> dict[str, dict]:
    payload = document.get("report", document.get("model", document))
    return {table["name"]: table for table in payload["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def require(condition, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def near(actual: float, expected: float, tolerance: float = 0.0002) -> bool:
    return abs(actual - expected) < tolerance


def overlap(a: float, b: float, c: float, d: float) -> float:
    return max(0.0, min(b, d) - max(a, c))


contract = read_json(ROOT / "contract.json")
delta = read_json(ROOT / "exact-diff.json")
parent_path = ROOT / contract["direct_parent"]["source"]
manual_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
exe_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")

require(sha(parent_path) == contract["direct_parent"]["sha256"], "accepted parent hash")
require(sha(ROOT / "exact-diff.json") == contract["sources_sha256"]["exact_diff"], "frozen diff hash")
for key, path in (("manual_pdf", manual_path), ("table_dictionary", dictionary_path), ("simlox_exe", exe_path)):
    require(sha(path) == contract["installed_source_sha256"][key], "installed " + key)

parent = tables(read_json(parent_path))
control_path = ROOT / "control-input.json"
two_path = ROOT / "two-mode-input.json"
control = tables(read_json(control_path))
two = tables(read_json(two_path))
require(sha(control_path) == contract["sources_sha256"]["control"] == sha(parent_path), "byte-identical control parent")
require(sha(two_path) == contract["sources_sha256"]["two_mode"], "two-mode source hash")
require(parent == control, "control tables equal parent")
require(set(control) == set(two), "same table set")
changed = {name for name in control if control[name] != two[name]}
require(changed == {"FailureMode", "CMLocation", "DamageFailureMode", "ProblemDescription"}, "exact four-table delta")
require(set(delta["changed_tables"]) == changed and not delta["added_tables"] and not delta["removed_tables"], "declared diff topology")
require(delta["unchanged_table_count"] == len(control) - 4, "declared unchanged count")
for name in control:
    if name in changed:
        require(delta["changed_tables"][name]["before"] == control[name], "diff before " + name)
        require(delta["changed_tables"][name]["after"] == two[name], "diff after " + name)
    else:
        require(control[name] == two[name], "unchanged " + name)
for name in ("FailureMode", "CMLocation", "DamageFailureMode"):
    require(two[name]["columns"] == control[name]["columns"], "same columns " + name)
    require(rows(two[name])[:-1] == rows(control[name]), "original rows retained " + name)
    require(len(rows(two[name])) == len(rows(control[name])) + 1, "one new row " + name)
require(rows(two["FailureMode"])[-1] == ["FM-POS-B", "Second position A direct repair", "POS-A", 1e-9, "OPHOURS", 1.0, None, None, None], "new FM row")
require(rows(two["CMLocation"])[-1] == ["FM-POS-B", "TEACH-AIR-01", "BASE-01", 1.0, None, None, 1.0, None, None, None], "new one-hour CM row")
require(rows(two["DamageFailureMode"])[-1] == ["BATTLE-HIT", "TEACH-AIR-01", "FM-POS-B", 1.0, None], "new certain damage-FM row")
require(not any(name in two and rows(two[name]) for name in ("DamageItem", "DamageReplacement", "ItemRepair")), "no item-damage route")

parent_run = ROOT.parent / "H03-var01-position-fm-damage-v1.0.0" / "runs" / "h03-var01-posfm-mode-v100-ssh-20261002-01"
variants = (
    {
        "name": "control",
        "source": control,
        "source_path": control_path,
        "run_id": "h03-var02-control-v100-ssh-20261002-01",
        "damage": [8.13665, 20.6501, 33.1102],
        "return": [8.27329, 21.1501, 33.6102],
        "repair_A_end": [8.77329, 21.6501, 34.1102],
        "repair_B_end": [],
        "mtmf": 0.5056003928184509,
    },
    {
        "name": "two-mode",
        "source": two,
        "source_path": two_path,
        "run_id": "h03-var02-two-mode-v100-ssh-20261002-01",
        "damage": [8.13665, 20.1965, 32.0866],
        "return": [8.27329, 20.393, 32.1732],
        "repair_A_end": [8.77329, 20.893, 32.6732],
        "repair_B_end": [9.27329, 21.393, 33.1732],
        "mtmf": 0.13990212976932526,
    },
)

for arm in variants:
    name = arm["name"]
    run = ROOT / "runs" / arm["run_id"]
    invocation = read_json(run / "invocation.json")
    closure = read_json(run / "closure.json")
    require(invocation["run_id"] == closure["run_id"] == arm["run_id"], name + " run identity")
    require(sha(run / "invocation.json") == closure["invocation_sha256"], name + " invocation seal")
    require(invocation["input_sha256"] == sha(arm["source_path"]) == sha(run / "input.json"), name + " native input")
    require(invocation["parent_sha256"] == sha(parent_path), name + " invocation parent")
    require(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], name + " session-zero SSH")
    require(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", name + " queue mutex")
    require(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, name + " preserved GUI identity")
    require(closure["source_hashes_before"] == closure["source_hashes_after"], name + " source stability")
    source_paths = (
        ("input", arm["source_path"]), ("parent", parent_path), ("contract", ROOT / "contract.json"),
        ("manual", manual_path), ("dictionary", dictionary_path), ("builder", ROOT / "build.py"),
        ("exact_diff", ROOT / "exact-diff.json"), ("diff_checker", ROOT / "describe_diff.py"),
        ("checker", ROOT / "check_roundtrip.py"), ("python", pathlib.Path(invocation["planned_check"]["executable"])),
        ("runner_script", ROOT / "run_native_ssh.ps1"), ("simlox_exe", exe_path),
    )
    for key, path in source_paths:
        require(closure["source_hashes_before"][key] == sha(path), name + " source seal " + key)
    require(len(closure["raw"]) == 12, name + " twelve sealed raw artifacts")
    for filename, metadata in closure["raw"].items():
        path = run / filename
        require(path.is_file() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"], name + " raw seal " + filename)
    steps = read_json(run / "steps.json")
    require([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], name + " five native steps")
    for step in steps:
        require(step["exit_code"] == 0 and step["gui_preserved"] and step["status"] in ("completed", "calc_observed"), name + " step " + step["name"])
    exported = tables(read_json(run / "roundtrip-raw.json"))
    authored = {table_name: table for table_name, table in arm["source"].items() if rows(table)}
    require(len(authored) == 21, name + " twenty-one populated tables")
    for table_name, authored_table in authored.items():
        require(table_name in exported and authored_table["columns"] == exported[table_name]["columns"] and authored_table["instances"] == exported[table_name]["instances"], name + " exact table " + table_name)
    calculation = (run / "run.log").read_text(errors="replace")
    require("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in calculation and "warning #108" in calculation, name + " converter")
    require((run / "model.sxo").stat().st_size > 4, name + " valid SXO")

    log = (run / "model.log").read_text(errors="replace")
    require("Next random failure will occur 1e+010" in log and not re.search(r"random failure occured", log, re.I), name + " no observed ordinary random failure")
    require(log.count("Damage BATTLE-HIT occured") == 3, name + " three damage events")
    require(log.count("Failure Mode: FM-POS-A on materiel: <POS-A,0>") == 3, name + " three A failure identities")
    require(log.count("Failure Mode: FM-POS-B on materiel: <POS-A,0>") == (0 if name == "control" else 6), name + " B arrival and partial-repair identities")
    require(log.count("mission aborted:") == 3 and "mission success:" not in log, name + " three aborted missions")
    require(log.count("System ready <TEACH-AIR-01,0>") == 3, name + " three returns to ready")
    if name == "control":
        require(sha(run / "model.log") == sha(parent_run / "model.log"), "control event log equals accepted parent")
        require(sha(run / "report-raw.json") == sha(parent_run / "report-raw.json"), "control report equals accepted parent")

    alloc = [7, 19, 31]
    launch = [8, 20, 32]
    for wave in range(3):
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{wave}>"
        damage = arm["damage"][wave]
        returned = arm["return"][wave]
        a_end = arm["repair_A_end"][wave]
        b_end = arm["repair_B_end"][wave] if name == "two-mode" else None
        task_a = wave if name == "control" else 2 * wave
        require(f"Time: {alloc[wave]} {mission} mission allocates system: <TEACH-AIR-01,0>" in log, name + f" allocation {wave}")
        require(f"Time: {launch[wave]} {mission} mission starting" in log, name + f" launch {wave}")
        require(f"Time: {damage} <TEACH-AIR-01,0>Damage BATTLE-HIT occured" in log, name + f" damage time {wave}")
        require(f"Time: {damage} {mission} mission aborted" in log, name + f" abort {wave}")
        require(f"Time: {returned} {mission} aborted mission completed" in log, name + f" return {wave}")
        require(f"Time: {returned}  system CM task {task_a} on <TEACH-AIR-01,0> started" in log, name + f" A CM start {wave}")
        require(f"Time: {returned}  system CM task {task_a} on <TEACH-AIR-01,0> FMID: FM-POS-A" in log, name + f" A CM identity {wave}")
        require(f"Time: {a_end}  system CM task {task_a} on <TEACH-AIR-01,0> completed" in log, name + f" A CM end {wave}")
        if name == "two-mode":
            task_b = task_a + 1
            require(f"Time: {returned}  system CM task {task_b} on <TEACH-AIR-01,0> started" in log, name + f" B concurrent start {wave}")
            require(f"Time: {returned}  system CM task {task_b} on <TEACH-AIR-01,0> FMID: FM-POS-B" in log, name + f" B CM identity {wave}")
            require(f"Time: {b_end}  system CM task {task_b} on <TEACH-AIR-01,0> completed" in log, name + f" B CM end {wave}")
            require(f"Time: {a_end} <TEACH-AIR-01,BASE-01,0> System partially repaired" in log, name + f" partial state {wave}")
            require(f"Time: {b_end} <TEACH-AIR-01,BASE-01,0> System ready" in log, name + f" final ready {wave}")
            require(near(a_end - returned, .5) and near(b_end - returned, 1.0), name + f" concurrent durations {wave}")
        else:
            require(f"Time: {a_end} <TEACH-AIR-01,BASE-01,0> System ready" in log, name + f" ready {wave}")
            require(near(a_end - returned, .5), name + f" half-hour duration {wave}")

    report = tables(read_json(run / "report-raw.json"))
    system = report["SystemResults"]
    stock = report["StockTotalResults"]
    summary = report["ResultSummary"]
    sr = rows(system)
    st = rows(stock)
    sc = {column["name"]: index for index, column in enumerate(system["columns"])}
    ic = {column["name"]: index for index, column in enumerate(stock["columns"])}
    uc = {column["name"]: index for index, column in enumerate(summary["columns"])}
    require(len(sr) == len(st) == 72, name + " seventy-two System/Stock bins")
    long_end = arm["repair_B_end"] or arm["repair_A_end"]
    repair_completions = arm["repair_A_end"] + arm["repair_B_end"]
    nonzero_system = {"NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYUA", "NSYA", "FTMO", "NSYRP", "NREPT", "NDAM", "STACC", "NSYDT"}
    for index, (system_row, stock_row) in enumerate(zip(sr, st)):
        a = index / 2
        b = a + .5
        ma = sum(overlap(a, b, alloc[k], arm["return"][k]) * 2 for k in range(3))
        mo = sum(overlap(a, b, launch[k], arm["return"][k]) * 2 for k in range(3))
        mr = sum(overlap(a, b, alloc[k], launch[k]) * 2 for k in range(3))
        repair_occupancy = sum(overlap(a, b, arm["return"][k], long_end[k]) * 2 for k in range(3))
        expected_system = {
            "NSYRY": 1 - ma - repair_occupancy,
            "NSYMA": ma,
            "NSYMO": mo,
            "NSYMR": mr,
            "NSYUA": repair_occupancy,
            "NSYA": 1 - repair_occupancy,
            "FTMO": mo,
            "NSYRP": repair_occupancy,
            "NREPT": sum(a <= time < b for time in repair_completions),
            "NDAM": sum(a <= time < b for time in arm["damage"]),
            "STACC": mo,
            "NSYDT": sum(a <= time < b for time in arm["return"]),
        }
        require(near(system_row[sc["STINT"]], a) and near(system_row[sc["ETINT"]], b), name + f" System time {index}")
        require(near(stock_row[ic["STINT"]], a) and near(stock_row[ic["ETINT"]], b), name + f" Stock time {index}")
        for field, expected in expected_system.items():
            require(near(system_row[sc[field]], expected), name + f" {field} bin {index}")
        for field, column in sc.items():
            if field in nonzero_system or field in ("UNID", "SID", "STINT", "ETINT", "SYDT"):
                continue
            require(system_row[column] == 0, name + f" zero {field} bin {index}")
        require(stock_row[ic["PNB"]] == 1 and stock_row[ic["NBO"]] == 0, name + f" stock level bin {index}")
        for field, column in ic.items():
            if field in ("STINT", "ETINT", "PNB", "NBO", "NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
                continue
            require(stock_row[column] == 0, name + f" zero stock {field} bin {index}")

    flight_hours = sum(row[sc["NSYMO"]] * .5 for row in sr)
    repair_hours = sum(row[sc["NSYRP"]] * .5 for row in sr)
    require(near(flight_hours, sum(arm["return"][k] - launch[k] for k in range(3))), name + " flight integral")
    require(near(repair_hours, 1.5 if name == "control" else 3.0), name + " repair occupancy integral")
    require(near(sum(row[sc["NSYUA"]] * .5 for row in sr), repair_hours), name + " unavailable integral")
    require(sr[-1][sc["NSYRY"]] == 1 and sr[-1][sc["NSYRP"]] == 0 and st[-1][ic["PNB"]] == 1, name + " terminal ready and stock")
    summary_row = rows(summary)[0]
    require(summary_row[uc["NREP"]] == 1 and summary_row[uc["RTIUP"]] == 36, name + " summary horizon")
    require(near(summary_row[uc["MTMF"]], arm["mtmf"]) and near(summary_row[uc["STMF"]], arm["mtmf"]), name + " summary MTMF/STMF")
    require(summary_row[uc["MSTF"]] == 1 and summary_row[uc["MSUF"]] == 0, name + " summary mission factors")
    run_results[name] = {
        "run_id": arm["run_id"],
        "closure_sha256": sha(run / "closure.json"),
        "report_sha256": sha(run / "report-raw.json"),
        "model_log_sha256": sha(run / "model.log"),
        "flight_aircraft_hours": flight_hours,
        "system_repair_occupancy_hours": repair_hours,
        "cm_task_hours": 1.5 if name == "control" else 4.5,
        "terminal_ready_aircraft": sr[-1][sc["NSYRY"]],
    }

verdict = {
    "schema": "simlox-h03-var02-independent-readonly/v1",
    "passed": len(failures) == 0,
    "verdict": "GO: bounded two-FM damage on one position" if not failures else "NO-GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "runs": run_results,
    "scope": "At each of three fixed-seed BATTLE-HIT events, FM-POS-A and FM-POS-B on the same POS-A are logged and their 0.5-hour and 1-hour CM tasks overlap; the system becomes ready after both finish.",
    "limits": [
        "This one-seed, one-position result does not establish probability independence or behavior on other material positions.",
        "SystemResults.NSYRP counts three hours of union system-repair occupancy, while individual CM task work totals 4.5 task-hours; these are different metrics.",
        "No DamageItem consequence, resource constraint, alternate station, GUI visual behavior, or cross-engine parity was tested.",
        "Positive ordinary failure FRQ=1e-9 is not a zero-rate guarantee; no ordinary random failure occurred in these logs.",
    ],
}
RESULT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"verdict": verdict["verdict"], "checks_passed": verdict["checks_passed"], "checks_total": checks, "failures": failures, "result": str(RESULT)}))
sys.exit(0 if verdict["passed"] else 1)
