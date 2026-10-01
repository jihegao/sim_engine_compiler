"""Independent stdlib replay of G04 v1.0.1 source and sealed native evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
PARENT = BASE / "G02-var01-position-modes-v1.0.0" / "native-input.json"
SUPPORT = BASE / "G01-var01-lru-sru-v1.0.1" / "native-input.json"
V100 = BASE / "G04-series-active-parallel-v1.0.0"
OUT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICT = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
RAW = {"report-export.log", "roundtrip-validation.json", "import.log", "model.log",
       "model.sxo", "run.log", "report-raw.json", "roundtrip-raw.json", "input.json",
       "export.log", "model.sxi", "steps.json"}
checks = 0
failures: list[str] = []


def ck(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path, native: bool = False) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if native:
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def tables(doc: dict, root: str) -> dict:
    seq = doc[root]["tables"]
    result = {t["name"]: t for t in seq}
    ck(len(result) == len(seq), f"unique {root} tables")
    return result


def rows(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    result = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            ck(len(names) == len(values), f"well-formed {table['name']} row")
            result.append(dict(zip(names, values)))
    return result


def near(actual: float, expected: float, label: str, tol: float = 2e-4) -> None:
    ck(actual is not None and abs(actual - expected) <= tol,
       f"{label}: {actual!r} versus {expected!r}")


def overlap(start: float, end: float, left: float, right: float) -> float:
    return max(0.0, min(end, right) - max(start, left)) / (right - left)


def source_checks(contract: dict, diff: dict) -> dict[str, dict]:
    ck(sha(PARENT) == contract["direct_parent"]["input_sha256"] == diff["parent_sha256"],
       "accepted G02 parent fingerprint")
    ck(sha(SUPPORT) == "9c25a414615ac4ea523ee989385a913c692923e04bc41c6984b6866e86204bb9",
       "accepted G01 instructional source fingerprint")
    ck(sha(MANUAL) == contract["source"]["manual_pdf_sha256"] and
       sha(DICT) == contract["source"]["dictionary_sha256"] and
       sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
       "installed manual/dictionary/executable fingerprints")
    ck(sha(CASE / "exact-diff.json") ==
       "ea065a1072433b253922c1c0a24cfd6c8ad43dab542e0363cc63031a6792ff6b",
       "frozen exact-diff source hash")
    parent = tables(read(PARENT), "model")
    result = {}
    for arm in ("series", "parallel"):
        path = CASE / f"{arm}-input.json"
        ck(sha(path) == contract["input_sha256"][arm] == diff["arms"][arm]["input_sha256"],
           f"{arm} frozen source input SHA")
        child = tables(read(path), "model")
        old = set(parent)
        ck(old - set(child) == set() and
           set(child) - old == set(diff["arms"][arm]["added_tables"]) and
           {n for n in old if parent[n] != child[n]} ==
           set(diff["arms"][arm]["changed_existing_tables"]) == {"Control", "ProblemDescription"} and
           len([n for n in old if parent[n] == child[n]]) == diff["arms"][arm]["unchanged_existing_tables"] == 33,
           f"{arm} exact parent table delta")
        before, after = rows(parent["Control"]), rows(child["Control"])
        ck(len(before) == len(after) == 1 and
           {n for n in before[0] if before[0][n] != after[0][n]} == {"RELOP"} and
           before[0]["RELOP"] is None and after[0]["RELOP"] == "RBD" and
           after[0]["NREPS"] == 1 and after[0]["RSEED"] == "1" and
           after[0]["SIMPE"] == 36 and after[0]["RCINT"] == .5,
           f"{arm} sole Control.RELOP change")
        ck(len(rows(child["ProblemDescription"])) == 1 and
           rows(parent["ProblemDescription"]) != rows(child["ProblemDescription"]),
           f"{arm} description provenance delta")
        root = "G04-SERIES" if arm == "series" else "G04-PARALLEL"
        ck(rows(child["OperationalModes"]) ==
           [{"OPMID": "G04-OPS", "DESCR": "Two-position mission RBD", "NOTE": None}] and
           rows(child["MissionOperationalModes"]) ==
           [{"MTID": "BASIC-MISSION", "SID": "TEACH-AIR-01", "OPMID": "G04-OPS", "NOTE": None}],
           f"{arm} mission operational mode")
        mm = rows(child["MaterielOperationalModes"])
        ck(len(mm) == 3 and [(r["MID"], r["OPMID"], r["RBID"], r["USERT"]) for r in mm] ==
           [("TEACH-AIR-01", "G04-OPS", root, 1.0),
            ("POS-A", "G04-OPS", None, 1.0), ("POS-B", "G04-OPS", None, 1.0)],
           f"{arm} system root and two explicit leaf modes")
        structure = rows(child["RBDSeriesStructure" if arm == "series" else "RBDParallelStructure"])
        ck(len(structure) == 2 and
           [(r["RBID"], r["SRBID"], r["OPMID"], r["QTYPB"]) for r in structure] ==
           [(root, "POS-A", "G04-OPS", 1), (root, "POS-B", "G04-OPS", 1)],
           f"{arm} two position blocks exactly once")
        if arm == "series":
            ck(len(rows(child["RBDSeries"])) == 1 and
               rows(child["RBDSeries"])[0]["RBID"] == root,
               "series root block")
        else:
            pr = rows(child["RBDParallel"])
            ck(len(pr) == 1 and pr[0]["RBID"] == root and
               (pr[0]["NBREQ"], pr[0]["NBOP"], pr[0]["TSWOV"], pr[0]["ONLM"]) ==
               (1, 2, 0.0, "N"), "active one-of-two parallel, no online CM")
        ck(len([t for t in child.values() if any(i["rows"] for i in t["instances"])]) == 23,
           f"{arm} twenty-three populated business tables")
        result[arm] = child
    return result


def event_checks(arm: str, log: str) -> list[dict]:
    failures_at = [8.62763, 20.8222, 33.0996]
    positions = ["B", "B", "A"]
    if arm == "series":
        returns = [9.12763, 21.3222, 33.5996]
        repaired = [9.62763, 21.8222, 34.0996]
        ck(len(re.findall(r"^Time: [^\r\n]+ critical CM failure mode added", log, re.M)) == 3 and
           "noncritical CM failure mode added" not in log and
           log.count("mission aborted:") == 3 and
           "mission success:" not in log, "series three critical mission aborts")
    else:
        returns = [10, 22, 34]
        repaired = [10.5, 22.5, 34.5]
        ck(len(re.findall(r"^Time: [^\r\n]+ noncritical CM failure mode added", log, re.M)) == 3 and
           not re.search(r"^Time: [^\r\n]+ critical CM failure mode added", log, re.M) and
           log.count("mission success:") == 3 and
           "mission aborted:" not in log, "parallel three noncritical mission successes")
    ck(log.count("system CM task 0 on <TEACH-AIR-01,0> FMID:") == 1 and
       log.count("system CM task 1 on <TEACH-AIR-01,0> FMID:") == 1 and
       log.count("system CM task 2 on <TEACH-AIR-01,0> FMID:") == 1 and
       not re.search(r"stock demand|replacement", log, re.I),
       f"{arm} three direct CM task IDs and no stock movement")
    events = []
    for i, (f, pos, ret, rep) in enumerate(zip(failures_at, positions, returns, repaired)):
        ordered, launched = 7 + 12 * i, 8 + 12 * i
        ident = f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>"
        fmid = f"FM-POS-{pos}"
        ck(f"Time: {ordered:g} <TEACH-UNIT> mission ordered: BASIC-MISSION" in log and
           f"Time: {ordered:g} {ident} mission allocates system: <TEACH-AIR-01,0>" in log and
           f"Time: {launched:g} {ident} mission starting, duration: 2 : <TEACH-AIR-01,0>" in log,
           f"{arm} mission {i} unique identity/allocation/launch")
        ck(f"Time: {f:g} <TEACH-AIR-01,0> " in log and
           f"Failure Mode: {fmid} on materiel: <POS-{pos},0>" in log and
           f"Time: {ret:g} <TEACH-AIR-01,BASE-01,0> System arrives" in log,
           f"{arm} mission {i} position-labelled failure and return")
        if arm == "series":
            ck(f"Time: {f:g} {ident} mission aborted:" in log and
               f"Time: {ret:g} {ident} aborted mission completed:" in log and
               f"< system CM task {i} on <TEACH-AIR-01,0>, C, 0.5>" in log,
               f"series mission {i} failure ends operation")
        else:
            ck(f"Time: {ret:g} {ident} mission success:" in log and
               f"Time: {ret:g} {ident} mission completed: <TEACH-AIR-01,0>" in log and
               f"< system CM task {i} on <TEACH-AIR-01,0>, NC, 0.5>" in log,
               f"parallel mission {i} succeeds after branch failure")
        ck(f"Time: {ret:g}  system CM task {i} on <TEACH-AIR-01,0> started" in log and
           f"Time: {ret:g}  system CM task {i} on <TEACH-AIR-01,0> FMID: {fmid}" in log and
           f"Time: {ret:g}  subtask {i} seqno 0 within system CM task {i} on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours" in log and
           f"Time: {rep:g}  system CM task {i} on <TEACH-AIR-01,0> completed" in log and
           f"Time: {rep:g} <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>" in log,
           f"{arm} mission {i} postmission half-hour CM and recovery")
        near(rep - ret, .5, f"{arm} mission {i} direct CM duration", 1e-5)
        events.append({"mission_id": i, "position": pos, "failure_hour": f,
                       "mission_end_hour": ret, "repair_end_hour": rep,
                       "outcome": "abort" if arm == "series" else "success"})
    return events


def report_checks(arm: str, report: dict) -> dict:
    t = tables(report, "report")
    ck(set(t) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{arm} report table set")
    summary = rows(t["ResultSummary"])
    value = .6748974919319153 if arm == "series" else 1
    ck(len(summary) == 1 and summary[0]["NREP"] == 1 and
       summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36 and
       summary[0]["MTMF"] == summary[0]["STMF"] == value and
       summary[0]["MSTF"] == 1 and summary[0]["MSUF"] == (0 if arm == "series" else 1) and
       all(summary[0][f] == 0 for f in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF")),
       f"{arm} one-replication summary and factors")
    system, stock = rows(t["SystemResults"]), rows(t["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"{arm} 72 System/Stock bins")
    returned = [9.12763, 21.3222, 33.5996] if arm == "series" else [10, 22, 34]
    repaired = [x + .5 for x in returned]
    failures_at = [8.62763, 20.8222, 33.0996]
    for i, (sr, st) in enumerate(zip(system, stock)):
        left, right = i / 2, (i + 1) / 2
        assigned = sum(overlap(7 + 12 * j, returned[j], left, right) for j in range(3))
        operating = sum(overlap(8 + 12 * j, returned[j], left, right) for j in range(3))
        reserved = sum(overlap(7 + 12 * j, 8 + 12 * j, left, right) for j in range(3))
        repair = sum(overlap(returned[j], repaired[j], left, right) for j in range(3))
        expected = {"UNID": "Total over all Units", "SID": "Total over all Systems",
                    "STINT": left, "ETINT": right, "NSYRY": 1 - assigned - repair,
                    "NSYMA": assigned, "NSYMO": operating, "NSYMR": reserved,
                    "NSYUA": repair, "NSYA": 1 - repair, "FTMO": operating,
                    "NSYRP": repair, "STACC": operating,
                    "NFAIL": sum(left <= f < right for f in failures_at),
                    "NREPT": sum(left <= t < right for t in repaired),
                    "NSYDT": sum(left <= t < right for t in returned),
                    "SYDT": .5 if any(left <= t < right for t in returned) else None}
        for field, value in expected.items():
            if isinstance(value, (int, float)):
                near(sr[field], value, f"{arm} bin {i} {field}")
            else:
                ck(sr[field] == value, f"{arm} bin {i} {field}")
        ck(all(v in (0, None) for k, v in sr.items() if k not in expected),
           f"{arm} bin {i} other System fields")
        ck(st["STINT"] == left and st["ETINT"] == right and st["PNB"] == 1 and
           all(v in (0, None) for k, v in st.items() if k not in {"STINT", "ETINT", "PNB"}),
           f"{arm} bin {i} Stock ledger")
    flight = sum(r["NSYMO"] * .5 for r in system)
    near(flight, sum(returned[j] - (8 + 12 * j) for j in range(3)),
         f"{arm} event-derived flight hours", 1e-4)
    near(sum(r["NSYRP"] * .5 for r in system), 1.5,
         f"{arm} three postmission CM tasks", 1e-4)
    ck(sum(r["NFAIL"] for r in system) == sum(r["NREPT"] for r in system) == 3 and
       system[-1]["NSYRY"] == 1 and system[-1]["NSYMA"] == 0 and
       stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0,
       f"{arm} failure/repair counts and terminal ready/stock")
    return {"nrep": summary[0]["NREP"], "mtmf": summary[0]["MTMF"],
            "msuf": summary[0]["MSUF"], "flight_hours": flight,
            "failure_count": 3, "repair_count": 3, "terminal_ready": system[-1]["NSYRY"]}


def replay(arm: str, source: dict, contract: dict) -> dict:
    run_id = f"g04-{arm}-v101-ssh-20261002-01"
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
    invocation_keys = {"input": "input_sha256", "parent": "parent_sha256",
                       "support": "support_sha256", "contract": "contract_sha256",
                       "builder": "builder_sha256", "checker": "checker_sha256",
                       "python": "python_sha256", "runner_script": "runner_script_sha256",
                       "simlox_exe": "simlox_exe_sha256"}
    for name, path in files.items():
        digest = sha(path)
        ck(closure["source_hashes_before"].get(name) == digest and
           invocation.get(invocation_keys.get(name, ""), digest) == digest,
           f"{arm} source/invocation seal {name}")
    ck(set(closure["raw"]) == RAW, f"{arm} twelve raw seals")
    for name, meta in closure["raw"].items():
        path = p / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"],
           f"{arm} raw seal {name}")
    ck(sha(p / "input.json") == sha(CASE / f"{arm}-input.json") and
       (p / "model.sxi").stat().st_size > 4 and (p / "model.sxo").stat().st_size > 4,
       f"{arm} copied input and valid SXI/SXO")
    ck(invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
       "sshd.exe" in invocation["ssh_ancestor_names"] and
       invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
       invocation["gui"] == {"pid": 13340, "session_id": 1,
                             "start_utc": "2026-09-28T10:09:56.8261381Z"},
       f"{arm} guarded session-0 SSH/queue/GUI")
    ck([s["name"] for s in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"] and
       all(s["exit_code"] == 0 and s["gui_preserved"] and s["status"] == "completed" for s in steps) and
       "-threads 1 -calc" in steps[2]["arguments"], f"{arm} five guarded steps")
    ck([x["name"] for x in invocation["planned_commands"]] ==
       ["import", "export", "calc", "jsonreport"] and
       "-threads 1 -calc" in invocation["planned_commands"][2]["arguments"],
       f"{arm} planned native commands")
    exported = tables(read(p / "roundtrip-raw.json", native=True), "model")
    for name, table in source.items():
        if any(i["rows"] for i in table["instances"]):
            ck(exported.get(name) == table, f"{arm} exact native business roundtrip {name}")
    runlog = (p / "run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       re.findall(r"warning #(\d+)", runlog) == ["108"] and
       not re.search(r"error #\d+", runlog, re.I) and "Saving results" in runlog,
       f"{arm} zero converter errors and expected warning")
    ck("Import completed!" in (p / "import.log").read_text(encoding="utf-8-sig") and
       "Export completed!" in (p / "export.log").read_text(encoding="utf-8-sig"),
       f"{arm} import/export")
    events = event_checks(arm, (p / "model.log").read_text(encoding="utf-8-sig"))
    metrics = report_checks(arm, read(p / "report-raw.json", native=True))
    return {"run_id": run_id, "input_sha256": sha(p / "input.json"),
            "closure_sha256": sha(p / "closure.json"), "log_sha256": sha(p / "model.log"),
            "report_sha256": sha(p / "report-raw.json"), "events": events, **metrics}


def diagnostic() -> dict:
    d = read(CASE / "diagnostic-predecessor.json")
    p = V100 / "runs" / d["run_id"]
    log = (p / "run.log").read_text(encoding="utf-8-sig")
    ck(sha(V100 / "series-input.json") ==
       sha(CASE / "diagnostic-v100-series-input.json") ==
       sha(p / "input.json") == d["input_sha256"] and
       sha(p / "closure.json") == d["closure_sha256"] and
       sha(p / "run.log") == d["run_log_sha256"],
       "excluded v1.0.0 diagnostic source/raw SHA")
    ck(len(re.findall(r"error #464", log)) == 2 and
       "Unknown MaterielOperationalMode: POS-A / <DEFAULT>" in log and
       "Unknown MaterielOperationalMode: POS-B / <DEFAULT>" in log and
       "Errors: 2, Warnings: 1, Notes: 0" in log and
       (p / "model.sxo").stat().st_size == 4 and
       not (p / "report-raw.json").exists(),
       "excluded v1.0.0 converter #464 / invalid SXO / no report")
    return {"run_id": d["run_id"], "classification": "excluded_converter_diagnostic",
            "input_sha256": d["input_sha256"], "closure_sha256": d["closure_sha256"]}


def main() -> None:
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    sources = source_checks(contract, diff)
    accepted = {arm: replay(arm, sources[arm], contract) for arm in ("series", "parallel")}
    parent = (BASE / "G02-var01-position-modes-v1.0.0" / "runs" /
              "g02-var01-two-position-accepted-20261001-01")
    series_report = tables(read(CASE / "runs" / accepted["series"]["run_id"] /
                                "report-raw.json", native=True), "report")
    parent_report = tables(read(parent / "report-raw.json", native=True), "report")
    ck(accepted["series"]["log_sha256"] == sha(parent / "model.log") and
       {k: v for k, v in series_report.items() if k != "ProblemDescription"} ==
       {k: v for k, v in parent_report.items() if k != "ProblemDescription"} and
       series_report["ProblemDescription"] != parent_report["ProblemDescription"],
       "series event byte equality and business-report equality to G02 parent")
    ck(accepted["series"]["events"][0]["failure_hour"] ==
       accepted["parallel"]["events"][0]["failure_hour"] == 8.62763 and
       accepted["series"]["events"][0]["position"] ==
       accepted["parallel"]["events"][0]["position"] == "B" and
       accepted["series"]["events"][0]["outcome"] == "abort" and
       accepted["parallel"]["events"][0]["outcome"] == "success",
       "same first POS-B event, divergent block-state outcome")
    excluded = diagnostic()
    result = {"schema": "g04-series-active-parallel-independent-readonly/v1",
              "case": CASE.name, "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "checks_passed": checks - len(failures), "checks_total": checks,
              "failures": failures, "accepted_runs": accepted,
              "accepted_raw_seal_count": 2 * len(RAW), "excluded_diagnostic": excluded,
              "manual_basis": "Installed manual physical pp196-200,448-450,454-459,767-770: series requires every constituent; active parallel NBREQ1/NBOP2 can continue with one functional block; ONLM=N defers maintenance; explicit leaf modes bind positions.",
              "scope": "For this seed and two direct positions, the same first POS-B failure aborts the series mission but leaves the active one-of-two parallel mission running to success. Both modes still receive half-hour local CM after mission return; three position-labelled failures and full 72-bin ledgers reconcile per arm.",
              "limits": ["v1.0.0 error #464 is an excluded converter diagnostic with invalid four-byte SXO.",
                         "One seed and one mission mode do not establish population reliability, all Boolean RBDs or general failure-rate behavior.",
                         "Passive backup, switchover, online maintenance, QTYPB>1, nested or other RBDs, GUI visualization and cross-engine parity remain untested."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks,
                      "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                      "report_sha256": sha(OUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
