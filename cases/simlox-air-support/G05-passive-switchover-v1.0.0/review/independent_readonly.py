"""Independent standard-library replay of G05 passive switchover native runs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "G04-three-branch-threshold-v1.0.0" / "one-input.json"
SUPPORT = BASE / "G04-series-active-parallel-v1.0.1" / "parallel-input.json"
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
       "accepted G04 one-of-three active parent SHA")
    ck(sha(SUPPORT) == "ea56a9daf8705189c9162529355b28636ef7db168987b17ee90cdedbe9bb4b6f",
       "accepted passive schema donor SHA")
    for name, path in (("simlox_exe", EXE), ("manual_pdf", MANUAL), ("table_dictionary", DICT)):
        ck(sha(path) == contract["installed_source_sha256"][name], f"installed {name} SHA")
    parent = tables(read(PARENT), "model")
    sources = {}
    changed_expected = {"MaterielOperationalModes", "ProblemDescription", "RBDParallel",
                        "RBDParallelStructure"}
    for arm, switch in (("zero", 0.0), ("half", .5)):
        path = CASE / f"{arm}-input.json"
        ck(sha(path) == contract["source_sha256"][arm] == diff["source_sha256"][arm],
           f"{arm} frozen source SHA")
        child = tables(read(path), "model")
        changed = {n for n in parent.keys() | child.keys() if parent.get(n) != child.get(n)}
        ck(set(parent) == set(child) and changed == set(diff["parent_to_arm"][arm]) ==
           changed_expected, f"{arm} exact changed-table set")
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
           ("G05-PASSIVE", 1, 1, switch, "N") and
           [(r["SRBID"], r["PRIO"], r["OPMID"], r["QTYPB"]) for r in links] ==
           [("POS-B", 1, "G04-OPS", 1), ("POS-A", 2, "G04-OPS", 1),
            ("POS-C", 3, "G04-OPS", 1)] and all(r["RBID"] == "G05-PASSIVE" for r in links),
           f"{arm} one-operated passive B/A/C priority and switch time")
        fms = rows(child["FailureMode"])
        cm = rows(child["CMLocation"])
        ck({(r["FMID"], r["MID"], r["FRQ"], r["OPID"]) for r in fms} ==
           {("FM-POS-B", "POS-B", 600000, "OPHOURS"),
            ("FM-POS-A", "POS-A", 300000, "OPHOURS")} and
           {r["FMID"] for r in cm} == {"FM-POS-B", "FM-POS-A"} and
           all(r["CMT"] == .5 and r["STID"] == "BASE-01" for r in cm),
           f"{arm} B/A failure and direct repair; no C failure mode")
        sources[arm] = child
    first, second = sources["zero"], sources["half"]
    ck({n for n in first if first[n] != second[n]} == set(diff["zero_to_half"]) ==
       {"ProblemDescription", "RBDParallel"}, "pair changes switch duration and description only")
    for name in diff["zero_to_half"]:
        ck(rawrows(first[name]) == diff["zero_to_half"][name]["before"] and
           rawrows(second[name]) == diff["zero_to_half"][name]["after"],
           f"exact pair {name} row delta")
    return sources


def event_checks(arm: str, log: str) -> dict:
    ident = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    first = 8.94145
    second = 17.0636 if arm == "zero" else 17.5636
    switch = 0 if arm == "zero" else .5
    ck(log.count("mission ordered: BASIC-MISSION") == 1 and
       f"Time: 7 {ident} mission allocates system: <TEACH-AIR-01,0>" in log and
       f"Time: 8 {ident} mission starting, duration: 26 : <TEACH-AIR-01,0>" in log and
       f"Time: 34 {ident} mission success:" in log and
       f"Time: 34 {ident} mission completed: <TEACH-AIR-01,0>" in log and
       "mission aborted:" not in log, f"{arm} one successful 26h mission")
    for start, end, origin, target, pos, count in (
        (first, first + switch, "B", "A", "B", 1),
        (second, second + switch, "A", "C", "A", 2)):
        path = f"<G05-PASSIVE [POS-{origin} -> POS-{target}]>"
        ck(f"Time: {start:g} <TEACH-AIR-01,0>{path}. switch over started. Will be finished at {end:g}." in log and
           f"Time: {end:g} <TEACH-AIR-01,0>{path}. Switch over stopped." in log and
           f"Time: {start:g} <TEACH-AIR-01,0> noncritical CM failure mode added, now" in log,
           f"{arm} POS-{origin} to POS-{target} switch start/end and failure")
        ck(f"{count} failures:" in log and
           f"Failure Mode: FM-POS-{pos} on materiel: <POS-{pos},0>" in log,
           f"{arm} physical failure POS-{pos}")
    ck(log.count("switch over started") == log.count("Switch over stopped") == 2 and
       log.count("failure mode added, now") == 2 and
       "FM-POS-C" not in log and
       not re.search(r"Time: [^\r\n]+> critical CM failure", log),
       f"{arm} exactly B/A noncritical failures and switches; C remains unfailing")
    for task, pos in enumerate(("B", "A")):
        ck(f"Time: 34  system CM task {task} on <TEACH-AIR-01,0> started" in log and
           f"Time: 34  system CM task {task} on <TEACH-AIR-01,0> FMID: FM-POS-{pos}" in log and
           f"Time: 34  subtask {task} seqno 0 within system CM task {task} on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours" in log and
           f"Time: 34.5  system CM task {task} on <TEACH-AIR-01,0> completed" in log,
           f"{arm} postreturn half-hour CM for POS-{pos}")
    ck("Time: 34.5 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log,
       f"{arm} terminal aircraft ready")
    return {"first_failure_hour": first, "second_failure_hour": second,
            "switch_hours_each": switch, "mission_outcome": "success", "return_hour": 34,
            "repair_end_hour": 34.5}


def report_checks(arm: str, report: dict, events: dict) -> dict:
    ts = tables(report, "report")
    ck(set(ts) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{arm} report table set")
    sm = rows(ts["ResultSummary"])
    expected_stmf = 1 if arm == "zero" else 25 / 26
    ck(len(sm) == 1 and sm[0]["NREP"] == 1 and sm[0]["RTILW"] == 0 and
       sm[0]["RTIUP"] == 36 and sm[0]["MTMF"] == sm[0]["MSTF"] == sm[0]["MSUF"] == 1 and
       all(sm[0][f] == 0 for f in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")),
       f"{arm} one mission summary")
    near(sm[0]["STMF"], expected_stmf, f"{arm} system time factor", 1e-6)
    system, stock = rows(ts["SystemResults"]), rows(ts["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"{arm} 72 half-hour System/Stock bins")
    first, second, delay = events["first_failure_hour"], events["second_failure_hour"], events["switch_hours_each"]
    for i, (sr, st) in enumerate(zip(system, stock)):
        left, right = i / 2, (i + 1) / 2
        assigned = overlap(7, 34, left, right)
        reserved = overlap(7, 8, left, right)
        switching = (overlap(first, first + delay, left, right) +
                     overlap(second, second + delay, left, right))
        operating = overlap(8, 34, left, right) - switching
        repair = overlap(34, 34.5, left, right)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": left, "ETINT": right, "NSYRY": 1 - assigned - repair,
                    "NSYMA": assigned, "NSYMO": operating, "NSYMR": reserved,
                    "NSYUA": repair, "NSYA": 1 - repair,
                    "FTMO": operating, "NSYRP": repair, "STACC": operating,
                    "NSYSW": switching,
                    "NFAIL": int(left <= first < right) + int(left <= second < right),
                    "NREPT": 2 if left <= 34.5 < right else 0,
                    "NSYDT": 1 if left <= 34 < right else 0,
                    "SYDT": .5 if left <= 34 < right else None}
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
    near(flight, 26 - 2 * delay, f"{arm} integrated operating hours", 1e-4)
    near(switched, 2 * delay, f"{arm} integrated switch hours", 1e-4)
    near(sum(x["NSYRP"] * .5 for x in system), .5,
         f"{arm} concurrent repair elapsed hours", 1e-5)
    ck(sum(x["NFAIL"] for x in system) == 2 and sum(x["NREPT"] for x in system) == 2 and
       system[-1]["NSYRY"] == 1 and system[-1]["NSYMA"] == 0 and
       stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0,
       f"{arm} two failures/two repairs and terminal ready")
    return {"nrep": sm[0]["NREP"], "mtmf": sm[0]["MTMF"], "stmf": sm[0]["STMF"],
            "msuf": sm[0]["MSUF"], "operating_hours": flight,
            "switch_hours": switched, "terminal_ready": system[-1]["NSYRY"]}


def replay(arm: str, source: dict, contract: dict) -> dict:
    run_id = f"g05-passive-{arm}-v100-ssh-20261002-01"
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
    accepted = {arm: replay(arm, sources[arm], contract) for arm in ("zero", "half")}
    ck(accepted["zero"]["events"]["first_failure_hour"] ==
       accepted["half"]["events"]["first_failure_hour"] == 8.94145 and
       accepted["half"]["events"]["second_failure_hour"] -
       accepted["zero"]["events"]["second_failure_hour"] == .5 and
       accepted["zero"]["switch_hours"] == 0 and accepted["half"]["switch_hours"] > .9999,
       "paired first B sample; second A failure follows delayed activation")
    result = {"schema": "g05-passive-switchover-independent-readonly/v1",
              "case": CASE.name, "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO",
              "checks_passed": checks - len(failures), "checks_total": checks,
              "failures": failures, "accepted_runs": accepted,
              "accepted_raw_seal_count": 2 * len(RAW),
              "scope": "For one fixed seed and a 26h mission, native events identify B-to-A then A-to-C passive switches in both arms. TSWOV=0 transitions occur at the failure times, while TSWOV=0.5 produces two half-hour SWITCHOVER intervals and 25 operating hours; both missions succeed and B/A direct repairs finish after return.",
              "limits": ["Second A failure samples differ by 0.5h between arms; this is not an identical-time paired stochastic path.",
                         "The source and log show no C failure mode or C failure, so unavailable third-branch behavior is untested.",
                         "One seed/replication does not prove general priority selection, internal failure-clock onset, reliability, passive online repair, nested standby, GUI view or cross-engine parity."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
