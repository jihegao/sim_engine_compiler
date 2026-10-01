"""Independent standard-library replay of G04 nested OR and AND native runs."""
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
       "accepted G04 threshold parent SHA")
    ck(sha(SUPPORT) == "ea56a9daf8705189c9162529355b28636ef7db168987b17ee90cdedbe9bb4b6f",
       "accepted G04 nested schema donor SHA")
    for name, path in (("simlox_exe", EXE), ("manual_pdf", MANUAL), ("table_dictionary", DICT)):
        ck(sha(path) == contract["installed_source_sha256"][name], f"installed {name} SHA")
    parent = tables(read(PARENT), "model")
    sources = {}
    expected_changed = {"CMLocation", "FailureMode", "MaterielOperationalModes", "ProblemDescription",
                        "RBDParallel", "RBDParallelStructure", "RBDSeries", "RBDSeriesStructure"}
    for arm in ("or", "and"):
        path = CASE / f"{arm}-input.json"
        ck(sha(path) == contract["source_sha256"][arm] == diff["source_sha256"][arm],
           f"{arm} frozen source SHA")
        child = tables(read(path), "model")
        changed = {n for n in parent.keys() | child.keys() if parent.get(n) != child.get(n)}
        ck(changed == set(diff["parent_to_arm"][arm]) == expected_changed,
           f"{arm} exact changed-table set")
        for name in parent.keys() | child.keys():
            if name in changed:
                evidence = diff["parent_to_arm"][arm][name]
                old, new = parent.get(name), child.get(name)
                ck((rawrows(old) if old else None) == evidence["before"] and
                   (rawrows(new) if new else None) == evidence["after"] and
                   (old["columns"] == new["columns"] and evidence["columns"] is None if old else
                    new["columns"] == evidence["columns"]),
                   f"{arm} exact {name} row/schema delta")
                if old and new:
                    ck([i["instance_name"] for i in old["instances"]] ==
                       [i["instance_name"] for i in new["instances"]],
                       f"{arm} unchanged {name} instance topology")
            else:
                ck(parent[name] == child[name], f"{arm} unchanged table {name}")
        ck(len([t for t in child.values() if any(i["rows"] for i in t["instances"])]) == 25,
           f"{arm} twenty-five populated source tables")
        control = rows(child["Control"])[0]
        ck(control["NREPS"] == 1 and control["RSEED"] == "1" and control["SIMPE"] == 36 and
           control["RCINT"] == .5 and control["RELOP"] == "RBD", f"{arm} fixed-seed long RBD run")
        mission = rows(child["MissionType"])[0]
        profile = rows(child["OperationProfile"])
        ck(mission["DURN"] == 26 and len(profile) == 1 and profile[0]["STIM"] == 8,
           f"{arm} sole 26h mission scheduled at hour eight")
        pos = rows(child["MaterielPosition"])
        modes = rows(child["MaterielOperationalModes"])
        ck([r["MPID"] for r in pos] == ["POS-A", "POS-B", "POS-C"] and
           [r["MID"] for r in modes] == ["TEACH-AIR-01", "POS-A", "POS-B", "POS-C"] and
           all(r["OPMID"] == "G04-OPS" for r in modes), f"{arm} explicit position/leaf modes")
        root = "G04-ROOT-OR" if arm == "or" else "G04-ROOT-AND"
        nested = "G04-SER-BC" if arm == "or" else "G04-PAR-BC"
        ck(modes[0]["RBID"] == root and all(r["RBID"] is None for r in modes[1:]),
           f"{arm} root bound only to aircraft")
        series, parallel = rows(child["RBDSeries"]), rows(child["RBDParallel"])
        serlink = rows(child["RBDSeriesStructure"])
        parlink = rows(child["RBDParallelStructure"])
        ck(len(series) == len(parallel) == 1 and
           (parallel[0]["NBREQ"], parallel[0]["NBOP"], parallel[0]["TSWOV"], parallel[0]["ONLM"]) ==
           (1, 2, 0.0, "N") and series[0]["RBID"] == (nested if arm == "or" else root) and
           parallel[0]["RBID"] == (root if arm == "or" else nested),
           f"{arm} nested series and active parallel block identity")
        rootlinks, childlinks = (parlink, serlink) if arm == "or" else (serlink, parlink)
        ck([(r["RBID"], r["SRBID"], r["OPMID"], r["QTYPB"]) for r in rootlinks] ==
           [(root, "POS-A", "G04-OPS", 1), (root, nested, None, 1)] and
           [(r["RBID"], r["SRBID"], r["OPMID"], r["QTYPB"]) for r in childlinks] ==
           [(nested, "POS-B", "G04-OPS", 1), (nested, "POS-C", "G04-OPS", 1)],
           f"{arm} A root leaf plus B/C nested leaves")
        fms = rows(child["FailureMode"])
        cm = rows(child["CMLocation"])
        ck({(r["FMID"], r["MID"], r["FRQ"], r["OPID"]) for r in fms} ==
           {("FM-POS-B", "POS-B", 600000, "OPHOURS"),
            ("FM-POS-C", "POS-C", 300000, "OPHOURS")} and
           {r["FMID"] for r in cm} == {"FM-POS-B", "FM-POS-C"} and
           all(r["ID"] == "TEACH-AIR-01" and r["STID"] == "BASE-01" and r["CMT"] == .5
               for r in cm), f"{arm} B/C failure mode and corrected CM location")
        sources[arm] = child
    first, second = sources["or"], sources["and"]
    ck({n for n in first if first[n] != second[n]} == set(diff["or_to_and"]) ==
       {"MaterielOperationalModes", "ProblemDescription", "RBDParallel",
        "RBDParallelStructure", "RBDSeries", "RBDSeriesStructure"},
       "paired discriminator only nested RBD topology and description")
    for name in diff["or_to_and"]:
        ck(rawrows(first[name]) == diff["or_to_and"][name]["before"] and
           rawrows(second[name]) == diff["or_to_and"][name]["after"] and
           first[name]["columns"] == second[name]["columns"], f"exact pair {name} row diff")
    return sources


