"""Independent standard-library replay of G05 passive NBREQ boundary native runs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "G05-passive-switchover-v1.0.0" / "half-input.json"
SUPPORT = BASE / "G04-three-branch-threshold-v1.0.0" / "one-input.json"
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


def source_checks(contract: dict, diff: dict) -> dict[str, dict]:
    ck(sha(PARENT) == contract["parent"]["sha256"] == diff["parent_sha256"],
       "accepted G05 half-hour passive parent SHA")
    ck(sha(SUPPORT) == "cfdf287c4de93638e8117c71ad3de1846da3c62c24254bf7d2a3f0f7c7c0c4d7",
       "accepted G04 structural support SHA")
    for name, path in (("simlox_exe", EXE), ("manual_pdf", MANUAL), ("table_dictionary", DICT)):
        ck(sha(path) == contract["installed_source_sha256"][name], f"installed {name} SHA")
    parent = tables(read(PARENT), "model")
    sources = {}
    for arm, required in (("one", 1), ("two", 2)):
        path = CASE / f"{arm}-input.json"
        ck(sha(path) == contract["source_sha256"][arm] == diff["source_sha256"][arm],
           f"{arm} frozen source SHA")
        child = tables(read(path), "model")
        changed = {n for n in parent.keys() | child.keys() if parent.get(n) != child.get(n)}
        ck(set(parent) == set(child) and changed == set(diff["parent_to_arm"][arm]) ==
           {"ProblemDescription", "RBDParallel"}, f"{arm} exact parent changed tables")
        for name in parent:
            if name in changed:
                evidence = diff["parent_to_arm"][arm][name]
                ck(parent[name]["columns"] == child[name]["columns"] and
                   rawrows(parent[name]) == evidence["before"] and
                   rawrows(child[name]) == evidence["after"] and
                   [i["instance_name"] for i in parent[name]["instances"]] ==
                   [i["instance_name"] for i in child[name]["instances"]],
                   f"{arm} exact {name} row/schema delta")
            else:
                ck(parent[name] == child[name], f"{arm} unchanged {name}")
        ck(len([t for t in child.values() if any(i["rows"] for i in t["instances"])]) == 23,
           f"{arm} 23 populated tables")
        control = rows(child["Control"])[0]
        ck(control["NREPS"] == 1 and control["RSEED"] == "1" and control["SIMPE"] == 36 and
           control["RCINT"] == .5 and control["RELOP"] == "RBD", f"{arm} fixed seed control")
        mission = rows(child["MissionType"])[0]
        profile = rows(child["OperationProfile"])
        ck(mission["DURN"] == 26 and len(profile) == 1 and profile[0]["STIM"] == 8,
           f"{arm} fixed 26h mission")
        modes = rows(child["MaterielOperationalModes"])
        root = rows(child["RBDParallel"])[0]
        links = rows(child["RBDParallelStructure"])
        ck([r["MID"] for r in modes] == ["TEACH-AIR-01", "POS-A", "POS-B", "POS-C"] and
           modes[0]["RBID"] == "G05-PASSIVE" and
           all(r["RBID"] is None and r["OPMID"] == "G04-OPS" for r in modes[1:]),
           f"{arm} root and leaf mode bindings")
        ck((root["RBID"], root["NBREQ"], root["NBOP"], root["TSWOV"], root["ONLM"]) ==
           ("G05-PASSIVE", required, 2, .5, "N") and
           [(r["SRBID"], r["PRIO"], r["OPMID"], r["QTYPB"]) for r in links] ==
           [("POS-B", 1, "G04-OPS", 1), ("POS-A", 2, "G04-OPS", 1),
            ("POS-C", 3, "G04-OPS", 1)] and all(r["RBID"] == "G05-PASSIVE" for r in links),
           f"{arm} NBOP2 NBREQ{required} and B/A/C priority")
        fms = rows(child["FailureMode"])
        cm = rows(child["CMLocation"])
        ck({(r["FMID"], r["MID"], r["FRQ"], r["OPID"]) for r in fms} ==
           {("FM-POS-B", "POS-B", 600000, "OPHOURS"),
            ("FM-POS-A", "POS-A", 300000, "OPHOURS")} and
           {r["FMID"] for r in cm} == {"FM-POS-B", "FM-POS-A"} and
           all(r["CMT"] == .5 and r["STID"] == "BASE-01" for r in cm),
           f"{arm} B/A failure and direct repair; no C failure mode")
        sources[arm] = child
    first, second = sources["one"], sources["two"]
    ck({n for n in first if first[n] != second[n]} == set(diff["one_to_two"]) ==
       {"ProblemDescription", "RBDParallel"}, "pair changes NBREQ and description only")
    for name in diff["one_to_two"]:
        ck(rawrows(first[name]) == diff["one_to_two"][name]["before"] and
           rawrows(second[name]) == diff["one_to_two"][name]["after"],
           f"exact pair {name} row delta")
    return sources


def event_checks(arm: str, log: str) -> dict:
    ident = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    failure1, failure2 = 8.62763, 11.5942
    sw_end = 9.12763
    ret = 34 if arm == "one" else 15.1884
    repaired = ret + .5
    ck(log.count("mission ordered: BASIC-MISSION") == 1 and
       f"Time: 7 {ident} mission allocates system: <TEACH-AIR-01,0>" in log and
       f"Time: 8 {ident} mission starting, duration: 26 : <TEACH-AIR-01,0>" in log,
       f"{arm} mission identity and launch")
    path = "<G05-PASSIVE [POS-B -> POS-C]>"
    ck(f"Time: {failure1:g} <TEACH-AIR-01,0>{path}. switch over started. Will be finished at {sw_end:g}." in log and
       f"Time: {sw_end:g} <TEACH-AIR-01,0>{path}. Switch over stopped." in log and
       log.count("switch over started") == log.count("Switch over stopped") == 1,
       f"{arm} sole branch B-to-C half-hour switch")
    ck(f"Time: {failure1:g} <TEACH-AIR-01,0> noncritical CM failure mode added" in log and
       f"Time: {failure2:g} <TEACH-AIR-01,0> " in log and
       log.count("failure mode added, now") == 2 and
       "Failure Mode: FM-POS-B on materiel: <POS-B,0>" in log and
       "Failure Mode: FM-POS-A on materiel: <POS-A,0>" in log and
       "FM-POS-C" not in log, f"{arm} physical B then A failures, no C failure")
    if arm == "one":
        ck(f"Time: {failure2:g} <TEACH-AIR-01,0> noncritical CM failure mode added" in log and
           f"Time: 34 {ident} mission success:" in log and
           f"Time: 34 {ident} mission completed: <TEACH-AIR-01,0>" in log and
           "mission aborted:" not in log, "NBREQ1 retains operation and mission success")
    else:
        ck(f"Time: {failure2:g} <TEACH-AIR-01,0> critical CM failure mode added" in log and
           f"Time: {failure2:g} {ident} mission aborted:" in log and
           f"Time: {ret:g} {ident} aborted mission completed:" in log and
           "mission success:" not in log, "NBREQ2 becomes critical and aborts")
    ck(f"Time: {ret:g} <TEACH-AIR-01,BASE-01,0> System arrives" in log and
       f"Time: {repaired:g} <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log,
       f"{arm} return then terminal ready")
    for task, pos in enumerate(("B", "A")):
        ck(f"Time: {ret:g}  system CM task {task} on <TEACH-AIR-01,0> started" in log and
           f"Time: {ret:g}  system CM task {task} on <TEACH-AIR-01,0> FMID: FM-POS-{pos}" in log and
           f"Time: {ret:g}  subtask {task} seqno 0 within system CM task {task} on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours" in log and
           f"Time: {repaired:g}  system CM task {task} on <TEACH-AIR-01,0> completed" in log,
           f"{arm} postreturn direct CM for POS-{pos}")
    return {"first_failure_hour": failure1, "second_failure_hour": failure2,
            "branch_switch_start": failure1, "branch_switch_end": sw_end,
            "mission_outcome": "success" if arm == "one" else "abort",
            "return_hour": ret, "repair_end_hour": repaired}


def report_checks(arm: str, report: dict, events: dict) -> dict:
    ts = tables(report, "report")
    ck(set(ts) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{arm} report table set")
    sm = rows(ts["ResultSummary"])
    ck(len(sm) == 1 and sm[0]["NREP"] == 1 and sm[0]["RTILW"] == 0 and
       sm[0]["RTIUP"] == 36 and sm[0]["MSTF"] == 1 and
       sm[0]["MSUF"] == (1 if arm == "one" else 0) and
       all(sm[0][f] == 0 for f in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")),
       f"{arm} mission summary")
    near(sm[0]["MTMF"], 1 if arm == "one" else .27647578716278076, f"{arm} MTMF", 1e-6)
    near(sm[0]["STMF"], 1 if arm == "one" else .2572450339794159, f"{arm} STMF", 1e-6)
    system, stock = rows(ts["SystemResults"]), rows(ts["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"{arm} 72 half-hour System/Stock bins")
    ret, repaired = events["return_hour"], events["repair_end_hour"]
    for i, (sr, st) in enumerate(zip(system, stock)):
        left, right = i / 2, (i + 1) / 2
        assigned = overlap(7, ret, left, right)
        reserved = overlap(7, 8, left, right)
        switching = overlap(8.62763, 9.12763, left, right) if arm == "two" else 0
        operating = overlap(8, ret, left, right) - switching
        repair = overlap(ret, repaired, left, right)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": left, "ETINT": right, "NSYRY": 1 - assigned - repair,
                    "NSYMA": assigned, "NSYMO": operating, "NSYMR": reserved,
                    "NSYUA": repair, "NSYA": 1 - repair,
                    "FTMO": operating, "NSYRP": repair, "STACC": operating,
                    "NSYSW": switching,
                    "NFAIL": int(left <= 8.62763 < right) + int(left <= 11.5942 < right),
                    "NREPT": 2 if left <= repaired < right else 0,
                    "NSYDT": 1 if left <= ret < right else 0,
                    "SYDT": .5 if left <= ret < right else None}
        for field, val in expected.items():
            if isinstance(val, (int, float)):
                near(sr[field], val, f"{arm} bin {i} {field}")
            else:
                ck(sr[field] == val, f"{arm} bin {i} {field}")
        ck(all(v in (0, None) for k, v in sr.items() if k not in expected),
           f"{arm} bin {i} other System fields")
        ck(st["STINT"] == left and st["ETINT"] == right and st["PNB"] == 1 and
           all(v in (0, None) for k, v in st.items() if k not in {"STINT", "ETINT", "PNB"}),
           f"{arm} bin {i} zero-demand Stock ledger")
    flight = sum(x["NSYMO"] * .5 for x in system)
    switched = sum(x["NSYSW"] * .5 for x in system)
    near(flight, ret - 8 - (.5 if arm == "two" else 0),
         f"{arm} integrated operating hours", 1e-4)
    near(switched, .5 if arm == "two" else 0, f"{arm} system SWITCHOVER hours", 1e-5)
    near(sum(x["NSYRP"] * .5 for x in system), .5,
         f"{arm} repair occupancy hours", 1e-5)
    ck(sum(x["NFAIL"] for x in system) == 2 and sum(x["NREPT"] for x in system) == 2 and
       system[-1]["NSYRY"] == 1 and system[-1]["NSYMA"] == 0 and
       stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0,
       f"{arm} two failures/two repairs and terminal ready")
    return {"nrep": sm[0]["NREP"], "mtmf": sm[0]["MTMF"], "stmf": sm[0]["STMF"],
            "msuf": sm[0]["MSUF"], "operating_hours": flight,
            "system_switchover_hours": switched, "terminal_ready": system[-1]["NSYRY"]}


def replay(arm: str, source: dict, contract: dict) -> dict:
    run_id = f"g05-nbreq-{arm}-v100-ssh-20261002-01"
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
    sources = source_checks(contract, diff)
    accepted = {arm: replay(arm, sources[arm], contract) for arm in ("one", "two")}
    ck(accepted["one"]["events"]["first_failure_hour"] ==
       accepted["two"]["events"]["first_failure_hour"] == 8.62763 and
       accepted["one"]["events"]["second_failure_hour"] ==
       accepted["two"]["events"]["second_failure_hour"] == 11.5942 and
       accepted["one"]["system_switchover_hours"] == 0 and
       accepted["two"]["system_switchover_hours"] == .5,
       "paired same failure samples, branch switch versus system SWITCHOVER")
    result = {"schema": "g05-passive-threshold-independent-readonly/v1",
              "case": CASE.name, "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO",
              "checks_passed": checks - len(failures), "checks_total": checks,
              "failures": failures, "accepted_runs": accepted,
              "accepted_raw_seal_count": 2 * len(RAW),
              "scope": "For one fixed seed with NBOP=2 and B/A initially operated, B fails at8.62763 and a B-to-C branch switch lasts to9.12763 in both arms. NBREQ1 retains system operation and succeeds at34 with zero system NSYSW; NBREQ2 records 0.5h system SWITCHOVER and aborts on A failure at11.5942, returning15.1884. Both defer B/A half-hour CM until return and finish ready.",
              "limits": ["The log identifies a B-to-C switch, but does not list initial operated branches directly; B/A initial operation is inferred from B/A failure and C standby selection plus source priority.",
                         "One fixed seed and no C failure do not cover other priorities, NBREQ values, third-branch failure, or overlapping switches.",
                         "This pair does not resolve the manual's activation failure-clock onset discrepancy, nor demonstrate GUI view or cross-engine parity."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
