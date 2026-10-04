"""Independent standard-library read-only replay for F03.var03 demand location."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
ROOT=CASE.parent
F02=ROOT/"F02-var01-var02-integrated-fleet-v1.0.2"
F03A=ROOT/"F03-var01-two-base-crew-v1.0.0"
F03B=ROOT/"F03-var02-two-base-stock-v1.0.0"
BASE1=CASE/"runs/f03-demand-base1-v100-ssh-20261004-01"
BASE2=CASE/"runs/f03-demand-base2-v100-ssh-20261004-01"
OUT=CASE/"review/independent-verdict.json"
failures=[]
checks=0

def check(ok,label):
    global checks
    checks+=1
    if not ok:failures.append(label)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def load(path):
    return json.loads(re.sub(r",\s*([}\]])",r"\1",path.read_text(encoding="utf-8-sig")))

def table(doc,name,root):return next(t for t in doc[root]["tables"] if t["name"]==name)

def rows(doc,name,root):
    t=table(doc,name,root)
    keys=[c["name"] for c in t["columns"]]
    return [dict(zip(keys,r)) for inst in t["instances"] for r in inst["rows"]]

def near(x,y,tol=2e-4):return x is not None and abs(float(x)-float(y))<=tol
def overlap(x,y,a,b):return max(0,min(y,b)-max(x,a))

def events(text):
    return [(float(m[1]),m[2]) for line in text.splitlines() if (m:=re.match(r"Time: ([\d.]+)\s+(.*)",line))]

def at(ev,time,pattern):
    return any(abs(t-time)<1e-4 and re.search(pattern,msg) for t,msg in ev)

def native(run):
    inv,clo=load(run/"invocation.json"),load(run/"closure.json")
    check(sha(run/"invocation.json")==clo["invocation_sha256"],f"{run.name} invocation seal")
    check(inv["run_id"]==clo["run_id"]==run.name,f"{run.name} identity")
    check(inv["session_id"]==0 and "sshd.exe" in inv["ssh_ancestor_names"],f"{run.name} SSH0")
    check(inv["queue_mutex"]=="Global\\SimloxIssue18NativeQueue",f"{run.name} queue")
    check(inv["gui"]["pid"]==13340 and inv["gui"]["session_id"]==1,f"{run.name} GUI")
    check(clo["source_hashes_before"]==clo["source_hashes_after"] and clo["error"] is None,f"{run.name} source stability")
    check(len(clo["raw"])==12,f"{run.name} twelve sealed files")
    for name,meta in sorted(clo["raw"].items()):
        p=run/name
        check(p.is_file() and p.stat().st_size==meta["bytes"] and sha(p)==meta["sha256"],f"{run.name}/{name} raw seal")
    steps=load(run/"steps.json")
    check([s["name"] for s in steps]==["import","export","calc","jsonreport","check_import_export"],f"{run.name} step sequence")
    for s in steps:
        check(s["status"]=="completed" and s["exit_code"]==0 and s["error"] is None and s.get("gui_preserved",True),f"{run.name} step {s['name']}")
    conv=(run/"run.log").read_text(encoding="utf-8-sig")
    check("Errors: 0, Warnings: 1, Notes: 0" in conv and "warning #108" in conv,f"{run.name} converter")
    check(not re.search(r"\b(error|warning)\s*#(?!108\b)\d+",conv,re.I),f"{run.name} no other diagnostic")
    check((run/"model.sxo").stat().st_size>4,f"{run.name} valid output")
    return inv,clo

def resource_intervals(ev):
    active={};booked=[];req={};wait=[]
    for t,msg in ev:
        m=re.search(r"<(P-CREW|P-MAINT) at <(BASE-01|BASE-02),0>> (allocated to|deallocated from)",msg)
        if m:
            key=(m[2],m[1])
            if m[3]=="allocated to":
                check(key not in active,f"non-overlapping {key} booking h{t}")
                active[key]=t
            else:
                check(key in active,f"matched {key} release h{t}")
                if key in active:booked.append((key,active.pop(key),t))
        r=re.search(r"subtask (\d+) seqno .* requests resources$",msg)
        if r:req[r[1]]=t
        g=re.search(r"subtask (\d+) seqno .* resource received$",msg)
        if g and g[1] in req:wait.append((req.pop(g[1]),t))
    check(not active,"all resource leases closed")
    return booked,[(a,b) for a,b in wait if b>a]

def main():
    contract,diff=load(CASE/"contract.json"),load(CASE/"exact-diff.json")
    parent_path=F03B/"depot_only-input.json"
    parent_run=F03B/"runs/f03-stock-depot-v100-ssh-20261004-01"
    source={
        "risk_base1":CASE/"risk_base1-input.json","risk_base2":CASE/"risk_base2-input.json",
        "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
        "accepted_parent":parent_path,"accepted_parent_closure":parent_run/"closure.json",
        "accepted_parent_signoff":F03B/"cli-scope-signoff-2026-10-04.md",
        "parent":F02/"risk-input.json","parent_closure":F02/"runs/f02-pair-v102-risk-ssh-20261004-01/closure.json",
        "parent_signoff":F02/"cli-scope-signoff-2026-10-04.md",
        "two_base_input":F03A/"staffed-input.json","two_base_signoff":F03A/"cli-scope-signoff-2026-10-04.md",
        "A17_input":ROOT/"A17-multi-unit-group-v1.0.0/native-input.json",
        "A17_signoff":ROOT/"A17-multi-unit-group-v1.0.0/cli-scope-signoff-2026-09-29.md",
        "E07_signoff":ROOT/"E07-item-specific-transport-v1.0.1/cli-scope-signoff-2026-10-01.md",
        "I01_signoff":ROOT/"I01-var01-resource-points-v1.0.0/cli-scope-signoff-2026-10-02.md",
        "build.py":CASE/"build.py","describe_diff.py":CASE/"describe_diff.py",
        "check_roundtrip.py":CASE/"check_roundtrip.py","run_native_ssh.ps1":CASE/"run_native_ssh.ps1",
    }
    observed={}
    for arm,run in [("risk_base1",BASE1),("risk_base2",BASE2)]:
        inv,clo=native(run)
        for key,p in sorted(source.items()):
            check(sha(p)==clo["source_hashes_before"][key]==inv["source_hashes_before"][key],f"{arm} pinned {key}")
        check((run/"input.json").read_bytes()==(CASE/f"{arm}-input.json").read_bytes(),f"{arm} source copy")
        inp=load(CASE/f"{arm}-input.json")
        exported={t["name"]:t for t in load(run/"roundtrip-raw.json")["model"]["tables"]}
        count=0
        for t in inp["model"]["tables"]:
            if any(inst["rows"] for inst in t["instances"]):
                count+=1
                check(t==exported[t["name"]],f"{arm} roundtrip {t['name']}")
        check(count==30,f"{arm} 30 authored populated tables")
        text=(run/"model.log").read_text(encoding="utf-8-sig")
        observed[arm]={"input":inp,"text":text,"events":events(text),"report":load(run/"report-raw.json")}
    check(sha(parent_path)==contract["accepted_parent"]["input_sha256"],"accepted parent pin")
    check(sha(CASE/"risk_base1-input.json")==contract["inputs_sha256"]["risk_base1"],"base1 input pin")
    check(sha(CASE/"risk_base2-input.json")==contract["inputs_sha256"]["risk_base2"],"base2 input pin")
    check(sha(CASE/"exact-diff.json")==contract["exact_diff_sha256"],"diff pin")
    parent=load(parent_path)
    one=observed["risk_base1"]["input"]
    two=observed["risk_base2"]["input"]
    pa={t["name"]:t for t in parent["model"]["tables"]}
    oa={t["name"]:t for t in one["model"]["tables"]}
    ta={t["name"]:t for t in two["model"]["tables"]}
    check({name for name in pa if pa[name]!=oa[name]}=={"ProblemDescription"}==set(diff["parent_changed_tables"]),"control description-only vs accepted parent")
    pair_changed={name for name in oa if oa[name]!=ta[name]}
    check(pair_changed==set(diff["pair_changed_tables"])=={"ProblemDescription","Unit","MissionPreparation","MissionTurnround"},"exact pair changed tables")
    changed_cells=[]
    for name in sorted(oa):
        left,right=oa[name],ta[name]
        check(left["columns"]==right["columns"],f"{name} columns unchanged")
        if name not in pair_changed:check(left==right,f"{name} pair stable")
        names=[c["name"] for c in left["columns"]]
        lr=left["instances"][0]["rows"];rr=right["instances"][0]["rows"]
        check(len(lr)==len(rr),f"{name} row count stable")
        for i,(a,b) in enumerate(zip(lr,rr),1):
            for j,(x,y) in enumerate(zip(a,b)):
                if x!=y:changed_cells.append((name,i,names[j],x,y))
    declared=[(d["table"],d["row"],d["column"],d["risk_base1"],d["risk_base2"]) for d in diff["pair_changed_cells"]]
    check(set(changed_cells)==set(declared) and len(changed_cells)==9,"exact nine-cell location switch")
    check(all(k in ("PDESC","STID") for _,_,k,_,_ in changed_cells),"no stock/resource/route/repair edits")
    check(sha(BASE1/"model.log")==sha(parent_run/"model.log"),"control reproduces accepted parent event log")
    parent_report=load(parent_run/"report-raw.json")
    control_report=observed["risk_base1"]["report"]
    for name in ("ResultSummary","SystemResults","StockTotalResults","ResourceResults","ResourceResultsTotal"):
        check(rows(control_report,name,"report")==rows(parent_report,name,"report"),f"control reproduces parent {name} rows")

    reports={}
    for arm,station,riskids,localid,run in [
        ("risk_base1","BASE-01",(0,1),2,BASE1),
        ("risk_base2","BASE-02",(1,2),0,BASE2),
    ]:
        ob=observed[arm];ev=ob["events"];text=ob["text"]
        checks_local=[
            (8,rf"BASE2-MISSION.*mission starting, duration: 2 : <TEACH-AIR-01,{localid}>"),
            (10,r"BASE2-MISSION.*mission success"),
            (21.5,rf"RISK-MISSION.*mission starting, duration: 2 : <TEACH-AIR-01,{riskids[0]}>,<TEACH-AIR-01,{riskids[1]}>"),
            (22.24,rf"RISK-MISSION.*mission aborted: <TEACH-AIR-01,{riskids[0]}>"),
            (23.74,rf"<TEACH-LRU-01,0,{station},0> Item demand arrives.*<TEACH-LRU-01,0,4>"),
            (23.74,rf"<TEACH-LRU-01,0,{station},0> Backorder added"),
            (23.74,r"<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,2> from stock"),
            (25.74,rf"<TEACH-LRU-01,0,{station},0> Backorder removed, waiting time was 2"),
            (26.5733,rf"BASIC-MISSION.*mission starting, duration: 2 : <TEACH-AIR-01,{riskids[0]}>,<TEACH-AIR-01,{riskids[1]}>"),
            (26.6566,r"<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,4> to stock"),
            (28.5733,r"BASIC-MISSION.*mission success"),
            (45.5,rf"RISK-MISSION.*mission starting, duration: 2 : <TEACH-AIR-01,{riskids[0]}>,<TEACH-AIR-01,{riskids[1]}>"),
            (46.7231,rf"RISK-MISSION.*mission aborted: <TEACH-AIR-01,{riskids[1]}>"),
            (48.2231,rf"<TEACH-LRU-01,0,{station},0> Item demand arrives.*<TEACH-LRU-01,0,6>"),
            (48.2231,rf"<TEACH-LRU-01,0,{station},0> Item demand arrives.*<TEACH-LRU-01,0,8>"),
            (50.2231,rf"<TEACH-LRU-01,0,{station},0> Backorder removed, waiting time was 2"),
            (50.25,r"BASIC-MISSION.*mission cancelled"),
            (51.1398,r"Put back replacement item <TEACH-LRU-01,0,6> to stock"),
            (51.3065,r"Put back replacement item <TEACH-LRU-01,0,8> to stock"),
        ]
        for t,pattern in checks_local:check(at(ev,t,pattern),f"{arm} h{t} {pattern}")
        check(sum(1 for _,m in ev if f"<TEACH-LRU-01,0,{station},0> Item demand arrives" in m)==3,f"{arm} three demands at risk base")
        other="BASE-02" if station=="BASE-01" else "BASE-01"
        check(not re.search(rf"<TEACH-LRU-01,0,{other},0> (Item demand arrives|Backorder added)",text),f"{arm} no other-base LRU demand")
        check(sum(1 for _,m in ev if f"<TEACH-LRU-01,0,{station},0> Backorder added" in m)==3,f"{arm} three station-scoped backorders")
        check(sum(1 for _,m in ev if "<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item" in m)==3,f"{arm} three depot issues")
        check(sum(1 for _,m in ev if "<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item" in m)==3,f"{arm} three depot LRU returns")
        check(sum(1 for _,m in ev if f"to <{station},0>" in m and "transport task" in m and "created" in m)>=3,f"{arm} physical depot-to-risk-base transport route")
        report=ob["report"]
        sy=rows(report,"SystemResults","report");stock=rows(report,"StockTotalResults","report");resource=rows(report,"ResourceResults","report")
        summary=rows(report,"ResultSummary","report")[0]
        rt=rows(report,"ResourceResultsTotal","report")[0]
        reports[arm]=(sy,stock,resource,summary,rt)
        check(len(sy)==len(stock)==len(resource)==120,f"{arm} 120 aligned bins")
        booked,waiting=resource_intervals(ev)
        bo=[(23.74,25.74),(48.2231,50.2231),(48.2231,50.2231)]
        for i,(s,st,r) in enumerate(zip(sy,stock,resource)):
            a,b=i/2,(i+1)/2
            check(s["STINT"]==st["STINT"]==r["STINT"]==a and s["ETINT"]==st["ETINT"]==r["ETINT"]==b,f"{arm} aligned bin {i}")
            check(near(s["NSYA"]+s["NSYUA"],3),f"{arm} three aircraft conserved bin {i}")
            check(near(st["NBO"],2*sum(overlap(x,y,a,b) for x,y in bo)),f"{arm} backorder occupancy bin {i}")
            check(r["NR"]==4,f"{arm} four aggregate workers bin {i}")
            check(near(r["NRUM"],2*sum(overlap(x,y,a,b) for _,x,y in booked)),f"{arm} resource use bin {i}")
            check(near(r["NRW"],2*sum(overlap(x,y,a,b) for x,y in waiting)),f"{arm} resource wait bin {i}")
        check(near(rt["NRUM"]*60,sum(y-x for _,x,y in booked)) and near(rt["NRW"]*60,sum(y-x for x,y in waiting)),f"{arm} resource-hour totals")
        check(summary["NREP"]==1 and summary["RTIUP"]==60 and near(summary["MSTF"],.8) and near(summary["MSUF"],.4),f"{arm} summary")
        check(near(sy[-1]["NSYRY"],3) and stock[-1]["NBO"]==0 and resource[-1]["NRUM"]==0 and resource[-1]["NRW"]==0,f"{arm} terminal ready/no BO/no worker use")
    for name in ("ResultSummary","SystemResults","StockTotalResults","ResourceResults","ResourceResultsTotal"):
        a=rows(observed["risk_base1"]["report"],name,"report")
        b=rows(observed["risk_base2"]["report"],name,"report")
        check(a==b,f"aggregate {name} full row equality")
    result={"case":"F03-var03-demand-location-v1.0.0","passed":not failures,
        "verdict":"GO — bounded risk-unit demand relocation" if not failures else "NO-GO",
        "checks_passed":checks-len(failures),"checks_total":checks,"failures":failures,
        "evidence":{"base1_closure_sha256":sha(BASE1/"closure.json"),"base2_closure_sha256":sha(BASE2/"closure.json"),
                    "base1_report_sha256":sha(BASE1/"report-raw.json"),"base2_report_sha256":sha(BASE2/"report-raw.json"),
                    "risk_demand_hours":[23.74,48.2231,48.2231],"risk_demand_station":{"risk_base1":"BASE-01","risk_base2":"BASE-02"},
                    "aggregate_report_business_rows_equal":True},
        "limits":["One fixed seed, symmetric two-hour depot legs and equal local staffing; aggregate report equality does not identify which base demanded stock.",
                  "Risk aircraft physical IDs shift 0/1→1/2 while the single-aircraft unit shifts 2→0; comparison uses unit and role, not equal physical IDs.",
                  "No asymmetric route, interbase transfer, different capacity, independent failure-time law or larger-network claim.",
                  "Native event timestamps are printed with limited precision; report-bin integrals allow 0.0002 occupancy rounding."]}
    OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({k:result[k] for k in ("verdict","checks_passed","checks_total","failures")},indent=2))
    return 0 if not failures else 1

if __name__=="__main__":
    raise SystemExit(main())
