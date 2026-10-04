"""Independent read-only F03.var02 native evidence replay; no author imports."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
F02 = ROOT / "F02-var01-var02-integrated-fleet-v1.0.2"
F03 = ROOT / "F03-var01-two-base-crew-v1.0.0"
DEPOT = CASE / "runs/f03-stock-depot-v100-ssh-20261004-01"
FORWARD = CASE / "runs/f03-stock-forward-v100-ssh-20261004-01"
OUT = CASE / "review/independent-verdict.json"
failures: list[str] = []
checks = 0


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def table(doc, name, root):
    return next(t for t in doc[root]["tables"] if t["name"] == name)


def rows(doc, name, root):
    t = table(doc, name, root)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r)) for inst in t["instances"] for r in inst["rows"]]


def overlap(x, y, a, b):
    return max(0, min(y,b)-max(x,a))


def near(x,y,tol=1.2e-4):
    return x is not None and abs(float(x)-float(y)) <= tol


def physical_events(text):
    return [(float(m[1]),m[2]) for line in text.splitlines() if (m:=re.match(r"Time: ([\d.]+)\s+(.*)",line))]


def has(ev,time,pattern):
    return any(abs(t-time)<1e-4 and re.search(pattern,s) for t,s in ev)


def native(run):
    inv, clo = load(run/"invocation.json"), load(run/"closure.json")
    check(sha(run/"invocation.json")==clo["invocation_sha256"],f"{run.name} invocation seal")
    check(inv["run_id"]==clo["run_id"]==run.name,f"{run.name} identity")
    check(inv["session_id"]==0 and "sshd.exe" in inv["ssh_ancestor_names"],f"{run.name} SSH0")
    check(inv["queue_mutex"]=="Global\\SimloxIssue18NativeQueue",f"{run.name} mutex")
    check(inv["gui"]["pid"]==13340 and inv["gui"]["session_id"]==1,f"{run.name} GUI")
    check(clo["source_hashes_before"]==clo["source_hashes_after"] and clo["error"] is None,f"{run.name} stable source")
    check(len(clo["raw"])==12,f"{run.name} 12 sealed raw files")
    for name,meta in sorted(clo["raw"].items()):
        p=run/name
        check(p.is_file() and p.stat().st_size==meta["bytes"] and sha(p)==meta["sha256"],f"{run.name}/{name} seal")
    steps=load(run/"steps.json")
    check([s["name"] for s in steps]==["import","export","calc","jsonreport","check_import_export"],f"{run.name} five steps")
    for s in steps:
        check(s["status"]=="completed" and s["exit_code"]==0 and s["error"] is None and s.get("gui_preserved",True),f"{run.name} {s['name']}")
    conv=(run/"run.log").read_text(encoding="utf-8-sig")
    check("Errors: 0, Warnings: 1, Notes: 0" in conv and "warning #108" in conv,f"{run.name} converter")
    check(not re.search(r"\b(error|warning)\s*#(?!108\b)\d+",conv,re.I),f"{run.name} no unreviewed diagnostic")
    check((run/"model.sxo").stat().st_size>4,f"{run.name} valid SXO")
    return inv,clo


def resource_spans(ev):
    active={}
    booked=[]
    requested={}
    waiting=[]
    for t,msg in ev:
        m=re.search(r"<(P-CREW|P-MAINT) at <(BASE-01|BASE-02),0>> (allocated to|deallocated from)",msg)
        if m:
            key=(m[2],m[1])
            if m[3]=="allocated to":
                check(key not in active,f"nonoverlapping resource lease {key} h{t}")
                active[key]=t
            else:
                check(key in active,f"paired resource release {key} h{t}")
                if key in active:booked.append((key,active.pop(key),t))
        req=re.search(r"subtask (\d+) seqno .* requests resources$",msg)
        if req:requested[req[1]]=t
        got=re.search(r"subtask (\d+) seqno .* resource received$",msg)
        if got and got[1] in requested:waiting.append((requested.pop(got[1]),t))
    check(not active,"all booked resource leases closed")
    return booked,[(a,b) for a,b in waiting if b>a]


def main():
    contract=load(CASE/"contract.json")
    diff=load(CASE/"exact-diff.json")
    parent_file=F02/"risk-input.json"
    parent_run=F02/"runs/f02-pair-v102-risk-ssh-20261004-01"
    source_files={
        "depot_only":CASE/"depot_only-input.json", "forward_spare":CASE/"forward_spare-input.json",
        "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
        "parent":parent_file,"parent_closure":parent_run/"closure.json",
        "parent_signoff":F02/"cli-scope-signoff-2026-10-04.md",
        "two_base_input":F03/"staffed-input.json",
        "two_base_signoff":F03/"cli-scope-signoff-2026-10-04.md",
        "A17_input":ROOT/"A17-multi-unit-group-v1.0.0/native-input.json",
        "A17_signoff":ROOT/"A17-multi-unit-group-v1.0.0/cli-scope-signoff-2026-09-29.md",
        "E07_signoff":ROOT/"E07-item-specific-transport-v1.0.1/cli-scope-signoff-2026-10-01.md",
        "I01_signoff":ROOT/"I01-var01-resource-points-v1.0.0/cli-scope-signoff-2026-10-02.md",
        "build.py":CASE/"build.py","describe_diff.py":CASE/"describe_diff.py",
        "check_roundtrip.py":CASE/"check_roundtrip.py","run_native_ssh.ps1":CASE/"run_native_ssh.ps1",
    }
    obs={}
    for arm,run in [("depot_only",DEPOT),("forward_spare",FORWARD)]:
        inv,clo=native(run)
        for key,p in sorted(source_files.items()):
            check(sha(p)==clo["source_hashes_before"][key]==inv["source_hashes_before"][key],f"{arm} source pin {key}")
        check((run/"input.json").read_bytes()==(CASE/f"{arm}-input.json").read_bytes(),f"{arm} frozen input copy")
        inp=load(CASE/f"{arm}-input.json")
        exp=load(run/"roundtrip-raw.json")
        exported={t["name"]:t for t in exp["model"]["tables"]}
        count=0
        for t in inp["model"]["tables"]:
            if any(i["rows"] for i in t["instances"]):
                count+=1
                check(t==exported[t["name"]],f"{arm} exact roundtrip {t['name']}")
        check(count==30,f"{arm} 30 populated authored tables")
        text=(run/"model.log").read_text(encoding="utf-8-sig")
        obs[arm]={"input":inp,"report":load(run/"report-raw.json"),"events":physical_events(text),"text":text}
    check(sha(parent_file)==contract["accepted_risk_parent"]["input_sha256"],"accepted risk parent pin")
    check(sha(F03/"staffed-input.json")==contract["accepted_two_base_precedent"]["staffed_input_sha256"],"accepted F03 structural precedent pin")
    check(sha(CASE/"depot_only-input.json")==contract["inputs_sha256"]["depot_only"],"depot source pin")
    check(sha(CASE/"forward_spare-input.json")==contract["inputs_sha256"]["forward_spare"],"forward source pin")
    check(sha(CASE/"exact-diff.json")==contract["exact_diff_sha256"],"exact diff pin")
    parent={t["name"]:t for t in load(parent_file)["model"]["tables"]}
    depot={t["name"]:t for t in obs["depot_only"]["input"]["model"]["tables"]}
    forward={t["name"]:t for t in obs["forward_spare"]["input"]["model"]["tables"]}
    changed={name for name in parent if parent[name]!=depot[name]}
    check(changed==set(diff["parent_changed_tables"]) and len(changed)==14,"exact parent changed-table set")
    for name in sorted(parent):
        a,b=parent[name],depot[name]
        if name not in changed:check(a==b,f"unchanged inherited {name}")
        elif name!="ProblemDescription":
            old=a["instances"][0]["rows"];new=b["instances"][0]["rows"]
            check(a["columns"]==b["columns"] and new[:len(old)]==old and len(new)>len(old),f"{name} append-only ancestor")
    pair_changed={name for name in depot if depot[name]!=forward[name]}
    check(pair_changed==set(diff["pair_changed_tables"])=={"ProblemDescription","StockAllocation"},"pair two-table diff")
    stockcols=[c["name"] for c in depot["StockAllocation"]["columns"]]
    stockrows=depot["StockAllocation"]["instances"][0]["rows"]
    target=[i for i,r in enumerate(stockrows) if r[stockcols.index("IID")] == "TEACH-LRU-01" and r[stockcols.index("STID")]=="BASE-01"]
    check(len(target)==1,"unique BASE-01 LRU stock row")
    for name in sorted(depot):
        if name not in pair_changed:check(depot[name]==forward[name],f"pair unchanged {name}")
    if target:
        i=target[0];idx=stockcols.index("STSIZ");left=stockrows[i];right=forward["StockAllocation"]["instances"][0]["rows"][i]
        check(left[idx]==0 and right[idx]==1 and all(x==y for j,(x,y) in enumerate(zip(left,right)) if j!=idx),"sole business cell STSIZ0→1")
        check(len(stockrows)==len(forward["StockAllocation"]["instances"][0]["rows"]),"no stock row added")

    report_rows={}
    for arm in ("depot_only","forward_spare"):
        ev=obs[arm]["events"];text=obs[arm]["text"]
        common=[(8,r"BASE2-MISSION.*mission starting, duration: 2.*<TEACH-AIR-01,2>"),
                (10,r"BASE2-MISSION.*mission success"),
                (11,r"System ready <TEACH-AIR-01,2>"),
                (22.24,r"RISK-MISSION.*mission aborted: <TEACH-AIR-01,0>"),
                (23.74,r"Item demand arrives.*<TEACH-LRU-01,0,[45]>"),
                (46.7231,r"RISK-MISSION.*mission aborted: <TEACH-AIR-01,1>"),
                (48.2231,r"system SURP task 20 on <TEACH-AIR-01,0> started"),
                (48.2231,r"system SURP task 21 on <TEACH-AIR-01,1> started"),
                (50.25,r"BASIC-MISSION.*mission cancelled")]
        for t,pattern in common:check(has(ev,t,pattern),f"{arm} matched event h{t} {pattern}")
        check(sum(1 for _,msg in ev if "<TEACH-LRU-01,0,BASE-01,0> Item demand arrives" in msg)==3,f"{arm} three BASE-01 LRU demands")
        check(not re.search(r"<TEACH-LRU-01,0,BASE-02,0> (Item demand arrives|Backorder added)",text),f"{arm} BASE-02 no LRU demand")
        if arm=="depot_only":
            specific=[(23.74,r"Backorder added"),(23.74,r"Take replacement item <TEACH-LRU-01,0,2> from stock"),
                      (25.74,r"Backorder removed, waiting time was 2"),(26.0733,r"system SURP task 6.*completed"),
                      (48.2231,r"Take replacement item <TEACH-LRU-01,0,3> from stock"),
                      (48.2231,r"Take replacement item <TEACH-LRU-01,0,4> from stock"),
                      (50.2231,r"Backorder removed, waiting time was 2"),
                      (51.1398,r"Put back replacement item <TEACH-LRU-01,0,6> to stock"),
                      (51.3065,r"Put back replacement item <TEACH-LRU-01,0,8> to stock")]
            check(sum(1 for _,m in ev if "<TEACH-LRU-01,0,BASE-01,0> Backorder added" in m)==3,"depot three BASE-01 backorders")
        else:
            specific=[(23.74,r"Take replacement item <TEACH-LRU-01,0,4> from stock"),
                      (23.74,r"system SURP task 6.*subitem received <TEACH-LRU-01,0,4>"),
                      (24.24,r"system SURP task 6.*completed"),
                      (25.74,r"Put back replacement item <TEACH-LRU-01,0,2> to stock"),
                      (48.2231,r"Take replacement item <TEACH-LRU-01,0,2> from stock"),
                      (48.2231,r"Backorder added"),(50.2231,r"Backorder removed, waiting time was 2"),
                      (51.1398,r"Put back replacement item <TEACH-LRU-01,0,7> to stock"),
                      (51.6398,r"Put back replacement item <TEACH-LRU-01,0,9> to stock")]
            check(sum(1 for _,m in ev if "<TEACH-LRU-01,0,BASE-01,0> Backorder added" in m)==1,"forward only one late BASE-01 backorder")
            check(not has(ev,23.74,r"<TEACH-LRU-01,0,BASE-01,0> Backorder added"),"forward first demand no local backorder")
        for t,pattern in specific:check(has(ev,t,pattern),f"{arm} physical h{t} {pattern}")
        rep=obs[arm]["report"]
        sy=rows(rep,"SystemResults","report");st=rows(rep,"StockTotalResults","report");rr=rows(rep,"ResourceResults","report")
        summ=rows(rep,"ResultSummary","report")[0];rt=rows(rep,"ResourceResultsTotal","report")[0]
        report_rows[arm]=(sy,st,rr,summ,rt)
        check(len(sy)==len(st)==len(rr)==120,f"{arm} 120 aligned bins")
        booked,waiting=resource_spans(ev)
        check(not re.search(r"<P-(CREW|MAINT) at <BASE-02,0>>.*(failed|no resources)",text),f"{arm} BASE-02 crew/maintainer available")
        backorders=[(23.74,25.74),(48.2231,50.2231),(48.2231,50.2231)] if arm=="depot_only" else [(48.2231,50.2231)]
        for i,(s,b,r) in enumerate(zip(sy,st,rr)):
            a,e=i/2,(i+1)/2
            check(s["STINT"]==b["STINT"]==r["STINT"]==a and s["ETINT"]==b["ETINT"]==r["ETINT"]==e,f"{arm} bin alignment {i}")
            check(near(s["NSYA"]+s["NSYUA"],3),f"{arm} aircraft conservation bin {i}")
            nbo=2*sum(overlap(x,y,a,e) for x,y in backorders)
            check(near(b["NBO"],nbo),f"{arm} BASE-01 backorder occupancy bin {i}")
            use=2*sum(overlap(x,y,a,e) for _,x,y in booked)
            wait=2*sum(overlap(x,y,a,e) for x,y in waiting)
            check(near(r["NRUM"],use,2e-4),f"{arm} booked resource occupancy bin {i}")
            check(near(r["NRW"],wait),f"{arm} queued resource occupancy bin {i}")
            check(r["NR"]==4,f"{arm} four workers capacity bin {i}")
        check(near(rt["NRUM"]*60,sum(y-x for _,x,y in booked)) and near(rt["NRW"]*60,sum(y-x for x,y in waiting)),f"{arm} resource integrals")
        check(summ["NREP"]==1 and summ["RTIUP"]==60 and near(summ["MSTF"],.8) and near(summ["MSUF"],.4),f"{arm} summary outcomes")
        check(near(sy[-1]["NSYRY"],3) and st[-1]["NBO"]==0 and rr[-1]["NRUM"]==0 and rr[-1]["NRW"]==0,f"{arm} terminal ready/no BO/no work")
    dsy,dst,drr,dsum,_=report_rows["depot_only"]
    fsy,fst,frr,fsum,_=report_rows["forward_spare"]
    check(dsum==fsum,"summary pair equality despite local readiness difference")
    for i,(a,b) in enumerate(zip(dst,fst)):
        if i<47 or i>102:check(a==b,f"stock parity outside observed demand bins {i}")
    check(dst[47]["NBO"]>fst[47]["NBO"],"early backorder bin discriminator")
    check(any(a!=b for a,b in zip(dsy,fsy)),"system readiness changed by forward spare")
    check(any(a!=b for a,b in zip(drr,frr)),"resource work timing changed by forward spare")
    result={"case":"F03-var02-two-base-stock-v1.0.0","passed":not failures,
        "verdict":"GO — bounded BASE-01 forward-stock comparison" if not failures else "NO-GO",
        "checks_passed":checks-len(failures),"checks_total":checks,"failures":failures,
        "evidence":{"depot_closure_sha256":sha(DEPOT/"closure.json"),"forward_closure_sha256":sha(FORWARD/"closure.json"),
                    "depot_report_sha256":sha(DEPOT/"report-raw.json"),"forward_report_sha256":sha(FORWARD/"report-raw.json"),
                    "matched_lru_demand_hours":[23.74,48.2231,48.2231],
                    "depot_only_base01_backorder_hours":6,"forward_base01_backorder_hours":2,
                    "base02_mission":"aircraft2 successful h8–10 in both"},
        "limits":["One seed, two bases and three aircraft; only BASE-01 LRU opening stock changes as a business field.",
                  "Physical item IDs differ between arms and are matched by role and event chronology, not numeric equality.",
                  "Forward opening stock also changes downstream BASIC launch timing; equal final ResultSummary does not mean equal intermediate readiness.",
                  "No BASE-02 stock demand, route contention, repair-capacity contrast or larger-network behavior is established.",
                  "Half-hour report occupancies are reconciled from printed event times within rounding tolerance; aggregate ResourceResults does not expose per-base rows."],}
    OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({k:result[k] for k in ("verdict","checks_passed","checks_total","failures")},indent=2))
    return 0 if not failures else 1


if __name__=="__main__":
    raise SystemExit(main())
