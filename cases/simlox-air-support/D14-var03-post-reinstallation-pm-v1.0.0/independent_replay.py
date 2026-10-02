"""Independent standard-library replay of D14.var03 post-reinstallation evidence.

Reads sealed sources and raw native outputs only; never calls author code or SIMLOX.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "D14-var02-03-zero-age-reinstallation-v1.0.0"
ARMS = ("monitored", "system-converted")
PARENT_INPUT = {a: PARENT / f"native-input-{a}.json" for a in ARMS}
PARENT_CLOSURE = {a: PARENT / "runs" / f"d14-var02-03-{a}-v100-ssh-20261002-01" / "closure.json" for a in ARMS}
RUNS = {a: CASE / "runs" / f"d14-var03-post-reinstall-{a}-v100-ssh-20261002-01" for a in ARMS}
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICT = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
OUT = CASE / "independent-verdict.json"
TOTAL = 0
FAILURES = []


def check(ok, label):
    global TOTAL
    TOTAL += 1
    if not ok:
        FAILURES.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(path, root):
    return {t["name"]:t for t in load(path)[root]["tables"]}


def rows(table):
    keys = [c["name"] for c in table["columns"]]
    return [dict(zip(keys,r)) for i in table["instances"] for r in i["rows"]]


def close(x,y):
    return math.isclose(float(x or 0),float(y),abs_tol=1e-6,rel_tol=0)


def main():
    contract, diff = load(CASE/"contract.json"), load(CASE/"exact-diff.json")
    check(sha(CASE/"exact-diff.json") == contract["exact_diff_sha256"],"exact diff fingerprint")
    check(sha(MANUAL) == contract["source"]["manual_sha256"],"manual fingerprint")
    check(sha(DICT) == contract["source"]["dictionary_sha256"],"dictionary fingerprint")
    check(sha(EXE) == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "installed CLI fingerprint")
    models = {}
    for arm in ARMS:
        parent_pin = contract["accepted_parent"]["inputs"][arm]
        check(sha(PARENT_INPUT[arm]) == parent_pin["sha256"] == diff["parents"][arm]["input_sha256"],f"{arm} parent source")
        check(sha(PARENT_CLOSURE[arm]) == parent_pin["native_closure_sha256"],f"{arm} accepted parent run closure")
        src = CASE/f"native-input-{arm}.json"
        check(sha(src) == contract["inputs"][arm]["sha256"] == diff["inputs"][arm],f"{arm} child source")
        before, after = tables(PARENT_INPUT[arm],"model"), tables(src,"model")
        check(set(before)==set(after),f"{arm} table names unchanged")
        actual_delta = {n:{"before":before[n],"after":after[n]} for n in before if before[n]!=after[n]}
        check(actual_delta == diff["parents"][arm]["changed"] and
              set(actual_delta)=={"Control","OperationProfile","ProblemDescription","ResultCollection"},
              f"{arm} exact four-table 36 to 48 hour source delta")
        control = rows(after["Control"])[0]
        schedule = rows(after["OperationProfile"])
        collections = rows(after["ResultCollection"])
        check(control["SIMPE"]==48 and control["RCEND"]==48 and control["RSEED"]=="1" and
              [r["STIM"] for r in schedule]==[8,20,32,44] and all(r["RCEND"]==48 for r in collections),
              f"{arm} four sorties and 48h report horizon")
        pm = {r["PMID"]:r for r in rows(after["MaterielPM"])}
        check(pm["SYS-SWAP"]["PMINT"]==2 and pm["SYS-SWAP"]["MNOCC"]==1 and
              pm["LRU-OP3"]["PMINT"]==3 and pm["LRU-OP3"]["MONIT"]==contract["inputs"][arm]["MONIT"],
              f"{arm} distinct PMIDs and one-time system swap")
        check("Prelife" not in after or not rows(after["Prelife"]),f"{arm} no authored prelife")
        models[arm] = (src, after)
    pair = {n:{"before":models["monitored"][1][n],"after":models["system-converted"][1][n]}
            for n in models["monitored"][1] if models["monitored"][1][n]!=models["system-converted"][1][n]}
    check(pair==diff["arm_contrast"] and set(pair)=={"MaterielPM","ProblemDescription"},
          "MONIT alone is behavioral arm discriminator")

    evidence={}
    for arm in ARMS:
        src, model = models[arm]
        run=RUNS[arm]
        closure, invocation, steps = [load(run/name) for name in ("closure.json","invocation.json","steps.json")]
        check(closure["run_id"]==invocation["run_id"]==run.name and
              closure["arm"]==invocation["arm"]==arm, f"{arm} run identity")
        check(sha(run/"invocation.json")==closure["invocation_sha256"],f"{arm} invocation SHA")
        check(invocation["source_hashes_before"]==closure["source_hashes_before"]==closure["source_hashes_after"],
              f"{arm} stable pre/post source seals")
        paths={"input":src,"parent_y":PARENT_INPUT["monitored"],
               "parent_y_closure":PARENT_CLOSURE["monitored"],
               "parent_n":PARENT_INPUT["system-converted"],
               "parent_n_closure":PARENT_CLOSURE["system-converted"],
               "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
               "builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py",
               "checker":CASE/"check_roundtrip.py","runner":CASE/"run_native_ssh.ps1",
               "python":PYTHON,"exe":EXE,"manual":MANUAL,"dictionary":DICT}
        for key,path in paths.items():
            check(sha(path)==closure["source_hashes_before"][key],f"{arm} source SHA {key}")
        check(len(closure["raw"])==12,f"{arm} twelve raw seals")
        for name,seal in closure["raw"].items():
            path=run/name
            check(path.exists() and path.stat().st_size==seal["bytes"],f"{arm} raw bytes {name}")
            check(sha(path)==seal["sha256"],f"{arm} raw SHA {name}")
        check(sha(run/"input.json")==sha(src),f"{arm} raw input equals source")
        check(invocation["execution_mode"]=="session0_ssh_cli" and invocation["session_id"]==0 and
              "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]],f"{arm} SSH0 provenance")
        check(invocation["queue_mutex"]=="Global\\SimloxIssue18NativeQueue" and
              invocation["gui"]["pid"]==13340 and invocation["gui"]["session_id"]==1,
              f"{arm} mutex and GUI")
        check([s["name"] for s in steps]==["import","export","calc","jsonreport","check_import_export"],
              f"{arm} five steps")
        for s in steps:
            check(s["exit_code"]==0 and s["status"] in ("completed","calc_observed") and
                  s["gui_preserved"] is True,f"{arm} step {s['name']}")
        exported=tables(run/"roundtrip-raw.json","model")
        populated=[n for n,t in model.items() if any(i["rows"] for i in t["instances"])]
        check(len(populated)==20 and set(exported)>=set(model),f"{arm} 20 row-containing source tables")
        for name in populated:
            check(exported[name]["columns"]==model[name]["columns"] and
                  exported[name]["instances"]==model[name]["instances"],f"{arm} exact native table {name}")
        runlog=(run/"run.log").read_text(encoding="utf-8-sig",errors="replace")
        check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
              "warning #108" in runlog and "Saving results" in runlog and
              "warning #243" not in runlog and "error #" not in runlog.lower(),
              f"{arm} conversion/runtime clean except #108")
        check((run/"model.sxo").stat().st_size>4,f"{arm} usable native results")
        event=(run/"model.log").read_text(encoding="utf-8-sig",errors="replace")
        pm=[(float(h),int(k),pid) for h,k,pid in re.findall(
            r"Time: ([0-9.]+)  system PM task (\d+) on <TEACH-AIR-01,0> PMID: ([A-Z0-9-]+)",event)]
        expected=[(10,0,"SYS-SWAP"),(34,2,"LRU-OP3"),(46,4,"LRU-OP3")] if arm=="monitored" else \
                 [(10,0,"SYS-SWAP"),(22,2,"LRU-OP3"),(46,4,"LRU-OP3")]
        check(pm==expected,f"{arm} PMID-specific PM event sequence")
        removed=[int(x) for x in re.findall(r"Item requiring maintenance arrives <TEACH-LRU-01,0,(\d+)>.*?1 PM tasks:",event)]
        issued=[int(x) for x in re.findall(r"Take replacement item <TEACH-LRU-01,0,(\d+)> from stock",event)]
        restocked=[int(x) for x in re.findall(r"Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock",event)]
        expect_ids=([0,1,0],[1,0,1],[0,1,0]) if arm=="monitored" else ([1,2,3],[0,1,2],[1,2,3])
        check((removed,issued,restocked)==expect_ids,f"{arm} exact item issue/removal/return identities")
        for j,(hour,task,pid) in enumerate(expected):
            check(f"Time: {hour}  system PM task {task} on <TEACH-AIR-01,0> started" in event and
                  f"Time: {hour+.5}  system PM task {task} on <TEACH-AIR-01,0> completed" in event and
                  f"Time: {hour+.5} <TEACH-AIR-01,BASE-01,0> System ready" in event,
                  f"{arm} positive half-hour system swap {j}")
            check(f"Time: {hour} <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,{issued[j]}> from stock" in event and
                  f"Time: {hour+.25} <TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,{removed[j]}>" in event,
                  f"{arm} physical item exchange {j}")
            check(f"Time: {hour+.25}  item PM task {task+1} on <TEACH-LRU-01,0,{removed[j]}> started" in event and
                  f"Time: {hour+1.25}  item PM task {task+1} on <TEACH-LRU-01,0,{removed[j]}> completed" in event and
                  f"Time: {hour+1.25} <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{removed[j]}> to stock" in event,
                  f"{arm} distinct item overhaul and physical return {j}")
        starts=[float(x) for x in re.findall(r"Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,\d+> mission starting",event)]
        check(starts==[8,20,32,44],f"{arm} exact four launch times")
        for i,h in enumerate(starts):
            check(f"Time: {int(h+2)} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission success" in event and
                  f"Time: {int(h+2)} <BASIC-MISSION,TEACH-UNIT,0,0,{i}> mission completed" in event,
                  f"{arm} successful mission {i}")
        check("failure added" not in event and "mission aborted" not in event and
              "Backorder added" not in event and "mission cancelled" not in event,
              f"{arm} no failure/abort/shortage confound")
        report=tables(run/"report-raw.json","report")
        check({"ResultSummary","SystemResults","StockTotalResults"}<=set(report),f"{arm} report tables")
        sy,st=[rows(report[n]) for n in ("SystemResults","StockTotalResults")]
        summary=rows(report["ResultSummary"])[0]
        check(len(sy)==len(st)==96,f"{arm} 96 System and Stock bins")
        work=[h for h,_,_ in expected]
        marker=[10,33,45] if arm=="monitored" else [10,21,45]
        for i,(s,t) in enumerate(zip(sy,st)):
            h=i/2
            check(close(s["STINT"],h) and close(s["ETINT"],h+.5) and
                  close(t["STINT"],h) and close(t["ETINT"],h+.5),f"{arm} half-hour interval {i}")
            flight=int(any(a<=h<a+2 for a in starts))
            unavailable=int(any(a<=h<a+.5 for a in work))
            engaged=int(any(a-1<=h<a+.5 for a in work) or any(a-1<=h<a+2 for a in starts))
            # Availability follows mission preparation from h7,19,31,43 and PM work.
            ready=int(not any(a-1<=h<a+2 for a in starts) and not unavailable)
            check(close(s["NSYMO"],flight) and close(s["FTMO"],flight) and
                  close(s["NSYPM"],int(h in work)) and close(s["NSYRY"],ready),
                  f"{arm} flight/PM/ready ledger {i}")
            check(close(s["NPMS"],int(h in marker)) and
                  close(s["NPMT"],int(h in [a+.5 for a in work])) and
                  close(s["NFAIL"],0) and close(s["NSYRP"],0),
                  f"{arm} PM threshold versus work marker {i}")
            check(close(t["NBO"],0) and close(t["PNB"],1) and close(t["NDF"],0),
                  f"{arm} no backorder/damage ledger {i}")
        check(summary["NREP"]==1 and close(summary["RTIUP"],48) and
              close(summary["MSUF"],1) and close(summary["MTMF"],1),f"{arm} summary")
        check(close(sum(float(s["FTMO"] or 0)*.5 for s in sy),8) and
              close(sum(float(s["NSYPM"] or 0)*.5 for s in sy),1.5) and
              close(sy[-1]["NSYRY"],1) and close(st[-1]["NBO"],0),
              f"{arm} integrated eight flight and 1.5 PM hours; terminal ready")
        evidence[arm]={"input_sha256":sha(src),"closure_sha256":sha(run/"closure.json"),
                       "model_log_sha256":sha(run/"model.log"),"report_sha256":sha(run/"report-raw.json"),
                       "pm_events":pm,"removed_item_ids":removed,"issued_item_ids":issued,
                       "returned_item_ids":restocked,"summary":summary}
    result={"schema":"simlox-independent-readonly-d14-var03-post-reinstallation/v1",
            "passed":not FAILURES,
            "verdict":"GO: bounded post-reinstallation LRU-OP3 recurrence on physical ID0" if not FAILURES else
                      "NO-GO: independent replay failure", "checks_passed":TOTAL-len(FAILURES),
            "checks_total":TOTAL,"failures":FAILURES,"evidence":evidence,
            "finding":"In MONIT=Y, original item ID0 is removed at h10 for distinct-PMID SYS-SWAP, overhauled and stocked h11.25, then physically reinstalled h34. It operates in the h44–46 mission and is removed by LRU-OP3 at h46. The monitored former spare ID1 first receives LRU-OP3 at h34. In MONIT=N, the system-converted LRU-OP3 occurs at h22 and again h46 on successive IDs. All four missions succeed in both arms.",
            "interpretation_limit":"The h46 MONIT=Y LRU-OP3 on reinstalled physical ID0 supports bounded persistence of the distinct LRU-OP3 eligibility across SYS-SWAP removal and item overhaul in this exact model. The log does not report a numeric per-item counter, so the value/reset mechanism is inferred from frozen source and event timing, not directly measured. NPMS marks h45 before h46 task work.",
            "limits":["One aircraft, one stocked item, one seed, one SYS-SWAP and one post-reinstallation mission; no general age/counter law.",
                      "SYS-SWAP includes different-PMID item overhaul, so the result does not isolate all effects of maintenance on every counter.",
                      "No GUI-only or cross-engine parity claim."]}
    OUT.write_bytes((json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"checks_total":TOTAL,"failures":FAILURES,
                      "verdict":result["verdict"],"output":str(OUT)},ensure_ascii=False))
    return 0 if not FAILURES else 1


if __name__=="__main__":
    raise SystemExit(main())
