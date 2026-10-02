"""Independent read-only replay for G11.var11 stock PrelifeData row order."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

CASE=Path(__file__).resolve().parent
PARENT=CASE.parent/"G11-var04-inherit-item-prelife-v1.0.1"
PARENT_INPUT=PARENT/"native-input-explicit-control.json"
PARENT_CLOSURE=PARENT/"runs/g11-var04-explicit-control-v101-ssh-20261002-01/closure.json"
MANUAL=Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY=Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE=Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
PYTHON=Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
ARMS={"age10-first":"g11-var11-age10-first-v100-ssh-20261003-01",
      "age70-first":"g11-var11-age70-first-v100-ssh-20261003-01"}
COUNT=0
FAILURES=[]

def ck(ok,label):
    global COUNT
    COUNT+=1
    if not ok: FAILURES.append(label)

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def rd(path): return json.loads(re.sub(r",\s*([}\]])",r"\1",path.read_text(encoding="utf-8-sig")))
def tables(path,root): return {t["name"]:t for t in rd(path)[root]["tables"]}
def rows(table):
    names=[c["name"] for c in table["columns"]]
    return [dict(zip(names,r)) for i in table["instances"] for r in i["rows"]]
def near(a,b,tol=.0001): return isinstance(a,(float,int)) and abs(a-b)<=tol

def report_checks(arm,run):
    report=tables(run/"report-raw.json","report")
    ck(set(report)=={"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},f"{arm}: report tables")
    sy,st=rows(report["SystemResults"]),rows(report["StockTotalResults"])
    ck(len(sy)==len(st)==280,f"{arm}: 280 half-hour bins")
    ck(rows(report["ResultSummary"])==[{"NREP":1,"RTILW":0,"RTIUP":140,"MTMF":0,
        "RSMTMF":0,"MSTF":0,"RSMSTF":0,"MSUF":0,"RSMSUF":0,"STMF":0,"RSSTMF":0}],
       f"{arm}: no-mission summary")
    hours=(80,) if arm=="age10-first" else (80,110.5)
    zero_sy=("NSYMA","NSYMO","NSYMC","NSYMP","NSYMT","NSYMS","NSYMR","NSYAL","FTMO",
             "NSYRP","NSYTP","NSYWR","NSYWI","NSYLA","NSYUH","NREPT","NFAIL","NDAM",
             "NROBT","NRCFG","STREQ","STACC","STF","STLOW","SYDTU","NSYSW","NPSTA","NPSUC")
    for i,(s,k) in enumerate(zip(sy,st)):
        t=i/2
        ck(s["STINT"]==k["STINT"]==t and s["ETINT"]==k["ETINT"]==t+.5,
           f"{arm}: aligned bin {i}")
        active=int(t in hours); tail=int(any(t==h+.5 for h in hours))
        for key,value in {"NSYRY":1-active,"NSYA":1-active,"NSYUA":active,"NSYPM":active}.items():
            ck(near(s[key],value),f"{arm}: SystemResults {key} bin {i}")
        for key,value in {"NPMS":active,"NPMT":tail,"NSYDT":active}.items():
            ck(s[key]==value,f"{arm}: PM marker {key} bin {i}")
        ck(s["SYDT"]==(.5 if active else None),f"{arm}: SYDT bin {i}")
        for key in zero_sy: ck(s[key]==0,f"{arm}: zero SystemResults {key} bin {i}")
        ck(k["PNB"]==1 and k["NDP"]==active and k["NWT"]==active,
           f"{arm}: stock demand/replace bin {i}")
        for key in ("NBO","NDF","NDD","NDR","NLD"):
            ck(k[key]==0,f"{arm}: zero StockTotalResults {key} bin {i}")
        for key in ("NBOU","WTS"): ck(k[key] is None,f"{arm}: null {key} bin {i}")
        for key in ("ROS","ROST","WT","WTT"):
            ck(k[key] in (None,0),f"{arm}: no positive {key} bin {i}")
    ck(near(sum(s["NSYPM"]*.5 for s in sy),.5*len(hours)) and
       near(sum(s["NSYMO"]*.5 for s in sy),0),f"{arm}: PM and flight integral")
    ck(near(sy[-1]["NSYRY"],1) and st[-1]["NBO"]==0,f"{arm}: terminal ready one, no BO")
    return {"report_sha256":sha(run/"report-raw.json"),"system_bins":len(sy),"stock_bins":len(st)}

def main():
    contract,diff=rd(CASE/"contract.json"),rd(CASE/"exact-diff.json")
    ck(sha(PARENT_INPUT)==contract["accepted_parent"]["input_sha256"]==diff["parent_sha256"],"parent source")
    ck(sha(PARENT_CLOSURE)==contract["accepted_parent"]["native_closure_sha256"],"parent closure")
    ck(sha(CASE/"exact-diff.json")==contract["exact_diff_sha256"],"exact diff seal")
    ck(sha(MANUAL)==contract["source"]["manual_sha256"],"manual seal")
    ck(sha(DICTIONARY)==contract["source"]["dictionary_sha256"],"dictionary seal")
    ck(sha(EXE)=="fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0","CLI seal")
    parent=tables(PARENT_INPUT,"model")
    models={}; evidence={}
    for arm,run_id in ARMS.items():
        source=CASE/f"native-input-{arm}.json"; run=CASE/"runs"/run_id
        model=tables(source,"model"); models[arm]=model
        ck(sha(source)==contract["inputs"][arm]["sha256"]==diff["arms"][arm]["input_sha256"],f"{arm}: source seal")
        delta={n:{"before":parent[n],"after":model[n]} for n in parent if parent[n]!=model[n]}
        delta.update({n:{"before":None,"after":model[n]} for n in set(model)-set(parent)})
        ck(delta==diff["arms"][arm]["changed"],f"{arm}: exact parent delta")
        ck(set(parent).issubset(model),f"{arm}: parent table topology")
        ck([r["IQTY"] for r in rows(model["OperationProfile"])]==[0,0,0],f"{arm}: no mission quantities")
        stock=rows(model["StockAllocation"])
        ck(len(stock)==1 and stock[0]["STSIZ"]==2 and stock[0]["PLID"]=="PL-STOCK",
           f"{arm}: two stocked spares with referenced prelife")
        pre=rows(model["PrelifeData"])
        expected=[10,70] if arm=="age10-first" else [70,10]
        ck([(r["PLID"],r["PLIND"],r["QTY"],r["AGE"],r["TYPE"]) for r in pre[-2:]]==
           [("PL-STOCK",f"STOCK-{age}",1,age,"FIXED") for age in expected],
           f"{arm}: two ordered stocked age rows")
        closure,invocation,steps=(rd(run/n) for n in ("closure.json","invocation.json","steps.json"))
        ck(closure["run_id"]==invocation["run_id"]==run_id and closure["arm"]==arm,f"{arm}: run identity")
        ck(sha(run/"invocation.json")==closure["invocation_sha256"],f"{arm}: invocation seal")
        ck(invocation["source_hashes_before"]==closure["source_hashes_before"]==closure["source_hashes_after"],
           f"{arm}: source stability")
        pins={"input":source,"parent":PARENT_INPUT,"parent_closure":PARENT_CLOSURE,
              "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
              "builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py",
              "checker":CASE/"check_roundtrip.py","runner":CASE/"run_native_ssh.ps1",
              "python":PYTHON,"exe":EXE,"manual":MANUAL,"dictionary":DICTIONARY}
        for key,path in pins.items(): ck(sha(path)==closure["source_hashes_before"][key],f"{arm}: source pin {key}")
        ck(len(closure["raw"])==13 and closure["error"] is None,f"{arm}: thirteen raw seals")
        for name,seal in closure["raw"].items():
            path=run/name
            ck(path.exists() and path.stat().st_size==seal["bytes"],f"{arm}: raw size {name}")
            ck(sha(path)==seal["sha256"],f"{arm}: raw SHA {name}")
        ck(sha(run/"input.json")==sha(source),f"{arm}: run input source")
        ck(invocation["execution_mode"]=="session0_ssh_cli" and invocation["session_id"]==0 and
           "sshd.exe" in [x.lower() for x in invocation["ssh_ancestor_names"]],f"{arm}: SSH0")
        ck(invocation["queue_mutex"]=="Global\\SimloxIssue18NativeQueue" and
           invocation["gui"]["pid"]==13340 and invocation["gui"]["session_id"]==1,f"{arm}: mutex and GUI")
        ck(invocation["prelife_log_option_before"]==closure["prelife_log_option_after"]=="NO",
           f"{arm}: Prelife Log option restored")
        ck([s["name"] for s in steps]==["import","export","calc","jsonreport","check_import_export"],
           f"{arm}: five guarded steps")
        for s in steps: ck(s["exit_code"]==0 and s["status"]=="completed" and s["gui_preserved"] is True,
                           f"{arm}: step {s['name']}")
        exported=tables(run/"roundtrip-raw.json","model")
        populated=[n for n,t in model.items() if any(i["rows"] for i in t["instances"])]
        ck(len(populated)==23,f"{arm}: 23 authored row-containing tables")
        for name in populated:
            ck(name in exported and model[name]["columns"]==exported[name]["columns"] and
               model[name]["instances"]==exported[name]["instances"],f"{arm}: roundtrip {name}")
        runlog=(run/"run.log").read_text(encoding="utf-8-sig",errors="replace")
        ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
           re.findall(r"\(warning #(\d+)\)",runlog)==["108"] and "(error #" not in runlog,
           f"{arm}: zero errors/notes, warning108 only")
        ck((run/"model.sxo").stat().st_size>4,f"{arm}: valid SXO")
        prelog=(run/"model_Prelife.log").read_text(encoding="utf-8-sig")
        ages=re.findall(r"\*\*(TEACH-AIR-01|POS-A|TEACH-LRU-01)\*\*"
                        r"(SYS-60|POS-INH|LRU-20|STOCK-10|STOCK-70)\*\* Age\[CALHOURS\]:([0-9.]+)",prelog)
        ck(ages==[("TEACH-AIR-01","SYS-60","60.00"),("POS-A","POS-INH","60.00"),
                  ("TEACH-LRU-01","LRU-20","20.00")]+
           [("TEACH-LRU-01",f"STOCK-{age}",f"{age}.00") for age in expected],
           f"{arm}: installed and stock Prelife ages in source row order")
        log=(run/"model.log").read_text(encoding="utf-8-sig")
        pm=[(float(h),int(a)) for h,a in re.findall(
            r"Time: ([0-9.]+)  system PM task \d+ on <TEACH-AIR-01,(\d+)> PMID: LRU-CAL100",log)]
        ck(pm==([(80.,0)] if arm=="age10-first" else [(80.,0),(110.5,0)]),
           f"{arm}: exact system PM schedule")
        demands=[(float(h),int(item)) for h,item in re.findall(
            r"Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos .*?"
            r"item requiring maintenance is <TEACH-LRU-01,0,(\d+)>",log)]
        ck(demands==([(80.,0)] if arm=="age10-first" else [(80.,0),(110.5,1)]),
           f"{arm}: original and later physical item identities")
        issues=[(float(h),int(item)) for h,item in re.findall(
            r"Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,(\d+)> from stock",log)]
        ck(issues==([(80.,1)] if arm=="age10-first" else [(80.,1),(110.5,2)]),
           f"{arm}: physical spare issue order")
        item_starts=[(float(h),int(item)) for h,item in re.findall(
            r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,(\d+)> started",log)]
        item_ends=[(float(h),int(item)) for h,item in re.findall(
            r"Time: ([0-9.]+)  item PM task \d+ on <TEACH-LRU-01,0,(\d+)> completed",log)]
        ck(item_starts==[(h+.25,item) for h,item in demands] and
           item_ends==[(h+1.25,item) for h,item in demands],f"{arm}: one-hour item PMs")
        returned=[(float(h),int(item)) for h,item in re.findall(
            r"Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock",log)]
        ck(returned==item_ends,f"{arm}: repaired items return to stock")
        ck("Stock initiated" in log and "Level: 2 Items:<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,2>" in log and
           log.count("Level: 1 Items:")==len(pm) and log.count("Level: 2 Items:")==len(pm)+1,
           f"{arm}: two initial spares, each issue/return physical stock level")
        ck("mission starting" not in log and "mission ordered" not in log and
           "books resources" not in log and "failure occurs" not in log,
           f"{arm}: no mission/resource/failure")
        rep=report_checks(arm,run)
        evidence[arm]={"input_sha256":sha(source),"closure_sha256":sha(run/"closure.json"),
                       "model_log_sha256":sha(run/"model.log"),
                       "prelife_log_sha256":sha(run/"model_Prelife.log"),**rep}
    a,b=models["age10-first"],models["age70-first"]
    contrast={n:{"before":a.get(n),"after":b.get(n)} for n in set(a)|set(b) if a.get(n)!=b.get(n)}
    ck(contrast==diff["arm_contrast"] and set(contrast)=={"PrelifeData","ProblemDescription"},
       "pair changes only PrelifeData order and description")
    ar,br=rows(a["PrelifeData"]),rows(b["PrelifeData"])
    ck(ar[:3]==br[:3] and ar[3:]==list(reversed(br[3:])) and
       sorted(x["AGE"] for x in ar[3:])==[10,70],"exact stock row order swap")
    result={"schema":"simlox-independent-g11-var11/v1","passed":not FAILURES,
            "verdict":"GO: bounded stocked-item prelife row-order observation" if not FAILURES else
                      "NO-GO: independent replay failed",
            "checks_passed":COUNT-len(FAILURES),"checks_total":COUNT,"failures":FAILURES,
            "evidence":evidence,
            "finding":"Both arms Prelife Logs preserve stock ages in source row order. Physical stock ID1 is issued at original item ID0's h80 PM in both. With age10 assigned first, no further PM appears by h140. With age70 first, installed ID1 begins a second system PM h110.5, its item PM h110.75, and spare ID2 is issued. Original/replacement items return to stock; reports reconcile and the system is ready at horizon.",
            "limits":["One system, one monitored LRU, two initial same-type spares, fixed CALHOURS ages10/70, one seed and h140 horizon. The observed first-ID issue does not prove a general stock selection priority.",
                      "Numeric physical ID-to-age mapping is inferred by ordered Prelife Log and event identity, not printed as a single joined record.",
                      "The default StockTotalResults is aggregate and does not expose on-hand physical IDs; those are established by native event text.",
                      "No other prelife patterns, population or stochastic claim, GUI visual behavior, or cross-engine parity.",
                      "Registry restoration is recorded by guarded invocation/closure, not an independent live registry read."]}
    out=CASE/"independent-validation.json"
    out.write_bytes((json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"checks_total":COUNT,"failures":FAILURES,
                      "verdict":result["verdict"],"output":str(out)},ensure_ascii=False))
    return 0 if not FAILURES else 1

if __name__=="__main__": raise SystemExit(main())
