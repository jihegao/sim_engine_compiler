"""Independent read-only F02.var03 maintainer-capacity raw evidence replay."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
BASE=CASE.parent
PARENT=BASE/"F02-var01-var02-integrated-fleet-v1.0.2"
PRUN=PARENT/"runs/f02-pair-v102-risk-ssh-20261004-01"
RUN=CASE/"runs/f02-var03-pmaint2-v100-ssh-20261004-01"
OUT=CASE/"review/independent-verdict.json"
total=0
fail=[]


def ck(ok,label):
    global total
    total+=1
    if not ok:fail.append(label)


def h(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def j(path):return json.loads(re.sub(r",\s*([}\]])",r"\1",path.read_text(encoding="utf-8-sig")))


def ts(doc,root):return {t["name"]:t for t in doc[root]["tables"]}


def rs(t):return [r for ins in t["instances"] for r in ins["rows"]]


def cs(t):return [c["name"] for c in t["columns"]]


def near(a,b,label,tol=.0003):
    if a is None and b==0:a=0
    ck(isinstance(a,(float,int)) and abs(a-b)<=tol,f"{label}: {a} versus {b}")


def occ(a,b,spans):return sum(max(0,min(b,y)-max(a,x))/(b-a) for x,y in spans)


def ev(lines,time,phrase,arm):
    ck(any((m:=re.match(r"Time: ([\d.e+\-]+) (.*)",s)) and
           abs(float(m[1])-time)<.00011 and phrase in m[2] for s in lines),
       f"{arm} event {time}: {phrase}")


contract=j(CASE/"contract.json")
diff=j(CASE/"exact-diff.json")
parent_source=PARENT/"risk-input.json"
child_source=CASE/"no-conflict-input.json"
pinpaths={
    "input":child_source,"parent":parent_source,
    "parent_closure":PRUN/"closure.json",
    "parent_evidence_index":PARENT/"evidence-index.json",
    "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
    "build.py":CASE/"build.py","describe_diff.py":CASE/"describe_diff.py",
    "check_roundtrip.py":CASE/"check_roundtrip.py",
    "run_native_ssh.ps1":CASE/"run_native_ssh.ps1",
}
closure=j(RUN/"closure.json")
inv=j(RUN/"invocation.json")
steps=j(RUN/"steps.json")
ck(closure["source_hashes_before"]==closure["source_hashes_after"],"source stability")
ck(inv["source_hashes_before"]==closure["source_hashes_before"],"invocation source pins")
for key,path in sorted(pinpaths.items()):
    ck(path.is_file(),f"source exists {key}")
    if path.is_file():ck(h(path)==closure["source_hashes_before"][key],f"source SHA {key}")
ck(h(child_source)==contract["no_conflict_input_sha256"],"contract child pin")
ck(h(parent_source)==contract["accepted_parent"]["input_sha256"],"contract parent pin")
ck(h(CASE/"exact-diff.json")==contract["exact_diff_sha256"],"contract diff pin")
ck(h(RUN/"input.json")==h(child_source),"run input copied from frozen source")
ck(h(RUN/"invocation.json")==closure["invocation_sha256"],"invocation SHA")
ck(len(closure["raw"])==12,"12 raw seals")
for name,seal in sorted(closure["raw"].items()):
    path=RUN/name
    ck(path.is_file(),f"raw exists {name}")
    if path.is_file():
        ck(path.stat().st_size==seal["bytes"],f"raw bytes {name}")
        ck(h(path)==seal["sha256"],f"raw SHA {name}")
ck(closure["error"] is None and closure["run_id"]==RUN.name,"closed native run")
ck(inv["session_id"]==0 and "sshd.exe" in inv["ssh_ancestor_names"],"SSH session zero")
ck(inv["queue_mutex"]=="Global\\SimloxIssue18NativeQueue","native queue mutex")
ck(inv["gui"]["pid"]==13340 and inv["gui"]["session_id"]==1,"separate GUI preserved")
ck([s["name"] for s in steps]==
   ["import","export","calc","jsonreport","check_import_export"],"guarded five steps")
for s in steps:
    ck(s["status"]=="completed" and s["exit_code"]==0,f"step {s['name']}")
for s in steps[:4]:ck(s["gui_preserved"] is True,f"native GUI guard {s['name']}")

parent=ts(j(parent_source),"model")
child=ts(j(child_source),"model")
export=ts(j(RUN/"roundtrip-raw.json"),"model")
ck(diff["parent_input_sha256"]==h(parent_source),"exact diff parent")
ck(diff["no_conflict_input_sha256"]==h(child_source),"exact diff child")
differences=[]
for name in sorted(set(parent)|set(child)):
    a,b=parent.get(name),child.get(name)
    if a is None or b is None:
        if a!=b:differences.append((name,None,None,None,None))
        continue
    ck(cs(a)==cs(b),f"unchanged table schema {name}")
    ar,br=rs(a),rs(b)
    ck(len(ar)==len(br),f"unchanged row count {name}")
    for i,(x,y) in enumerate(zip(ar,br)):
        for k,(u,v) in enumerate(zip(x,y)):
            if u!=v:differences.append((name,i,cs(a)[k],u,v))
ck(differences==[("ResourceAllocation",0,"RQTY",1,2)],"sole RQTY1 to2 cell")
ck(diff["changed_cells"]==[{"table":"ResourceAllocation","row":0,
    "column":"RQTY","before":1,"after":2}],"frozen diff describes exact cell")
authored=sorted(name for name in child if rs(child[name]))
ck(len(authored)==30,"30 row-containing business tables")
for name in authored:
    ck(name in export,f"native export has {name}")
    if name in export:
        ac,ec=cs(child[name]),cs(export[name])
        ck(all(c in ec for c in ac),f"roundtrip columns {name}")
        if all(c in ec for c in ac):
            ck([[r[ec.index(c)] for c in ac] for r in rs(export[name])]==rs(child[name]),
               f"roundtrip authored rows {name}")
runlog=(RUN/"run.log").read_text(encoding="utf-8-sig")
ck("Errors: 0, Warnings: 1, Notes: 0" in runlog,"converter counts")
ck(set(re.findall(r"\((?:warning|notice|error) #(\d+)\)",runlog))=={"108"},
   "converter diagnostic #108 only")
ck((RUN/"model.sxo").stat().st_size>4,"usable simulation SXO")

plines=(PRUN/"model.log").read_text(encoding="utf-8-sig").splitlines()
lines=(RUN/"model.log").read_text(encoding="utf-8-sig").splitlines()
for arm,l in (("parent",plines),("child",lines)):
    for t,phrase in [
        (21.5,"<RISK-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2"),
        (23.5,"<RISK-MISSION,TEACH-UNIT,0,0,0> mission completed"),
        (25.5,"<BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2"),
        (27.5,"<BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed"),
        (45.5,"<RISK-MISSION,TEACH-UNIT,0,0,2> mission starting, duration: 2"),
        (46.4896,"<TEACH-AIR-01,0> critical random failure added"),
        (46.4896,"<RISK-MISSION,TEACH-UNIT,0,0,2> mission aborted"),
        (50.25,"<BASIC-MISSION,TEACH-UNIT,0,0,3> mission cancelled"),
        (47.9896,"<TEACH-LRU-01,0,BASE-01,0> Backorder added"),
        (47.9896,"Take replacement item <TEACH-LRU-01,0,2> from stock"),
        (47.9896,"transport task 0 starts with 1 items/systems, transport time: 2"),
        (48.1563,"transport task 2 starts with 1 items/systems, transport time: 2"),
        (49.9896,"transport task 0 arrives with 1 items/systems"),
        (49.9896,"<TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 2"),
        (50.1563,"transport task 2 arrives with 1 items/systems"),
        (50.1563,"item SURP task 16 on <TEACH-LRU-01,0,4> started"),
        (50.1563,"Take replacement item <TEACH-SRU-01,0,0> from stock"),
        (50.3229,"system SURP task 14 on <TEACH-AIR-01,0> completed"),
        (50.5313,"item DIRP task 18 on <TEACH-SRU-01,0,5> started"),
        (50.9063,"Put back replacement item <TEACH-LRU-01,0,4> to stock"),
        (51.5313,"Put back replacement item <TEACH-SRU-01,0,5> to stock"),
    ]:ev(l,t,phrase,arm)
    ck(sum("Backorder added" in s for s in l)==1,f"{arm} one LRU BO")
    ck(sum("Backorder removed" in s for s in l)==1,f"{arm} BO clears")
    for physical in (
        "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-LRU-01,0,3>,<TEACH-LRU-01,0,4>",
        "Stock at: <TEACH-SRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-SRU-01,0,1>,<TEACH-SRU-01,0,5>",
    ):
        ck(any(physical in s for s in l),f"{arm} terminal physical stock {physical}")
ev(plines,28.5,"<P-MAINT at <BASE-01,0>> allocated to maintenance task: 1  available now: 0","parent")
ev(plines,29.5,"<P-MAINT at <BASE-01,0>> allocated to maintenance task: 1  available now: 0","parent")
ev(plines,29.5,"system PM task 4 on <TEACH-AIR-01,0> completed","parent")
ev(plines,30.5,"system PM task 6 on <TEACH-AIR-01,1> completed","parent")
ev(lines,28.5,"<P-MAINT at <BASE-01,0>> allocated to maintenance task: 1  available now: 1","child")
ev(lines,28.5,"<P-MAINT at <BASE-01,0>> allocated to maintenance task: 1  available now: 0","child")
ev(lines,29.5,"system PM task 4 on <TEACH-AIR-01,0> completed","child")
ev(lines,29.5,"system PM task 6 on <TEACH-AIR-01,1> completed","child")
for task,air in [(19,1),(20,0)]:
    ev(lines,53.5,f"system PM task {task} on <TEACH-AIR-01,{air}> PMID: CAL24","child")
    ev(lines,54.5,f"system PM task {task} on <TEACH-AIR-01,{air}> completed","child")
ck(sum("<P-MAINT at <BASE-01,0>> allocated to maintenance task" in s for s in lines)==6,
   "child six maintainer task allocations")
ck(sum("<P-CREW at <BASE-01,0>> allocated to maintenance task" in s for s in lines)==7,
   "child same seven crew allocations")
for at in (21,25,45):
    ev(lines,at,"<P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0",
       "child queued crew")

preport=ts(j(PRUN/"report-raw.json"),"report")
report=ts(j(RUN/"report-raw.json"),"report")
ck(set(report)==set(preport),"report tables same")
ck(rs(report["ProblemDescription"])==rs(child["ProblemDescription"]),"report description")
for name in ("ResultSummary","StockTotalResults"):
    ck(rs(report[name])==rs(preport[name]),f"{name} parent parity")
for name in ("SystemResults","StockTotalResults","ResourceResults"):
    ck(len(rs(report[name]))==120,f"120 {name} bins")
parent_sr,child_sr=rs(preport["SystemResults"]),rs(report["SystemResults"])
parent_st,child_st=rs(preport["StockTotalResults"]),rs(report["StockTotalResults"])
pc,sc=cs(preport["SystemResults"]),cs(report["SystemResults"])
tc=cs(report["StockTotalResults"])
ck(pc==sc,"same system report columns")
pm_parent=[(28.5,29.5),(29.5,30.5),(53.5,54.5),(54.5,55.5)]
pm_child=[(28.5,29.5),(28.5,29.5),(53.5,54.5),(53.5,54.5)]
pm_affected={"NSYRY","NSYUA","NSYA","NSYPM","NPMT","NPMS","SYDT","NSYDT"}
for i,(pr,cr,ps,st) in enumerate(zip(parent_sr,child_sr,parent_st,child_st)):
    a,b=i*.5,(i+1)*.5
    for row,label in ((pr,"parent system"),(cr,"child system"),(st,"child stock")):
        c=pc if "system" in label else tc
        near(row[c.index("STINT")],a,f"{label} bin {i} start")
        near(row[c.index("ETINT")],b,f"{label} bin {i} end")
    ck(ps==st,f"stock row parity {i}")
    pmap,cmap=dict(zip(pc,pr)),dict(zip(sc,cr))
    for col in sc:
        if col in ("UNID","SID","STINT","ETINT"):continue
        if col not in pm_affected:
            near(cmap[col],pmap[col],f"system unchanged {i} {col}")
    pwork,cwork=occ(a,b,pm_parent),occ(a,b,pm_child)
    near(pmap["NSYPM"],pwork,f"parent bin {i} PM occupancy")
    near(cmap["NSYPM"],cwork,f"child bin {i} PM occupancy")
    near(cmap["NSYUA"],(pmap["NSYUA"] or 0)-pwork+cwork,
         f"child bin {i} unavailable PM substitution")
    near(cmap["NSYA"],(pmap["NSYA"] or 0)+pwork-cwork,
         f"child bin {i} available PM substitution")
    near(cmap["NSYRY"],(pmap["NSYRY"] or 0)+pwork-cwork,
         f"child bin {i} ready PM substitution")
    for col,expected in {
        "NPMT":(2 if i in (59,109) else 0),
        "NPMS":(2 if i in (48,107) else 0),
        "NSYDT":(2 if i in (57,107) else (1 if i==95 else 0)),
        "SYDT":(1 if i in (57,107) else (2.333333333 if i==95 else 0)),
    }.items():near(cmap[col],expected,f"child bin {i} {col}")
ck(child_sr[-1][sc.index("NSYRY")] == 2,"terminal two aircraft ready")
ck(child_st[-1][tc.index("NBO")] == 0,"terminal no stock backorder")

# Replay pooled workers from each native allocation/deallocation event.  Multiple
# simultaneous P-MAINT bookings are legal in this arm and must be counted twice.
def bookings(lines):
    counts={"P-MAINT":0,"P-CREW":0}
    starts={"P-MAINT":None,"P-CREW":None}
    spans={"P-MAINT":[],"P-CREW":[]}
    for line in lines:
        m=re.match(r"Time: ([\d.e+\-]+)  <(P-MAINT|P-CREW) at <BASE-01,0>> "
                   r"(allocated to maintenance task|deallocated from  maintenance task)",line)
        if not m:continue
        t=float(m[1]);person=m[2];action=m[3]
        if starts[person] is not None and t>starts[person]:
            spans[person].append((starts[person],t,counts[person]))
        counts[person]+=1 if action.startswith("allocated") else -1
        ck(0<=counts[person]<= (2 if person=="P-MAINT" else 1),
           f"resource capacity {person} at {t}")
        starts[person]=t if counts[person] else None
    ck(all(x==0 for x in counts.values()),"all resource leases released")
    return spans

spans=bookings(lines)
resource=report["ResourceResults"]
parent_resource=preport["ResourceResults"]
rr,prr=rs(resource),rs(parent_resource)
rc=cs(resource)
ck(rc==cs(parent_resource),"resource columns same")
crew_wait=[(20.5,21),(24.5,25),(44.5,45)]
for i,(r,p) in enumerate(zip(rr,prr)):
    a,b=i*.5,(i+1)*.5
    rm,pm=dict(zip(rc,r)),dict(zip(rc,p))
    near(rm["STINT"],a,f"resource bin {i} start")
    near(rm["ETINT"],b,f"resource bin {i} end")
    busy=sum(q*occ(a,b,[(x,y)]) for v in spans.values() for x,y,q in v)
    near(rm["NRUM"],busy,f"resource bin {i} event bookings")
    near(rm["NRW"],occ(a,b,crew_wait),f"resource bin {i} crew wait")
    for col in rc:
        if col in ("RID","STID","STINT","ETINT","NRUM","NRW"):continue
        near(rm[col],3 if col in ("NR","NRA","NRN") else 0,
             f"resource bin {i} {col}")
    for col in ("NRMO","NRMA","NRLA","NRF","NRRI","NRRT","NRRO"):
        near(rm[col],pm[col],f"resource unchanged {i} {col}")
near(sum((r[rc.index("NRUM")] or 0)*.5 for r in rr),8,"eight worker-hours")
near(sum((r[rc.index("NRW")] or 0)*.5 for r in rr),1.5,"crew-only waiting 1.5h")
totalres=dict(zip(cs(report["ResourceResultsTotal"]),rs(report["ResourceResultsTotal"])[0]))
near(totalres["NR"],3,"resource total three")
near(totalres["NRUM"],8/60,"resource total busy fraction")
near(totalres["NRW"],1.5/60,"resource total wait fraction")
near(rr[-1][rc.index("NRUM")],0,"terminal no worker booked")

verdict={
    "case":"F02.var03 maintainer capacity v1.0.0",
    "passed":not fail,"verdict":"GO: bounded P-MAINT capacity observation" if not fail else "NO-GO",
    "checks_passed":total-len(fail),"checks_total":total,"failures":fail,
    "child_closure_sha256":h(RUN/"closure.json"),
    "child_report_sha256":h(RUN/"report-raw.json"),
    "parent_closure_sha256":h(PRUN/"closure.json"),
    "limits":[
        "Only one seed, two aircraft, one base and depot, one P-CREW pool and a 60-hour horizon.",
        "The isolated RQTY1→2 change removes observed first-day PM worker waiting; P-CREW preparation waiting remains.",
        "Second-day PM also overlaps under two workers in this realized run, but was not a preset contention gate.",
        "Mission, fault, depot transport, item repair and StockTotalResults paths are event-matched; no generic capacity law or larger-fleet conclusion.",
        "ResourceResults.NRA is not treated as free-worker complement; bookings and NRUM establish worker occupancy.",
    ],
}
OUT.write_bytes((json.dumps(verdict,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8"))
print(json.dumps({"passed":verdict["passed"],"checks":total,"failures":fail[:25],
                  "script_sha256":h(Path(__file__)),"verdict_sha256":h(OUT)},sort_keys=True))
raise SystemExit(0 if verdict["passed"] else 1)
