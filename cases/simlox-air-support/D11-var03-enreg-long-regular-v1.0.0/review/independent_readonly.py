"""Independent standard-library replay of the sealed D11 long-gap ENREG pair."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
REGULAR = "regular" in CASE.name
RUN_ID = "d11-enreg-long-regular-v100-ssh-20261001-01" if REGULAR else "d11-enreg-long-drift-v100-ssh-20261001-01"
RUN = CASE / "runs" / RUN_ID
PARENT = BASE / ("D11-var03-enreg-long-drift-v1.0.0" if REGULAR else "D03-calendar-pm-v1.0.0") / "native-input.json"
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
    source_hash = "a7f41c9e202c136760ea22c67aecf5abe52a55331c60590694ca012521a34f30" if REGULAR else "76836c8b1dd8f9d5552e9fb908b766e80995bc9fdcd7b7967f75a73de6f6b7c5"
    parent_hash = "76836c8b1dd8f9d5552e9fb908b766e80995bc9fdcd7b7967f75a73de6f6b7c5" if REGULAR else "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
    check(sha(source_path) == source_hash == contract["input_sha256"], "contract and input SHA")
    check(sha(PARENT) == parent_hash == contract["parent_input_sha256"], "accepted parent SHA")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
    check(sha(manual) == contract["installed_manual_sha256"], "manual SHA")
    check(sha(dictionary) == contract["installed_dictionary_sha256"], "dictionary SHA")
    src, old = tables(source, "model"), tables(parent, "model")
    difference = {k for k in src.keys() | old.keys() if src.get(k) != old.get(k)}
    expected_difference = {"MaterielPM", "ProblemDescription"} if REGULAR else {
        "Control", "MaterielPM", "MissionType", "OperationProfile", "ProblemDescription", "ResultCollection"}
    check(difference == expected_difference, "exact changed source tables")
    pm = records(src["MaterielPM"])
    check(len(pm) == 1 and all(pm[0][k] == v for k, v in {"PMID": "CAL24", "MID": "TEACH-AIR-01", "OPID": "CALHOURS", "PMINT": 24, "ATIM": 0, "DTIM": 0, "ENREG": "Y" if REGULAR else "N"}.items()), "calendar PM row")
    check(any(r["SUTID"] == "INSPECT" and r["DURN"] == 1 for r in records(src["TaskBreakDown"])), "one-hour INSPECT task")
    mission_types = {r["MTID"]: r for r in records(src["MissionType"])}
    check(mission_types["BASIC-MISSION"]["DURN"] == 2 and mission_types["LONG-MISSION"]["DURN"] == 26, "two-hour and 26-hour mission durations")
    profile = records(src["OperationProfile"])
    check(len(profile) == 3 and [r["STIM"] for r in profile] == [8, 20, 23.5], "three scheduled missions")
    check([r["SPRID"] for r in profile] == ["BASIC-MISSION", "BASIC-MISSION", "LONG-MISSION"], "long mission source identity")
    control_row = records(src["Control"])[0]
    check(control_row["SIMPE"] == 84 and control_row["RCEND"] == 84, "84-hour control horizon")
    check(all(r["RCEND"] == 84 for r in records(src["ResultCollection"])), "84-hour report horizon")
    check("MaterielPMInterval" not in src or not rows(src["MaterielPMInterval"]), "no extra counter rows")
    if REGULAR:
        control_pm = records(old["MaterielPM"])[0]
        check({k: v for k, v in pm[0].items() if k != "ENREG"} == {k: v for k, v in control_pm.items() if k != "ENREG"}, "ENREG-only PM row delta")
        check(control_pm["ENREG"] == "N" and pm[0]["ENREG"] == "Y", "ENREG N to Y")
        check(all(src[k] == old[k] for k in src if k not in expected_difference), "paired business source retained")
    else:
        check([r["STIM"] for r in records(old["OperationProfile"])][:2] == [8, 20], "D03 first two missions retained")

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
    check(len(log) > 5000 and "failed:" not in log.lower(), "event log and no failure")

    mission_ids = ["BASIC-MISSION", "BASIC-MISSION", "LONG-MISSION"]
    starts = [8, 20, 23.5]
    ends = [10, 22, 49.5]
    allocations = [7, 19, 22.5]
    for i, (typ, start, end, allocation) in enumerate(zip(mission_ids, starts, ends, allocations)):
        identity = f"<{typ},TEACH-UNIT,0,0,{i}>"
        check(at(log, allocation, f"{identity} mission allocates system: <TEACH-AIR-01,0>"), f"mission {i} aircraft allocation")
        check(at(log, start, f"{identity} mission starting, duration: {end-start:g}"), f"mission {i} launch")
        check(at(log, end, f"{identity} mission success:"), f"mission {i} success")
        check(at(log, end, f"{identity} mission completed: <TEACH-AIR-01,0>"), f"mission {i} completion")
    check(len(re.findall(r"mission starting, duration:", log)) == 3, "exactly three launches")
    check(len(re.findall(r"mission success:", log)) == 3, "exactly three successes")
    check(at(log, 49.5, "System arrives <TEACH-AIR-01,0>, mission success,") and " 1 PM tasks:" in log and ".CAL24 Critical" in log, "first PM created after long mission return")
    pm_starts = [49.5, 72 if REGULAR else 74.5]
    pm_ends = [h + 1 for h in pm_starts]
    check(len(re.findall(r"^Time: [0-9.]+  system PM task \d+ on <TEACH-AIR-01,0> started$", log, re.M)) == len(pm_starts), "exact PM task count")
    for i, (start, end) in enumerate(zip(pm_starts, pm_ends)):
        task = f"system PM task {i} on <TEACH-AIR-01,0>"
        check(at(log, start, f"{task} started"), f"PM {i} starts")
        check(at(log, start, f"{task} PMID: CAL24"), f"PM {i} identity")
        check(at(log, start, f"subtask {i} seqno 1 within {task} started"), f"PM {i} INSPECT starts")
        check(at(log, start, f"subtask {i} seqno 1 within {task} starts performing, planned to last for 1 hours"), f"PM {i} positive work")
        check(at(log, end, f"subtask {i} seqno 1 within {task} completed"), f"PM {i} INSPECT ends")
        check(at(log, end, f"{task} completed"), f"PM {i} ends")
        check(at(log, end, "System ready <TEACH-AIR-01,0>"), f"PM {i} restores aircraft")
    check("system PM task 2" not in log, "no third PM")
    check(pm_starts[0] == ends[2] and starts[2] < 24 < 48 < ends[2], "24 and 48 slots lie in long mission")
    check(len(re.findall(r"^Time: 48(?:\.0+)?  system PM task", log, re.M)) == 0, "no separate PM at skipped h48 slot")
    check(pm_starts[1] == (72 if REGULAR else pm_ends[0] + 24), "regular grid versus drift interval")
    report = {t["name"]: t for t in load(RUN / "report-raw.json", native=True)["report"]["tables"]}
    check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
    summary = records(report["ResultSummary"])[0]
    for key, value in {"NREP": 1, "RTILW": 0, "RTIUP": 84, "MTMF": 1, "MSTF": 1, "MSUF": 1, "STMF": 1}.items():
        close(summary[key], value, f"summary {key}")
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    check(len(system) == len(stock) == 168, "168 System and Stock bins")
    mission_alloc = list(zip(allocations, ends))
    mission_oper = list(zip(starts, ends))
    mission_reserved = list(zip(allocations, starts))
    pm_spans = list(zip(pm_starts, pm_ends))
    ready_spans = ([(0, 7), (10, 19), (22, 22.5), (50.5, 72), (73, 84)] if REGULAR
                   else [(0, 7), (10, 19), (22, 22.5), (50.5, 74.5), (75.5, 84)])
    pm_markers = [24, pm_starts[1]]
    for i, (sr, sk) in enumerate(zip(system, stock)):
        for row in (sr, sk):
            close(row["STINT"], i/2, f"bin {i} start")
            close(row["ETINT"], (i+1)/2, f"bin {i} end")
        expected = {"NSYRY": covered(ready_spans, i), "NSYMA": covered(mission_alloc, i),
                    "NSYMO": covered(mission_oper, i), "NSYMR": covered(mission_reserved, i),
                    "NSYPM": covered(pm_spans, i), "NSYUA": covered(pm_spans, i),
                    "NSYA": covered(ready_spans, i) + covered(mission_alloc, i),
                    "FTMO": covered(mission_oper, i), "STACC": covered(mission_oper, i),
                    "NPMS": int(i/2 in pm_markers), "NPMT": int(i/2 in pm_ends),
                    "NSYDT": int(i/2 in pm_starts), "NFAIL": 0, "NREPT": 0}
        for key, value in expected.items():
            close(sr[key], value, f"bin {i} {key}", 3e-5)
        if i/2 in pm_starts:
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
    close(sum(r["NSYMO"] for r in system)*.5, 30, "thirty flight hours")
    close(sum(r["NSYPM"] for r in system)*.5, 2, "two PM work hours", 3e-5)
    check(system[-1]["NSYRY"] == 1 and system[-1]["NSYPM"] == 0 and stock[-1]["NBO"] == 0, "terminal ready, no PM, no backorder")
    result = {
        "schema": "independent-d11-enreg-long-readonly/v1", "case": CASE.name, "run_id": RUN_ID,
        "verdict": "GO" if not failures else "NO-GO", "passed": not failures,
        "check_count": checks, "failures": failures,
        "source_sha256": sha(source_path), "closure_sha256": sha(RUN / "closure.json"),
        "log_sha256": sha(RUN / "model.log"), "report_sha256": sha(RUN / "report-raw.json"),
        "scope": "26-hour mission crosses h24 and h48; ENREG=Y second PM on h72 grid" if REGULAR else "26-hour mission crosses h24 and h48; ENREG=N second PM at h74.5",
        "limitations": ["SystemResults.NPMS marks the first PM threshold at h24; task creation and work start only after mission return at h49.5. No separate catch-up PM at h48 is observable.",
                        "One fixed long delay, calendar interval, and seed; other omissions, intervals, and cross-engine behavior remain unverified."],
    }
    OUTPUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks, "failures": failures,
                      "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUTPUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
