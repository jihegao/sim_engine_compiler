"""Independent, read-only replay of the sealed D09.var03 MAXNC native pair.

This uses Python's standard library and never invokes SIMLOX or author validators.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
CASES = CASE.parent
PARENT = CASES / "D09-var02-unset-vs-finite-v1.0.0"
PARENT_SOURCE = PARENT / "native-input-unset.json"
PARENT_CLOSURE = PARENT / "runs/d09-var02-unset-v100-ssh-20261002-01/closure.json"
PREREQ = CASES / "D08-var03-criticality-v1.0.0"
PREREQ_SOURCE = PREREQ / "native-input-traditional.json"
PREREQ_CLOSURE = PREREQ / "runs/d08-var03-traditional-v100-ssh-20261002-01/closure.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
OUT = CASE / "independent-verdict.json"
RUN_IDS = {k: f"d09-var03-{k}-v100-ssh-20261002-01" for k in ("limit-2", "limit-3")}
COUNT = 0
FAILURES: list[str] = []


def check(test: bool, label: str) -> None:
    global COUNT
    COUNT += 1
    if not test:
        FAILURES.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    data = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", data))


def tables(path: Path, root: str) -> dict:
    return {x["name"]: x for x in read(path)[root]["tables"]}


def records(table: dict) -> list[dict]:
    columns = [x["name"] for x in table["columns"]]
    return [dict(zip(columns, row)) for ins in table["instances"] for row in ins["rows"]]


def close(actual, expected, tolerance=1e-3) -> bool:
    return math.isclose(float(actual or 0), float(expected), abs_tol=tolerance, rel_tol=0)


def occupancy(start: float, end: float, bin_start: float) -> float:
    return max(0.0, min(end, bin_start + .5) - max(start, bin_start)) / .5


def occurrence(log: str, expression: str) -> list[float]:
    return [float(x) for x in re.findall(r"(?m)^Time: ([0-9.]+) " + expression, log)]


def exact_source_delta(before: dict, after: dict) -> tuple[dict, int]:
    delta = {}
    unchanged = 0
    for name in before:
        if before[name] == after[name]:
            unchanged += 1
            continue
        a, b = before[name], after[name]
        check(a["columns"] == b["columns"], f"source columns unchanged {name}")
        aa, bb = records(a), records(b)
        check(len(aa) == len(bb), f"source row cardinality {name}")
        changes = {}
        for ar, br in zip(aa, bb):
            for key in ar:
                if ar[key] != br[key]:
                    changes[key] = {"before": ar[key], "after": br[key]}
        delta[name] = changes
    return delta, unchanged


def main() -> int:
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    check(sha(PARENT_SOURCE) == contract["accepted_parent"]["input_sha256"] == diff["parent_input_sha256"], "parent source SHA")
    check(sha(PARENT_CLOSURE) == contract["accepted_parent"]["native_closure_sha256"], "parent closure SHA")
    check(sha(PREREQ_SOURCE) == contract["earlier_noncritical_prerequisite"]["input_sha256"], "D08 source SHA")
    check(sha(PREREQ_CLOSURE) == contract["earlier_noncritical_prerequisite"]["native_closure_sha256"], "D08 closure SHA")
    check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff SHA")
    check(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "manual SHA")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary SHA")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "installed CLI SHA")
    parent = tables(PARENT_SOURCE, "model")
    arms = {}
    for arm in RUN_IDS:
        src = CASE / f"native-input-{arm}.json"
        model = tables(src, "model")
        check(sha(src) == contract["arms"][arm]["input_sha256"] == diff["children"][arm]["input_sha256"], f"{arm} input SHA")
        check(set(model) == set(parent) and len(model) == 31, f"{arm} 31 source tables")
        delta, same = exact_source_delta(parent, model)
        check(delta == diff["children"][arm]["changed_tables"] and same == 27, f"{arm} exact parent delta")
        system, item = records(model["System"])[0], records(model["Item"])[0]
        check(system["MAXNC"] == contract["arms"][arm]["maxnc"] and system["FRT"] == 9000000 and
              item["FRT"] == 3000000 and item["CRIT"] == 0 and item["NCFTL"] is None and
              records(model["ItemStructure"])[0]["QTYPM"] == 3 and
              records(model["StockAllocation"])[0]["STSIZ"] == 0, f"{arm} model geometry")
        arms[arm] = (src, model)
    pair_delta, pair_same = exact_source_delta(arms["limit-2"][1], arms["limit-3"][1])
    check(set(pair_delta) == {"ProblemDescription", "System"} and
          set(pair_delta["System"]) == {"MAXNC"} and
          set(pair_delta["ProblemDescription"]) == {"PDESC"} and pair_same == 29,
          "pair differs only in MAXNC and description")

    evidence = {}
    for arm, run_id in RUN_IDS.items():
        src, model = arms[arm]
        run = CASE / "runs" / run_id
        closure, invocation, steps = read(run / "closure.json"), read(run / "invocation.json"), read(run / "steps.json")
        check(closure["run_id"] == invocation["run_id"] == run_id and closure["arm"] == invocation["arm"] == arm, f"{arm} run identity")
        check(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation seal")
        check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], f"{arm} stable source seals")
        source_paths = {"input": src, "parent": PARENT_SOURCE, "parent_closure": PARENT_CLOSURE,
                        "prerequisite": PREREQ_SOURCE, "prerequisite_closure": PREREQ_CLOSURE,
                        "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
                        "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
                        "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
                        "simlox_exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY, "python": PYTHON}
        for key, path in source_paths.items():
            check(sha(path) == closure["source_hashes_before"][key], f"{arm} source seal {key}")
        check(len(closure["raw"]) == 12, f"{arm} twelve raw seals")
        for name, spec in closure["raw"].items():
            path = run / name
            check(path.exists() and path.stat().st_size == spec["bytes"], f"{arm} raw bytes {name}")
            check(sha(path) == spec["sha256"], f"{arm} raw SHA {name}")
        check(sha(run / "input.json") == sha(src), f"{arm} copied input")
        check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and
              invocation["ssh_connection_present"] and "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]], f"{arm} session-zero SSH")
        check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
              invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, f"{arm} mutex and GUI")
        check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], f"{arm} five ordered steps")
        for step in steps:
            check(step["exit_code"] == 0 and step["status"] in {"completed", "calc_observed"} and step["gui_preserved"] is True,
                  f"{arm} step {step['name']}")
        exported = tables(run / "roundtrip-raw.json", "model")
        populated = [name for name, t in model.items() if any(ins["rows"] for ins in t["instances"])]
        check(len(populated) == 18 and set(exported) >= set(model), f"{arm} 18 row-containing native tables")
        for name in populated:
            check(model[name]["columns"] == exported[name]["columns"] and
                  model[name]["instances"] == exported[name]["instances"], f"{arm} exact roundtrip {name}")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
              "warning #108" in runlog and "Saving results" in runlog, f"{arm} converter and result")
        check((run / "model.sxo").stat().st_size > 4, f"{arm} valid SXO")
        rr = tables(run / "report-raw.json", "report")
        check({"ResultSummary", "SystemResults", "StockTotalResults"} <= set(rr), f"{arm} report tables")
        sy, st, summary = records(rr["SystemResults"]), records(rr["StockTotalResults"]), records(rr["ResultSummary"])[0]
        check(len(sy) == len(st) == 72, f"{arm} 72 System/Stock bins")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        fault_times = occurrence(log, r"<TEACH-AIR-01,0> noncritical random failure added")
        check(fault_times[:3] == [8.06276, 8.16075, 8.22615], f"{arm} matched first three fault times")
        for index, at in enumerate(fault_times[:3]):
            segment = log[log.index(f"Time: {at} <TEACH-AIR-01,0> noncritical random failure added"):]
            segment = segment.split("\nTime:", 1)[0]
            check(f"subitem failed: <TEACH-LRU-01,0,{index}>" in segment and
                  f"{index+1} failures:" in segment, f"{arm} fault {index} physical identity/count")
        for i, start in enumerate((8, 20, 32)):
            check(f"Time: {start} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission starting" in log,
                  f"{arm} mission {i} start")
        if arm == "limit-2":
            aborts = [8.22615, 20.0115, 33.0263]
            returned = [8.45229, 20.023, 33.5263]
            ready = [9.95229, 21.523, 35.0263]
            bo_ends = [9.70229, 21.273, 34.7763]
            for i, (at, ret, done, bo) in enumerate(zip(aborts, returned, ready, bo_ends)):
                check(f"Time: {at} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission aborted" in log and
                      f"Time: {ret} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> aborted mission completed" in log,
                      f"limit-2 abort and return {i}")
                check(f"Time: {done} <TEACH-AIR-01,BASE-01,0> System ready" in log and
                      log.count(f"Time: {bo} <TEACH-LRU-01,0,BASE-01,0> Backorder removed") == 3,
                      f"limit-2 repair ready and three backorders cleared {i}")
            check("mission success:" not in log, "limit-2 no mission success")
            check("< system SURP task 0 on <TEACH-AIR-01,0>, C, 0.5>" in log and
                  "< system SURP task 1 on <TEACH-AIR-01,0>, C, 0.5>" in log and
                  "< system SURP task 2 on <TEACH-AIR-01,0>, C, 0.5>" in log,
                  "limit-2 first repair priority C for all three")
            for i in range(9):
                check(f"Finished repair of item <TEACH-LRU-01,0,{i}>" in log and
                      f"Replacement item arrives <TEACH-LRU-01,0,{i}>" in log,
                      f"limit-2 same physical item repaired/reused {i}")
            check(log.count("Backorder added") == log.count("Backorder removed") == 9,
                  "limit-2 nine temporary backorders")
            check(fault_times == [8.06276, 8.16075, 8.22615, 20.0007, 20.0087,
                                  20.0115, 32.2884, 32.8222, 33.0263],
                  "limit-2 nine failures in three waves")
            check(close(summary["MSUF"], 0) and close(summary["MTMF"], .333595246076584),
                  "limit-2 summary")
            flights = [(8, 8.45229), (20, 20.023), (32, 33.5263)]
            backorders = [(8.45229, 9.70229), (20.023, 21.273), (33.5263, 34.7763)]
            waits = [(8.70229, 9.70229), (20.273, 21.273), (33.7763, 34.7763)]
            repairs = [(8.45229, 8.70229), (9.70229, 9.95229),
                       (20.023, 20.273), (21.273, 21.523),
                       (33.5263, 33.7763), (34.7763, 35.0263)]
            engaged = [(7, 8.45229), (19, 20.023), (31, 33.5263)]
            unavailable = [(8.45229, 9.95229), (20.023, 21.523), (33.5263, 35.0263)]
            for idx, (a, b) in enumerate(zip(sy, st)):
                h = idx / 2
                check(close(a["STINT"], h) and close(a["ETINT"], h+.5) and
                      close(b["STINT"], h) and close(b["ETINT"], h+.5), f"limit-2 half-hour interval {idx}")
                check(close(a["NSYMO"], sum(occupancy(s, e, h) for s, e in flights)) and
                      close(a["FTMO"], a["NSYMO"]), f"limit-2 flight occupancy {idx}")
                check(close(a["NSYRP"], sum(occupancy(s, e, h) for s, e in repairs)) and
                      close(a["NSYWI"], sum(occupancy(s, e, h) for s, e in waits)), f"limit-2 repair/wait bins {idx}")
                check(close(b["NBO"], 3*sum(occupancy(s, e, h) for s, e in backorders)),
                      f"limit-2 three-item backorder occupancy {idx}")
                check(close(a["NSYMA"], sum(occupancy(s, e, h) for s, e in engaged)) and
                      close(a["NSYUA"], sum(occupancy(s, e, h) for s, e in unavailable)) and
                      close(a["NSYA"], 1-sum(occupancy(s, e, h) for s, e in unavailable)),
                      f"limit-2 engaged/unavailable/available bins {idx}")
                check(close(a["NFAIL"], sum(h <= t < h+.5 for t in fault_times)) and
                      close(a["NREPT"], 3*sum(h <= t < h+.5 for t in ready)),
                      f"limit-2 fault and repair-completion markers {idx}")
                check(close(b["PNB"], 1-sum(occupancy(s, e, h) for s, e in backorders)) and
                      close(b["NDF"], 3*sum(h <= t < h+.5 for t in returned)),
                      f"limit-2 stock no-backorder and demand markers {idx}")
            check(close(sy[-1]["NSYRY"], 1) and close(st[-1]["NBO"], 0), "limit-2 terminal ready and clear")
            check(close(sum(float(a["FTMO"] or 0)*.5 for a in sy), sum(e-s for s,e in flights)) and
                  close(sum(float(b["NBO"] or 0)*.5 for b in st), 3*sum(e-s for s,e in backorders)),
                  "limit-2 integrated flight and backorder hours")
        else:
            for i, end in enumerate((10, 22, 34)):
                check(f"Time: {end} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission success" in log and
                      f"Time: {end} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission completed" in log,
                      f"limit-3 mission success {i}")
            check("mission aborted:" not in log and "starts performing" not in log and
                  "Finished repair of item" not in log and "Backorder removed" not in log,
                  "limit-3 no abort or physical repair")
            check(all(f"< system SURP task {i} on <TEACH-AIR-01,0>, NC, 0.5>" in log for i in range(3)),
                  "limit-3 three noncritical waiting tasks")
            check(log.count("Backorder added") == 3, "limit-3 three unresolved backorders")
            check(fault_times == [8.06276, 8.16075, 8.22615], "limit-3 exactly first three failures")
            check(close(summary["MSUF"], 1) and close(summary["MTMF"], 1), "limit-3 summary")
            for idx, (a, b) in enumerate(zip(sy, st)):
                h = idx / 2
                flight = int(any(s <= h < e for s, e in ((8, 10), (20, 22), (32, 34))))
                check(close(a["STINT"], h) and close(a["ETINT"], h+.5) and
                      close(b["STINT"], h) and close(b["ETINT"], h+.5), f"limit-3 half-hour interval {idx}")
                check(close(a["NSYMO"], flight) and close(a["FTMO"], flight) and
                      close(a["NSYRP"], 0) and close(a["NSYWI"], 0), f"limit-3 flight/no-work bins {idx}")
                check(close(b["NBO"], 3 if h >= 10 else 0), f"limit-3 three unresolved backorders {idx}")
                check(close(a["NFAIL"], 3 if h == 8 else 0) and
                      close(a["NSYMA"], int(any(s <= h < e for s,e in ((7,10),(19,22),(31,34))))) and
                      close(a["NSYRY"], int(not any(s <= h < e for s,e in ((7,10),(19,22),(31,34))))),
                      f"limit-3 failure/preparation/readiness bins {idx}")
                check(close(b["NDF"], 3 if h == 10 else 0) and
                      close(b["PNB"], 1 if h < 10 else 0),
                      f"limit-3 stock demand and no-backorder bins {idx}")
            check(close(sy[-1]["NSYRY"], 1) and close(st[-1]["NBO"], 3), "limit-3 terminal ready with three BO")
            check(close(sum(float(a["FTMO"] or 0)*.5 for a in sy), 6) and
                  close(sum(float(b["NBO"] or 0)*.5 for b in st), 78),
                  "limit-3 integrated six flight and 78 backorder hours")
        check(summary["NREP"] == 1 and close(summary["RTIUP"], 36), f"{arm} one replication and horizon")
        evidence[arm] = {"input_sha256": sha(src), "closure_sha256": sha(run / "closure.json"),
                         "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json"),
                         "first_fault_hours": fault_times[:3], "summary": summary}

    result = {"schema": "simlox-independent-readonly-d09-var03/v1",
              "passed": not FAILURES,
              "verdict": "GO: bounded MAXNC=2 versus 3 threshold observation" if not FAILURES else "NO-GO: independent replay failure",
              "checks_passed": COUNT-len(FAILURES), "checks_total": COUNT, "failures": FAILURES,
              "evidence": evidence,
              "finding": "Both fixed-seed arms log three distinct noncritical LRU failures at h8.06276, 8.16075, and 8.22615. At MAXNC=2 the third exceeds the configured count, the mission aborts at h8.22615, and three first-wave SURP tasks carry C priority with physical removal, direct repair and same-item reuse. At MAXNC=3 the third reaches the configured count, the mission succeeds at h10, and three NC SURP tasks wait on zero stock; they remain pending through h36 while the aircraft is ready and three backorders remain.",
              "interpretation_limit": "The native log says 'noncritical random failure added' for all three arrivals and does not explicitly say 'changed to critical' for MAXNC=2. Threshold escalation is inferred from the C task priorities, immediate abort, physical repair path and the isolated MAXNC source difference.",
              "limits": ["One aircraft with three identical LRUs, fixed seed 1, artificial FRT and 36-hour horizon.",
                         "Only MAXNC 2 and 3 are tested; no general count law or intermediate configuration is inferred.",
                         "No GUI-only execution or cross-engine parity claim."]}
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": COUNT, "failures": FAILURES,
                      "verdict": result["verdict"], "output": str(OUT)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
