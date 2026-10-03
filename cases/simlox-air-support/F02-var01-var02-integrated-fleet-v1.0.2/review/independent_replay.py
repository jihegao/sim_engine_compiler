"""Independent read-only F02.var01/var02 replay using standard-library raw parsing."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
BASE = CASE.parent
OUT = CASE / "review/independent-verdict.json"
RUNS = {
    "deterministic": CASE / "runs/f02-pair-v102-det-ssh-20261004-01",
    "risk": CASE / "runs/f02-pair-v102-risk-ssh-20261004-01",
}
checks = 0
errors = []


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        errors.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def table_map(document, root):
    return {x["name"]: x for x in document[root]["tables"]}


def rows(table):
    return [row for inst in table["instances"] for row in inst["rows"]]


def cols(table):
    return [x["name"] for x in table["columns"]]


def close(actual, expected, label, tol=.0003):
    if actual is None and expected == 0:
        actual = 0
    check(isinstance(actual,(int,float)) and abs(actual-expected) <= tol,
          f"{label}: {actual} vs {expected}")


def overlap(a,b,intervals):
    return sum(max(0,min(b,y)-max(a,x))/(b-a) for x,y in intervals)


def timed_event(lines, time, snippet):
    return any((m := re.match(r"Time: ([\d.e+\-]+) (.*)",line)) and
               abs(float(m[1])-time) <= .00011 and snippet in m[2] for line in lines)


def event(lines, time, snippet, arm):
    check(timed_event(lines,time,snippet),f"{arm} event {time} {snippet}")


contract = read(CASE / "contract.json")
diff = read(CASE / "exact-diff.json")
source_paths = {
    "deterministic": CASE / "deterministic-input.json",
    "risk": CASE / "risk-input.json",
    "contract": CASE / "contract.json",
    "exact_diff": CASE / "exact-diff.json",
    "D05": BASE / "D05-maintenance-competition-v1.0.0/native-input.json",
    "F01": BASE / "F01-var01-two-three-level-v1.0.1/three-level-input.json",
    "A04": BASE / "A04-two-day-formation-v1.0.0/native-input.json",
    "B04": BASE / "B04-cross-midnight-turnround-v1.0.1/turnround-input.json",
    "C03": BASE / "C03-shared-crew-formation-v1.0.2/inputs/staffing-1.json",
    "E04": BASE / "E04-upstream-transport-fast-v1.0.0/native-input.json",
    "build.py": CASE / "build.py",
    "describe_diff.py": CASE / "describe_diff.py",
    "check_roundtrip.py": CASE / "check_roundtrip.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
for key,path in sorted(source_paths.items()):
    check(path.is_file(),f"source exists {key}")
    if path.is_file():
        check(sha(path) == read(RUNS["risk"] / "closure.json")["source_hashes_before"][key],
              f"frozen source SHA {key}")
check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"],"contract diff pin")
for key,path in [("deterministic","F02.var01_deterministic"),("risk","F02.var02_risk")]:
    check(sha(source_paths[key]) == contract["inputs_sha256"][path],f"contract input {key}")
check(diff["parent"]["sha256"] == sha(source_paths["D05"]),"D05 direct parent pin")

parent=table_map(read(source_paths["D05"]),"model")
sources={arm:table_map(read(path),"model") for arm,path in source_paths.items() if arm in RUNS}
for arm,source in sources.items():
    changed={name for name in set(source)|set(parent) if
             (rows(source[name]) if name in source else []) !=
             (rows(parent[name]) if name in parent else [])}
    check(changed == set(diff["arms"][arm]["changed_tables"]), f"{arm} exact parent table set")
    for name,delta in sorted(diff["arms"][arm]["changed_tables"].items()):
        check(delta["before"] == (rows(parent[name]) if name in parent else None),
              f"{arm} parent rows {name}")
        check(delta["after"] == (rows(source[name]) if name in source else []),
              f"{arm} child rows {name}")
    check(len([name for name in source if rows(source[name])]) == 30,
          f"{arm} 30 authored row-containing tables")

pair=[]
for name in sorted(set(sources["risk"])|set(sources["deterministic"])):
    a=sources["deterministic"].get(name)
    b=sources["risk"].get(name)
    if a!=b:
        check(name == "MissionType",f"pair table isolation {name}")
        if a and b:
            ac,bc=cols(a),cols(b)
            for i,(ar,br) in enumerate(zip(rows(a),rows(b))):
                for col in ac:
                    if ar[ac.index(col)] != br[bc.index(col)]:
                        pair.append({"table":name,"row":i,"column":col,
                                     "deterministic":ar[ac.index(col)],"risk":br[bc.index(col)]})
check(pair == diff["paired_differences"],"pair exact MFF-only cell")
check(pair == [{"table":"MissionType","row":1,"column":"MFF",
                "deterministic":0.0,"risk":1.0}],"MFF boundary zero versus one")

observed={}
for arm,run in RUNS.items():
    closure=read(run/"closure.json")
    invocation=read(run/"invocation.json")
    steps=read(run/"steps.json")
    check(closure["source_hashes_before"] == closure["source_hashes_after"],f"{arm} stable sources")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"],
          f"{arm} invocation sources")
    for key,path in sorted(source_paths.items()):
        check(closure["source_hashes_before"][key] == sha(path),f"{arm} source SHA {key}")
    check(sha(run/"invocation.json") == closure["invocation_sha256"],f"{arm} invocation SHA")
    check(sha(run/"input.json") == sha(source_paths[arm]),f"{arm} native input SHA")
    check(len(closure["raw"]) == 12,f"{arm} 12 raw seals")
    for filename,seal in sorted(closure["raw"].items()):
        path=run/filename
        check(path.is_file(),f"{arm} raw {filename}")
        if path.is_file():
            check(path.stat().st_size == seal["bytes"],f"{arm} size {filename}")
            check(sha(path) == seal["sha256"],f"{arm} SHA {filename}")
    check(closure["error"] is None and closure["run_id"] == run.name,f"{arm} closed run")
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"],
          f"{arm} session-zero SSH")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue",f"{arm} mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
          f"{arm} separate preserved GUI")
    check([s["name"] for s in steps] ==
          ["import","export","calc","jsonreport","check_import_export"],f"{arm} five steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0,
              f"{arm} step {step['name']}")
    for step in steps[:4]:
        check(step["gui_preserved"] is True,f"{arm} GUI guard {step['name']}")
    export=table_map(read(run/"roundtrip-raw.json"),"model")
    for name in sorted(name for name in sources[arm] if rows(sources[arm][name])):
        check(name in export,f"{arm} roundtrip table {name}")
        if name in export:
            authored=cols(sources[arm][name]); exported=cols(export[name])
            check(all(col in exported for col in authored),f"{arm} columns {name}")
            if all(col in exported for col in authored):
                projected=[[row[exported.index(col)] for col in authored] for row in rows(export[name])]
                check(projected == rows(sources[arm][name]),f"{arm} exact rows {name}")
    log=(run/"run.log").read_text(encoding="utf-8-sig")
    check("Errors: 0, Warnings: 1, Notes: 0" in log,f"{arm} converter counts")
    check(set(re.findall(r"\((?:warning|error|notice) #(\d+)\)",log)) == {"108"},
          f"{arm} exact diagnostic set")
    check((run/"model.sxo").stat().st_size > 4,f"{arm} valid SXO")
    ev=(run/"model.log").read_text(encoding="utf-8-sig").splitlines()
    report=table_map(read(run/"report-raw.json"),"report")
    check(set(report) == {"ProblemDescription","ResultSummary","SystemResults",
                          "StockTotalResults","ResourceResults","ResourceResultsTotal"},
          f"{arm} report tables")
    for name in ("SystemResults","StockTotalResults","ResourceResults"):
        check(len(rows(report[name])) == 120,f"{arm} 120 {name} bins")
    check(rows(report["ProblemDescription"]) == rows(sources[arm]["ProblemDescription"]),
          f"{arm} report description")
    sm=dict(zip(cols(report["ResultSummary"]),rows(report["ResultSummary"])[0]))
    for key,value in {"NREP":1,"RTILW":0,"RTIUP":60}.items():
        close(sm[key],value,f"{arm} summary {key}")
    observed[arm]={"events":ev,"report":report,"summary":sm,"closure":closure}

for arm,ob in observed.items():
    lines=ob["events"]
    # Four group orders, each requiring both distinct aircraft.
    orders=[(20.5,"RISK-MISSION",0),(23.75,"BASIC-MISSION",1),
            (44.5,"RISK-MISSION",2),(47.75,"BASIC-MISSION",3)]
    for at,typ,mid in orders:
        event(lines,at,f"<{typ},TEACH-UNIT,0,0,{mid}> mission created",arm)
    for at,typ,mid in [(21.5,"RISK-MISSION",0),(25.5,"BASIC-MISSION",1),
                       (45.5,"RISK-MISSION",2)]:
        event(lines,at,f"<{typ},TEACH-UNIT,0,0,{mid}> mission starting, duration: 2 : "
              "<TEACH-AIR-01,0>,<TEACH-AIR-01,1>",arm)
    for at,typ,mid in [(23.5,"RISK-MISSION",0),(27.5,"BASIC-MISSION",1)]:
        event(lines,at,f"<{typ},TEACH-UNIT,0,0,{mid}> mission completed: "
              "<TEACH-AIR-01,0>,<TEACH-AIR-01,1>",arm)
    for at,air,task in [(24.5,0,4),(24.5,1,6)]:
        event(lines,at,f"system PM task {task} on <TEACH-AIR-01,{air}> PMID: CAL24",arm)
    for at,air,task in [(29.5,0,4),(30.5,1,6)]:
        event(lines,at,f"system PM task {task} on <TEACH-AIR-01,{air}> completed",arm)
    for at,air in [(20.5,0),(20.5,1),(24.5,0),(24.5,1),(44.5,0),(44.5,1)]:
        event(lines,at,f"<TEACH-AIR-01,{air}> preparation started",arm)
    check(sum("<P-CREW at <BASE-01,0>> allocated to maintenance task" in s for s in lines) ==
          (8 if arm=="deterministic" else 7),f"{arm} shared crew allocations")
    check(sum("<P-MAINT at <BASE-01,0>> allocated to maintenance task" in s for s in lines) ==
          (4 if arm=="deterministic" else 6),f"{arm} maintainer allocations")
    check(not any("<P-CREW" in s and "system PM task" in s for s in lines),
          f"{arm} crew not used for PM")

det=observed["deterministic"]
risk=observed["risk"]
dlines=det["events"]
rlines=risk["events"]
check(not any("random failure added" in s for s in dlines),"deterministic no stochastic fault")
for t,kind,mid in [(47.5,"RISK-MISSION",2),(51.5,"BASIC-MISSION",3)]:
    event(dlines,t,f"<{kind},TEACH-UNIT,0,0,{mid}> mission completed", "deterministic")
for at,air,task in [(53.5,0,18),(54.5,1,19)]:
    event(dlines,at,f"system PM task {task} on <TEACH-AIR-01,{air}> PMID: CAL24",
          "deterministic")
for at,air,task in [(54.5,0,18),(55.5,1,19)]:
    event(dlines,at,f"system PM task {task} on <TEACH-AIR-01,{air}> completed",
          "deterministic")
event(rlines,46.4896,"<TEACH-AIR-01,0> critical random failure added","risk")
event(rlines,46.4896,"<RISK-MISSION,TEACH-UNIT,0,0,2> mission aborted","risk")
event(rlines,46.9896,"<RISK-MISSION,TEACH-UNIT,0,0,2> aborted mission completed","risk")
event(rlines,50.25,"<BASIC-MISSION,TEACH-UNIT,0,0,3> mission cancelled","risk")
for at,air,task in [(53.5,0,19),(54.5,1,20)]:
    event(rlines,at,f"system PM task {task} on <TEACH-AIR-01,{air}> PMID: CAL24","risk")
for at,air,task in [(54.5,0,19),(55.5,1,20)]:
    event(rlines,at,f"system PM task {task} on <TEACH-AIR-01,{air}> completed","risk")
# One failed installed LRU and SRU, physical depot spare ID2, two 2h legs, nested repair.
physical=[
    (47.9896,"<TEACH-LRU-01,0,BASE-01,0> Backorder added"),
    (47.9896,"Take replacement item <TEACH-LRU-01,0,2> from stock"),
    (47.9896,"transport task 0 starts with 1 items/systems, transport time: 2"),
    (48.1563,"transport task 2 starts with 1 items/systems, transport time: 2"),
    (49.9896,"transport task 0 arrives with 1 items/systems"),
    (49.9896,"<TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 2"),
    (49.9896,"system SURP task 14 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,2>"),
    (50.1563,"transport task 2 arrives with 1 items/systems"),
    (50.1563,"item SURP task 16 on <TEACH-LRU-01,0,4> started"),
    (50.1563,"Take replacement item <TEACH-SRU-01,0,0> from stock"),
    (50.3229,"system SURP task 14 on <TEACH-AIR-01,0> completed"),
    (50.5313,"item DIRP task 18 on <TEACH-SRU-01,0,5> started"),
    (50.9063,"item SURP task 16 on <TEACH-LRU-01,0,4> completed"),
    (50.9063,"Put back replacement item <TEACH-LRU-01,0,4> to stock"),
    (51.5313,"item DIRP task 18 on <TEACH-SRU-01,0,5> completed"),
    (51.5313,"Put back replacement item <TEACH-SRU-01,0,5> to stock"),
]
for t,s in physical:
    event(rlines,t,s,"risk")
event(rlines,47.9896,
      "transport request <<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,DEPOT-01,0>,"
      "<TEACH-LRU-01,0,BASE-01,0>> attached to  transport task 0","risk")
event(rlines,48.1563,
      "transport request <<TEACH-LRU-01,0,4>,<TEACH-LRU-01,0,BASE-01,0>,"
      "<TEACH-LRU-01,0,DEPOT-01,0>> attached to  transport task 2","risk")
for phrase in (
    "Stock at: <TEACH-SRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-SRU-01,0,0>,<TEACH-SRU-01,0,1>",
    "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,3>",
    "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:",
    "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-LRU-01,0,3>,<TEACH-LRU-01,0,4>",
    "Stock at: <TEACH-SRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-SRU-01,0,1>,<TEACH-SRU-01,0,5>",
):
    check(any(phrase in s for s in rlines),f"risk physical stock ledger {phrase}")
event(rlines,55.5,"systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>","risk")
close(49.9896-47.9896,2,"risk downward LRU transport hours")
close(50.1563-48.1563,2,"risk upward failed LRU transport hours")
close(50.9063-50.1563,.75,"risk depot LRU/SRU replacement hours")
close(51.5313-50.5313,1,"risk depot SRU direct repair hours")
check(sum("Backorder added" in s for s in rlines)==1,"risk one event-log backorder")
check(sum("Backorder removed" in s for s in rlines)==1,"risk one cleared backorder")
check(not any("Backorder added" in s for s in dlines),"deterministic no backorder")
check(not any("transport task" in s for s in dlines),"deterministic no depot transport")
for arm,ob in observed.items():
    lines=ob["events"]
    rep=ob["report"]
    st=rep["SystemResults"]
    stk=rep["StockTotalResults"]
    res=rep["ResourceResults"]
    sc,tc,rc=cols(st),cols(stk),cols(res)
    sr,tr,rr=rows(st),rows(stk),rows(res)
    summary=ob["summary"]
    for key,val in ({"MTMF":1,"MSTF":1,"MSUF":1} if arm=="deterministic" else
                    {"MTMF":.6862013936042786,"MSTF":.75,"MSUF":.5}).items():
        close(summary[key],val,f"{arm} summary {key}")
    # Physical flight status persists through the abort return interval.
    flight=[(21.5,23.5,2),(25.5,27.5,2)]
    flight += ([(45.5,47.5,2),(49.5,51.5,2)] if arm=="deterministic"
               else [(45.5,46.9896,2)])
    lease={"P-CREW":[],"P-MAINT":[]}
    starts={}
    for line in lines:
        m=re.match(r"Time: ([\d.e+\-]+)  <(P-CREW|P-MAINT) at <BASE-01,0>> "
                   r"(allocated to maintenance task|deallocated from  maintenance task)",line)
        if m:
            t=float(m[1]); person=m[2]; action=m[3]
            if action.startswith("allocated"):
                check(person not in starts,f"{arm} no double booking {person} at {t}")
                starts[person]=t
            else:
                check(person in starts,f"{arm} matching release {person} at {t}")
                if person in starts:
                    lease[person].append((starts.pop(person),t))
    check(not starts,f"{arm} no unreleased worker")
    close(sum(b-a for v in lease.values() for a,b in v),8,f"{arm} eight worker-hours")
    phases={"preparation":[],"turnround":[]}
    phase_starts={}
    for line in lines:
        m=re.match(r"Time: ([\d.e+\-]+) <TEACH-AIR-01,(\d)> "
                   r"(preparation|turnround) (started|ended), mission:",line)
        if not m:
            continue
        t=float(m[1]); system=int(m[2]); kind=m[3]; action=m[4]
        key=(kind,system)
        if action=="started":
            check(key not in phase_starts,f"{arm} unique active {kind} {system}")
            phase_starts[key]=t
        else:
            check(key in phase_starts,f"{arm} {kind} {system} has start")
            if key in phase_starts:
                phases[kind].append((phase_starts.pop(key),t))
    check(not phase_starts,f"{arm} all preparation/turnround intervals closed")
    check(len(phases["preparation"]) == (8 if arm=="deterministic" else 7),
          f"{arm} individual preparation count")
    check(len(phases["turnround"]) == (8 if arm=="deterministic" else 7),
          f"{arm} individual turnround count")
    pm_work=[(28.5,29.5),(29.5,30.5),(53.5,54.5),(54.5,55.5)]
    repair_work=[] if arm=="deterministic" else [(47.9896,48.1563),(49.9896,50.3229)]
    repair_wait=[] if arm=="deterministic" else [(48.1563,49.9896)]
    worker_wait=[(20.5,21),(24.5,25),(28.5,29.5),(44.5,45)]
    if arm=="deterministic":
        worker_wait.append((48.5,49))
    markers={
        "NPMT":{59:1,61:1,109:1,111:1},
        "NPMS":{48:2,107:1,109:1},
        "NPSTA":({41:2,49:2,89:2,97:2} if arm=="deterministic" else
                  {41:2,49:2,89:2,95:1}),
        "NPSUC":({42:1,43:1,50:1,51:1,90:1,91:1,98:1,99:1} if
                   arm=="deterministic" else
                   {42:1,43:1,50:1,51:1,90:1,91:1,96:1}),
        "NREPT":({} if arm=="deterministic" else {100:1}),
        "NFAIL":({} if arm=="deterministic" else {92:1}),
        "NSYDT":({57:1,59:1,107:1,109:1} if arm=="deterministic" else
                  {57:1,59:1,95:1,107:1,109:1}),
        "SYDT":({57:1,59:1,107:1,109:1} if arm=="deterministic" else
                {57:1,59:1,95:2.3333333,107:1,109:1}),
    }
    system_derived={"NSYRY","NSYMA","NSYMO","NSYMP","NSYMT","NSYMR","NSYUA",
                    "NSYA","FTMO","NSYRP","NSYPM","NSYWI","STACC"}
    for i,(srow,trow,rrow) in enumerate(zip(sr,tr,rr)):
        a,b=.5*i,.5*(i+1)
        sm,tm,rm=dict(zip(sc,srow)),dict(zip(tc,trow)),dict(zip(rc,rrow))
        for label,record in (("system",sm),("stock",tm),("resource",rm)):
            close(record["STINT"],a,f"{arm} {label} bin {i} start")
            close(record["ETINT"],b,f"{arm} {label} bin {i} end")
        expected_flight=sum(overlap(a,b,[(x,y)])*count for x,y,count in flight)
        close(sm["NSYMO"],expected_flight,f"{arm} bin {i} operating aircraft")
        close(sm["STACC"],expected_flight,f"{arm} bin {i} operating accumulation")
        close(sm["FTMO"],expected_flight/2,f"{arm} bin {i} formation flight")
        close(sm["NSYA"],2-(sm["NSYUA"] or 0),f"{arm} bin {i} available aircraft")
        close((sm["NSYRY"] or 0)+(sm["NSYMA"] or 0)+(sm["NSYUA"] or 0),
              2,f"{arm} bin {i} aircraft conservation")
        close(sm["NSYMP"],overlap(a,b,phases["preparation"]),
              f"{arm} bin {i} preparation occupancy")
        close(sm["NSYMT"],overlap(a,b,phases["turnround"]),
              f"{arm} bin {i} turnround occupancy")
        close(sm["NSYPM"],overlap(a,b,pm_work),f"{arm} bin {i} PM work occupancy")
        close(sm["NSYRP"],overlap(a,b,repair_work),f"{arm} bin {i} system repair work")
        close(sm["NSYWI"],overlap(a,b,repair_wait),f"{arm} bin {i} part wait")
        close(sm["NSYUA"],sum((sm[col] or 0) for col in ("NSYPM","NSYRP","NSYWI")),
              f"{arm} bin {i} unavailable component sum")
        close(sm["NSYMA"],sum((sm[col] or 0) for col in
              ("NSYMP","NSYMT","NSYMO","NSYMR")),
              f"{arm} bin {i} mission component sum")
        check(0 <= (sm["NSYMR"] or 0) <= 2,f"{arm} bin {i} reserved bounds")
        for col in sc:
            if col in ("UNID","SID","STINT","ETINT") or col in system_derived:
                continue
            close(sm[col],markers.get(col,{}).get(i,0),f"{arm} system bin {i} {col}")
        expected_busy=sum(overlap(a,b,spans) for spans in lease.values())
        close(rm["NRUM"],expected_busy,f"{arm} bin {i} booked workers")
        close(rm["NR"],2,f"{arm} bin {i} two worker pool")
        close(rm["NRW"],overlap(a,b,worker_wait),f"{arm} bin {i} worker wait")
        for col in rc:
            if col in ("RID","STID","STINT","ETINT","NR","NRUM","NRW"):
                continue
            close(rm[col],2 if col in ("NRA","NRN") else 0,
                  f"{arm} resource bin {i} {col}")
        check(0 <= (sm["NSYPM"] or 0) <= 2 and 0 <= (sm["NSYRP"] or 0) <= 1,
              f"{arm} bin {i} PM/repair bounds")
        wait=overlap(a,b,[(47.9896,49.9896)]) if arm=="risk" else 0
        close(tm["NBO"],wait,f"{arm} bin {i} base LRU backorder")
        close(tm["PNB"],1-wait,f"{arm} bin {i} no-backorder fraction")
        for col in tc:
            if col not in ("STINT","ETINT","NBO","PNB"):
                expected=(2 if col in ("WT","WTT","WTS") else 1) if (
                    arm=="risk" and i==95 and col in
                    ("ROS","ROST","WT","WTT","WTS","NDF","NWT")) else 0
                close(tm[col],expected,f"{arm} stock bin {i} {col}")
    close(sum((r[sc.index("NSYMO")] or 0)*.5 for r in sr),
          sum((y-x)*qty for x,y,qty in flight),f"{arm} flight hours")
    close(sum((r[rc.index("NRUM")] or 0)*.5 for r in rr),8,f"{arm} booked resource hours")
    close(sum((r[rc.index("NRW")] or 0)*.5 for r in rr),
          3 if arm=="deterministic" else 2.5,f"{arm} waiting resource hours")
    close(sum((r[tc.index("NBO")] or 0)*.5 for r in tr),
          0 if arm=="deterministic" else 2,f"{arm} base backorder hours")
    for col,value in ({"NSYPM":4,"NSYRP":0,"NFAIL":0,"NPMT":2,"NPMS":2,"SYDT":2} if
                      arm=="deterministic" else
                      {"NSYPM":4,"NSYRP":.5,"NFAIL":.5,"NPMT":2,"NPMS":2,
                       "SYDT":3.1666667}).items():
        close(sum((r[sc.index(col)] or 0)*.5 for r in sr),value,
              f"{arm} integrated {col}")
    close(sr[-1][sc.index("NSYRY")],2,f"{arm} terminal two ready")
    close(tr[-1][tc.index("NBO")],0,f"{arm} terminal no aggregate backorder")
    close(rr[-1][rc.index("NRUM")],0,f"{arm} terminal no booked worker")
    total=dict(zip(cols(rep["ResourceResultsTotal"]),rows(rep["ResourceResultsTotal"])[0]))
    close(total["NR"],2,f"{arm} resource total pool")
    close(total["NRUM"],8/60,f"{arm} resource total busy fraction")
    close(total["NRW"],(3 if arm=="deterministic" else 2.5)/60,
          f"{arm} resource total waiting fraction")

result={
    "case":"F02.var01/var02 integrated fleet v1.0.2",
    "passed":not errors,
    "verdict":"GO: bounded paired two-aircraft integrated support" if not errors else "NO-GO",
    "checks_passed":checks-len(errors),"checks_total":checks,"failures":errors,
    "run_closures_sha256":{arm:sha(path/"closure.json") for arm,path in RUNS.items()},
    "report_sha256":{arm:sha(path/"report-raw.json") for arm,path in RUNS.items()},
    "limits":[
        "One seed, two aircraft, one base/depot pair, 60h horizon and four group mission opportunities.",
        "MFF switch is isolated in source, but resulting mission timing, PM contention and repair outcomes interact; no componentwise causal decomposition.",
        "Every 120-bin System/Stock/Resource numeric field is checked against events, a report identity, a marker, or an expected zero; NSYMR uses rowwise conservation and bounds rather than a separate per-aircraft preassignment reconstruction.",
        "ResourceResults.NRA is not interpreted as free capacity; native book/release events and NRUM supply occupancy evidence.",
        "No population risk, GUI-only behavior, larger fleet or long-horizon claim.",
    ],
}
OUT.write_bytes((json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8"))
print(json.dumps({"passed":result["passed"],"checks":checks,"failures":errors[:25],
                  "script_sha256":sha(Path(__file__)),"verdict_sha256":sha(OUT)},sort_keys=True))
raise SystemExit(0 if result["passed"] else 1)
