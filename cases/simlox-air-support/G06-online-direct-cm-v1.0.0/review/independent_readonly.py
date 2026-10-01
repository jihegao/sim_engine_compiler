"""Independent standard-library replay of G06 online versus deferred direct CM."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "G05-unavailable-standby-v1.0.3" / "unavailable-input.json"
SUPPORT = BASE / "G05-passive-switchover-v1.0.0" / "half-input.json"
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
       "accepted ONLM-Y continuous parent SHA")
    ck(sha(SUPPORT) == "d5a38dcb0006f3a2dc6447bdafdeb5c5e5a98b8eb2ccb49db57fa2801ae76c20",
       "accepted G05 passive structural support SHA")
    ck(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"],
       "frozen exact diff SHA")
    for name, path in (("simlox_exe", EXE), ("manual_pdf", MANUAL), ("table_dictionary", DICT)):
        ck(sha(path) == contract["installed_source_sha256"][name], f"installed {name} SHA")
    path = CASE / "deferred-input.json"
    ck(sha(path) == contract["child_sha256"] == diff["source_sha256"],
       "deferred frozen source SHA")
    parent, child = tables(read(PARENT), "model"), tables(read(path), "model")
    changed = {n for n in parent.keys() | child.keys() if parent.get(n) != child.get(n)}
    ck(set(parent) == set(child) and changed == set(diff["parent_to_deferred"]) ==
       {"ProblemDescription", "RBDParallel"}, "exact ONLM and description source delta")
    for name in parent:
        if name in changed:
            evidence = diff["parent_to_deferred"][name]
            ck(parent[name]["columns"] == child[name]["columns"] and
               rawrows(parent[name]) == evidence["before"] and
               rawrows(child[name]) == evidence["after"] and
               [i["instance_name"] for i in parent[name]["instances"]] ==
               [i["instance_name"] for i in child[name]["instances"]],
               f"exact {name} row/schema delta")
        else:
            ck(parent[name] == child[name], f"unchanged {name}")
    ck(len([t for t in child.values() if any(i["rows"] for i in t["instances"])]) == 23,
       "23 populated source tables")
    control = rows(child["Control"])[0]
    ck(control["NREPS"] == 1 and control["RSEED"] == "1" and control["SIMPE"] == 36 and
       control["RCINT"] == .5 and control["RELOP"] == "RBD", "fixed seed control")
    mission = rows(child["MissionType"])[0]
    profile = rows(child["OperationProfile"])
    ck(mission["DURN"] == 26 and mission["MPAT"] == "CONTINUOUS" and
       mission["TFOUT"] is None and mission["TFRET"] is None and
       len(profile) == 1 and profile[0]["STIM"] == 8,
       "same continuous 26h mission with cleared flight fraction fields")
    root = rows(child["RBDParallel"])[0]
    links = rows(child["RBDParallelStructure"])
    ck((root["RBID"], root["NBREQ"], root["NBOP"], root["TSWOV"], root["ONLM"]) ==
       ("G05-PASSIVE", 1, 1, .5, "N") and
       [(r["SRBID"], r["PRIO"], r["OPMID"], r["QTYPB"]) for r in links] ==
       [("POS-B", 1, "G04-OPS", 1), ("POS-A", 2, "G04-OPS", 1),
        ("POS-C", 3, "G04-OPS", 1)], "same passive priority, isolated ONLM=N")
    cm = {r["FMID"]: r for r in rows(child["CMLocation"])}
    ck(cm["FM-POS-B"]["CMT"] == 40 and cm["FM-POS-A"]["CMT"] == .5 and
       {r["MID"] for r in rows(child["FailureMode"])} == {"POS-A", "POS-B"},
       "same B40h and A0.5h direct CM source")
    return child


def event_checks(arm: str, log: str) -> dict:
    ident = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    first, end1, second, end2 = 8.94145, 9.44145, 17.5636, 18.0636
    ck(log.count("mission ordered: BASIC-MISSION") == 1 and
       f"Time: 7 {ident} mission allocates system: <TEACH-AIR-01,0>" in log and
       f"Time: 8 {ident} mission starting, duration: 26 : <TEACH-AIR-01,0>" in log and
       f"Time: 8 {ident} task starting: <TEACH-AIR-01,0>" in log and
       f"Time: 34 {ident} task completed: <TEACH-AIR-01,0>" in log and
       f"Time: 34 {ident} mission success:" in log and
       f"Time: 34 {ident} mission completed: <TEACH-AIR-01,0>" in log and
       "mission aborted:" not in log, "continuous mission task/event success 8-34")
    for start, end, origin, target in ((first, end1, "B", "A"),
                                       (second, end2, "A", "C")):
        path = f"<G05-PASSIVE [POS-{origin} -> POS-{target}]>"
        ck(f"Time: {start:g} <TEACH-AIR-01,0>{path}. switch over started. Will be finished at {end:g}." in log and
           f"Time: {end:g} <TEACH-AIR-01,0>{path}. Switch over stopped." in log and
           f"Time: {start:g} <TEACH-AIR-01,0> noncritical CM failure mode added, now" in log and
           f"Failure Mode: FM-POS-{origin} on materiel: <POS-{origin},0>" in log,
           f"POS-{origin} to POS-{target} switch and physical failure")
    ck(log.count("switch over started") == log.count("Switch over stopped") == 2 and
       log.count("failure mode added, now") == 2 and "FM-POS-C" not in log,
       "same B/A noncritical failure/switch sequence")
    ck(not re.search(r"Time: (?:[89]|1[0-9]|2[0-9]|3[0-3])(?:\.[0-9]+)?  system CM task", log) and
       not re.search(r"Time: (?:[89]|1[0-9]|2[0-9]|3[0-3])(?:\.[0-9]+)?  subtask", log),
       "no direct CM task starts before mission return")
    ck("Time: 34 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>, mission success," in log and
       "Time: 34 <TEACH-AIR-01,BASE-01,0> Repair task priority list:" in log,
       "deferred CM begins after successful return")
    ck("Time: 34  system CM task 1 on <TEACH-AIR-01,0> FMID: FM-POS-A" in log and
       "Time: 34  subtask 0 seqno 0 within system CM task 1 on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours" in log and
       "Time: 34.5  system CM task 1 on <TEACH-AIR-01,0> completed" in log,
       "A direct CM deferred to return and ends34.5")
    ck("Time: 34  system CM task 0 on <TEACH-AIR-01,0> FMID: FM-POS-B" in log and
       "Time: 34  subtask 1 seqno 0 within system CM task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 40 hours" in log and
       "system CM task 0 on <TEACH-AIR-01,0> completed" not in log,
       "B forty-hour CM deferred to return and open at horizon")
    return {"first_failure_hour": first, "first_switch_end": end1,
            "second_failure_hour": second, "second_switch_end": end2,
            "A_CM_start_hour": 34, "A_CM_end_hour": 34.5,
            "B_CM_start_hour": 34, "B_CM_planned_end_hour": 74,
            "mission_event_outcome": "success", "return_hour": 34,
            "B_repair_unfinished_at_horizon": True}


def report_checks(arm: str, report: dict, events: dict) -> dict:
    ts = tables(report, "report")
    ck(set(ts) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       "report table set")
    sm = rows(ts["ResultSummary"])
    ck(len(sm) == 1 and sm[0]["NREP"] == 1 and sm[0]["RTILW"] == 0 and
       sm[0]["RTIUP"] == 36 and sm[0]["MTMF"] == 1 and sm[0]["STMF"] > .96153 and
       sm[0]["STMF"] < .96155 and sm[0]["MSTF"] == sm[0]["MSUF"] == 0 and
       all(sm[0][f] == 0 for f in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")),
       "continuous success event and zero summary MSTF/MSUF")
    system, stock = rows(ts["SystemResults"]), rows(ts["StockTotalResults"])
    ck(len(system) == len(stock) == 72, "72 half-hour System/Stock bins")
    first, end1 = events["first_failure_hour"], events["first_switch_end"]
    second, end2 = events["second_failure_hour"], events["second_switch_end"]
    for i, (sr, st) in enumerate(zip(system, stock)):
        left, right = i / 2, (i + 1) / 2
        assigned = overlap(7, 34, left, right)
        reserved = overlap(7, 8, left, right)
        switching = overlap(first, end1, left, right) + overlap(second, end2, left, right)
        operating = overlap(8, 34, left, right) - switching
        repair = overlap(34, 36, left, right)
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": left, "ETINT": right, "NSYRY": 1 - assigned - repair,
                    "NSYMA": assigned, "NSYMO": operating, "NSYMR": reserved,
                    "NSYUA": repair, "NSYA": 1 - repair,
                    "FTMO": operating, "NSYRP": repair, "STACC": operating,
                    "NSYSW": switching,
                    "NFAIL": int(left <= first < right) + int(left <= second < right),
                    "NREPT": 1 if left <= 34.5 < right else 0}
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
    repair = sum(x["NSYRP"] * .5 for x in system)
    near(flight, 25, "integrated operating hours", 1e-5)
    near(switched, 1, "integrated system SWITCHOVER hours", 1e-5)
    near(repair, 2, "h34-36 B repair system occupancy", 1e-5)
    ck(sum(x["NFAIL"] for x in system) == 2 and sum(x["NREPT"] for x in system) == 1 and
       system[-1]["NSYRY"] == 0 and system[-1]["NSYUA"] == 1 and
       stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0,
       "two failures/one completed repair and terminal in-repair")
    return {"nrep": sm[0]["NREP"], "mtmf": sm[0]["MTMF"], "stmf": sm[0]["STMF"],
            "mstf": sm[0]["MSTF"], "msuf": sm[0]["MSUF"],
            "operating_hours": flight, "switch_hours": switched,
            "horizon_observed_repair_occupancy_hours": repair,
            "terminal_ready": system[-1]["NSYRY"],
            "terminal_under_repair": system[-1]["NSYUA"]}


def replay(arm: str, source: dict, contract: dict) -> dict:
    run_id = f"g06-deferred-v100-ssh-20261002-01"
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
    accepted = replay("deferred", source, contract)
    parent_run = PARENT.parent / "runs" / contract["parent"]["accepted_run_id"]
    parent_closure = read(parent_run / "closure.json")
    ck(parent_closure["source_hashes_before"]["input"] == sha(PARENT) and
       parent_closure["source_hashes_after"]["input"] == sha(PARENT) and
       parent_closure["raw"]["model.log"]["sha256"] == sha(parent_run / "model.log") and
       parent_closure["raw"]["report-raw.json"]["sha256"] == sha(parent_run / "report-raw.json"),
       "accepted ONLM-Y parent source/log/report seals")
    parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig")
    ck("Time: 8.94145  system CM task 0 on <TEACH-AIR-01,0> started" in parent_log and
       "Time: 17.5636  system CM task 1 on <TEACH-AIR-01,0> started" in parent_log and
       "Time: 18.0636  system CM task 1 on <TEACH-AIR-01,0> completed" in parent_log and
       "system CM task 0 on <TEACH-AIR-01,0> completed" not in parent_log,
       "ONLM-Y parent starts B/A in mission and A completes18.0636")
    parent_report = read(parent_run / "report-raw.json", native=True)
    child_report = read(CASE / "runs" / accepted["run_id"] / "report-raw.json", native=True)
    ptab, ctab = tables(parent_report, "report"), tables(child_report, "report")
    ck(set(ptab) == set(ctab) and
       ptab["ResultSummary"] == ctab["ResultSummary"] and
       ptab["StockTotalResults"] == ctab["StockTotalResults"],
       "summary and all Stock bins identical across ONLM arms")
    pr, cr = rows(ptab["SystemResults"]), rows(ctab["SystemResults"])
    ck(len(pr) == len(cr) == 72 and all(
       {k:v for k,v in x.items() if k != "NREPT"} ==
       {k:v for k,v in y.items() if k != "NREPT"}
       for x,y in zip(pr,cr)) and
       [(i,x["NREPT"],y["NREPT"]) for i,(x,y) in enumerate(zip(pr,cr)) if x["NREPT"] != y["NREPT"]] ==
       [(36,1,0),(69,0,1)],
       "all 72 System bins equal except completed A repair marker shifted h18 to h34.5")
    ck(accepted["events"]["first_failure_hour"] == 8.94145 and
       accepted["events"]["second_failure_hour"] == 17.5636 and
       accepted["events"]["A_CM_start_hour"] == 34,
       "matched failures/switches with child A CM deferred to return")
    result = {"schema": "g06-online-direct-cm-independent-readonly/v1",
              "case": CASE.name, "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO",
              "checks_passed": checks - len(failures), "checks_total": checks,
              "failures": failures, "accepted_run": accepted,
              "accepted_parent_run": contract["parent"]["accepted_run_id"],
              "accepted_raw_seal_count": len(RAW),
              "scope": "The child changes only ONLM Y to N plus description. Identical fixed-seed B/A failures and B-to-A/A-to-C switches accompany the same continuous mission success event at34. With ONLM Y, B/A direct CM starts at each failure and A completes18.0636. With ONLM N, both tasks start at return34; A completes34.5, B40h remains unfinished at horizon. All 72 report bins match except the NREPT completed-repair marker moves from [18,18.5) to [34.5,35).",
              "limits": ["This isolates ONLM only for one continuous mission and direct CM without replacement, resource contention or stock demand.",
                         "Both arms log mission success while ResultSummary.MSTF and MSUF are zero; retain event and summary observations separately.",
                         "One seed and horizon36 do not establish general repair policy, failure-clock semantics, fixed/extendable mission behavior, GUI view or cross-engine parity."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
