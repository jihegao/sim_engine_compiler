"""Independent standard-library replay of G05 nested passive switch native run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "G05-passive-switchover-v1.0.0" / "half-input.json"
SUPPORT = BASE / "G04-nested-series-parallel-v1.0.0" / "and-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICT = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
OUT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
RAW = {"report-export.log", "roundtrip-validation.json", "import.log", "model.log",
       "model.sxo", "run.log", "report-raw.json", "roundtrip-raw.json", "input.json",
       "export.log", "model.sxi", "steps.json"}
failures: list[str] = []
checks = 0


def ck(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native: bool = False) -> dict:
    value = path.read_text(encoding="utf-8-sig")
    if native:
        value = re.sub(r",\s*([}\]])", r"\1", value)
    return json.loads(value)


def tables(doc: dict, root: str) -> dict:
    source = doc[root]["tables"]
    result = {t["name"]: t for t in source}
    ck(len(result) == len(source), f"unique {root} table names")
    return result


def rows(table: dict) -> list[dict]:
    cols = [c["name"] for c in table["columns"]]
    result = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            ck(len(cols) == len(values), f"well-formed {table['name']} row")
            result.append(dict(zip(cols, values)))
    return result


def rawrows(table: dict) -> list[list]:
    return [row for inst in table["instances"] for row in inst["rows"]]


def near(actual: float, expected: float, label: str, tol: float = 2e-4) -> None:
    ck(actual is not None and abs(actual - expected) <= tol,
       f"{label}: {actual!r} versus {expected!r}")


def overlap(start: float, end: float, left: float, right: float) -> float:
    return max(0.0, min(end, right) - max(start, left)) / (right - left)


def source_checks(contract: dict, diff: dict) -> dict:
    ck(sha(PARENT) == contract["parent"]["sha256"] == diff["parent_sha256"],
       "accepted G05 half-hour passive parent SHA")
    ck(sha(SUPPORT) == contract["topology_template"]["sha256"] == diff["template_sha256"],
       "accepted G04 nested series template SHA")
    for name, path in (("simlox_exe", EXE), ("manual_pdf", MANUAL), ("table_dictionary", DICT)):
        ck(sha(path) == contract["installed_source_sha256"][name], f"installed {name} SHA")
    path = CASE / "nested-input.json"
    ck(sha(path) == contract["source_sha256"] == diff["source_sha256"],
       "nested frozen source SHA")
    parent, child, template = (tables(read(x), "model") for x in (PARENT, path, SUPPORT))
    changed = {n for n in parent.keys() | child.keys() if parent.get(n) != child.get(n)}
    ck(changed == set(diff["changed_tables"]) | set(diff["added_tables"]) and
       set(diff["changed_tables"]) == {"MaterielOperationalModes", "ProblemDescription",
                                       "RBDParallel", "RBDParallelStructure"} and
       set(diff["added_tables"]) == {"RBDSeries", "RBDSeriesStructure"},
       "exact parent topology delta table set")
    for name in parent:
        if name in diff["changed_tables"]:
            evidence = diff["changed_tables"][name]
            ck(parent[name]["columns"] == child[name]["columns"] and
               rawrows(parent[name]) == evidence["before"] and
               rawrows(child[name]) == evidence["after"] and
               [i["instance_name"] for i in parent[name]["instances"]] ==
               [i["instance_name"] for i in child[name]["instances"]],
               f"exact changed {name} rows/schema")
        else:
            ck(parent[name] == child[name], f"unchanged {name}")
    for name in diff["added_tables"]:
        ck(name not in parent and child[name] == diff["added_tables"][name] and
           child[name]["columns"] == template[name]["columns"],
           f"added {name} exact source and accepted template schema")
    ck(len([t for t in child.values() if any(i["rows"] for i in t["instances"])]) == 25,
       "25 populated source tables")
    control = rows(child["Control"])[0]
    ck(control["NREPS"] == 1 and control["RSEED"] == "1" and control["SIMPE"] == 36 and
       control["RCINT"] == .5 and control["RELOP"] == "RBD", "fixed seed control")
    mission = rows(child["MissionType"])[0]
    profile = rows(child["OperationProfile"])
    ck(mission["DURN"] == 26 and len(profile) == 1 and profile[0]["STIM"] == 8,
       "fixed 26h mission")
    modes = rows(child["MaterielOperationalModes"])
    ck([r["MID"] for r in modes] == ["TEACH-AIR-01", "POS-A", "POS-B", "POS-C"] and
       modes[0]["RBID"] == "G05-ROOT-SERIES" and
       all(r["RBID"] is None and r["OPMID"] == "G04-OPS" for r in modes[1:]),
       "aircraft series root and leaf modes")
    series, serieslink = rows(child["RBDSeries"]), rows(child["RBDSeriesStructure"])
    ck(len(series) == 1 and series[0]["RBID"] == "G05-ROOT-SERIES" and
       [(r["SRBID"], r["OPMID"], r["QTYPB"]) for r in serieslink] ==
       [("G05-PASSIVE", None, 1), ("POS-C", "G04-OPS", 1)] and
       all(r["RBID"] == "G05-ROOT-SERIES" for r in serieslink),
       "series root has null-mode passive child and nonfailing C leaf")
    root = rows(child["RBDParallel"])[0]
    links = rows(child["RBDParallelStructure"])
    ck((root["RBID"], root["NBREQ"], root["NBOP"], root["TSWOV"], root["ONLM"]) ==
       ("G05-PASSIVE", 1, 1, .5, "N") and
       [(r["SRBID"], r["PRIO"], r["OPMID"], r["QTYPB"]) for r in links] ==
       [("POS-B", 1, "G04-OPS", 1), ("POS-A", 2, "G04-OPS", 1)],
       "passive B/A child with C moved out")
    fms = rows(child["FailureMode"])
    cm = rows(child["CMLocation"])
    ck({(r["FMID"], r["MID"], r["FRQ"], r["OPID"]) for r in fms} ==
       {("FM-POS-B", "POS-B", 600000, "OPHOURS"),
        ("FM-POS-A", "POS-A", 300000, "OPHOURS")} and
       {r["FMID"] for r in cm} == {"FM-POS-B", "FM-POS-A"} and
       all(r["CMT"] == .5 and r["STID"] == "BASE-01" for r in cm),
       "B/A failure and direct repair; C nonfailing")
    return child


def event_checks(arm: str, log: str) -> dict:
    ident = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    first, switch_end, second, ret, repaired = 8.94145, 9.44145, 17.5636, 24.0636, 24.5636
    ck(log.count("mission ordered: BASIC-MISSION") == 1 and
       f"Time: 7 {ident} mission allocates system: <TEACH-AIR-01,0>" in log and
       f"Time: 8 {ident} mission starting, duration: 26 : <TEACH-AIR-01,0>" in log,
       "one 26h mission allocates/launches")
    path = "<G05-PASSIVE [POS-B -> POS-A]>"
    ck(f"Time: {first:g} <TEACH-AIR-01,0>{path}. switch over started. Will be finished at {switch_end:g}." in log and
       f"Time: {switch_end:g} <TEACH-AIR-01,0>{path}. Switch over stopped." in log and
       log.count("switch over started") == log.count("Switch over stopped") == 1,
       "B-to-A passive child half-hour switch")
    ck(f"Time: {first:g} <TEACH-AIR-01,0> noncritical CM failure mode added" in log and
       f"Time: {second:g} <TEACH-AIR-01,0> critical CM failure mode added" in log and
       "Failure Mode: FM-POS-B on materiel: <POS-B,0>" in log and
       "Failure Mode: FM-POS-A on materiel: <POS-A,0>" in log and
       "FM-POS-C" not in log and log.count("failure mode added, now") == 2,
       "B then A failure and criticality; C remains nonfailing")
    ck(f"Time: {second:g} {ident} mission aborted:" in log and
       f"Time: {ret:g} {ident} aborted mission completed:" in log and
       "mission success:" not in log and
       f"Time: {ret:g} <TEACH-AIR-01,BASE-01,0> System arrives" in log,
       "A failure aborts mission; return after 6.5h")
    near(ret - second, 6.5, "abort-to-return hours", 1e-4)
    for task, pos in enumerate(("B", "A")):
        ck(f"Time: {ret:g}  system CM task {task} on <TEACH-AIR-01,0> started" in log and
           f"Time: {ret:g}  system CM task {task} on <TEACH-AIR-01,0> FMID: FM-POS-{pos}" in log and
           f"Time: {ret:g}  subtask {task} seqno 0 within system CM task {task} on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours" in log and
           f"Time: {repaired:g}  system CM task {task} on <TEACH-AIR-01,0> completed" in log,
           f"postreturn CM for POS-{pos}")
    ck(f"Time: {repaired:g} <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log,
       "terminal ready aircraft")
    return {"first_failure_hour": first, "switch_end": switch_end,
            "second_failure_hour": second, "mission_outcome": "abort",
            "return_hour": ret, "repair_end_hour": repaired}


def report_checks(arm: str, report: dict, events: dict) -> dict:
    ts = tables(report, "report")
    ck(set(ts) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       "report table set")
    sm = rows(ts["ResultSummary"])
    ck(len(sm) == 1 and sm[0]["NREP"] == 1 and sm[0]["RTILW"] == 0 and
       sm[0]["RTIUP"] == 36 and sm[0]["MSTF"] == 1 and sm[0]["MSUF"] == 0 and
       all(sm[0][f] == 0 for f in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")),
       "aborted mission summary")
    near(sm[0]["MTMF"], .6178310513496399, "MTMF", 1e-6)
    near(sm[0]["STMF"], .5986002683639526, "STMF", 1e-6)
    system, stock = rows(ts["SystemResults"]), rows(ts["StockTotalResults"])
    ck(len(system) == len(stock) == 72, "72 half-hour System/Stock bins")
    ret, repaired = events["return_hour"], events["repair_end_hour"]
    for i, (sr, st) in enumerate(zip(system, stock)):
        left, right = i / 2, (i + 1) / 2
        assigned = overlap(7, ret, left, right)
        reserved = overlap(7, 8, left, right)
        switching = overlap(8.94145, 9.44145, left, right)
        operating = overlap(8, ret, left, right) - switching
        repair = overlap(ret, repaired, left, right)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": left, "ETINT": right, "NSYRY": 1 - assigned - repair,
                    "NSYMA": assigned, "NSYMO": operating, "NSYMR": reserved,
                    "NSYUA": repair, "NSYA": 1 - repair,
                    "FTMO": operating, "NSYRP": repair, "STACC": operating,
                    "NSYSW": switching,
                    "NFAIL": int(left <= 8.94145 < right) + int(left <= 17.5636 < right),
                    "NREPT": 2 if left <= repaired < right else 0,
                    "NSYDT": 1 if left <= ret < right else 0,
                    "SYDT": .5 if left <= ret < right else None}
        for field, val in expected.items():
            if isinstance(val, (int, float)):
                near(sr[field], val, f"bin {i} {field}")
            else:
                ck(sr[field] == val, f"bin {i} {field}")
        ck(all(v in (0, None) for k, v in sr.items() if k not in expected),
           f"bin {i} other System fields")
        ck(st["STINT"] == left and st["ETINT"] == right and st["PNB"] == 1 and
           all(v in (0, None) for k, v in st.items() if k not in {"STINT", "ETINT", "PNB"}),
           f"bin {i} zero-demand Stock ledger")
    flight = sum(x["NSYMO"] * .5 for x in system)
    switched = sum(x["NSYSW"] * .5 for x in system)
    near(flight, ret - 8 - .5, "integrated operating hours", 1e-4)
    near(switched, .5, "integrated root SWITCHOVER hours", 1e-5)
    near(sum(x["NSYRP"] * .5 for x in system), .5, "repair occupancy hours", 1e-5)
    ck(sum(x["NFAIL"] for x in system) == 2 and sum(x["NREPT"] for x in system) == 2 and
       system[-1]["NSYRY"] == 1 and system[-1]["NSYMA"] == 0 and
       stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0,
       "two failures/two repairs and terminal ready")
    return {"nrep": sm[0]["NREP"], "mtmf": sm[0]["MTMF"], "stmf": sm[0]["STMF"],
            "msuf": sm[0]["MSUF"], "operating_hours": flight,
            "system_switchover_hours": switched, "terminal_ready": system[-1]["NSYRY"]}


def replay(arm: str, source: dict, contract: dict) -> dict:
    run_id = f"g05-nested-v100-ssh-20261002-01"
    p = CASE / "runs" / run_id
    invocation, closure, steps = (read(p / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck(invocation["run_id"] == closure["run_id"] == run_id and
       invocation["arm"] == arm and
       invocation["input_sha256"] == sha(CASE / f"{arm}-input.json") and
       invocation["parent_sha256"] == sha(PARENT) and
       invocation["support_sha256"] == sha(SUPPORT) and
       closure["invocation_sha256"] == sha(p / "invocation.json") and
       closure["error"] is None and closure["scope"] == "five_step_native_candidate",
       f"{arm} invocation/closure binding")
    files = {"input": CASE / f"{arm}-input.json", "parent": PARENT, "support": SUPPORT,
             "table_dictionary": DICT, "manual": MANUAL, "contract": CASE / "contract.json",
             "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
             "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
             "python": PYTHON, "runner_script": CASE / "run_native_ssh.ps1", "simlox_exe": EXE}
    ck(closure["source_hashes_before"] == closure["source_hashes_after"] and
       set(closure["source_hashes_before"]) == set(files), f"{arm} source stability/map")
    keys = {"input": "input_sha256", "parent": "parent_sha256", "support": "support_sha256",
            "contract": "contract_sha256", "builder": "builder_sha256", "checker": "checker_sha256",
            "python": "python_sha256", "runner_script": "runner_script_sha256",
            "simlox_exe": "simlox_exe_sha256"}
    for name, path in files.items():
        digest = sha(path)
        ck(closure["source_hashes_before"].get(name) == digest and
           invocation.get(keys.get(name, ""), digest) == digest,
           f"{arm} source/invocation SHA {name}")
    ck(set(closure["raw"]) == RAW, f"{arm} twelve raw seals")
    for name, meta in closure["raw"].items():
        path = p / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"],
           f"{arm} raw SHA {name}")
    ck(sha(p / "input.json") == sha(CASE / f"{arm}-input.json") and
       (p / "model.sxi").stat().st_size > 4 and (p / "model.sxo").stat().st_size > 4,
       f"{arm} copied source and valid model files")
    ck(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
       "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
       invocation["gui"] == {"pid": 13340, "session_id": 1,
                             "start_utc": "2026-09-28T10:09:56.8261381Z"},
       f"{arm} session-zero SSH/queue/GUI guard")
    ck([s["name"] for s in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(s["exit_code"] == 0 and s["gui_preserved"] and s["status"] == "completed" for s in steps) and
       "-threads 1 -calc" in steps[2]["arguments"], f"{arm} guarded steps")
    ck([x["name"] for x in invocation["planned_commands"]] ==
       ["import", "export", "calc", "jsonreport"] and
       "-threads 1 -calc" in invocation["planned_commands"][2]["arguments"],
       f"{arm} planned native commands")
    exported = tables(read(p / "roundtrip-raw.json", native=True), "model")
    for name, table in source.items():
        if any(i["rows"] for i in table["instances"]):
            ck(exported.get(name) == table, f"{arm} exact populated-table roundtrip {name}")
    runlog = (p / "run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       re.findall(r"warning #(\d+)", runlog) == ["108"] and
       not re.search(r"error #\d+", runlog, re.I) and "Saving results" in runlog,
       f"{arm} converter and calculation")
    ck("Import completed!" in (p / "import.log").read_text(encoding="utf-8-sig") and
       "Export completed!" in (p / "export.log").read_text(encoding="utf-8-sig"),
       f"{arm} import/export")
    events = event_checks(arm, (p / "model.log").read_text(encoding="utf-8-sig"))
    metrics = report_checks(arm, read(p / "report-raw.json", native=True), events)
    return {"run_id": run_id, "input_sha256": sha(p / "input.json"),
            "closure_sha256": sha(p / "closure.json"), "log_sha256": sha(p / "model.log"),
            "report_sha256": sha(p / "report-raw.json"), "events": events, **metrics}


def main() -> None:
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    source = source_checks(contract, diff)
    accepted = replay("nested", source, contract)
    parent_run = PARENT.parent / "runs" / contract["parent"]["accepted_run_id"]
    parent_closure = read(parent_run / "closure.json")
    ck(parent_closure["source_hashes_before"]["input"] == sha(PARENT) and
       parent_closure["source_hashes_after"]["input"] == sha(PARENT) and
       parent_closure["raw"]["model.log"]["sha256"] == sha(parent_run / "model.log"),
       "accepted half-hour parent source and log seal")
    parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig")
    ck("Time: 8.94145 <TEACH-AIR-01,0><G05-PASSIVE [POS-B -> POS-A]>. switch over started. Will be finished at 9.44145." in parent_log and
       "Time: 17.5636 <TEACH-AIR-01,0> noncritical CM failure mode added" in parent_log and
       "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in parent_log,
       "same B/A sample parent continues successfully with C passive")
    ck(accepted["events"]["first_failure_hour"] == 8.94145 and
       accepted["events"]["second_failure_hour"] == 17.5636 and
       accepted["system_switchover_hours"] > .4999 and accepted["msuf"] == 0,
       "nested source changes outcome with matched B/A event times")
    result = {"schema": "g05-nested-switch-independent-readonly/v1",
              "case": CASE.name, "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO",
              "checks_passed": checks - len(failures), "checks_total": checks,
              "failures": failures, "accepted_run": accepted,
              "accepted_parent_run": contract["parent"]["accepted_run_id"],
              "accepted_raw_seal_count": len(RAW),
              "scope": "The authored/roundtripped series root contains a passive B/A child and nonfailing C leaf. At fixed seed1, B failure8.94145 starts child B-to-A switch to9.44145; SystemResults records 0.5h system SWITCHOVER. A failure17.5636 is critical, aborts the mission, and both B/A repairs run after return24.0636 to ready24.5636. The accepted three-branch passive parent with the same B/A event times succeeds, supporting propagation of this child's unavailability through the series root for this trace.",
              "limits": ["The text log names the G05-PASSIVE child, not a separate G05-ROOT-SERIES state transition; root propagation is inferred jointly from exact source topology, aircraft criticality/mission abort, NSYSW and the accepted parent contrast.",
                         "One seed, a nonfailing C leaf and one B/A failure order do not prove a general nested truth table or other priority/standby states.",
                         "No unavailable preferred standby, overlapping switches, GUI RBD view or cross-engine parity claim follows."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