def event_checks(arm: str, log: str) -> dict:
    identity = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    first, second = 8.62763, 16.7498
    end = 34.0 if arm == "or" else 23.2498
    repair_end = end + .5
    ck(log.count("mission ordered: BASIC-MISSION") == 1 and
       f"Time: 7 {identity} mission allocates system: <TEACH-AIR-01,0>" in log and
       f"Time: 8 {identity} mission starting, duration: 26 : <TEACH-AIR-01,0>" in log,
       f"{arm} sole long mission identity and launch")
    ck(f"Time: {first:g} <TEACH-AIR-01,0> noncritical CM failure mode added" in log and
       f"Time: {second:g} <TEACH-AIR-01,0> " in log and
       log.count("failure mode added, now") == 2 and
       "Failure Mode: FM-POS-B on materiel: <POS-B,0>" in log and
       "Failure Mode: FM-POS-C on materiel: <POS-C,0>" in log and
       "POS-A,0>" not in log,
       f"{arm} two distinct B/C failures and unaffected A")
    if arm == "or":
        ck(f"Time: {second:g} <TEACH-AIR-01,0> noncritical CM failure mode added" in log and
           f"Time: 34 {identity} mission success:" in log and
           f"Time: 34 {identity} mission completed: <TEACH-AIR-01,0>" in log and
           "mission aborted:" not in log,
           "OR root remains operational after both B/C failures")
    else:
        ck(f"Time: {second:g} <TEACH-AIR-01,0> critical CM failure mode added" in log and
           f"Time: {second:g} {identity} mission aborted:" in log and
           f"Time: {end:g} {identity} aborted mission completed:" in log and
           "mission success:" not in log,
           "AND root aborts when second nested branch fails")
    ck(f"Time: {end:g} <TEACH-AIR-01,BASE-01,0> System arrives" in log and
       all(f"Time: {end:g}  system CM task {i} on <TEACH-AIR-01,0> started" in log and
           f"Time: {end:g}  system CM task {i} on <TEACH-AIR-01,0> FMID: FM-POS-{pos}" in log and
           f"Time: {end:g}  subtask {i} seqno 0 within system CM task {i} on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours" in log and
           f"Time: {repair_end:g}  system CM task {i} on <TEACH-AIR-01,0> completed" in log
           for i, pos in enumerate(("B", "C"))) and
       f"Time: {repair_end:g} <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log,
       f"{arm} two concurrent postmission half-hour CM tasks")
    near(repair_end - end, .5, f"{arm} CM elapsed duration", 1e-5)
    return {"first_failure_hour": first, "first_position": "POS-B",
            "second_failure_hour": second, "second_position": "POS-C",
            "second_status": "noncritical" if arm == "or" else "critical",
            "outcome": "success" if arm == "or" else "abort",
            "mission_return_hour": end, "repair_end_hour": repair_end}


