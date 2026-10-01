"""Independent standard-library replay of the sealed D11 DTIM pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
DEFER = "defer" in CASE.name
RUN_ID = "d11-dtim-defer-v100-ssh-20261001-01" if DEFER else "d11-dtim-control-v100-ssh-20261001-01"
RUN = CASE / "runs" / RUN_ID
PARENT = BASE / ("D11-var02-dtim-control-v1.0.0" if DEFER else "D11-var01-atim-control-v1.0.0") / "native-input.json"
OUTPUT = CASE / "review" / "independent-readonly-2026-10-01.json"
checks = 0
failures: list[str] = []


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, native=False):
    s = path.read_text(encoding="utf-8-sig")
    if native:
        s = re.sub(r",\s*([}\]])", r"\1", s)
    return json.loads(s)


def tables(obj, root):
    return {t["name"]: t for t in obj[root]["tables"]}


def rows(t):
    return [row for instance in t["instances"] for row in instance["rows"]]


def records(t):
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r)) for r in rows(t)]


def close(actual, expected, label, tolerance=2e-5):
    check(actual is not None and abs(actual - expected) <= tolerance, f"{label}: {actual!r} vs {expected!r}")


def at(log, hour, fragment):
    return any(abs(float(time) - hour) < 2e-4 and fragment in line
               for time, line in re.findall(r"^Time: ([0-9.]+) (.*)$", log, re.M))


def frac(a, b, i):
    return 2 * max(0, min(b, (i + 1) / 2) - max(a, i / 2))


def covered(spans, i):
    return sum(frac(a, b, i) for a, b in spans)


def main():
    contract = load(CASE / "contract.json")
    source_path = CASE / "native-input.json"
    source = load(source_path)
    parent = load(PARENT)
    source_hash = "5288d185639174b07c8a062d0ebae7e53cf9bfccbe6936884e58ad15807e9b29" if DEFER else "29e7cdb16e9ab376641edf774a5fc91eb9c44283fd997fa435b79b48423fe901"
    parent_hash = "29e7cdb16e9ab376641edf774a5fc91eb9c44283fd997fa435b79b48423fe901" if DEFER else "94c0addbaff610b656b25dd328949ea9710ab9a593cafebe488f7bfca665ead8"
    check(sha(source_path) == source_hash == contract["input_sha256"], "contract and input SHA")
    check(sha(PARENT) == parent_hash == contract["parent_input_sha256"], "accepted parent SHA")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
    check(sha(manual) == contract["installed_manual_sha256"], "manual SHA")
    check(sha(dictionary) == contract["installed_dictionary_sha256"], "dictionary SHA")
    src, old = tables(source, "model"), tables(parent, "model")
    difference = {k for k in src.keys() | old.keys() if src.get(k) != old.get(k)}
    expected_difference = {"MaterielPM", "ProblemDescription"} if DEFER else {
        "OperationProfile", "ProblemDescription"}
    check(difference == expected_difference, "exact changed source tables")
    pm = records(src["MaterielPM"])
    check(len(pm) == 1 and all(pm[0][k] == v for k, v in {"PMID": "MS4", "MID": "TEACH-AIR-01", "OPID": "MISSIONS", "PMINT": 4, "ATIM": 0, "DTIM": .3 if DEFER else 0}.items()), "mission-count PM row")
    check(any(r["SUTID"] == "INSPECT" and r["DURN"] == 1 for r in records(src["TaskBreakDown"])), "one-hour INSPECT task")
    mission_types = {r["MTID"]: r for r in records(src["MissionType"])}
    check(mission_types["BASIC-MISSION"]["DURN"] == 4 and mission_types["SHORT-MISSION"]["DURN"] == 1, "mission durations")
    profile = records(src["OperationProfile"])
    check(len(profile) == 6 and [r["STIM"] for r in profile] == [8, 16, 20, 24, 25.25, 26.5], "six scheduled mission waves")
    check([r["SPRID"] for r in profile] == ["BASIC-MISSION"] + ["SHORT-MISSION"] * 5, "source mission identities")
    check("MaterielPMInterval" not in src or not rows(src["MaterielPMInterval"]), "no extra counter rows")
    if DEFER:
        control_pm = records(old["MaterielPM"])[0]
        check({k: v for k, v in pm[0].items() if k != "DTIM"} == {k: v for k, v in control_pm.items() if k != "DTIM"}, "DTIM-only PM row delta")
        check(control_pm["DTIM"] == 0 and pm[0]["DTIM"] == .3, "DTIM 0 to .3")
        check(all(src[k] == old[k] for k in src if k not in expected_difference), "paired business source retained")
    else:
        check(src["MaterielPM"] == old["MaterielPM"] and src["TaskBreakDown"] == old["TaskBreakDown"], "parent PM and task preserved")

    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    check(invocation["run_id"] == closure["run_id"] == RUN_ID, "run identity")
    check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation SHA seal")
    check(invocation["input_sha256"] == source_hash and invocation["parent_sha256"] == parent_hash, "invocation source lineage")
    check(invocation["contract_sha256"] == sha(CASE / "contract.json"), "invocation contract seal")
    mapped = {"input": source_path, "parent": PARENT, "contract": CASE / "contract.json",
              "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py",
              "runner_script": CASE / "run_native_ssh.ps1",
              "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
              "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}
    for key, path in mapped.items():
        actual = sha(path)
        check(invocation["source_hashes_before"][key] == actual, f"invocation {key} SHA")
        check(closure["source_hashes_before"][key] == actual, f"closure before {key} SHA")
        check(closure["source_hashes_after"][key] == actual, f"closure after {key} SHA")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "stable source hashes")
    for name, meta in closure["raw"].items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw seal {name}")
    check(sha(RUN / "input.json") == source_hash, "raw input exact")
    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True, "SSH session-zero provenance")
    check("sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "SSH ancestry and mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "preserved GUI identity")
    steps = load(RUN / "steps.json")
    check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five guarded stages")
    for s in steps:
        check(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] is True, f"stage {s['name']}")
    check(closure["error"] is None and closure["scope"] == "five_step_native_candidate", "closure success")
    exported = tables(load(RUN / "roundtrip-raw.json", native=True), "model")
    populated = [name for name, t in src.items() if rows(t)]
    check(len(populated) == 18, "18 row-containing source tables")
    for name in populated:
        check(exported.get(name) == src[name], f"exact native roundtrip {name}")
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, "zero conversion errors")
    check("warning #108" in runlog and "warning #126" in runlog, "expected converter warnings")
    check((RUN / "model.sxo").stat().st_size > 100000, "nontrivial result SXO")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    check(len(log) > 9000 and "failed:" not in log.lower(), "event log and no failure")

    types = ["BASIC-MISSION"] + ["SHORT-MISSION"] * 5
    ordered = [7, 15, 19, 23, 24.25, 25.5]
    allocations = [7, 15, 19, 23, 25, 26.25] if DEFER else [7, 15, 19, 23, None, 26]
    starts = [8, 16, 20, 24, 25.25, 26.5] if DEFER else [8, 16, 20, 24, None, 26.5]
    ends = [12, 17, 21, 25, 26.25, 27.5] if DEFER else [12, 17, 21, 25, None, 27.5]
    for i, typ in enumerate(types):
        identity = f"<{typ},TEACH-UNIT,0,0,{i}>"
        check(at(log, ordered[i], f"{identity} mission created:"), f"mission {i} created")
        if i == 4 and not DEFER:
            check(at(log, 25.5833, f"{identity} mission cancelled:"), "fifth request cancels without an aircraft")
            check(f"{identity} mission starting" not in log and f"{identity} mission allocates system" not in log, "cancelled fifth never launches or allocates")
        else:
            allocation, start, end = allocations[i], starts[i], ends[i]
            check(at(log, allocation, f"{identity} mission allocates system: <TEACH-AIR-01,0>"), f"mission {i} aircraft allocation")
            check(at(log, start, f"{identity} mission starting, duration: {end-start:g}"), f"mission {i} launch")
            check(at(log, end, f"{identity} mission success:"), f"mission {i} success")
            check(at(log, end, f"{identity} mission completed: <TEACH-AIR-01,0>"), f"mission {i} completion")
    check(len(re.findall(r"mission starting, duration:", log)) == (6 if DEFER else 5), "exact launch count")
    check(len(re.findall(r"mission success:", log)) == (6 if DEFER else 5), "exact success count")
    check(len(re.findall(r"mission cancelled:", log)) == (0 if DEFER else 1), "exact cancellation count")
    task = "system PM task 0 on <TEACH-AIR-01,0>"
    work_start = 27.5 if DEFER else 25
    work_end = work_start + 1
    check(len(re.findall(r"^Time: [0-9.]+  system PM task \d+ on <TEACH-AIR-01,0> started$", log, re.M)) == 1, "exactly one PM task starts")
    check(at(log, 25, f"{task} started") and at(log, 25, f"{task} PMID: MS4"), "PM task created and started at fourth return")
    check(" 1 PM tasks:" in log and at(log, 25, "System arrives <TEACH-AIR-01,0>, mission success,"), "PM creation on fourth return")
    if DEFER:
        check(log.count(".MS4 Non-Critical") == 2 and log.count(".MS4 Critical") == 1, "noncritical after fourth/fifth; critical after sixth")
        check(at(log, 25, f"{task} paused."), "noncritical PM paused at 25")
        check(at(log, 27.5, f"{task} continued  : PM task has become critical"), "critical PM continued at 27.5")
        check("subtask 0 seqno 1 within system PM task 0 on <TEACH-AIR-01,0> started" not in log, "deferred subtask has no separate started event")
        check(not at(log, 25, "starts performing, planned to last for 1 hours"), "no PM work at initial task start")
    else:
        check(log.count(".MS4 Critical") == 1 and ".MS4 Non-Critical" not in log, "immediately critical PM")
        check(at(log, 25, f"subtask 0 seqno 1 within {task} started"), "control PM subtask starts at 25")
        check("paused." not in log and "continued  : PM task has become critical" not in log, "control PM not deferred")
    check(at(log, work_start, f"subtask 0 seqno 1 within {task} starts performing, planned to last for 1 hours"), "one-hour PM work starts")
    check(at(log, work_end, f"subtask 0 seqno 1 within {task} completed"), "PM subtask work ends")
    check(at(log, work_end, f"{task} completed") and at(log, work_end, "System ready <TEACH-AIR-01,0>"), "PM task ends and aircraft ready")
    check("system PM task 1" not in log, "no second PM")
    check((4 + 2) == 4 + int(.3 * 4 + .999999) if DEFER else True, "manual integer deferment ceil(.3*4)=2")
    report = {t["name"]: t for t in load(RUN / "report-raw.json", native=True)["report"]["tables"]}
    check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
    summary = records(report["ResultSummary"])[0]
    for key, value in {"NREP": 1, "RTILW": 0, "RTIUP": 60,
                       "MTMF": 1 if DEFER else 8/9, "MSTF": 1 if DEFER else 5/6,
                       "MSUF": 1 if DEFER else 5/6, "STMF": 1 if DEFER else 8/9}.items():
        close(summary[key], value, f"summary {key}")
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    check(len(system) == len(stock) == 120, "120 System and Stock bins")
    mission_alloc = [(a, b) for a, b in zip(allocations, ends) if a is not None]
    mission_oper = [(a, b) for a, b in zip(starts, ends) if a is not None]
    mission_reserved = [(a, b) for a, b in zip(allocations, starts) if a is not None]
    pm_spans = [(work_start, work_end)]
    ready_spans = ([(0, 7), (12, 15), (17, 19), (21, 23), (28.5, 60)] if DEFER
                   else [(0, 7), (12, 15), (17, 19), (21, 23), (27.5, 60)])
    for i, (sr, sk) in enumerate(zip(system, stock)):
        for row in (sr, sk):
            close(row["STINT"], i/2, f"bin {i} start")
            close(row["ETINT"], (i+1)/2, f"bin {i} end")
        expected = {"NSYRY": covered(ready_spans, i), "NSYMA": covered(mission_alloc, i),
                    "NSYMO": covered(mission_oper, i), "NSYMR": covered(mission_reserved, i),
                    "NSYPM": covered(pm_spans, i), "NSYUA": covered(pm_spans, i),
                    "NSYA": covered(ready_spans, i) + covered(mission_alloc, i),
                    "FTMO": covered(mission_oper, i), "STACC": covered(mission_oper, i),
                    "NPMS": int(i/2 == 25), "NPMT": int(i/2 == work_end),
                    "NSYDT": int(i/2 == work_start), "NFAIL": 0, "NREPT": 0}
        for key, value in expected.items():
            close(sr[key], value, f"bin {i} {key}", 3e-5)
        if i/2 == work_start:
            close(sr["SYDT"], 1, f"bin {i} PM downtime metric")
        else:
            check(sr["SYDT"] is None, f"bin {i} no downtime metric")
        for key, value in sr.items():
            if key not in set(expected) | {"UNID", "SID", "STINT", "ETINT", "SYDT"}:
                check(value in (0, None), f"bin {i} other system {key}")
        close(sk["PNB"], 1, f"bin {i} PNB baseline")
        for key, value in sk.items():
            if key not in {"STINT", "ETINT", "PNB"}:
                check(value in (0, None), f"bin {i} stock {key}")
    close(sum(r["NSYMO"] for r in system)*.5, 9 if DEFER else 8, "flight hours")
    close(sum(r["NSYPM"] for r in system)*.5, 1, "one PM work hour", 3e-5)
    check(system[-1]["NSYRY"] == 1 and system[-1]["NSYPM"] == 0 and stock[-1]["NBO"] == 0, "terminal ready, no PM, no backorder")
    result = {
        "schema": "independent-d11-dtim-readonly/v1", "case": CASE.name, "run_id": RUN_ID,
        "verdict": "GO" if not failures else "NO-GO", "passed": not failures,
        "check_count": checks, "failures": failures,
        "source_sha256": sha(source_path), "closure_sha256": sha(RUN / "closure.json"),
        "log_sha256": sha(RUN / "model.log"), "report_sha256": sha(RUN / "report-raw.json"),
        "scope": "Six fixed requests; DTIM=.3 permits two extra missions before critical PM work" if DEFER else "Six fixed requests; DTIM=0 critical PM cancels fifth request",
        "limitations": (["PM task starts and pauses at h25; actual subtask work begins at h27.5. Do not equate those timestamps.",
                         "One integer mission-count threshold/fraction; no other OPID, tie, ENREG, MNOCC, or cross-engine claim."] if DEFER else
                        ["This DTIM=0 control alone does not establish deferment.",
                         "One fixed queued-mission schedule; no other threshold, OPID, or cross-engine claim."]),
    }
    OUTPUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks, "failures": failures,
                      "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUTPUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
