"""Read-only author replay of paired stocked-LRU Prelife row-order runs."""
import hashlib
import json
import math
import re
from pathlib import Path
from check_roundtrip import SHA, native_json, populated

HERE=Path(__file__).resolve().parent
RUNS={arm:f"g11-var11-{arm}-v100-ssh-20261003-01" for arm in SHA}
PARENT=HERE.parent/"G11-var04-inherit-item-prelife-v1.0.1"
PARENT_SHA="76cd71fe989b84a8f8c5c23007926a417c8f01c820cfc534846216e4a9fe7311"
PARENT_CLOSURE="60ae9d2e2feadb6843cec3d1bb53c7afa7b59fc9374d5a35018df1aa1a2cb4f7"
CONTRACT="6191891eb422b417caea43a87cd6bf6c26037f8c0526c0600c3a3e34b50d60ad"
DIFF="b5320f54915edcd258c6319df0464c32e1576a449872ef4832a5628d38a6f73b"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def vals(t,name):
    i=[c["name"] for c in t["columns"]].index(name)
    return [row[i] for inst in t["instances"] for row in inst["rows"]]
class Audit:
    def __init__(self):self.checks,self.errors=0,[]
    def need(self,ok,label):
        self.checks+=1
        if not ok:self.errors.append(label)

