"""Independent read-only replay of D09.var04 sealed three-arm native evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
CASES = CASE.parent
PARENT = CASES / "D09-var01-calendar-vs-operational-v1.0.0"
DONOR = CASES / "I01-var03-three-allocation-joint-v1.0.0"
PARENT_INPUT = PARENT / "native-input-calendar.json"
PARENT_CLOSURE = PARENT / "runs/d09-var01-calendar-v100-ssh-20261002-01/closure.json"
DONOR_INPUT = DONOR / "one-base-input.json"
DONOR_CLOSURE = DONOR / "runs/i01-var03-three-one-base-v100-ssh-20261002-01/closure.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
RUNS = {a: CASE / "runs" / f"d09-var04-{a}-v100-ssh-20261002-01" for a in
        ("part-short", "crew-short", "supplied")}
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


def tables(path, root):
    return {t["name"]: t for t in read(path)[root]["tables"]}


def rows(table):
    names = [x["name"] for x in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def approx(a, b, tol=2e-4):
    return math.isclose(float(a or 0), float(b), abs_tol=tol, rel_tol=0)


def span(start, end, hour):
    return max(0, min(end, hour+.5)-max(start, hour))/.5


def source_delta(a, b):
    found, unchanged = {}, 0
    for name in a:
        if a[name] == b[name]:
            unchanged += 1
            continue
        ar, br = rows(a[name]), rows(b[name])
        check(a[name]["columns"] == b[name]["columns"], f"source schema {name}")
        delta = {}
        for old, new in zip(ar, br):
            for key in old:
                if old[key] != new[key]:
                    delta[key] = {"before": old[key], "after": new[key]}
        if len(br) > len(ar):
            delta["added_rows"] = br[len(ar):]
        found[name] = delta
    return found, unchanged


def extract_at(log, prefix):
    return [float(x) for x in re.findall(r"(?m)^Time: ([0-9.]+) " + re.escape(prefix), log)]


def main():
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    check(sha(PARENT_INPUT) == contract["accepted_parent"]["input_sha256"] == diff["parent_input_sha256"], "parent input SHA")
    check(sha(PARENT_CLOSURE) == contract["accepted_parent"]["native_closure_sha256"], "parent closure SHA")
    check(sha(DONOR_INPUT) == contract["accepted_resource_and_task_donor"]["input_sha256"], "resource donor SHA")
    check(sha(DONOR_CLOSURE) == contract["accepted_resource_and_task_donor"]["native_closure_sha256"], "donor closure SHA")
    check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff seal")
    check(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "manual seal")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary seal")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "installed executable seal")
    parent = tables(PARENT_INPUT, "model")
    models = {}
    for arm in RUNS:
        src = CASE / f"native-input-{arm}.json"
        model = tables(src, "model")
        check(sha(src) == contract["arms"][arm]["input_sha256"] == diff["children"][arm]["input_sha256"], f"{arm} source SHA")
        check(set(model) == set(parent), f"{arm} table topology")
        found, same = source_delta(parent, model)
        check(found == diff["children"][arm]["changed_tables"] and same == diff["children"][arm]["identical_tables"],
              f"{arm} exact parent delta")
        check(rows(model["StockAllocation"])[0]["STSIZ"] == contract["arms"][arm]["stock_nominal"] and
              rows(model["ResourceAllocation"])[0]["RQTY"] == contract["arms"][arm]["crew_quantity"], f"{arm} stock and crew capacity")
        check(rows(model["SubTaskResource"])[0]["QTY"] == 1 and
              [r["SUTID"] for r in rows(model["TaskBreakDown"])] == ["<REMOVE>", "<REPLACE>"],
              f"{arm} one crew demanded by removal task")
        models[arm] = (src, model)
    for a, b, key in (("part-short", "supplied", "part_to_supplied"),
                      ("crew-short", "supplied", "crew_to_supplied"),
                      ("part-short", "crew-short", "part_to_crew")):
        found, _ = source_delta(models[a][1], models[b][1])
        check(found == diff["arm_contrasts"][key], f"exact {key} arm contrast")

    evidence = {}
    for arm, run in RUNS.items():
        src, model = models[arm]
        closure, invocation, steps = read(run / "closure.json"), read(run / "invocation.json"), read(run / "steps.json")
        check(closure["run_id"] == invocation["run_id"] == run.name and closure["arm"] == invocation["arm"] == arm,
              f"{arm} run identity")
        check(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation SHA")
        check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"],
              f"{arm} stable run source seals")
        pins = {"input": src, "parent": PARENT_INPUT, "parent_closure": PARENT_CLOSURE,
                "donor": DONOR_INPUT, "donor_closure": DONOR_CLOSURE,
                "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
                "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
                "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
                "python": PYTHON, "simlox_exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY}
        for name, path in pins.items():
            check(sha(path) == closure["source_hashes_before"][name], f"{arm} source seal {name}")
        check(len(closure["raw"]) == 12, f"{arm} 12 raw files")
        for name, spec in closure["raw"].items():
            path = run / name
            check(path.exists() and path.stat().st_size == spec["bytes"], f"{arm} raw size {name}")
            check(sha(path) == spec["sha256"], f"{arm} raw hash {name}")
        check(sha(run / "input.json") == sha(src), f"{arm} native copied input")
        check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and
              invocation["ssh_connection_present"] and "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]],
              f"{arm} session-zero SSH")
        check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
              invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
              f"{arm} mutex and GUI identity")
        check([x["name"] for x in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"],
              f"{arm} five ordered steps")
        for step in steps:
            check(step["exit_code"] == 0 and step["status"] in ("completed", "calc_observed") and
                  step["gui_preserved"] is True, f"{arm} step {step['name']}")
        native = tables(run / "roundtrip-raw.json", "model")
        populated = [n for n,t in model.items() if any(x["rows"] for x in t["instances"])]
        check(len(populated) == 23 and set(native) >= set(model), f"{arm} 23 row-containing tables")
        for name in populated:
            check(native[name]["columns"] == model[name]["columns"] and
                  native[name]["instances"] == model[name]["instances"], f"{arm} roundtrip {name}")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
              "warning #108" in runlog and "Saving results" in runlog, f"{arm} zero errors warning 108")
        check((run / "model.sxo").stat().st_size > 4, f"{arm} valid native SXO")

        log = (run / "model.log").read_text(encoding="utf-8-sig")
        check(extract_at(log, "<TEACH-AIR-01,0> noncritical random failure added") == [9.8829],
              f"{arm} same first noncritical fault")
        check("subitem failed: <TEACH-LRU-01,0," in log and
              "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and
              "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log,
              f"{arm} physical LRU and first mission success")
        check("< system SURP task 0 on <TEACH-AIR-01,0>, NC, 0.5>" in log,
              f"{arm} initial noncritical SURP")
        if arm == "supplied":
            check("failure becomes critical" not in log and "changed to critical" not in log,
                  "supplied active work avoids escalation")
            check("Time: 10  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> books resources" in log and
                  "Time: 10.25  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> frees resources" in log,
                  "supplied crew lease 10-10.25")
            check("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log and
                  "Time: 10.5 <TEACH-AIR-01,BASE-01,0> System ready" in log and
                  "Time: 11.25 <TEACH-LRU-01,0,BASE-01,0> Finished repair of item <TEACH-LRU-01,0,1>" in log,
                  "supplied stocked replacement and later failed-item repair")
            check("Backorder added" not in log, "supplied no stock backorder")
        elif arm == "part-short":
            check("Time: 10.0829 <TEACH-AIR-01,0> failure becomes critical" in log and
                  "Time: 10.0829 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> changed to critical" in log,
                  "part shortage calendar escalation")
            check("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Backorder added" in log and
                  "Time: 11.3329 <TEACH-LRU-01,0,BASE-01,0> Backorder removed" in log and
                  "Time: 11.3329 <TEACH-LRU-01,0,BASE-01,0> Finished repair of item <TEACH-LRU-01,0,0>" in log,
                  "part shortage backorder and same-item repair")
            check("Time: 10.0829  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> books resources" in log and
                  "Time: 10.3329  remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> frees resources" in log and
                  "Time: 11.5829 <TEACH-AIR-01,BASE-01,0> System ready" in log,
                  "part shortage crew lease, removal and restored readiness")
        else:
            check("Time: 10.0829 <TEACH-AIR-01,0> failure becomes critical" in log and
                  "Time: 10.0829 <TEACH-AIR-01,BASE-01,0> system SURP task 0 on <TEACH-AIR-01,0> changed to critical" in log and
                  "Time: 10.0829 <TEACH-AIR-01,0> nbr resourcewait increased" in log,
                  "crew shortage escalation and resource wait")
            check("Time: 10 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock" in log and
                  "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in log and
                  log.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed") >= 3,
                  "crew shortage reserved stock and failed QTY1 tests")
            check("Backorder added" not in log and "books resources" not in log and
                  "starts performing" not in log and "Start repair of item" not in log,
                  "crew shortage no BO, lease, positive work or physical removal")
            check("Time: 20.3333 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission cancelled" in log and
                  "Time: 32.3333 <BASIC-MISSION,TEACH-UNIT,0,0,2> mission cancelled" in log,
                  "crew shortage later mission cancellations")
        if arm != "crew-short":
            for i, start, end in ((1,20,22),(2,32,34)):
                check(f"Time: {start} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission starting" in log and
                      f"Time: {end} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission success" in log,
                      f"{arm} later successful mission {i}")
        report = tables(run / "report-raw.json", "report")
        check({"ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} <= set(report),
              f"{arm} result table set")
        sy, st, rs = [rows(report[name]) for name in ("SystemResults", "StockTotalResults", "ResourceResults")]
        summary = rows(report["ResultSummary"])[0]
        check(len(sy) == len(st) == len(rs) == 72, f"{arm} 72 aligned report bins")
        supplied = arm == "supplied"
        crew_short = arm == "crew-short"
        repair = (10, 10.5) if supplied else ((10.0829,10.3329),(11.3329,11.5829))
        ready_time = 10.5 if supplied else 11.5829
        crew_work = (10,10.25) if supplied else (10.0829,10.3329)
        for idx, (s,t,r) in enumerate(zip(sy, st, rs)):
            h=idx/2
            check(all(approx(x["STINT"],h) and approx(x["ETINT"],h+.5) for x in (s,t,r)),
                  f"{arm} interval {idx}")
            flight = int((8<=h<10) or (not crew_short and ((20<=h<22) or (32<=h<34))))
            check(approx(s["NSYMO"],flight) and approx(s["FTMO"],flight) and
                  approx(s["NFAIL"],1 if h==9.5 else 0), f"{arm} flight and fault bin {idx}")
            expected_rp = 0 if crew_short else (span(*repair,h) if supplied else sum(span(*x,h) for x in repair))
            check(approx(s["NSYRP"], expected_rp), f"{arm} physical system work bin {idx}")
            check(approx(t["NBO"], span(10,11.3329,h) if arm=="part-short" else 0) and
                  approx(t["NDF"], 1 if h==10 else 0), f"{arm} stock BO and demand bin {idx}")
            check(approx(r["NRUM"], span(*crew_work,h) if not crew_short else 0) and
                  approx(r["NRW"], 1 if crew_short and h>=10 else 0),
                  f"{arm} crew booking/wait bin {idx}")
            expected_ready = (span(0,7,h) + (span(10,10.0829,h) if not supplied else 0) +
                              (0 if crew_short else span(ready_time,19,h) + span(22,31,h) + span(34,36,h)))
            if supplied:
                expected_ready = span(0,7,h) + span(10.5,19,h) + span(22,31,h) + span(34,36,h)
            check(approx(s["NSYRY"], expected_ready), f"{arm} readiness bin {idx}")
            check(approx(r["NR"], 0 if crew_short else 1), f"{arm} resource capacity bin {idx}")
        check(summary["NREP"] == 1 and approx(summary["RTIUP"],36) and
              approx(summary["MSUF"], 1/3 if crew_short else 1), f"{arm} summary mission success factor")
        check(approx(sum(float(x["FTMO"] or 0)*.5 for x in sy), 2 if crew_short else 6) and
              approx(sum(float(x["NRUM"] or 0)*.5 for x in rs), 0 if crew_short else .25),
              f"{arm} integrated aircraft/crew hours")
        check(approx(sy[-1]["NSYRY"], 0 if crew_short else 1) and
              approx(st[-1]["NBO"],0) and approx(rs[-1]["NRW"],1 if crew_short else 0),
              f"{arm} terminal system/stock/resource state")
        evidence[arm] = {"input_sha256":sha(src),"closure_sha256":sha(run/"closure.json"),
                         "model_log_sha256":sha(run/"model.log"),"report_sha256":sha(run/"report-raw.json"),
                         "summary":summary}
    result={"schema":"simlox-independent-readonly-d09-var04/v1", "passed":not FAILURES,
            "verdict":"GO: bounded part-versus-crew shortage at NCFTL escalation" if not FAILURES else
                      "NO-GO: independent replay failed", "checks_passed":CHECKS-len(FAILURES),
            "checks_total":CHECKS,"failures":FAILURES,"evidence":evidence,
            "finding":"All three arms share one first-flight noncritical LRU fault at h9.8829 and successful first return at h10. Part shortage and crew shortage each escalate at h10.0829; supplied begins physical replacement at h10 and does not escalate. Part shortage books crew h10.0829-10.3329, repairs the failed LRU, clears its backorder h11.3329 and completes later missions. Crew shortage takes the replacement item from stock at h10 but repeated P-CREW QTY1 tests fail, no physical removal or repair begins, resource wait persists, and later missions cancel at h20.3333/h32.3333.",
            "limits":["One aircraft, LRU, seed, 0.2-hour calendar tolerance, stock 0/1 and crew 0/1.",
                      "Stock reservation at h10 in crew-short is an observed stock event, not physical removal or installed replacement; no backorder appears.",
                      "Only comparisons with supplied isolate one capacity factor; part-short versus crew-short changes both.",
                      "No general shortage priority law, GUI-only or cross-engine claim."]}
    OUT.write_bytes((json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"checks_total":CHECKS,"failures":FAILURES,
                      "verdict":result["verdict"],"output":str(OUT)},ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__=="__main__":
    raise SystemExit(main())
