"""Standalone read-only verification of D14.var01 v1.0.1 native MONIT Y/N evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE.parent
PARENT = CASES / "D06-explicit-position-direct-repair-v1.0.0"
DONOR = CASES / "E01-local-spare-explicit-replacement-v1.0.0"
PARENT_INPUT = PARENT / "native-input.json"
PARENT_CLOSURE = PARENT / "runs/d06-position-cm-v100-ssh-20260930-02/closure.json"
DONOR_INPUT = DONOR / "native-input.json"
DONOR_CLOSURE = DONOR / "runs/e01-v100-ssh-20260929-01/closure.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
RUNS = {arm: HERE / "runs" / f"d14-var01-{arm}-v101-ssh-20261002-01"
        for arm in ("monitored", "system-converted")}
OUTPUT = HERE / "independent-verdict.json"
N = 0
FAIL: list[str] = []


def assert_raw(condition, label):
    global N
    N += 1
    if not condition:
        FAIL.append(label)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def table_map(path, top):
    return {t["name"]: t for t in data(path)[top]["tables"]}


def records(table):
    keys = [c["name"] for c in table["columns"]]
    return [dict(zip(keys, row)) for inst in table["instances"] for row in inst["rows"]]


def near(a, b, eps=1e-6):
    return math.isclose(float(a or 0), float(b), abs_tol=eps, rel_tol=0)


def main():
    contract, diff = data(HERE / "contract.json"), data(HERE / "exact-diff.json")
    assert_raw(digest(PARENT_INPUT) == contract["accepted_parent"]["input_sha256"] == diff["parent_input_sha256"], "D06 parent SHA")
    assert_raw(digest(PARENT_CLOSURE) == contract["accepted_parent"]["native_closure_sha256"], "D06 accepted closure SHA")
    assert_raw(digest(DONOR_INPUT) == contract["accepted_stock_donor"]["input_sha256"], "E01 donor source SHA")
    assert_raw(digest(DONOR_CLOSURE) == contract["accepted_stock_donor"]["native_closure_sha256"], "E01 donor closure SHA")
    assert_raw(digest(MANUAL) == contract["source"]["manual_sha256"], "installed manual SHA")
    assert_raw(digest(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary SHA")
    assert_raw(digest(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "native CLI SHA")
    assert_raw(digest(HERE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen exact diff SHA")
    parent = table_map(PARENT_INPUT, "model")
    models = {}
    for arm in RUNS:
        source = HERE / f"native-input-{arm}.json"
        model = table_map(source, "model")
        expected_sha = diff["monitored_input_sha256"] if arm == "monitored" else diff["system_converted_input_sha256"]
        assert_raw(digest(source) == contract["arms"][arm]["input_sha256"] == expected_sha, f"{arm} source SHA")
        assert_raw(set(model) == set(parent) | {"PMReplacement"}, f"{arm} source table names")
        expected_delta = diff["parent_to_monitored" if arm == "monitored" else "parent_to_system_converted"]
        actual_delta = {name: {"before": parent.get(name), "after": model.get(name)}
                        for name in set(parent) | set(model) if parent.get(name) != model.get(name)}
        assert_raw(actual_delta == expected_delta, f"{arm} exact parent table delta")
        pm = records(model["MaterielPM"])[0]
        assert_raw(pm["MONIT"] == contract["arms"][arm]["MONIT"] and pm["MID"] == "TEACH-LRU-01" and
                   pm["PMINT"] == 2 and pm["OPID"] == "OPHOURS", f"{arm} item operation-hour PM")
        assert_raw(records(model["StockAllocation"])[0]["STSIZ"] == 1 and
                   len(records(model["PMReplacement"])) == 1 and
                   not records(model["ItemStructure"]) and not records(model["FailureMode"]),
                   f"{arm} one spare, scheduled replacement, no traditional failure route")
        models[arm] = (source, model)
    actual_pair = {name: {"before": models["monitored"][1][name], "after": models["system-converted"][1][name]}
                   for name in models["monitored"][1] if models["monitored"][1][name] != models["system-converted"][1][name]}
    assert_raw(actual_pair == diff["monitored_to_system_converted"] and
               set(actual_pair) == {"MaterielPM", "ProblemDescription"}, "isolated MONIT and description contrast")

    reports = {}
    evidence = {}
    for arm, run in RUNS.items():
        source, model = models[arm]
        closure, invocation, steps = data(run / "closure.json"), data(run / "invocation.json"), data(run / "steps.json")
        assert_raw(closure["run_id"] == invocation["run_id"] == run.name and
                   closure["arm"] == invocation["arm"] == arm, f"{arm} run identity")
        assert_raw(digest(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation hash")
        assert_raw(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"],
                   f"{arm} stable source pins")
        pins = {"input": source, "parent": PARENT_INPUT, "parent_closure": PARENT_CLOSURE,
                "stock_donor": DONOR_INPUT, "stock_donor_closure": DONOR_CLOSURE,
                "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json",
                "builder": HERE / "build.py", "diff_builder": HERE / "describe_diff.py",
                "checker": HERE / "check_roundtrip.py", "runner": HERE / "run_native_ssh.ps1",
                "python": PYTHON, "exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY}
        for key, path in pins.items():
            assert_raw(digest(path) == closure["source_hashes_before"][key], f"{arm} source pin {key}")
        assert_raw(len(closure["raw"]) == 12, f"{arm} twelve raw seals")
        for name, seal in closure["raw"].items():
            path = run / name
            assert_raw(path.exists() and path.stat().st_size == seal["bytes"], f"{arm} raw bytes {name}")
            assert_raw(digest(path) == seal["sha256"], f"{arm} raw digest {name}")
        assert_raw(digest(run / "input.json") == digest(source), f"{arm} native input equals frozen source")
        assert_raw(invocation["execution_mode"] == "session0_ssh_cli" and invocation["session_id"] == 0 and
                   "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]], f"{arm} SSH session zero")
        assert_raw(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
                   invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
                   f"{arm} mutex and GUI preservation")
        assert_raw([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"],
                   f"{arm} five native steps")
        for step in steps:
            assert_raw(step["exit_code"] == 0 and step["status"] in ("completed", "calc_observed") and
                       step["gui_preserved"] is True, f"{arm} step {step['name']}")
        exported = table_map(run / "roundtrip-raw.json", "model")
        populated = [name for name,t in model.items() if any(inst["rows"] for inst in t["instances"])]
        assert_raw(len(populated) == 20 and set(exported) >= set(model), f"{arm} twenty populated source tables")
        for name in populated:
            assert_raw(model[name]["columns"] == exported[name]["columns"] and
                       model[name]["instances"] == exported[name]["instances"], f"{arm} native roundtrip {name}")
        run_log = (run / "run.log").read_text(encoding="utf-8-sig")
        assert_raw("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in run_log and
                   "warning #108" in run_log and "Saving results" in run_log and
                   "error #" not in run_log.lower(), f"{arm} converter and runtime diagnostics")
        assert_raw((run / "model.sxo").stat().st_size > 4, f"{arm} usable SXO")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        assert_raw("random failure added" not in log and "Backorder added" not in log and
                   "mission aborted" not in log and "mission cancelled" not in log,
                   f"{arm} no failure, shortage or lost mission")
        removed = [int(x) for x in re.findall(r"Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>.*?1 PM tasks:", log)]
        taken = [int(x) for x in re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock", log)]
        returned = [int(x) for x in re.findall(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock", log)]
        expected = ([0,1,0], [1,0,1], [0,1,0]) if arm == "monitored" else ([1,2,3], [0,1,2], [1,2,3])
        assert_raw((removed,taken,returned) == expected, f"{arm} three physical item identity cycles")
        for i, (return_hour, pm_end, overhaul_end) in enumerate(((10,10.5,11.25),(22,22.5,23.25),(34,34.5,35.25))):
            start = return_hour-2
            assert_raw(f"Time: {start} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission starting" in log and
                       f"Time: {return_hour} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission success" in log,
                       f"{arm} mission {i} success")
            assert_raw(f"Time: {return_hour}  system PM task {2*i} on <TEACH-AIR-01,0> started" in log and
                       f"Time: {return_hour}  system PM task {2*i} on <TEACH-AIR-01,0> PMID: LRU-OP2" in log and
                       f"Time: {pm_end}  system PM task {2*i} on <TEACH-AIR-01,0> completed" in log,
                       f"{arm} scheduled system swap PM {i}")
            assert_raw(f"Time: {return_hour+.25}  item PM task {2*i+1} on <TEACH-LRU-01,0,{removed[i]}> started" in log and
                       f"Time: {overhaul_end}  item PM task {2*i+1} on <TEACH-LRU-01,0,{removed[i]}> completed" in log and
                       f"Time: {overhaul_end} <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{returned[i]}> to stock" in log,
                       f"{arm} same removed item overhauled and restocked {i}")
            assert_raw(f"Time: {return_hour} <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,{taken[i]}> from stock" in log and
                       f"Time: {pm_end} <TEACH-AIR-01,BASE-01,0> System ready" in log,
                       f"{arm} spare issue and aircraft readiness {i}")
        report = table_map(run / "report-raw.json", "report")
        assert_raw({"ResultSummary","SystemResults","StockTotalResults"} <= set(report), f"{arm} report table set")
        sys, stock = records(report["SystemResults"]), records(report["StockTotalResults"])
        summary = records(report["ResultSummary"])[0]
        assert_raw(len(sys) == len(stock) == 72, f"{arm} 72 report bins")
        for i, (s,t) in enumerate(zip(sys,stock)):
            h = i/2
            assert_raw(near(s["STINT"],h) and near(s["ETINT"],h+.5) and
                       near(t["STINT"],h) and near(t["ETINT"],h+.5), f"{arm} half-hour bin {i}")
            flight = int(any(a<=h<b for a,b in ((8,10),(20,22),(32,34))))
            pm = int(h in (10,22,34))
            ready = int(not any(a<=h<b for a,b in ((7,10.5),(19,22.5),(31,34.5))))
            assert_raw(near(s["NSYMO"],flight) and near(s["FTMO"],flight) and
                       near(s["NSYRY"],ready) and near(s["NSYPM"],pm), f"{arm} flight/ready/PM bin {i}")
            assert_raw(near(s["NPMS"],pm) and near(s["NPMT"],int(h in (10.5,22.5,34.5))) and
                       near(s["NFAIL"],0) and near(s["NSYRP"],0), f"{arm} PM markers/no repair bin {i}")
            assert_raw(near(t["NBO"],0) and near(t["PNB"],1) and near(t["NDF"],0),
                       f"{arm} no stock backorder or damage bin {i}")
        assert_raw(summary["NREP"] == 1 and near(summary["RTIUP"],36) and near(summary["MSUF"],1) and
                   near(summary["MTMF"],1), f"{arm} summary all missions succeed")
        assert_raw(near(sum(float(s["FTMO"] or 0)*.5 for s in sys),6) and
                   near(sum(float(s["NSYPM"] or 0)*.5 for s in sys),1.5) and
                   near(sys[-1]["NSYRY"],1) and near(stock[-1]["NBO"],0),
                   f"{arm} integrated flight/PM hours and terminal ready")
        reports[arm] = report
        evidence[arm] = {"input_sha256":digest(source),"closure_sha256":digest(run/"closure.json"),
                         "model_log_sha256":digest(run/"model.log"),"report_sha256":digest(run/"report-raw.json"),
                         "removed_item_ids":removed,"issued_item_ids":taken,"restocked_item_ids":returned,
                         "summary":summary}
    assert_raw(all(reports["monitored"][name] == reports["system-converted"][name]
                   for name in ("ResultSummary","SystemResults","StockTotalResults")),
               "equal summary/System/Stock tables despite different physical IDs")
    result = {"schema":"simlox-independent-readonly-d14-var01-v101/v1","passed":not FAIL,
              "verdict":"GO: bounded MONIT identity-retention versus observed recreation" if not FAIL else
                        "NO-GO: independent replay failed", "checks_passed":N-len(FAIL),"checks_total":N,
              "failures":FAIL,"evidence":evidence,
              "finding":"Under matched scheduled PM and one spare, MONIT=Y alternates the same two physical item IDs 0/1 through three exchanges and returns each removed item after one-hour overhaul. MONIT=N logs removed item IDs 1/2/3 across the three exchanges, while issued spares are IDs 0/1/2; thus individual installed identity is not retained in the same way. Both arms complete PM system work in 0.5 hour and item overhaul in 1 hour at h10/22/34, succeed in all three missions, and have identical aggregate result ledgers.",
              "limits":["The native events establish the observed physical ID sequences; they do not expose a PM counter-age field or prove its reset/persistence mechanism.",
                        "One zero-prelife item, one spare, one seed, OPHOURS=2, scheduled replacement and 36-hour horizon.",
                        "The earlier v1.0.0 missing-PMReplacement diagnostic is excluded; no other initial-age, multiple-counter, GUI-only or cross-engine claim."]}
    OUTPUT.write_bytes((json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"checks_total":N,"failures":FAIL,
                      "verdict":result["verdict"],"output":str(OUTPUT)},ensure_ascii=False))
    return 0 if not FAIL else 1


if __name__ == "__main__":
    raise SystemExit(main())
