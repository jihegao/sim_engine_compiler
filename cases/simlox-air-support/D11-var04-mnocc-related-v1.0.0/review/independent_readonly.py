"""Independent standard-library replay of a corrected linked-PM cap run."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
BASE = CASE.parent
CAP = int(sys.argv[1]) if len(sys.argv) == 2 else -1
if CAP not in (2, 3):
    raise SystemExit("Usage: independent_readonly.py 2|3")
RUN_ID = f"d11-mnocc-related-{CAP}-v100-ssh-20261001-02"
RUN = CASE / "runs" / RUN_ID
PARENT = BASE / "D10-var01-missions-v1.0.0" / "native-input.json"
OUTPUT = CASE / "review" / f"independent-readonly-cap-{CAP}-2026-10-01.json"
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
    source_path = CASE / f"native-related-cap-{CAP}.json"
    source = load(source_path)
    parent = load(PARENT)
    source_hash = contract["input_sha256"][f"MS2_MNOCC={CAP}"]
    parent_hash = "6607991260e3f911d0121c7949443409a57937e95f80c7e4f3a2faa6ac20ba72"
    check(sha(source_path) == source_hash, "contract and input SHA")
    check(sha(PARENT) == parent_hash == contract["parent_input_sha256"], "accepted parent SHA")
    manual = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
    dictionary = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
    check(sha(manual) == contract["installed_manual_sha256"], "manual SHA")
    check(sha(dictionary) == contract["installed_dictionary_sha256"], "dictionary SHA")
    src, old = tables(source, "model"), tables(parent, "model")
    difference = {k for k in src.keys() | old.keys() if src.get(k) != old.get(k)}
    expected_difference = {"MaterielPM", "PMLocation", "ProblemDescription", "TaskBreakDown", "Tasks"}
    check(difference == expected_difference, "exact changed source tables")
    pm = records(src["MaterielPM"])
    check(len(pm) == 2, "two linked PM rows")
    pm_by_id = {r["PMID"]: r for r in pm}
    check(all(pm_by_id["MS2"][k] == v for k, v in {"MID": "TEACH-AIR-01", "OPID": "MISSIONS", "PMINT": 2, "MNOCC": CAP, "ATIM": 0, "DTIM": 0}.items()), "capped smaller PM")
    check(all(pm_by_id["MS3"][k] == v for k, v in {"MID": "TEACH-AIR-01", "OPID": "MISSIONS", "PMINT": 3, "PMRID": "MS2", "ATIM": 0, "DTIM": 0}.items()), "larger related PM")
    check(any(r["SUTID"] == "INSPECT" and r["DURN"] == 1 for r in records(src["TaskBreakDown"])), "one-hour INSPECT task")
    mission_types = {r["MTID"]: r for r in records(src["MissionType"])}
    check(mission_types["BASIC-MISSION"]["DURN"] == 4 and mission_types["SHORT-MISSION"]["DURN"] == 1, "mission durations")
    check("MaterielPMInterval" not in src or not rows(src["MaterielPMInterval"]), "no extra counter rows")
    check(all(src[k] == old[k] for k in src if k not in expected_difference), "parent unrelated tables retained")
    other = load(CASE / f"native-related-cap-{3 if CAP == 2 else 2}.json")
    other_tables = tables(other, "model")
    check({k for k in src.keys() | other_tables.keys() if src.get(k) != other_tables.get(k)} == {"MaterielPM", "ProblemDescription"}, "exact cap pair table difference")
    other_small = next(r for r in records(other_tables["MaterielPM"]) if r["PMID"] == "MS2")
    check({k: v for k, v in pm_by_id["MS2"].items() if k != "MNOCC"} == {k: v for k, v in other_small.items() if k != "MNOCC"}, "only MS2.MNOCC differs in pair")
    locations = {r["PMID"]: r for r in records(src["PMLocation"])}
    check(set(locations) == {"MS2", "MS3"} and all(r["STID"] == "BASE-01" and r["PMT"] == 1 for r in locations.values()), "both PMs at base one hour")
    check({r["TID"] for r in records(src["Tasks"])} == {"PM-MS2", "PM-MS3"}, "distinct task identities")
    check({(r["TID"], r["SUTID"], r["DURN"]) for r in records(src["TaskBreakDown"])} == {("PM-MS2", "INSPECT", 1), ("PM-MS3", "INSPECT", 1)}, "distinct one-hour task breakdowns")

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

    mission_ids = ["BASIC-MISSION"] + ["SHORT-MISSION"] * 4
    starts = [8, 16, 20, 48, 52]
    ends = [12, 17, 21, 49, 53]
    allocations = [7, 15, 19, 47, 51]
    for i, (typ, start, end, allocation) in enumerate(zip(mission_ids, starts, ends, allocations)):
        identity = f"<{typ},TEACH-UNIT,0,0,{i}>"
        check(at(log, allocation, f"{identity} mission allocates system: <TEACH-AIR-01,0>"), f"mission {i} aircraft allocation")
        check(at(log, start, f"{identity} mission starting, duration: {end-start}"), f"mission {i} launch")
        check(at(log, end, f"{identity} mission success:"), f"mission {i} success")
        check(at(log, end, f"{identity} mission completed: <TEACH-AIR-01,0>"), f"mission {i} completion")
    check(len(re.findall(r"mission starting, duration:", log)) == 5, "exactly five launches")
    check(len(re.findall(r"mission success:", log)) == 5, "exactly five successes")
    pm_starts = [17, 21] + ([53] if CAP == 3 else [])
    pm_ids = ["MS2", "MS3"] + (["MS2"] if CAP == 3 else [])
    pm_ends = [h + 1 for h in pm_starts]
    check(len(re.findall(r"^Time: [0-9.]+  system PM task \d+ on <TEACH-AIR-01,0> started$", log, re.M)) == len(pm_starts), "exact PM task count")
    for i, (start, end, pmid) in enumerate(zip(pm_starts, pm_ends, pm_ids)):
        task = f"system PM task {i} on <TEACH-AIR-01,0>"
        check(at(log, start, f"{task} started"), f"PM {i} starts")
        check(at(log, start, f"{task} PMID: {pmid}"), f"PM {i} {pmid} identity")
        check(at(log, start, f"subtask {i} seqno 1 within {task} started"), f"PM {i} INSPECT starts")
        check(at(log, start, f"subtask {i} seqno 1 within {task} starts performing, planned to last for 1 hours"), f"PM {i} positive work")
        check(at(log, end, f"subtask {i} seqno 1 within {task} completed"), f"PM {i} INSPECT ends")
        check(at(log, end, f"{task} completed"), f"PM {i} ends")
        check(at(log, end, "System ready <TEACH-AIR-01,0>"), f"PM {i} restores aircraft")
    check(f"system PM task {len(pm_starts)}" not in log, "no extra PM task")
    check(log.count(".MS2 Critical") == (2 if CAP == 3 else 1) and log.count(".MS3 Critical") == 1, "separate PMID critical labels")
    check(not at(log, 49, "system PM task") and (at(log, 53, "system PM task 2") if CAP == 3 else not at(log, 53, "system PM task")), "later MS2 cap contrast")
    report = {t["name"]: t for t in load(RUN / "report-raw.json", native=True)["report"]["tables"]}
    check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
    summary = records(report["ResultSummary"])[0]
    for key, value in {"NREP": 1, "RTILW": 0, "RTIUP": 60, "MTMF": 1, "MSTF": 1, "MSUF": 1, "STMF": 1}.items():
        close(summary[key], value, f"summary {key}")
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    check(len(system) == len(stock) == 120, "120 System and Stock bins")
    mission_alloc = list(zip(allocations, ends))
    mission_oper = list(zip(starts, ends))
    mission_reserved = list(zip(allocations, starts))
    pm_spans = list(zip(pm_starts, pm_ends))
    ready_spans = [(0, 7), (12, 15), (18, 19), (22, 47), (49, 51), (54 if CAP == 3 else 53, 60)]
    pm_markers = pm_starts
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
    close(sum(r["NSYMO"] for r in system)*.5, 8, "eight flight hours")
    close(sum(r["NSYPM"] for r in system)*.5, len(pm_starts), "PM work hours", 3e-5)
    check(system[-1]["NSYRY"] == 1 and system[-1]["NSYPM"] == 0 and stock[-1]["NBO"] == 0, "terminal ready, no PM, no backorder")
    result = {
        "schema": "independent-d11-related-mnocc-readonly/v1", "case": CASE.name, "run_id": RUN_ID,
        "verdict": "GO" if not failures else "NO-GO", "passed": not failures,
        "check_count": checks, "failures": failures,
        "source_sha256": sha(source_path), "closure_sha256": sha(RUN / "closure.json"),
        "log_sha256": sha(RUN / "model.log"), "report_sha256": sha(RUN / "report-raw.json"),
        "scope": f"Corrected linked MS2/MS3 pair with MS2.MNOCC={CAP}; observed PMID cycles {pm_ids}",
        "limitations": ["Native logs name the performed PMID but expose no occurrence-counter value. MS3 consuming one MS2 allowance is an inference from the cap-2 suppression versus cap-3 h53 MS2 event plus the manual.",
                        "Initial #2011 diagnostic is excluded; only corrected -02 closures are accepted.",
                        "Other PM links, prelife, intervals, seeds, GUI-only behavior, and cross-engine equivalence remain unverified."],
    }
    OUTPUT.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": checks, "failures": failures,
                      "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUTPUT)}, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == "__main__":
    main()
