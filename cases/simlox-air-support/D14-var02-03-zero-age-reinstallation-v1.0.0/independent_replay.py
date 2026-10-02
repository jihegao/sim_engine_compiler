"""Independent read-only replay of the sealed D14.var02/03 MONIT pair."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "D14-var01-monitored-item-pm-v1.0.1"
PARENT_SOURCES = {a: PARENT / f"native-input-{a}.json" for a in ("monitored", "system-converted")}
PARENT_CLOSURES = {a: PARENT / "runs" / f"d14-var01-{a}-v101-ssh-20261002-01" / "closure.json"
                   for a in PARENT_SOURCES}
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
ARMS = ("monitored", "system-converted")
RUNS = {a: CASE / "runs" / f"d14-var02-03-{a}-v100-ssh-20261002-01" for a in ARMS}
OUT = CASE / "independent-verdict.json"
CHECKS = 0
FAILURES = []


def check(value, label):
    global CHECKS
    CHECKS += 1
    if not value:
        FAILURES.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(path, top):
    return {t["name"]: t for t in read(path)[top]["tables"]}


def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for ins in table["instances"] for row in ins["rows"]]


def near(x, y):
    return math.isclose(float(x or 0), float(y), abs_tol=1e-6, rel_tol=0)


def main():
    contract, diff = read(CASE / "contract.json"), read(CASE / "exact-diff.json")
    check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen exact diff SHA")
    check(sha(MANUAL) == contract["source"]["manual_sha256"], "manual SHA")
    check(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "dictionary SHA")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "installed CLI SHA")
    model_maps = {}
    for arm in ARMS:
        parent_pin = contract["accepted_parent"]["inputs"][arm]
        check(sha(PARENT_SOURCES[arm]) == parent_pin["sha256"] == diff["parents"][arm]["input_sha256"],
              f"{arm} accepted parent source")
        check(sha(PARENT_CLOSURES[arm]) == parent_pin["native_closure_sha256"], f"{arm} accepted closure")
        src = CASE / f"native-input-{arm}.json"
        check(sha(src) == contract["inputs"][arm]["sha256"] == diff["inputs"][arm], f"{arm} child SHA")
        old, new = tables(PARENT_SOURCES[arm], "model"), tables(src, "model")
        check(set(old) == set(new), f"{arm} same source table topology")
        delta = {name: {"before": old[name], "after": new[name]} for name in old if old[name] != new[name]}
        check(delta == diff["parents"][arm]["changed"] and
              set(delta) == {"MaterielPM", "PMLocation", "PMReplacement", "ProblemDescription"},
              f"{arm} exact accepted-parent delta")
        pm = records(new["MaterielPM"])
        check(len(pm) == 2 and {(r["PMID"], r["MID"], r["PMINT"], r["MNOCC"]) for r in pm} ==
              {("SYS-SWAP", "TEACH-AIR-01", 2, 1), ("LRU-OP3", "TEACH-LRU-01", 3, None)},
              f"{arm} separate capped system and item PM")
        check(next(r["MONIT"] for r in pm if r["PMID"] == "LRU-OP3") == contract["inputs"][arm]["MONIT"] and
              len(records(new["PMReplacement"])) == 2 and
              records(new["StockAllocation"])[0]["STSIZ"] == 1,
              f"{arm} MONIT, scheduled replacement and one spare")
        check("Prelife" not in new or len(records(new["Prelife"])) == 0, f"{arm} no authored prelife")
        model_maps[arm] = (src, new)
    pair = {name: {"before": model_maps["monitored"][1][name],
                   "after": model_maps["system-converted"][1][name]}
            for name in model_maps["monitored"][1]
            if model_maps["monitored"][1][name] != model_maps["system-converted"][1][name]}
    check(pair == diff["arm_contrast"] and set(pair) == {"MaterielPM", "ProblemDescription"},
          "MONIT-only behavioral pair contrast")

    proof = {}
    for arm in ARMS:
        run, (src, model) = RUNS[arm], model_maps[arm]
        closure, invocation, steps = [read(run / name) for name in ("closure.json", "invocation.json", "steps.json")]
        check(closure["run_id"] == invocation["run_id"] == run.name and
              closure["arm"] == invocation["arm"] == arm, f"{arm} run identity")
        check(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation seal")
        check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"],
              f"{arm} source hashes stable")
        files = {"input": src, "parent_y": PARENT_SOURCES["monitored"],
                 "parent_y_closure": PARENT_CLOSURES["monitored"],
                 "parent_n": PARENT_SOURCES["system-converted"],
                 "parent_n_closure": PARENT_CLOSURES["system-converted"],
                 "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
                 "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
                 "checker": CASE / "check_roundtrip.py", "runner": CASE / "run_native_ssh.ps1",
                 "python": PYTHON, "exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY}
        for key, path in files.items():
            check(sha(path) == closure["source_hashes_before"][key], f"{arm} source seal {key}")
        check(len(closure["raw"]) == 12, f"{arm} twelve raw seals")
        for name, seal in closure["raw"].items():
            path = run / name
            check(path.exists() and path.stat().st_size == seal["bytes"], f"{arm} raw size {name}")
            check(sha(path) == seal["sha256"], f"{arm} raw SHA {name}")
        check(sha(run / "input.json") == sha(src), f"{arm} raw copied source")
        check(invocation["execution_mode"] == "session0_ssh_cli" and invocation["session_id"] == 0 and
              "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]], f"{arm} session-zero SSH")
        check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
              invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
              f"{arm} mutex and preserved GUI")
        check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"],
              f"{arm} five native steps")
        for step in steps:
            check(step["exit_code"] == 0 and step["status"] in ("completed", "calc_observed") and
                  step["gui_preserved"] is True, f"{arm} step {step['name']}")
        exported = tables(run / "roundtrip-raw.json", "model")
        populated = [name for name,t in model.items() if any(ins["rows"] for ins in t["instances"])]
        check(len(populated) == 20 and set(exported) >= set(model), f"{arm} 20 populated source tables")
        for name in populated:
            check(model[name]["columns"] == exported[name]["columns"] and
                  model[name]["instances"] == exported[name]["instances"], f"{arm} exact roundtrip {name}")
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
              "warning #108" in runlog and "Saving results" in runlog and
              "warning #243" not in runlog and "error #" not in runlog.lower(),
              f"{arm} clean conversion/runtime except 108")
        check((run / "model.sxo").stat().st_size > 4, f"{arm} valid SXO")
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        expected_pm = [(10, "SYS-SWAP", 0)] + ([(34,"LRU-OP3",2)] if arm == "monitored" else [(22,"LRU-OP3",2)])
        actual_pm = [(float(h), pid, int(task)) for h,task,pid in re.findall(
            r"Time: ([0-9.]+)  system PM task (\d+) on <TEACH-AIR-01,0> PMID: ([A-Z0-9-]+)", log)]
        check(actual_pm == expected_pm, f"{arm} system PM identities and timing")
        removed = [int(x) for x in re.findall(r"Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>.*?1 PM tasks:",log)]
        taken = [int(x) for x in re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock",log)]
        restored = [int(x) for x in re.findall(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock",log)]
        ids = ([0,1],[1,0],[0,1]) if arm == "monitored" else ([1,2],[0,1],[1,2])
        check((removed,taken,restored) == ids, f"{arm} exact physical item exchange identities")
        pm_hours = [10, 34] if arm == "monitored" else [10,22]
        for i,(h, removed_id, spare_id) in enumerate(zip(pm_hours,removed,taken)):
            sys_task = 2*i
            item_task = sys_task+1
            check(f"Time: {h}  system PM task {sys_task} on <TEACH-AIR-01,0> started" in log and
                  f"Time: {h+.5}  system PM task {sys_task} on <TEACH-AIR-01,0> completed" in log and
                  f"Time: {h+.5} <TEACH-AIR-01,BASE-01,0> System ready" in log,
                  f"{arm} 0.5-hour system swap {i}")
            check(f"Time: {h} <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,{spare_id}> from stock" in log and
                  f"Time: {h+.25} <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,{removed_id}>" in log,
                  f"{arm} stocked spare replaces removed physical item {i}")
            check(f"Time: {h+.25}  item PM task {item_task} on <TEACH-LRU-01,0,{removed_id}> started" in log and
                  f"Time: {h+1.25}  item PM task {item_task} on <TEACH-LRU-01,0,{removed_id}> completed" in log and
                  f"Time: {h+1.25} <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{removed_id}> to stock" in log,
                  f"{arm} one-hour overhaul and same-item stock return {i}")
        for i,start in enumerate((8,20,32)):
            check(f"Time: {start} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission starting" in log and
                  f"Time: {start+2} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission success" in log,
                  f"{arm} successful mission {i}")
        check([float(x) for x in re.findall(r"Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission starting", log)]
              == [8,20,32], f"{arm} no post-h34 sortie to test reinstalled item")
        check("failure added" not in log and "mission aborted" not in log and
              "Backorder added" not in log and "mission cancelled" not in log,
              f"{arm} no failure/abort/backorder confound")
        report = tables(run / "report-raw.json", "report")
        check({"ResultSummary","SystemResults","StockTotalResults"} <= set(report), f"{arm} report tables")
        sy, st = records(report["SystemResults"]), records(report["StockTotalResults"])
        summary = records(report["ResultSummary"])[0]
        check(len(sy) == len(st) == 72, f"{arm} 72 System/Stock bins")
        for idx,(s,t) in enumerate(zip(sy,st)):
            h=idx/2
            check(near(s["STINT"],h) and near(s["ETINT"],h+.5) and
                  near(t["STINT"],h) and near(t["ETINT"],h+.5), f"{arm} report interval {idx}")
            flying = int(any(a<=h<b for a,b in ((8,10),(20,22),(32,34))))
            pm = int(h in pm_hours)
            ready = int(not any(a<=h<b for a,b in [(7,10.5),(19,22),(31,34)] + [(a,a+.5) for a in pm_hours if a!=10]))
            # The h22 or h34 PM starts after mission return; ready intervals resume at +0.5.
            check(near(s["NSYMO"],flying) and near(s["FTMO"],flying) and
                  near(s["NSYPM"],pm) and near(s["NSYRY"],ready), f"{arm} mission/PM/ready bin {idx}")
            marker = int(h == 10 or h == (33 if arm=="monitored" else 21))
            check(near(s["NPMS"],marker) and near(s["NPMT"],int(h in [a+.5 for a in pm_hours])) and
                  near(s["NFAIL"],0) and near(s["NSYRP"],0), f"{arm} PM marker versus work bin {idx}")
            check(near(t["NBO"],0) and near(t["PNB"],1) and near(t["NDF"],0),
                  f"{arm} zero stock shortage/damage bin {idx}")
        check(summary["NREP"] == 1 and near(summary["RTIUP"],36) and
              near(summary["MSUF"],1) and near(summary["MTMF"],1), f"{arm} summary")
        check(near(sum(float(s["FTMO"] or 0)*.5 for s in sy),6) and
              near(sum(float(s["NSYPM"] or 0)*.5 for s in sy),1) and
              near(sy[-1]["NSYRY"],1) and near(st[-1]["NBO"],0),
              f"{arm} six flight hours, one system PM work hour, terminal ready")
        proof[arm]={"input_sha256":sha(src),"closure_sha256":sha(run/"closure.json"),
                    "model_log_sha256":sha(run/"model.log"),"report_sha256":sha(run/"report-raw.json"),
                    "pm_events":actual_pm,"removed_item_ids":removed,"spare_item_ids":taken,
                    "returned_item_ids":restored,"summary":summary}
    result={"schema":"simlox-independent-readonly-d14-var02-03/v1", "passed":not FAILURES,
            "verdict":"GO: bounded var02 timing; RESTRICTED var03 physical reinstallation only" if not FAILURES else
                      "NO-GO: independent replay failure", "checks_passed":CHECKS-len(FAILURES),
            "checks_total":CHECKS,"failures":FAILURES,"evidence":proof,
            "finding":"Both arms perform one-time SYS-SWAP after the first h8–10 mission, replacing the installed item with a stocked spare and returning the removed physical item after one-hour overhaul. MONIT=Y next starts LRU-OP3 at h34 on the same former spare ID1 after its second and third two-hour sorties, while MONIT=N starts LRU-OP3 at h22 on successor ID2. All three missions succeed and both arms finish with one ready aircraft and no backorder.",
            "interpretation_limit":"The timing and native item IDs support a bounded zero-initial-age/individual-monitoring interpretation, but no per-item PM counter age is directly reported. NPMS marks the item-PM threshold bin at h33 or h21, ahead of actual task work at h34 or h22.",
            "catalog_scope":{"D14.var02":"GO only for the observed MONIT Y/N timing contrast with zero authored prelife: after the h10 SYS-SWAP, LRU-OP3 appears at h34 versus h22.",
                             "D14.var03":"RESTRICTED GO for the observed physical reinstallation of overhauled original item ID0 at h34 in the monitored arm. Full retained-counter behavior after reinstallation is untested: no subsequent mission occurs before the h36 horizon. A later mission and PM observation with a frozen prediction is needed for full var03 acceptance."},
            "limits":["One aircraft, one stocked item, one seed, one SYS-SWAP occurrence, OPHOURS intervals 2/3, and 36-hour horizon.",
                      "Only observed physical item identity and PM timing are accepted; no general reset, prelife, or counter progression law.",
                      "No GUI-only or cross-engine parity claim."]}
    OUT.write_bytes((json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"checks_total":CHECKS,"failures":FAILURES,
                      "verdict":result["verdict"],"output":str(OUT)},ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
