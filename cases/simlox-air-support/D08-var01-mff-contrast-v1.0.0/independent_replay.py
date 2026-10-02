"""Independent read-only replay of the D08.var01 MFF native pair."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parent
CASES = CASE.parent
D05 = CASES / "D05-maintenance-competition-v1.0.0"
D02 = CASES / "D02-var01-traditional-op-hours-v1.0.0"
D05_NATIVE = D05 / "runs/d05-pilot-v100-ssh-20260930-03"
D02_NATIVE = D02 / "runs/d02-var01-traditional-op-v100-ssh-20260930-01"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
OUT = CASE / "independent-verdict.json"
CHECKS = 0
FAILURES: list[str] = []


def check(ok, label):
    global CHECKS
    CHECKS += 1
    if not ok:
        FAILURES.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(path, kind):
    return {t["name"]: t for t in read(path)[kind]["tables"]}


def rows(table):
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, r)) for inst in table["instances"] for r in inst["rows"]]


def near(a, b, tol=1e-4):
    return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)


def delta(a, b):
    out = []
    for name in a:
        check(a[name]["columns"] == b[name]["columns"], f"source columns {name}")
        ar, br = rows(a[name]), rows(b[name])
        check(len(ar) == len(br), f"source row count {name}")
        for idx, (before, after) in enumerate(zip(ar, br)):
            for field, value in before.items():
                if value != after[field]:
                    out.append({"table": name, "row": idx, "field": field,
                                "before": value, "after": after[field]})
    return sorted(out, key=lambda x: (x["table"], x["row"], x["field"]))


def sealed(run):
    c, i = read(run / "closure.json"), read(run / "invocation.json")
    check(c["run_id"] == i["run_id"] == run.name, f"run identity {run.name}")
    check(c["invocation_sha256"] == sha(run / "invocation.json"), f"invocation seal {run.name}")
    check(i["source_hashes_before"] == c["source_hashes_before"] == c["source_hashes_after"],
          f"source unchanged {run.name}")
    check(len(c["raw"]) == 12, f"12 raw seals {run.name}")
    for name, spec in c["raw"].items():
        f = run / name
        check(f.exists() and f.stat().st_size == spec["bytes"], f"raw bytes {run.name}/{name}")
        check(sha(f) == spec["sha256"], f"raw SHA {run.name}/{name}")
    check(i["execution_mode"] == "ssh_cli_v1" and i["session_id"] == 0,
          f"session-0 SSH {run.name}")
    check("sshd.exe" in [x.lower() for x in i["ssh_ancestor_names"]],
          f"SSH ancestor {run.name}")
    check(i["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"mutex {run.name}")
    check(i["gui"]["pid"] == 13340 and i["gui"]["session_id"] == 1,
          f"GUI preserved {run.name}")
    return c, i


def main():
    contract, declared = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    donor = D05 / "native-input.json"
    parent = D02 / "native-input.json"
    check(sha(donor) == contract["direct_behavioral_donor"]["input_sha256"] ==
          declared["parent_sha256"], "accepted D05 donor source")
    check(sha(D05_NATIVE / "closure.json") ==
          contract["direct_behavioral_donor"]["native_closure_sha256"], "accepted D05 closure")
    check(sha(parent) == contract["catalog_parent_prerequisite"]["input_sha256"],
          "D02 prerequisite source")
    check(sha(D02_NATIVE / "closure.json") ==
          contract["catalog_parent_prerequisite"]["native_closure_sha256"],
          "D02 prerequisite closure")
    check(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "manual pin")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary pin")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
          "installed CLI pin")
    dm = tables(donor, "model")
    arms = {}
    for arm in ("default", "low"):
        source = CASE / f"native-input-{arm}.json"
        check(sha(source) == contract["arms"][arm]["input_sha256"] ==
              declared["source_sha256"][arm], f"frozen source {arm}")
        model = tables(source, "model")
        check(set(model) == set(dm) and len(model) == 31, f"31 source tables {arm}")
        expected = sorted(declared["changes_from_parent"][arm],
                          key=lambda x: (x["table"], x["row"], x["field"]))
        check(delta(dm, model) == expected, f"exact D05→{arm} source delta")
        check(sum(dm[t] == model[t] for t in dm) == 29, f"29 unchanged donor tables {arm}")
        mission = rows(model["MissionType"])
        check(mission[0]["MFF"] == 0 and
              mission[1]["MFF"] == (None if arm == "default" else 1e-6),
              f"BASIC control and RISK MFF {arm}")
        run = CASE / "runs" / f"d08-var01-{arm}-v100-ssh-20261002-01"
        c, i = sealed(run)
        source_files = {
            "input": source, "parent": donor, "catalog_parent": parent,
            "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
            "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "simlox_exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY,
        }
        for key, path in source_files.items():
            check(c["source_hashes_before"][key] == sha(path), f"source seal {arm}/{key}")
        check(c["source_hashes_before"]["python"] == i["python_sha256"],
              f"Python runtime seal {arm}")
        check(sha(run / "input.json") == sha(source), f"raw input {arm}")
        steps = read(run / "steps.json")
        check([s["name"] for s in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"],
              f"five ordered native steps {arm}")
        for step in steps:
            check(step["exit_code"] == 0 and step["status"] in {"completed", "calc_observed"} and
                  step["gui_preserved"] is True, f"step success and GUI {arm}/{step['name']}")
        export = tables(run / "roundtrip-raw.json", "model")
        populated = [name for name, table in model.items() if any(inst["rows"] for inst in table["instances"])]
        check(len(populated) == 22 and set(export) >= set(model), f"22 source tables {arm}")
        for name in populated:
            check(model[name]["columns"] == export[name]["columns"] and
                  model[name]["instances"] == export[name]["instances"],
                  f"exact native roundtrip {arm}/{name}")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog and
              "warning #108" in runlog and "warning #126" in runlog,
              f"zero conversion errors, expected warnings {arm}")
        check("Saving results" in runlog and (run / "model.sxo").stat().st_size > 4,
              f"valid native output {arm}")
        report = tables(run / "report-raw.json", "report")
        check({"ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults"} <= set(report),
              f"default report table set {arm}")
        sy, st, rs = (rows(report[name]) for name in
                      ("SystemResults", "StockTotalResults", "ResourceResults"))
        check(len(sy) == len(st) == len(rs) == 72, f"72 system/stock/resource bins {arm}")
        for idx, (system, stock, resource) in enumerate(zip(sy, st, rs)):
            hour = idx / 2
            check(all(near(row["STINT"], hour) and near(row["ETINT"], hour + .5)
                      for row in (system, stock, resource)), f"half-hour bins {arm}/{idx}")
            check(near(resource["NR"], 1) and near(resource["NRA"], 1) and
                  resource["NRUM"] <= 1.0001, f"one worker capacity {arm}/{idx}")
            check(near(stock["NBO"], 0), f"no stock backorders {arm}/{idx}")
            check(near(system["NFAIL"], int(arm == "default" and hour == 22.5)),
                  f"failure bin {arm}/{idx}")
            check(near(system["NSYRP"], int(arm == "default" and 23 <= hour < 28)),
                  f"system CM bin {arm}/{idx}")
            pm = (28 <= hour < 30) if arm == "default" else (24 <= hour < 26)
            check(near(system["NSYPM"], int(pm)), f"system PM bin {arm}/{idx}")
            work = (23 <= hour < 30) if arm == "default" else (24 <= hour < 26)
            check(near(resource["NRUM"], int(work)), f"worker occupied bin {arm}/{idx}")
        summary = rows(report["ResultSummary"])[0]
        check(summary["NREP"] == 1 and near(summary["MSUF"], 2 / 3 if arm == "default" else 1),
              f"summary mission success factor {arm}")
        check(near(sum(float(x["NSYPM"] or 0) * .5 for x in sy), 2) and
              near(sum(float(x["NSYRP"] or 0) * .5 for x in sy),
                   5 if arm == "default" else 0), f"integrated PM and CM hours {arm}")
        check(near(sum(float(x["NRUM"] or 0) * .5 for x in rs),
                   7 if arm == "default" else 2), f"worker work hours {arm}")
        check(near(sy[-1]["NSYRY"], 2), f"two terminal ready aircraft {arm}")
        arms[arm] = {"run": run, "log": (run / "model.log").read_text(encoding="utf-8-sig"),
                     "report": report, "source": source}

    check(sha(arms["default"]["run"] / "model.log") == sha(D05_NATIVE / "model.log"),
          "default log byte-identical to accepted D05")
    default, low = arms["default"]["log"], arms["low"]["log"]
    for arm, log in [("default", default), ("low", low)]:
        for mid, start, end, kind in [(0, 8, 10, "BASIC-MISSION"),
                                       (1, 20, 23, "RISK-MISSION"),
                                       (2, 32, 34, "BASIC-MISSION")]:
            check(f"Time: {start} <{kind},TEACH-UNIT,0,0,{mid}> mission starting" in log,
                  f"mission launch {arm}/{mid}")
            outcome = "aborted mission completed" if arm == "default" and mid == 1 else "mission success"
            check(f"Time: {end} <{kind},TEACH-UNIT,0,0,{mid}> {outcome}" in log,
                  f"mission outcome {arm}/{mid}")
        check(log.count("PMID: CAL24") == 2, f"two CAL24 PM tasks {arm}")
    for fragment in [
        "Time: 22.6835 <TEACH-AIR-01,1> critical random failure added",
        "Time: 22.6835 <RISK-MISSION,TEACH-UNIT,0,0,1> mission aborted",
        "Time: 23  direct repair subtask 0 seqno 1 within system DIRP task 0 on <TEACH-AIR-01,1> starts performing, planned to last for 5 hours",
        "Time: 28  direct repair subtask 0 seqno 1 within system DIRP task 0 on <TEACH-AIR-01,1> completed",
        "Time: 28  subtask 1 seqno 1 within system PM task 1 on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours",
        "Time: 29  subtask 2 seqno 1 within system PM task 2 on <TEACH-AIR-01,1> starts performing, planned to last for 1 hours",
        "Time: 30  system PM task 2 on <TEACH-AIR-01,1> completed",
    ]:
        check(fragment in default, f"default failure/CM/PM event {fragment[:62]}")
    check("critical random failure added" not in low and "system DIRP task" not in low and
          "mission aborted" not in low, "low arm no failure, direct CM or abort")
    for arm, log, expected_leases in [
        ("default", default, [(23, 28, "system DIRP task 0"),
                              (28, 29, "system PM task 1"), (29, 30, "system PM task 2")]),
        ("low", low, [(24, 25, "system PM task 0"), (25, 26, "system PM task 1")]),
    ]:
        check(log.count("books resources") == log.count("frees resources") == len(expected_leases),
              f"worker book/free event count {arm}")
        for start, end, task in expected_leases:
            check(any(line.startswith(f"Time: {start} ") and task in line and "books resources" in line
                      for line in log.splitlines()), f"worker booking {arm}/{task}")
            check(any(line.startswith(f"Time: {end} ") and task in line and "frees resources" in line
                      for line in log.splitlines()), f"worker release {arm}/{task}")
        check(all(expected_leases[index][1] <= expected_leases[index + 1][0]
                  for index in range(len(expected_leases) - 1)),
              f"nonoverlapping single-worker leases {arm}")
    for fragment in [
        "Time: 23 <RISK-MISSION,TEACH-UNIT,0,0,1> mission success",
        "Time: 24  subtask 0 seqno 1 within system PM task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours",
        "Time: 25  subtask 0 seqno 1 within system PM task 0 on <TEACH-AIR-01,0> completed",
        "Time: 25  subtask 1 seqno 1 within system PM task 1 on <TEACH-AIR-01,1> starts performing, planned to last for 1 hours",
        "Time: 26  subtask 1 seqno 1 within system PM task 1 on <TEACH-AIR-01,1> completed",
        "Time: 26  system PM task 1 on <TEACH-AIR-01,1> completed",
    ]:
        check(fragment in low, f"low mission/serial PM event {fragment[:62]}")

    result = {
        "schema": "simlox-independent-readonly-d08-var01-mff/v1",
        "passed": not FAILURES,
        "verdict": "GO: bounded MFF fixed-seed contrast" if not FAILURES else "NO-GO: independent replay failed",
        "checks_passed": CHECKS - len(FAILURES), "checks_total": CHECKS,
        "failures": FAILURES,
        "runs": [arms[arm]["run"].name for arm in ("default", "low")],
        "evidence": {arm: {"input_sha256": sha(data["source"]),
                            "closure_sha256": sha(data["run"] / "closure.json"),
                            "model_log_sha256": sha(data["run"] / "model.log"),
                            "report_sha256": sha(data["run"] / "report-raw.json")}
                     for arm, data in arms.items()},
        "finding": "The omitted/default RISK MFF run reproduces accepted D05's failure at 22.6835, abort, five-hour CM and delayed serial PM. The 0.000001 MFF run has no observed failure/CM, succeeds in all three missions and performs two serial CAL24 PM jobs at hours 24-26 under one worker.",
        "limits": [
            "One fixed seed and one mission-type traditional operation-hour contrast; absence of failure in the low arm is not a reliability estimate.",
            "Calendar-rate failures, other MFF values, overrides, criticality, GUI-only behavior and cross-engine parity remain untested.",
            "ResourceResults.NRW is preserved as a native report field; it is not interpreted as booked work time. NRUM and event leases support worker occupancy.",
            "ResourceResults.NRA stays at one even during a booking, so it is not treated as the free-worker complement of NRUM.",
        ],
    }
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": CHECKS,
                      "failures": FAILURES, "verdict_json": str(OUT)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
