"""Independent, standard-library, read-only D08.var03 raw replay."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parent
CASES = CASE.parent
D01 = CASES / "D01-installed-lru-direct-repair-v1.0.0"
D06 = CASES / "D06-explicit-position-direct-repair-v1.0.0"
D02 = CASES / "D02-var01-traditional-op-hours-v1.0.0"
PARENTS = {"traditional": (D01 / "native-input.json",
                           D01 / "runs/d01-lru-v100-ssh-20260929-01"),
           "failure-mode": (D06 / "native-input.json",
                            D06 / "runs/d06-position-cm-v100-ssh-20260930-02")}
D02_RUN = D02 / "runs/d02-var01-traditional-op-v100-ssh-20260930-01"
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


def near(a, b, tol=1e-5):
    return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)


def edits(before, after):
    result = []
    for name in before:
        a, b = before[name], after[name]
        check(a["columns"] == b["columns"], f"source columns {name}")
        ar, br = rows(a), rows(b)
        check(len(ar) == len(br), f"source row count {name}")
        for idx, (x, y) in enumerate(zip(ar, br)):
            for field, value in x.items():
                if value != y[field]:
                    result.append({"table": name, "row": idx, "field": field,
                                   "before": value, "after": y[field]})
    return sorted(result, key=lambda x: (x["table"], x["row"], x["field"]))


def seal(run):
    closure, invocation = read(run / "closure.json"), read(run / "invocation.json")
    check(run.name == closure["run_id"] == invocation["run_id"], f"run identity {run.name}")
    check(sha(run / "invocation.json") == closure["invocation_sha256"],
          f"invocation seal {run.name}")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] ==
          closure["source_hashes_after"], f"source stable {run.name}")
    check(len(closure["raw"]) == 12, f"12 raw seals {run.name}")
    for filename, evidence in closure["raw"].items():
        path = run / filename
        check(path.exists() and path.stat().st_size == evidence["bytes"],
              f"raw bytes {run.name}/{filename}")
        check(sha(path) == evidence["sha256"], f"raw SHA {run.name}/{filename}")
    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0,
          f"session-0 SSH {run.name}")
    check("sshd.exe" in [s.lower() for s in invocation["ssh_ancestor_names"]],
          f"SSH ancestor {run.name}")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue",
          f"host mutex {run.name}")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
          f"preserved GUI identity {run.name}")
    return closure, invocation


def main():
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    check(sha(D02 / "native-input.json") ==
          contract["catalog_parent_prerequisite"]["input_sha256"], "D02 source pin")
    check(sha(D02_RUN / "closure.json") ==
          contract["catalog_parent_prerequisite"]["native_closure_sha256"], "D02 closure pin")
    check(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "manual pin")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary pin")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
          "installed CLI pin")
    result_arms = {}
    for arm in ("traditional", "failure-mode"):
        parent_source, parent_run = PARENTS[arm]
        source = CASE / f"native-input-{arm}.json"
        run = CASE / "runs" / f"d08-var03-{arm}-v100-ssh-20261002-01"
        check(sha(parent_source) == contract["accepted_controls"][arm]["input_sha256"] ==
              diff["arms"][arm]["parent_sha256"], f"accepted {arm} control source")
        check(sha(parent_run / "closure.json") ==
              contract["accepted_controls"][arm]["native_closure_sha256"],
              f"accepted {arm} control closure")
        check(sha(source) == contract["arms"][arm]["input_sha256"] ==
              diff["arms"][arm]["child_sha256"], f"frozen child source {arm}")
        parent_model, model = tables(parent_source, "model"), tables(source, "model")
        check(set(parent_model) == set(model) and
              len(model) == diff["arms"][arm]["parent_table_count"],
              f"parent-child table coverage {arm}")
        expected = sorted(diff["arms"][arm]["changes"],
                          key=lambda x: (x["table"], x["row"], x["field"]))
        check(edits(parent_model, model) == expected, f"exact criticality-only business delta {arm}")
        check(sum(model[k] == parent_model[k] for k in model) ==
              diff["arms"][arm]["unchanged_tables"], f"unchanged table count {arm}")
        crit_table, field = ("Item", "CRIT") if arm == "traditional" else ("FailureMode", "CRITF")
        check(rows(parent_model[crit_table])[0][field] == 1 and
              rows(model[crit_table])[0][field] == 0, f"one-to-zero criticality {arm}")
        c, i = seal(run)
        source_files = {
            "input": source, "parent": parent_source, "parent_closure": parent_run / "closure.json",
            "catalog_parent": D02 / "native-input.json", "catalog_closure": D02_RUN / "closure.json",
            "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
            "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "simlox_exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY,
        }
        for key, path in source_files.items():
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
                  step["gui_preserved"] is True, f"step success and GUI {arm}/{step['name']}")
        exported = tables(run / "roundtrip-raw.json", "model")
        populated = [k for k, t in model.items() if any(inst["rows"] for inst in t["instances"])]
        check(set(exported) >= set(model), f"native table coverage {arm}")
        for name in populated:
            check(model[name]["columns"] == exported[name]["columns"] and
                  model[name]["instances"] == exported[name]["instances"],
                  f"exact authored roundtrip {arm}/{name}")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
              "warning #108" in runlog, f"zero converter errors/expected warning {arm}")
        check("Saving results" in runlog and (run / "model.sxo").stat().st_size > 4,
              f"valid SXO and saved report {arm}")
        report = tables(run / "report-raw.json", "report")
        check({"ResultSummary", "SystemResults", "StockTotalResults"} <= set(report),
              f"report tables {arm}")
        sy, st = rows(report["SystemResults"]), rows(report["StockTotalResults"])
        check(len(sy) == len(st) == 72, f"72 system/stock half-hour bins {arm}")
        faults = {9.5} if arm == "traditional" else {9.5, 21.5}
        repairs = {10} if arm == "traditional" else {10, 22}
        for idx, (a, b) in enumerate(zip(sy, st)):
            hour = idx / 2
            check(all(near(r["STINT"], hour) and near(r["ETINT"], hour + .5)
                      for r in (a, b)), f"report bin interval {arm}/{idx}")
            operating = any(start <= hour < end for start, end in [(8, 10), (20, 22), (32, 34)])
            check(near(a["FTMO"], int(operating)) and near(a["NSYMO"], int(operating)),
                  f"successful mission occupancy {arm}/{idx}")
            check(near(a["NFAIL"], int(hour in faults)), f"failure report marker {arm}/{idx}")
            check(near(a["NSYRP"], int(hour in repairs)), f"postmission CM bin {arm}/{idx}")
            check(near(b["NBO"], 0), f"no aggregate stock backorder {arm}/{idx}")
        summary = rows(report["ResultSummary"])[0]
        check(summary["NREP"] == 1 and near(summary["MSUF"], 1),
              f"all three missions succeed summary {arm}")
        check(near(sum((x["FTMO"] or 0) * .5 for x in sy), 6) and
              near(sum((x["NFAIL"] or 0) * .5 for x in sy),
                   .5 if arm == "traditional" else 1) and
              near(sum((x["NSYRP"] or 0) * .5 for x in sy),
                   .5 if arm == "traditional" else 1),
              f"integrated flight/failure/repair ledger {arm}")
        check(near(sy[-1]["NSYRY"], 1), f"terminal aircraft ready {arm}")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig")
        check("Time: 9.8829 <TEACH-AIR-01,0> critical" in parent_log and
              "Time: 9.8829 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted" in parent_log,
              f"accepted critical control contrasted at first fault {arm}")
        check("mission aborted" not in log and
              not re.search(r"^Time: [^\n]+> critical (?:random failure|CM failure mode) added", log, re.M),
              f"noncritical continuation {arm}")
        for number, start, end in [(0, 8, 10), (1, 20, 22), (2, 32, 34)]:
            check(f"Time: {start} <BASIC-MISSION,TEACH-UNIT,0,0,{number}> mission starting" in log,
                  f"mission launch {arm}/{number}")
            check(f"Time: {end} <BASIC-MISSION,TEACH-UNIT,0,0,{number}> mission success" in log,
                  f"mission success {arm}/{number}")
        result_arms[arm] = {"run": run, "source": source, "log": log, "report": report,
                            "populated_count": len(populated)}

    traditional = result_arms["traditional"]["log"]
    for fragment in [
        "Time: 9.8829 <TEACH-AIR-01,0> noncritical random failure added",
        "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Item demand arrives",
        "item requiring maintenance is <TEACH-LRU-01,0,1>",
        "Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0>",
        "Time: 10  remove subitem subtask 0 seqno 0 within system SURP task 0",
        "Time: 10.25  fit subitem subtask 1 seqno 1 within system SURP task 0",
        "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready",
        "Time: 11.25 <TEACH-LRU-01,0,BASE-01,0> Finished repair of item <TEACH-LRU-01,0,1>",
        "Time: 11.25 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,1>",
        "Level: 1 Items:<TEACH-LRU-01,0,1>",
    ]:
        check(fragment in traditional, f"traditional fault/stock/SURP event {fragment[:55]}")
    fm = result_arms["failure-mode"]["log"]
    for hour, task, finish in [("9.8829", 0, "10.5"), ("21.8602", 1, "22.5")]:
        check(f"Time: {hour} <TEACH-AIR-01,0> noncritical CM failure mode added" in fm and
              "Failure Mode: FM-POS-A on materiel: <POS-A,0>" in fm,
              f"FM-POS-A noncritical fault {hour}")
        start = "10" if task == 0 else "22"
        check(f"Time: {start}  subtask {task} seqno 0 within system CM task {task} on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours" in fm,
              f"FM system CM starts {start}")
        check(f"Time: {finish} <TEACH-AIR-01,BASE-01,0> System ready" in fm,
              f"FM aircraft ready {finish}")
    check("Take replacement item" not in fm and "Stock at:" not in fm,
          "explicit FM path has no LRU stock exchange")

    result = {
        "schema": "simlox-independent-readonly-d08-var03-criticality/v1",
        "passed": not FAILURES,
        "verdict": "GO: bounded zero-criticality mission continuation" if not FAILURES else
                   "NO-GO: independent replay failed",
        "checks_passed": CHECKS - len(FAILURES), "checks_total": CHECKS,
        "failures": FAILURES,
        "evidence": {arm: {"input_sha256": sha(data["source"]),
                            "closure_sha256": sha(data["run"] / "closure.json"),
                            "model_log_sha256": sha(data["run"] / "model.log"),
                            "report_sha256": sha(data["run"] / "report-raw.json"),
                            "populated_authored_tables": data["populated_count"]}
                     for arm, data in result_arms.items()},
        "finding": "At CRIT/CRITF zero, the first h9.8829 fault is explicitly noncritical and the mission succeeds at h10, contrasting each accepted CRIT1 control abort. Traditional LRU replacement/SURP ends h10.5 and ID1 returns to stock h11.25. Explicit FM-POS-A faults occur h9.8829 and h21.8602 with half-hour CM after both successful returns. All three missions succeed and the aircraft is ready at h36.",
        "limits": [
            "One fixed seed, one aircraft, three two-hour missions and endpoint criticality zero versus accepted one controls; no fractional-probability conclusion.",
            "The explicit-FM second fault shifts to h21.8602; later random clocks are not asserted equal to the critical control.",
            "Traditional physical LRU replacement and explicit position-linked CM are distinct routes; no shared inventory inference.",
            "Mission-specific overrides, PFF, SYACF, NCFTL, simultaneous faults, GUI-only behavior and cross-engine parity untested.",
        ],
    }
    OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_total": CHECKS,
                      "failures": FAILURES, "verdict_json": str(OUT)}, ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
