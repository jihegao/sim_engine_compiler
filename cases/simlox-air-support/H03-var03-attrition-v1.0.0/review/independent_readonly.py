"""Independent read-only replay of the sealed H03.var03 attrition pair.

Uses only standard-library parsing of authored inputs and native raw artifacts.
The author builder, validators and SIMLOX executable are never called.
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


def tables(document: dict) -> dict[str, dict]:
    return {table["name"]: table for table in document.get("report", document.get("model", document))["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def check(value, label: str) -> None:
    global checks
    checks += 1
    if not value:
        failures.append(label)


def near(value: float, expected: float, tolerance: float = 0.0002) -> bool:
    return isinstance(value, (int, float)) and abs(value - expected) < tolerance


def overlap(a: float, b: float, c: float, d: float) -> float:
    return max(0.0, min(b, d) - max(a, c))


contract = read_json(ROOT / "contract.json")
diff = read_json(ROOT / "exact-diff.json")
parent_path = ROOT / contract["direct_parent"]["source"]
reference_path = ROOT / contract["attrition_schema_reference"]["source"]
manual_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
dictionary_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
exe_path = pathlib.Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
control_path = ROOT / "control-input.json"
attrition_path = ROOT / "attrition-input.json"

check(sha(parent_path) == contract["direct_parent"]["sha256"], "accepted H03.var01 parent hash")
check(sha(reference_path) == contract["attrition_schema_reference"]["sha256"], "accepted H01 attrition reference hash")
check(sha(ROOT / "exact-diff.json") == contract["sources_sha256"]["exact_diff"], "exact-diff hash")
for key, path in (("manual_pdf", manual_path), ("table_dictionary", dictionary_path), ("simlox_exe", exe_path)):
    check(sha(path) == contract["installed_source_sha256"][key], "installed " + key)
parent = tables(read_json(parent_path))
reference = tables(read_json(reference_path))
control = tables(read_json(control_path))
attrition = tables(read_json(attrition_path))
check(sha(control_path) == sha(parent_path) == contract["sources_sha256"]["control"], "byte-identical H03 control")
check(parent == control, "H03 control table equality")
check(sha(attrition_path) == contract["sources_sha256"]["attrition"], "attrition source hash")
check(set(attrition) - set(control) == {"DamageItem"} and set(control) - set(attrition) == set(), "exact added table")
changed = {name for name in control if control[name] != attrition[name]}
check(changed == {"DamageFailureMode", "DamageType", "ProblemDescription"}, "exact changed tables")
check(set(diff["added_tables"]) == {"DamageItem"} and not diff["removed_tables"] and set(diff["changed_tables"]) == changed, "declared diff topology")
check(diff["unchanged_table_count"] == len(control) - len(changed), "declared unchanged count")
check(diff["added_tables"]["DamageItem"] == attrition["DamageItem"], "declared added row")
for name in control:
    if name in changed:
        check(diff["changed_tables"][name]["before"] == control[name], "diff before " + name)
        check(diff["changed_tables"][name]["after"] == attrition[name], "diff after " + name)
    else:
        check(control[name] == attrition[name], "unchanged " + name)
check(attrition["DamageItem"]["columns"] == reference["DamageItem"]["columns"], "H01 DamageItem schema")
check(rows(attrition["DamageItem"]) == [["BATTLE-HIT", "TEACH-AIR-01", "<ATTRITION>", 1.0, None, None, None]], "certain whole-aircraft attrition row")
check(rows(control["DamageFailureMode"]) == [["BATTLE-HIT", "TEACH-AIR-01", "FM-POS-A", 1.0, None]], "parent certain FM row")
check(rows(attrition["DamageFailureMode"]) == [["BATTLE-HIT", "TEACH-AIR-01", "FM-POS-A", 0.0, None]], "child inactive FM consequence")
check(rows(control["MissionDamage"]) == rows(attrition["MissionDamage"]), "unchanged certain mission damage")

parent_run = ROOT.parent / "H03-var01-position-fm-damage-v1.0.0" / "runs" / "h03-var01-posfm-mode-v100-ssh-20261002-01"
variants = (
    ("control", control_path, control, "h03-var03-control-v100-ssh-20261002-01"),
    ("attrition", attrition_path, attrition, "h03-var03-attrition-v100-ssh-20261002-01"),
)
for name, source_path, source, run_id in variants:
    run = ROOT / "runs" / run_id
    invocation = read_json(run / "invocation.json")
    closure = read_json(run / "closure.json")
    check(invocation["run_id"] == closure["run_id"] == run_id, name + " run identity")
    check(sha(run / "invocation.json") == closure["invocation_sha256"], name + " invocation seal")
    check(invocation["input_sha256"] == sha(source_path) == sha(run / "input.json"), name + " exact native input")
    check(invocation["parent_sha256"] == sha(parent_path), name + " invocation parent")
    check(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"], name + " SSH session zero")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", name + " native mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, name + " GUI preservation")
    check(closure["source_hashes_before"] == closure["source_hashes_after"], name + " source stability")
    source_paths = (
        ("input", source_path), ("parent", parent_path), ("attrition_reference", reference_path),
        ("contract", ROOT / "contract.json"), ("manual", manual_path), ("dictionary", dictionary_path),
        ("builder", ROOT / "build.py"), ("exact_diff", ROOT / "exact-diff.json"),
        ("diff_checker", ROOT / "describe_diff.py"), ("checker", ROOT / "check_roundtrip.py"),
        ("python", pathlib.Path(invocation["planned_check"]["executable"])),
        ("runner_script", ROOT / "run_native_ssh.ps1"), ("simlox_exe", exe_path),
    )
    for key, path in source_paths:
        check(closure["source_hashes_before"][key] == sha(path), name + " source seal " + key)
    check(len(closure["raw"]) == 12, name + " twelve raw artifacts")
    for filename, metadata in closure["raw"].items():
        path = run / filename
        check(path.is_file() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"], name + " raw seal " + filename)
    steps = read_json(run / "steps.json")
    check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], name + " five native steps")
    for step in steps:
        check(step["exit_code"] == 0 and step["gui_preserved"] and step["status"] in ("completed", "calc_observed"), name + " step " + step["name"])
    exported = tables(read_json(run / "roundtrip-raw.json"))
    authored = {table_name: table for table_name, table in source.items() if rows(table)}
    check(len(authored) == (21 if name == "control" else 22), name + " populated-table count")
    for table_name, table in authored.items():
        check(table_name in exported and table["columns"] == exported[table_name]["columns"] and table["instances"] == exported[table_name]["instances"], name + " exact roundtrip " + table_name)
    calc = (run / "run.log").read_text(errors="replace")
    check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in calc and "warning #108" in calc, name + " converter")
    check((run / "model.sxo").stat().st_size > 4, name + " valid SXO")
    log = (run / "model.log").read_text(errors="replace")
    check("Next random failure will occur 1e+010" in log and not re.search("random failure occured", log, re.I), name + " no ordinary random failure")
    if name == "control":
        check(sha(run / "model.log") == sha(parent_run / "model.log"), "control log equals accepted parent")
        check(sha(run / "report-raw.json") == sha(parent_run / "report-raw.json"), "control report equals accepted parent")
        check(log.count("Damage BATTLE-HIT occured") == 3, "control three damage events")
        check(log.count("Failure Mode: FM-POS-A on materiel: <POS-A,0>") == 3, "control three FM failures")
        check(log.count("system CM task ") > 0 and log.count("mission aborted:") == 3, "control CM and aborts")
        check(log.count("System ready <TEACH-AIR-01,0>") == 3, "control three repairs to ready")
    else:
        check(log.count("Damage BATTLE-HIT occured") == 1, "one in-flight damage event")
        check("Time: 8.13665 <TEACH-AIR-01,0>Damage BATTLE-HIT occured. Damaged items: Time: 8.13665 <TEACH-AIR-01,0> subject to attrition" in log, "same-time attrition identity")
        check("Time: 8.13665 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in log, "first mission abort")
        check("Time: 8.27329 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed" in log, "aborted mission completion")
        check("Failure Mode: FM-POS-A" not in log and "system CM task" not in log and "System ready <TEACH-AIR-01,0>" not in log, "FM/CM/readiness suppressed")
        for index, ordered, cancelled in ((1, 19, 20.3333), (2, 31, 32.3333)):
            mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{index}>"
            check(f"Time: {ordered} {mission} mission waiting:  timeout at {cancelled}" in log, f"later wait {index}")
            check(f"Time: {cancelled} {mission} mission cancelled" in log, f"later cancellation {index}")
            check(f"{mission} mission starting" not in log, f"no later launch {index}")

    report = tables(read_json(run / "report-raw.json"))
    system = report["SystemResults"]
    stock = report["StockTotalResults"]
    summary = report["ResultSummary"]
    sr = rows(system)
    st = rows(stock)
    sc = {column["name"]: index for index, column in enumerate(system["columns"])}
    ic = {column["name"]: index for index, column in enumerate(stock["columns"])}
    uc = {column["name"]: index for index, column in enumerate(summary["columns"])}
    check(len(sr) == len(st) == 72, name + " seventy-two System/Stock bins")
    if name == "control":
        damage_times = [8.13665, 20.6501, 33.1102]
        launch_times = [8, 20, 32]
        allocation_times = [7, 19, 31]
        return_times = [8.27329, 21.1501, 33.6102]
        repair_ends = [8.77329, 21.6501, 34.1102]
    else:
        loss_time = 8.13665
    if name == "control":
        nonzero_system = {"NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYUA", "NSYA", "FTMO", "NSYRP", "NREPT", "NDAM", "STACC", "NSYDT"}
    else:
        nonzero_system = {"NSYRY", "NSYMA", "NSYMO", "NSYMR", "NSYA", "FTMO", "NSYLA", "STACC"}
    for index, (system_row, stock_row) in enumerate(zip(sr, st)):
        a = index / 2
        b = a + .5
        check(near(system_row[sc["STINT"]], a) and near(system_row[sc["ETINT"]], b), name + f" System time {index}")
        check(near(stock_row[ic["STINT"]], a) and near(stock_row[ic["ETINT"]], b), name + f" Stock time {index}")
        if name == "control":
            ma = sum(overlap(a, b, allocation_times[k], return_times[k]) * 2 for k in range(3))
            mo = sum(overlap(a, b, launch_times[k], return_times[k]) * 2 for k in range(3))
            mr = sum(overlap(a, b, allocation_times[k], launch_times[k]) * 2 for k in range(3))
            rp = sum(overlap(a, b, return_times[k], repair_ends[k]) * 2 for k in range(3))
            expected = {
                "NSYRY": 1 - ma - rp, "NSYMA": ma, "NSYMO": mo, "NSYMR": mr,
                "NSYUA": rp, "NSYA": 1 - rp, "FTMO": mo, "NSYRP": rp,
                "NREPT": sum(a <= time < b for time in repair_ends),
                "NDAM": sum(a <= time < b for time in damage_times),
                "STACC": mo, "NSYDT": sum(a <= time < b for time in return_times),
            }
        else:
            active = overlap(a, b, 7, loss_time) * 2
            flight = overlap(a, b, 8, loss_time) * 2
            expected = {
                "NSYRY": overlap(a, b, 0, 7) * 2,
                "NSYMA": active,
                "NSYMO": flight,
                "NSYMR": overlap(a, b, 7, 8) * 2,
                "NSYA": overlap(a, b, 0, loss_time) * 2,
                "FTMO": 1 if a == 8 else (None if a > 8 else 0),
                "NSYLA": overlap(a, b, loss_time, 36) * 2,
                "STACC": flight,
            }
        for field, value in expected.items():
            check(system_row[sc[field]] is None if value is None else near(system_row[sc[field]], value), name + f" {field} bin {index}")
        for field, column in sc.items():
            if field in nonzero_system or field in ("UNID", "SID", "STINT", "ETINT", "SYDT"):
                continue
            check(system_row[column] == 0, name + f" zero {field} bin {index}")
        check(stock_row[ic["PNB"]] == 1 and stock_row[ic["NBO"]] == 0, name + f" stock bin {index}")
        for field, column in ic.items():
            if field in ("STINT", "ETINT", "PNB", "NBO", "NBOU", "ROS", "ROST", "WT", "WTT", "WTS"):
                continue
            check(stock_row[column] == 0, name + f" zero stock {field} bin {index}")

    flight_hours = sum(row[sc["NSYMO"]] * .5 for row in sr)
    lost_hours = sum(row[sc["NSYLA"]] * .5 for row in sr)
    repair_hours = sum(row[sc["NSYRP"]] * .5 for row in sr)
    if name == "attrition":
        check(near(flight_hours, .13665), "attrition observed flight time")
        check(near(lost_hours, 36 - 8.13665), "attrition lost-state integral")
        check(repair_hours == 0 and sr[-1][sc["NSYLA"]] == 1 and sr[-1][sc["NSYRY"]] == 0, "terminal lost without repair")
        check(all(row[sc["NDAM"]] == 0 for row in sr), "native NDAM zero despite logged damage")
    else:
        check(near(flight_hours, sum(return_times[k] - launch_times[k] for k in range(3))), "control flight integral")
        check(near(repair_hours, 1.5) and lost_hours == 0, "control repair without loss")
        check(sr[-1][sc["NSYRY"]] == 1 and sr[-1][sc["NSYLA"]] == 0, "control terminal ready")
    summary_row = rows(summary)[0]
    check(summary_row[uc["NREP"]] == 1 and summary_row[uc["RTIUP"]] == 36, name + " summary horizon")
    check(near(summary_row[uc["MTMF"]], .5056003928184509 if name == "control" else .04554833471775055), name + " summary MTMF")
    check(near(summary_row[uc["STMF"]], summary_row[uc["MTMF"]]), name + " summary STMF")
    check(near(summary_row[uc["MSTF"]], 1 if name == "control" else 1 / 3) and summary_row[uc["MSUF"]] == 0, name + " mission factors")
    run_results[name] = {
        "run_id": run_id,
        "closure_sha256": sha(run / "closure.json"),
        "report_sha256": sha(run / "report-raw.json"),
        "model_log_sha256": sha(run / "model.log"),
        "flight_aircraft_hours": flight_hours,
        "lost_aircraft_hours": lost_hours,
        "repair_aircraft_hours": repair_hours,
        "terminal_ready": sr[-1][sc["NSYRY"]],
        "terminal_lost": sr[-1][sc["NSYLA"]],
    }

verdict = {
    "schema": "simlox-h03-var03-independent-readonly/v1",
    "passed": not failures,
    "verdict": "GO: bounded first-hit attrition under coupled FM-PROB0/ATTRITION-PROB1 configuration" if not failures else "NO-GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "runs": run_results,
    "scope": "One fixed-seed, one-aircraft in-flight BATTLE-HIT produced whole-aircraft attrition at h8.13665, suppressed the retained FM/CM path, and left later missions without an aircraft.",
    "limits": [
        "This is a coupled source change: DamageFailureMode.PROB 1 to 0 and a new DamageItem.<ATTRITION> PROB1. The pair does not isolate one cell's causal effect.",
        "The native SystemResults.NDAM column remains zero in the attrition arm despite the logged BATTLE-HIT; this is an observed report behavior in this model, not a general rule about all attrition reports.",
        "FTMO marks the first half-hour bin and becomes null after the aircraft is lost, while NSYMO/STACC integrate the shorter actual flight; the marker is not interpreted as flight duration.",
        "No claim about multiple aircraft, other seeds, concurrent positive FM and attrition consequences, GUI visual behavior, or cross-engine parity.",
    ],
}
RESULT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
print(json.dumps({"verdict": verdict["verdict"], "checks_passed": verdict["checks_passed"], "checks_total": checks, "failures": failures, "result": str(RESULT)}))
sys.exit(0 if verdict["passed"] else 1)