def arm_replay(arm,a):
    run=HERE/"runs"/RUNS[arm]
    closure,invocation,steps=(read(run/n) for n in ("closure.json","invocation.json","steps.json"))
    a.need(closure["arm"]==arm and closure["run_id"]==RUNS[arm] and closure["error"] is None,f"{arm} closure identity")
    a.need(sha(run/"invocation.json")==closure["invocation_sha256"],f"{arm} invocation seal")
    a.need(invocation["session_id"]==0 and "sshd.exe" in invocation["ssh_ancestor_names"],f"{arm} SSH0")
    a.need(invocation["gui"]["pid"]==13340 and invocation["gui"]["session_id"]==1,f"{arm} GUI")
    a.need(invocation["queue_mutex"]=="Global\\SimloxIssue18NativeQueue",f"{arm} mutex")
    a.need(invocation["prelife_log_option_before"]=="NO" and closure["prelife_log_option_after"]=="NO",f"{arm} registry restore")
    a.need([s["name"] for s in steps]==["import","export","calc","jsonreport","check_import_export"],f"{arm} five steps")
    for s in steps:a.need(s["status"]=="completed" and s["exit_code"]==0 and s["gui_preserved"],f"{arm} step {s['name']}")
    for key,digest in {"input":SHA[arm],"parent":PARENT_SHA,"parent_closure":PARENT_CLOSURE,"contract":CONTRACT,"exact_diff":DIFF}.items():a.need(closure["source_hashes_before"].get(key)==digest,f"{arm} pinned {key}")
    for key,digest in closure["source_hashes_before"].items():a.need(closure["source_hashes_after"].get(key)==digest,f"{arm} unchanged {key}")
    a.need(len(closure["raw"])==13,f"{arm} raw count")
    for name,seal in closure["raw"].items():
        p=run/name
        a.need(p.is_file() and p.stat().st_size==seal["bytes"] and sha(p)==seal["sha256"],f"{arm} raw {name}")
    roundtrip=read(run/"roundtrip-validation.json")
    before,after=populated(native_json(run/"input.json")),populated(native_json(run/"roundtrip-raw.json"))
    a.need(roundtrip["passed"] and not roundtrip["differences"] and len(before)==23 and roundtrip["populated_tables"]==sorted(before),f"{arm} roundtrip verdict")
    for name,body in before.items():a.need(after.get(name)==body,f"{arm} roundtrip {name}")
    runlog=(run/"run.log").read_text(encoding="utf-8-sig",errors="replace")
    a.need(re.findall(r"\(warning #(\d+)\)",runlog)==["108"] and "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and "(error #" not in runlog and "(notice #" not in runlog,f"{arm} conversion gate")
    prelife=(run/"model_Prelife.log").read_text(encoding="utf-8-sig",errors="replace")
    parsed=[(mid,plind,float(age)) for mid,plind,age in re.findall(r"\*\*(TEACH-AIR-01|POS-A|TEACH-LRU-01)\*\*([^*]+)\*\* Age\[CALHOURS\]:([0-9.]+)",prelife)]
    stock=[("TEACH-LRU-01","STOCK-10",10.),("TEACH-LRU-01","STOCK-70",70.)]
    if arm=="age70-first":stock.reverse()
    expected=[("TEACH-AIR-01","SYS-60",60.),("POS-A","POS-INH",60.),("TEACH-LRU-01","LRU-20",20.)]+stock
    a.need(parsed==expected,f"{arm} native installed/stock ages")
    event=(run/"model.log").read_text(encoding="utf-8-sig",errors="replace")
    expected_system=[80.] if arm=="age10-first" else [80.,110.5]
    expected_item=[80.25] if arm=="age10-first" else [80.25,110.75]
    for kind,target in (("system",expected_system),("item",expected_item)):
        identifier="TEACH-AIR-01,0" if kind=="system" else "TEACH-LRU-01,0,\\d+"
        found=[float(x) for x in re.findall(r"Time: ([0-9.]+)  "+kind+r" PM task \d+ on <"+identifier+r"> started",event)]
        a.need(found==target,f"{arm} {kind} PM starts")
    removed=[(float(t),int(i)) for t,i in re.findall(r"Time: ([0-9.]+).*item requiring maintenance is <TEACH-LRU-01,0,(\d+)>",event)]
    issued=[(float(t),int(i)) for t,i in re.findall(r"Time: ([0-9.]+).*Take replacement item <TEACH-LRU-01,0,(\d+)> from stock",event)]
    returned=[(float(t),int(i)) for t,i in re.findall(r"Time: ([0-9.]+).*Put back replacement item <TEACH-LRU-01,0,(\d+)> to stock",event)]
    a.need(removed==([(80.,0)] if arm=="age10-first" else [(80.,0),(110.5,1)]),f"{arm} removed IDs")
    a.need(issued==([(80.,1)] if arm=="age10-first" else [(80.,1),(110.5,2)]),f"{arm} issued IDs")
    a.need(returned==([(81.25,0)] if arm=="age10-first" else [(81.25,0),(111.75,1)]),f"{arm} returned IDs")
    a.need(not re.search(r"mission (started|success:|cancelled)",event,re.I) and "backorder" not in event.lower() and "(error #" not in event,f"{arm} event exclusions")
    report={t["name"]:t for t in native_json(run/"report-raw.json")["report"]["tables"]}
    a.need(set(report)=={"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},f"{arm} report tables")
    for field,target in {"NREP":1,"RTIUP":140,"MSTF":0,"MSUF":0}.items():a.need(vals(report["ResultSummary"],field)==[target],f"{arm} summary {field}")
    for name in ("SystemResults","StockTotalResults"):
        st,en=vals(report[name],"STINT"),vals(report[name],"ETINT")
        a.need(len(st)==280 and st[0]==0 and en[-1]==140 and all(x==y for x,y in zip(en,st[1:])),f"{arm} {name} bins")
    pmcount=1 if arm=="age10-first" else 2
    for field in ("NPMT","NPMS","NSYPM"):a.need(math.isclose(sum(x or 0 for x in vals(report["SystemResults"],field)),pmcount,abs_tol=1e-8),f"{arm} system {field}")
    for field in ("NDP","NWT"):a.need(sum(x or 0 for x in vals(report["StockTotalResults"],field))==pmcount,f"{arm} stock {field}")
    a.need(sum(x or 0 for x in vals(report["StockTotalResults"],"NBO"))==0 and sum(x or 0 for x in vals(report["SystemResults"],"NFAIL"))==0,f"{arm} no failure/backorder")
    stock_levels=[int(x) for x in re.findall(r"Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: (\d+)",event)]
    a.need(stock_levels[-1]==2,f"{arm} physical terminal stock2")
    a.need(vals(report["SystemResults"],"NSYRY")[-1]==1 and vals(report["StockTotalResults"],"PNB")[-1]==1,f"{arm} terminal ready and PNB")
    return {"arm":arm,"run_id":RUNS[arm],"closure_sha256":sha(run/"closure.json"),"prelife_log_sha256":sha(run/"model_Prelife.log"),"event_log_sha256":sha(run/"model.log"),"report_sha256":sha(run/"report-raw.json"),"prelife":parsed,"system_pm_hours":expected_system,"removed":removed,"issued":issued,"returned":returned,"terminal_physical_stock":stock_levels[-1]}

def main():
    a=Audit()
    for label,path,digest in (("parent",PARENT/"native-input-explicit-control.json",PARENT_SHA),("parent closure",PARENT/"runs/g11-var04-explicit-control-v101-ssh-20261002-01/closure.json",PARENT_CLOSURE),("contract",HERE/"contract.json",CONTRACT),("diff",HERE/"exact-diff.json",DIFF)):a.need(sha(path)==digest,f"{label} SHA")
    docs=[]
    for arm in RUNS:
        path=HERE/f"native-input-{arm}.json";a.need(sha(path)==SHA[arm],f"{arm} input SHA");docs.append(native_json(path))
    tables=[{t["name"]:t for t in doc["model"]["tables"]} for doc in docs]
    a.need({n for n in tables[0] if tables[0][n]!=tables[1][n]}=={"PrelifeData","ProblemDescription"},"pair changed tables")
    pdata=[t["PrelifeData"]["instances"][0]["rows"] for t in tables]
    a.need(pdata[0][:-2]==pdata[1][:-2] and pdata[0][-2:]==list(reversed(pdata[1][-2:])),"two stock rows only reversed")
    arms=[arm_replay(arm,a) for arm in RUNS]
    result={"schema":"simlox-g11-var11-stock-prelife-order-author-replay/v1","case_id":"G11","variant_id":"G11.var11","version":"1.0.0","checks":a.checks,"passed_checks":a.checks-len(a.errors),"passed":not a.errors,"differences":a.errors,"arms":arms,"scope":"two fixed-age stocked LRUs, observed first issue and one later PM within h140","publication_state":"not_published"}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result["passed"] else 1
if __name__=="__main__":raise SystemExit(main())
