"""Independent read-only F03.var04 replay from frozen source and native raw bytes."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

CASE=Path(__file__).resolve().parents[1]
ROOT=CASE.parent
PARENT=ROOT/"F03-var03-demand-location-v1.0.0"
F02=ROOT/"F02-var01-var02-integrated-fleet-v1.0.2"
F03A=ROOT/"F03-var01-two-base-crew-v1.0.0"
E08=ROOT/"E08-var01-immediate-lateral-v1.0.2"
ON=CASE/"runs/f03-lateral-on-v100-ssh-20261004-01"
OFF=CASE/"runs/f03-lateral-off-v100-ssh-20261004-01"
OUT=CASE/"review/independent-verdict.json"
failures=[];checks=0

def check(ok,label):
    global checks
    checks+=1
    if not ok:failures.append(label)

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(re.sub(r",\s*([}\]])",r"\1",p.read_text(encoding="utf-8-sig")))
def table(d,name,root):return next(t for t in d[root]["tables"] if t["name"]==name)
def rows(d,name,root):
    t=table(d,name,root);keys=[c["name"] for c in t["columns"]]
    return [dict(zip(keys,r)) for inst in t["instances"] for r in inst["rows"]]
def near(x,y,tol=2e-4):return x is not None and abs(float(x)-float(y))<=tol
def overlap(x,y,a,b):return max(0,min(y,b)-max(x,a))
def events(text):return [(float(m[1]),m[2]) for line in text.splitlines() if (m:=re.match(r"Time: ([\d.]+)\s+(.*)",line))]
def at(ev,t,pattern):return any(abs(x-t)<1e-4 and re.search(pattern,m) for x,m in ev)

def native(run):
    inv,clo=load(run/"invocation.json"),load(run/"closure.json")
    check(sha(run/"invocation.json")==clo["invocation_sha256"],f"{run.name} invocation seal")
    check(inv["run_id"]==clo["run_id"]==run.name,f"{run.name} identity")
    check(inv["session_id"]==0 and "sshd.exe" in inv["ssh_ancestor_names"],f"{run.name} SSH0")
    check(inv["queue_mutex"]=="Global\\SimloxIssue18NativeQueue",f"{run.name} mutex")
    check(inv["gui"]["pid"]==13340 and inv["gui"]["session_id"]==1,f"{run.name} GUI")
    check(clo["source_hashes_before"]==clo["source_hashes_after"] and clo["error"] is None,f"{run.name} source stability")
    check(len(clo["raw"])==12,f"{run.name} raw count")
    for name,meta in sorted(clo["raw"].items()):
        p=run/name
        check(p.is_file() and p.stat().st_size==meta["bytes"] and sha(p)==meta["sha256"],f"{run.name}/{name} raw seal")
    steps=load(run/"steps.json")
    check([s["name"] for s in steps]==["import","export","calc","jsonreport","check_import_export"],f"{run.name} five steps")
    for s in steps:check(s["status"]=="completed" and s["exit_code"]==0 and s["error"] is None and s.get("gui_preserved",True),f"{run.name} step {s['name']}")
    log=(run/"run.log").read_text(encoding="utf-8-sig")
    check("Errors: 0, Warnings: 1, Notes: 0" in log and "warning #108" in log,f"{run.name} converter")
    check(not re.search(r"\b(error|warning)\s*#(?!108\b)\d+",log,re.I),f"{run.name} no unreviewed diagnostics")
    check((run/"model.sxo").stat().st_size>4,f"{run.name} valid SXO")
    return inv,clo

def resources(ev):
    active={};booked=[];req={};waiting=[]
    for t,msg in ev:
        m=re.search(r"<(P-CREW|P-MAINT) at <(BASE-01|BASE-02),0>> (allocated to|deallocated from)",msg)
        if m:
            k=(m[2],m[1])
            if m[3]=="allocated to":
                check(k not in active,f"nonoverlap lease {k} h{t}")
                active[k]=t
            else:
                check(k in active,f"paired release {k} h{t}")
                if k in active:booked.append((active.pop(k),t))
        r=re.search(r"subtask (\d+) seqno .* requests resources$",msg)
        if r:req[r[1]]=t
        g=re.search(r"subtask (\d+) seqno .* resource received$",msg)
        if g and g[1] in req:waiting.append((req.pop(g[1]),t))
    check(not active,"all leases ended")
    return booked,[(x,y) for x,y in waiting if y>x]

def main():
    contract,diff=load(CASE/"contract.json"),load(CASE/"exact-diff.json")
    source={
        "lateral_on":CASE/"lateral_on-input.json","lateral_off":CASE/"lateral_off-input.json",
        "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
        "accepted_parent":PARENT/"risk_base1-input.json",
        "accepted_parent_closure":PARENT/"runs/f03-demand-base1-v100-ssh-20261004-01/closure.json",
        "accepted_parent_signoff":PARENT/"cli-scope-signoff-2026-10-04.md",
        "lateral_donor":E08/"on-input.json","lateral_donor_signoff":E08/"cli-scope-signoff-2026-10-02.md",
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
    obs={}
    for arm,run in [("lateral_on",ON),("lateral_off",OFF)]:
        inv,clo=native(run)
        for key,p in sorted(source.items()):
            check(sha(p)==clo["source_hashes_before"][key]==inv["source_hashes_before"][key],f"{arm} source {key}")
        check((run/"input.json").read_bytes()==(CASE/f"{arm}-input.json").read_bytes(),f"{arm} input copy")
        inp=load(CASE/f"{arm}-input.json")
        exported={t["name"]:t for t in load(run/"roundtrip-raw.json")["model"]["tables"]}
        count=0
        for t in inp["model"]["tables"]:
            if any(i["rows"] for i in t["instances"]):
                count+=1
                check(exported[t["name"]]==t,f"{arm} roundtrip {t['name']}")
        check(count==31,f"{arm} 31 authored populated tables")
        text=(run/"model.log").read_text(encoding="utf-8-sig")
        obs[arm]={"input":inp,"text":text,"events":events(text),"report":load(run/"report-raw.json")}
    check(sha(source["accepted_parent"])==contract["accepted_parent"]["input_sha256"],"accepted parent SHA")
    check(sha(source["lateral_donor"])==contract["accepted_lateral_donor"]["input_sha256"],"lateral donor SHA")
    for arm in ("lateral_on","lateral_off"):
        check(sha(CASE/f"{arm}-input.json")==contract["inputs_sha256"][arm],f"contract {arm} SHA")
    check(sha(CASE/"exact-diff.json")==contract["exact_diff_sha256"],"exact diff SHA")
    parent={t["name"]:t for t in load(source["accepted_parent"])["model"]["tables"]}
    on={t["name"]:t for t in obs["lateral_on"]["input"]["model"]["tables"]}
    off={t["name"]:t for t in obs["lateral_off"]["input"]["model"]["tables"]}
    check(set(on)-set(parent)==set(diff["parent_appended_tables"])=={"LateralSupport"},"single added table")
    check({n for n in parent if parent[n]!=on[n]}==set(diff["parent_changed_tables"])=={"ProblemDescription","Control","Station","StockAllocation"},"exact parent modified tables")
    for n in sorted(set(parent)&set(on)):
        if n not in diff["parent_changed_tables"]:check(parent[n]==on[n],f"unchanged parent table {n}")
    check(rows(obs["lateral_on"]["input"],"LateralSupport","model")==[{"LGID":"LAT-01","TLAT":.5,"DLAYL":"N","LSRUL":"IMMEDIATE","NOTE":None}],"LAT-01 half-hour immediate row")
    stations=rows(obs["lateral_on"]["input"],"Station","model")
    check({r["STID"]:r["LGID"] for r in stations if r["STID"] in ("BASE-01","BASE-02")}=={"BASE-01":"LAT-01","BASE-02":"LAT-01"},"both bases are peers")
    stock=rows(obs["lateral_on"]["input"],"StockAllocation","model")
    check({r["STID"]:r["STSIZ"] for r in stock if r["IID"]=="TEACH-LRU-01"}=={"BASE-01":0,"BASE-02":1,"DEPOT-01":2},"0/1/2 opening LRU geometry")
    check({n for n in on if on[n]!=off[n]}==set(diff["pair_changed_tables"])=={"ProblemDescription","Control"},"pair changed tables")
    for n in sorted(on):
        if n not in ("ProblemDescription","Control"):check(on[n]==off[n],f"paired business table {n} exact")
    c1=rows(obs["lateral_on"]["input"],"Control","model")[0]
    c0=rows(obs["lateral_off"]["input"],"Control","model")[0]
    check(c1["ENLAT"]=="Y" and c0["ENLAT"]=="N" and {k:v for k,v in c1.items() if k!="ENLAT"}=={k:v for k,v in c0.items() if k!="ENLAT"},"sole pair business cell ENLAT")
    expected_bo={"lateral_on":[(23.74,24.24),(48.3394,48.8394)],
                 "lateral_off":[(23.74,25.74),(48.2231,50.2231),(48.2231,50.2231)]}
    summaries={}
    for arm in ("lateral_on","lateral_off"):
        o=obs[arm];ev=o["events"];text=o["text"]
        first=[(8,r"BASE2-MISSION.*mission starting, duration: 2.*<TEACH-AIR-01,2>"),
               (10,r"BASE2-MISSION.*mission success"),
               (21.5,r"RISK-MISSION.*mission starting, duration: 2.*<TEACH-AIR-01,0>,<TEACH-AIR-01,1>"),
               (22.24,r"<TEACH-AIR-01,1> critical random failure added"),
               (22.24,r"RISK-MISSION.*mission aborted: <TEACH-AIR-01,0>"),
               (23.74,r"<TEACH-LRU-01,0,BASE-01,0> Item demand arrives.*<TEACH-LRU-01,0,5>"),
               (23.74,r"<TEACH-LRU-01,0,BASE-01,0> Backorder added"),
               (23.74,r"<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,2> from stock")]
        for t,pattern in first:check(at(ev,t,pattern),f"{arm} matched first event h{t} {pattern}")
        check(not re.search(r"<TEACH-LRU-01,0,BASE-02,0> Item demand arrives from pos <TEACH-AIR",text),f"{arm} BASE-02 mission does not consume peer LRU")
        if arm=="lateral_on":
            concrete=[(23.74,r"Lateral support from: <TEACH-LRU-01,0,BASE-02,0>"),
                      (23.74,r"<TEACH-LRU-01,0,BASE-02,0> Take replacement item <TEACH-LRU-01,0,4> from stock"),
                      (24.24,r"<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,4>"),
                      (24.24,r"Backorder removed, waiting time was 0.5"),
                      (25.74,r"<TEACH-LRU-01,0,BASE-02,0> Put back replacement item <TEACH-LRU-01,0,2> to stock"),
                      (25.0733,r"BASIC-MISSION.*mission starting"),
                      (27.0733,r"BASIC-MISSION.*mission success"),
                      (46.8394,r"<TEACH-AIR-01,0> critical random failure added"),
                      (48.3394,r"Lateral support from: <TEACH-LRU-01,0,BASE-02,0>"),
                      (48.8394,r"Backorder removed, waiting time was 0.5"),
                      (49.6727,r"BASIC-MISSION.*mission starting"),
                      (51.6727,r"BASIC-MISSION.*mission success")]
            check(sum(1 for _,m in ev if "Lateral support from: <TEACH-LRU-01,0,BASE-02,0>" in m)==2,"ON two observed lateral peer selections")
        else:
            concrete=[(25.74,r"<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,2>"),
                      (25.74,r"Backorder removed, waiting time was 2"),
                      (26.5733,r"BASIC-MISSION.*mission starting"),
                      (28.5733,r"BASIC-MISSION.*mission success"),
                      (46.7231,r"<TEACH-AIR-01,0> critical random failure added"),
                      (48.2231,r"<TEACH-LRU-01,0,BASE-01,0> Backorder added"),
                      (50.2231,r"Backorder removed, waiting time was 2"),
                      (50.25,r"BASIC-MISSION.*mission cancelled")]
            check("Lateral support from:" not in text,"OFF no lateral peer selection")
            check(not re.search(r"<TEACH-LRU-01,0,BASE-02,0> Take replacement item",text),"OFF peer stock not drawn")
        for t,pattern in concrete:check(at(ev,t,pattern),f"{arm} physical/mission h{t} {pattern}")
        report=o["report"]
        sy=rows(report,"SystemResults","report");st=rows(report,"StockTotalResults","report");rr=rows(report,"ResourceResults","report")
        summary=rows(report,"ResultSummary","report")[0];rt=rows(report,"ResourceResultsTotal","report")[0]
        summaries[arm]=summary
        check(len(sy)==len(st)==len(rr)==120,f"{arm} 120 aligned bins")
        booked,waiting=resources(ev)
        for i,(s,b,r) in enumerate(zip(sy,st,rr)):
            a,e=i/2,(i+1)/2
            check(s["STINT"]==b["STINT"]==r["STINT"]==a and s["ETINT"]==b["ETINT"]==r["ETINT"]==e,f"{arm} aligned bin {i}")
            check(near(s["NSYA"]+s["NSYUA"],3),f"{arm} three aircraft conserved {i}")
            check(near(b["NBO"],2*sum(overlap(x,y,a,e) for x,y in expected_bo[arm])),f"{arm} backorder occupancy {i}")
            check(r["NR"]==4,f"{arm} four workers capacity {i}")
            check(near(r["NRUM"],2*sum(overlap(x,y,a,e) for x,y in booked)),f"{arm} booked work occupancy {i}")
            check(near(r["NRW"],2*sum(overlap(x,y,a,e) for x,y in waiting)),f"{arm} resource queue occupancy {i}")
        check(near(rt["NRUM"]*60,sum(y-x for x,y in booked)) and near(rt["NRW"]*60,sum(y-x for x,y in waiting)),f"{arm} integrated worker hours")
        check(summary["NREP"]==1 and summary["RTIUP"]==60,f"{arm} one 60h replication")
        check(near(sy[-1]["NSYRY"],3) and st[-1]["NBO"]==0 and rr[-1]["NRUM"]==0 and rr[-1]["NRW"]==0,f"{arm} ready3/no BO/no worker terminal")
    check(near(summaries["lateral_on"]["MSTF"],1) and near(summaries["lateral_off"]["MSTF"],.8),"observed summary difference, not matched later causal estimate")
    check(at(obs["lateral_on"]["events"],46.8394,r"critical random failure added") and at(obs["lateral_off"]["events"],46.7231,r"critical random failure added"),"later random paths differ and are not paired matched faults")
    result={"case":"F03-var04-lateral-peer-v1.0.0","passed":not failures,
        "verdict":"GO — bounded first-demand lateral peer substitution" if not failures else "NO-GO",
        "checks_passed":checks-len(failures),"checks_total":checks,"failures":failures,
        "evidence":{"on_closure_sha256":sha(ON/"closure.json"),"off_closure_sha256":sha(OFF/"closure.json"),
                    "on_report_sha256":sha(ON/"report-raw.json"),"off_report_sha256":sha(OFF/"report-raw.json"),
                    "matched_first_demand_hour":23.74,"on_first_peer_item":"LRU physical ID4 BASE-02→BASE-01 h23.74–24.24",
                    "off_first_depot_item":"LRU physical ID2 DEPOT-01→BASE-01 h23.74–25.74",
                    "on_replenishment":"depot ID2 reaches BASE-02 h25.74"},
        "limits":["First fault/demand is matched at h22.24/h23.74; later random failures differ (ON h46.8394, OFF h46.7231), so later outcomes and aggregate differences are observations, not a matched-fault causal estimate.",
                  "One seed, IMMEDIATE lateral policy, TLAT 0.5h, symmetric two-base network; no broader policy, autonomy, overlapping-demand or route-contention claim.",
                  "Aggregate System/Stock/Resource reports are not per-base inventories; physical peer issue and depot replenishment are bound to station/item event lines.",
                  "Bin occupancy tolerates 0.0002 from native printed event-time rounding; ResourceResults.NRA is not interpreted as free capacity."],}
    OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({k:result[k] for k in ("verdict","checks_passed","checks_total","failures")},indent=2))
    return 0 if not failures else 1

if __name__=="__main__":raise SystemExit(main())