def report_checks(arm: str, report: dict, events: dict) -> dict:
    t = tables(report, "report")
    ck(set(t) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{arm} report table set")
    summary = rows(t["ResultSummary"])
    mtmf = 1 if arm == "or" else .5865303874015808
    ck(len(summary) == 1 and summary[0]["NREP"] == 1 and
       summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36 and
       summary[0]["MTMF"] == summary[0]["STMF"] == mtmf and
       summary[0]["MSTF"] == 1 and summary[0]["MSUF"] == (1 if arm == "or" else 0) and
       all(summary[0][k] == 0 for k in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")),
       f"{arm} summary factors")
    system, stock = rows(t["SystemResults"]), rows(t["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"{arm} 72 half-hour System/Stock bins")
    end = events["mission_return_hour"]
    repaired = events["repair_end_hour"]
    for i, (sr, st) in enumerate(zip(system, stock)):
        left, right = i / 2, (i + 1) / 2
        assigned = overlap(7, end, left, right)
        operating = overlap(8, end, left, right)
        reserved = overlap(7, 8, left, right)
        repair = overlap(end, repaired, left, right)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": left, "ETINT": right, "NSYRY": 1 - assigned - repair,
                    "NSYMA": assigned, "NSYMO": operating, "NSYMR": reserved,
                    "NSYUA": repair, "NSYA": 1 - repair,
                    "FTMO": operating, "NSYRP": repair, "STACC": operating,
                    "NFAIL": int(left <= 8.62763 < right) + int(left <= 16.7498 < right),
                    "NREPT": 2 if left <= repaired < right else 0,
                    "NSYDT": 1 if left <= end < right else 0,
                    "SYDT": .5 if left <= end < right else None}
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
    near(flight, end - 8, f"{arm} integrated aircraft flight hours", 1e-4)
    near(sum(x["NSYRP"] * .5 for x in system), .5,
         f"{arm} concurrent repair interval hours", 1e-4)
    ck(sum(x["NFAIL"] for x in system) == 2 and
       sum(x["NREPT"] for x in system) == 2 and
       system[-1]["NSYRY"] == 1 and system[-1]["NSYMA"] == 0 and
       stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0,
       f"{arm} two failures/two repairs and terminal ready")
    return {"nrep": summary[0]["NREP"], "mtmf": summary[0]["MTMF"],
            "msuf": summary[0]["MSUF"], "flight_hours": flight,
            "failure_count": 2, "repair_task_count": 2,
            "repair_elapsed_hours": .5, "terminal_ready": system[-1]["NSYRY"]}


def replay(arm: str, source: dict, contract: dict) -> dict:
    run_id = f"g04-nested-{arm}-v100-ssh-20261002-01"
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
    accepted = {arm: replay(arm, sources[arm], contract) for arm in ("or", "and")}
    ck(accepted["or"]["events"]["first_failure_hour"] ==
       accepted["and"]["events"]["first_failure_hour"] == 8.62763 and
       accepted["or"]["events"]["second_failure_hour"] ==
       accepted["and"]["events"]["second_failure_hour"] == 16.7498 and
       accepted["or"]["events"]["outcome"] == "success" and
       accepted["and"]["events"]["outcome"] == "abort",
       "paired identical B/C samples and divergent nested-RBD outcome")
    result = {"schema": "g04-nested-series-parallel-independent-readonly/v1",
              "case": CASE.name, "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO",
              "checks_passed": checks - len(failures), "checks_total": checks,
              "failures": failures, "accepted_runs": accepted,
              "accepted_raw_seal_count": 2 * len(RAW),
              "scope": "At fixed seed one, POS-B fails at8.62763 and POS-C at16.7498 in both arms while POS-A has no configured failure. Native events and 72-bin ledgers show the A OR (B AND C) mission succeeds at34 and A AND (B OR C) aborts on the second failure at16.7498; two direct half-hour CM tasks start after each return.",
              "limits": ["This tests one observed B/C failure combination and a healthy A, not a complete nested Boolean truth table.",
                         "One seed/replication cannot establish population reliability, other failure orders or same-time events.",
                         "No passive switching, online maintenance, QTYPB>1, GUI RBD view or cross-engine parity claim follows."]}

    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
