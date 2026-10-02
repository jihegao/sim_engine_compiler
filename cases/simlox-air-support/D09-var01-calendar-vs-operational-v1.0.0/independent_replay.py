"""Independent read-only D09.var01 calendar/operation escalation replay."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parent
CASES = CASE.parent
PARENT = CASES / "D08-var03-criticality-v1.0.0"
E02 = CASES / "E02-zero-stock-local-backorder-v1.0.0"
PARENT_SOURCE = PARENT / "native-input-traditional.json"
PARENT_RUN = PARENT / "runs/d08-var03-traditional-v100-ssh-20261002-01"
E02_RUN = E02 / "runs/e02-v100-ssh-20260929-01"
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


def tables(path, key):
    return {t["name"]: t for t in read(path)[key]["tables"]}


def rows(table):
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def near(a, b, tol=2e-4):
    return math.isclose(float(a or 0), float(b), abs_tol=tol, rel_tol=0)


def fraction(start, end, bin_start):
    return max(0, min(end, bin_start + .5) - max(start, bin_start)) / .5


def diff_tables(parent, child):
    found = {}
    for name in parent:
        a, b = parent[name], child[name]
        check(a["columns"] == b["columns"], f"source columns {name}")
        ar, br = rows(a), rows(b)
        check(len(ar) == len(br), f"source rows {name}")
        changes = {}
        for x, y in zip(ar, br):
            for field, value in x.items():
                if value != y[field]:
                    changes[field] = {"before": value, "after": y[field]}
        if changes:
            found[name] = changes
    return found


def sealed(run):
    c, i = read(run / "closure.json"), read(run / "invocation.json")
    check(c["run_id"] == i["run_id"] == run.name, f"run identity {run.name}")
    check(sha(run / "invocation.json") == c["invocation_sha256"], f"invocation SHA {run.name}")
    check(i["source_hashes_before"] == c["source_hashes_before"] == c["source_hashes_after"],
          f"source unchanged {run.name}")
    check(len(c["raw"]) == 12, f"12 raw seals {run.name}")
    for name, spec in c["raw"].items():
        f = run / name
        check(f.exists() and f.stat().st_size == spec["bytes"], f"raw length {run.name}/{name}")
        check(sha(f) == spec["sha256"], f"raw SHA {run.name}/{name}")
    check(i["execution_mode"] == "ssh_cli_v1" and i["session_id"] == 0,
          f"session-0 SSH {run.name}")
    check("sshd.exe" in [s.lower() for s in i["ssh_ancestor_names"]],
          f"SSH ancestor {run.name}")
    check(i["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"mutex {run.name}")
    check(i["gui"]["pid"] == 13340 and i["gui"]["session_id"] == 1,
          f"preserved GUI {run.name}")
    return c, i


def main():
    contract, declared = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    check(sha(PARENT_SOURCE) == contract["accepted_parent"]["input_sha256"] ==
          declared["parent_input_sha256"], "accepted D08 parent source SHA")
    check(sha(PARENT_RUN / "closure.json") ==
          contract["accepted_parent"]["native_closure_sha256"], "accepted D08 closure SHA")
    check(sha(E02 / "native-input.json") == contract["stock_shortage_precedent"]["input_sha256"],
          "E02 stock precedent source SHA")
    check(sha(E02_RUN / "closure.json") ==
          contract["stock_shortage_precedent"]["native_closure_sha256"],
          "E02 stock precedent closure SHA")
    check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen exact-diff SHA")
    check(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "manual SHA")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary SHA")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
          "installed CLI SHA")
    parent_model = tables(PARENT_SOURCE, "model")
    observed = {}
    for arm in ("calendar", "operational"):
        source = CASE / f"native-input-{arm}.json"
        run = CASE / "runs" / f"d09-var01-{arm}-v100-ssh-20261002-01"
        check(sha(source) == contract["arms"][arm]["input_sha256"] ==
              declared["children"][arm]["input_sha256"], f"child source SHA {arm}")
        model = tables(source, "model")
        check(set(model) == set(parent_model) and len(model) == len(parent_model),
              f"same table set {arm}")
        check(diff_tables(parent_model, model) == declared["children"][arm]["changed_tables"],
              f"exact parent-child source delta {arm}")
        check(sum(parent_model[t] == model[t] for t in model) == 28,
              f"28 unchanged source tables {arm}")
        item = rows(model["Item"])[0]
        allocation = rows(model["StockAllocation"])[0]
        check(item["NCFTL"] == .2 and item["NCFTT"] ==
              ("CALENDAR" if arm == "calendar" else "OPERATION") and
              item["CRIT"] == 0 and allocation["STSIZ"] == 0,
              f"criticality clock and zero stock source {arm}")
        c, i = sealed(run)
        files = {
            "input": source, "parent": PARENT_SOURCE, "parent_closure": PARENT_RUN / "closure.json",
            "stock_parent": E02 / "native-input.json", "stock_closure": E02_RUN / "closure.json",
            "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
            "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "simlox_exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY,
        }
        for key, path in files.items():
            check(c["source_hashes_before"][key] == sha(path), f"source seal {arm}/{key}")
        check(c["source_hashes_before"]["python"] == i["python_sha256"],
              f"Python runtime seal {arm}")
        check(sha(run / "input.json") == sha(source), f"raw child input {arm}")
        steps = read(run / "steps.json")
        check([s["name"] for s in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"],
              f"five ordered native steps {arm}")
        for step in steps:
            check(step["exit_code"] == 0 and step["status"] in {"completed", "calc_observed"} and
                  step["gui_preserved"] is True, f"native step success/GUI {arm}/{step['name']}")
        export = tables(run / "roundtrip-raw.json", "model")
        populated = [name for name, t in model.items() if any(inst["rows"] for inst in t["instances"])]
        check(len(populated) == 18 and set(export) >= set(model),
              f"18 authored row-containing tables {arm}")
        for name in populated:
            check(model[name]["columns"] == export[name]["columns"] and
                  model[name]["instances"] == export[name]["instances"],
                  f"exact native table roundtrip {arm}/{name}")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
              "warning #108" in runlog, f"zero converter errors and warning108 {arm}")
        check("Saving results" in runlog and (run / "model.sxo").stat().st_size > 4,
              f"nontrivial SXO/report {arm}")
        report = tables(run / "report-raw.json", "report")
        check({"ResultSummary", "SystemResults", "StockTotalResults"} <= set(report),
              f"report table set {arm}")
        sy, st = rows(report["SystemResults"]), rows(report["StockTotalResults"])
        check(len(sy) == len(st) == 72, f"72 report bins {arm}")
        remove = 11.3329 if arm == "calendar" else 21.4158
        first_work = (10.0829, 10.3329) if arm == "calendar" else (20.1658, 20.4158)
        second_work = (11.3329, 11.5829) if arm == "calendar" else (21.4158, 21.6658)
        # The operational failure escalates at 20.0829; the aborted aircraft returns at 20.1658.
        second_flight_end = 22 if arm == "calendar" else 20.1658
        for idx, (a, b) in enumerate(zip(sy, st)):
            hour = idx / 2
            check(all(near(row["STINT"], hour) and near(row["ETINT"], hour + .5)
                      for row in (a, b)), f"half-hour interval {arm}/{idx}")
            flight = sum(fraction(x, y, hour) for x, y in
                         [(8, 10), (20, second_flight_end), (32, 34)])
            check(near(a["FTMO"], flight) and near(a["NSYMO"], flight),
                  f"mission occupancy {arm}/{idx}")
            check(near(a["NFAIL"], int(hour == 9.5)), f"first noncritical fault bin {arm}/{idx}")
            work = fraction(*first_work, hour) + fraction(*second_work, hour)
            check(near(a["NSYRP"], work), f"SURP work fraction {arm}/{idx}")
            check(near(b["NBO"], fraction(10, remove, hour)),
                  f"zero-stock backorder occupancy {arm}/{idx}")
            wait = fraction(first_work[1], second_work[0], hour)
            check(near(a["NSYWI"], wait), f"aircraft waiting for same item {arm}/{idx}")
            check(near(b["PNB"], 1 - fraction(10, remove, hour)),
                  f"stock report complement {arm}/{idx}")
            check(near(b["ROS"], int(hour == 10)) and
                  near(b["ROST"], int(hour == 10)) and
                  near(b["NDF"], int(hour == 10)) and
                  near(b["NWT"], int(hour == 10)),
                  f"stock demand/backorder markers {arm}/{idx}")
            check(near(a["STACC"], flight), f"SystemResults flight accumulation {arm}/{idx}")
        summary = rows(report["ResultSummary"])[0]
        expected_factor = 1 if arm == "calendar" else 2 / 3
        check(summary["NREP"] == 1 and near(summary["MSUF"], expected_factor),
              f"summary mission success factor {arm}")
        check(near(sum(float(x["FTMO"] or 0) * .5 for x in sy),
                   6 if arm == "calendar" else 4.1658) and
              near(sum(float(x["NBO"] or 0) * .5 for x in st), remove - 10),
              f"integrated flight and stock backorder {arm}")
        check(near(sy[-1]["NSYRY"], 1) and near(st[-1]["NBO"], 0),
              f"terminal ready and backorder cleared {arm}")
        event = (run / "model.log").read_text(encoding="utf-8-sig")
        for fragment in [
            "Time: 9.8829 <TEACH-AIR-01,0> noncritical random failure added",
            "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success",
            "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives",
            "item requiring maintenance is <TEACH-LRU-01,0,0>",
            "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added",
            "Time: 10  system SURP task 0 on <TEACH-AIR-01,0> wait for subitem",
            "Time: 32 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting",
            "Time: 34 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission success",
            "Time: 34 <TEACH-AIR-01,BASE-01,0> System ready",
        ]:
            check(fragment in event, f"common native event {arm}/{fragment[:58]}")
        check(event.count("failure becomes critical") == 1 and
              event.count("Backorder removed") == 1,
              f"one escalation and one backorder resolution {arm}")
        observed[arm] = {"run": run, "source": source, "log": event, "report": report}

    cal, op = observed["calendar"]["log"], observed["operational"]["log"]
    for fragment in [
        "Time: 10.0829 <TEACH-AIR-01,0> failure becomes critical",
        "Time: 10.0829 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> changed to critical",
        "Time: 10.3329 <TEACH-LRU-01,0,BASE-01,0> Start repair of item <TEACH-LRU-01,0,0>",
        "Time: 11.3329 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 1.3329",
        "Time: 11.5829 <TEACH-AIR-01,BASE-01,0> System ready",
        "Time: 20 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting",
        "Time: 22 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission success",
    ]:
        check(fragment in cal, f"calendar escalation/repair/mission event {fragment[:62]}")
    check("mission aborted" not in cal, "calendar arm has no mission abort")
    for fragment in [
        "Time: 19 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> paused",
        "Time: 20 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting",
        "Time: 20.0829 <TEACH-AIR-01,0> failure becomes critical",
        "Time: 20.0829 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission aborted",
        "Time: 20.1658 <BASIC-MISSION,TEACH-UNIT,0,0,1> aborted mission completed",
        "Time: 20.1658 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> continued",
        "Time: 20.4158 <TEACH-LRU-01,0,BASE-01,0> Start repair of item <TEACH-LRU-01,0,0>",
        "Time: 21.4158 <TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 11.4158",
        "Time: 21.6658 <TEACH-AIR-01,BASE-01,0> System ready",
    ]:
        check(fragment in op, f"operation escalation/repair/mission event {fragment[:62]}")
    check("failure becomes critical" not in op.split("Time: 19 <TEACH-UNIT>")[0],
          "operational escalation did not occur during long idle interval")
    for arm, event, start, finish in [
        ("calendar", cal, "10.3329", "11.3329"),
        ("operational", op, "20.4158", "21.4158"),
    ]:
        check(f"Time: {start}  direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,0,0> starts performing, planned to last for 1 hours" in event and
              f"Time: {finish} <TEACH-LRU-01,0,BASE-01,0> Finished repair of item <TEACH-LRU-01,0,0>" in event,
              f"same failed LRU ID0 repaired and reused {arm}")
        check("Take replacement item" not in event,
              f"no spare issue despite zero stock {arm}")

    result = {
        "schema": "simlox-independent-readonly-d09-var01/v1",
        "passed": not FAILURES,
        "verdict": "GO: bounded calendar-versus-operation NCFTT contrast" if not FAILURES else
                   "NO-GO: independent replay failed",
        "checks_passed": CHECKS - len(FAILURES), "checks_total": CHECKS,
        "failures": FAILURES,
        "evidence": {arm: {"input_sha256": sha(data["source"]),
                            "closure_sha256": sha(data["run"] / "closure.json"),
                            "model_log_sha256": sha(data["run"] / "model.log"),
                            "report_sha256": sha(data["run"] / "report-raw.json")}
                     for arm, data in observed.items()},
        "finding": "Both zero-stock arms continue after a noncritical h9.8829 fault and succeed at h10 while SURP waits for the same LRU ID0. CALENDAR escalates at h10.0829, repairs ID0 and clears backorder at h11.3329, then succeeds at h22. OPERATION remains pending through idle, launches h20, escalates/aborts at h20.0829, repairs ID0 and clears backorder at h21.4158. Both finish ready after the third mission succeeds.",
        "limits": [
            "One aircraft, LRU, seed, zero local stock and 0.2-hour limit; no general NCFTT clock law or other tolerance claim.",
            "Native dictionary token is OPERATION; manual prose calls it OPERATIONAL. This replay verifies the installed source token and observed event timing.",
            "The operational second mission aborts at h20.0829; physical repair begins only after return at h20.4158. Aggregate report bins are fractional at those boundaries.",
            "GUI-only behavior and cross-engine parity untested.",
        ],
    }
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": CHECKS,
                      "failures": FAILURES, "verdict_json": str(OUT)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
