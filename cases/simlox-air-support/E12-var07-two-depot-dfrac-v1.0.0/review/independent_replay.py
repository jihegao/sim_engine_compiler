"""Independent standard-library replay of frozen E12.var07 native evidence."""
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "E12-var05-base02-zero-opening-stock-v1.0.0"
RUN = CASE / "runs" / "e12-var07-two-depot-dfrac-v100-ssh-20261004-01"
PRUN = PARENT / "runs" / "e12-var05-base02-zero-stock-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")

class Audit:
    def __init__(self): self.good = 0; self.bad = []
    def ok(self, assertion, name):
        if assertion: self.good += 1
        else: self.bad.append(name)
    def eq(self, got, expected, name): self.ok(got == expected, f"{name}: {got!r} != {expected!r}")
    def near(self, got, expected, name, tol=.00025):
        self.ok(isinstance(got, (float, int)) and abs(got-expected) <= tol, f"{name}: {got!r} != {expected!r}")

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path, native=False):
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw) if native else raw)
def tablemap(path, root="model"): return {x["name"]:x for x in load(path, root=="report")[root]["tables"]}
def rows(table): return [row for inst in table["instances"] for row in inst.get("rows", [])]
def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]
def occupancy(a, b, lo, hi): return max(0.0, min(b, hi)-max(a, lo))

def main():
    a=Audit(); contract=load(CASE/"contract.json"); diff=load(CASE/"exact-diff.json")
    source=tablemap(CASE/"native-input.json"); parent=tablemap(PARENT/"native-input.json")
    export=tablemap(RUN/"roundtrip-raw.json"); report=tablemap(RUN/"report-raw.json", "report")
    inv=load(RUN/"invocation.json"); closure=load(RUN/"closure.json"); steps=load(RUN/"steps.json")
    log=(RUN/"model.log").read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
    conversion=(RUN/"run.log").read_text(encoding="utf-8-sig",errors="replace")
    a.eq(contract["variant_id"],"E12.var07","contract identity")
    for path,key in [(CASE/"native-input.json","native_input_sha256"),(CASE/"exact-diff.json","exact_diff_sha256")]:
        a.eq(sha(path),contract[key],f"contract {key}")
    ap=contract["accepted_parent"]
    for path,key in [(PARENT/"native-input.json","input_sha256"),(PRUN/"closure.json","native_closure_sha256"),(PARENT/"evidence-index.json","evidence_index_sha256")]:
        a.eq(sha(path),ap[key],f"parent {key}")
    a.eq(diff["parent_sha256"],sha(PARENT/"native-input.json"),"diff parent")
    a.eq(diff["source_sha256"],sha(CASE/"native-input.json"),"diff child")
    changed=sorted(n for n in source if source[n]!=parent[n])
    a.eq(len(source),32,"source table count")
    a.eq(set(source),set(parent),"same business tables")
    a.eq(changed,diff["changed_tables"],"exact changed tables")
    a.eq(diff["unchanged_parent_tables"],27,"fixed table count")
    for name in sorted(source):
        a.eq(source[name]["columns"],parent[name]["columns"],f"schema {name}")
        if name not in changed: a.eq(source[name],parent[name],f"fixed table {name}")
    a.eq(len(diff["modified_cells"]),5,"five modified cells")
    a.eq(len(diff["added_rows"]),6,"six added rows")
    for spec in diff["modified_cells"]:
        name=spec["table"]; index=next(i for i,c in enumerate(source[name]["columns"]) if c["name"]==spec["column"])
        a.eq(rows(parent[name])[spec["row"]][index],spec["before"],f"old {name}.{spec['column']}")
        a.eq(rows(source[name])[spec["row"]][index],spec["after"],f"new {name}.{spec['column']}")
    for spec in diff["added_rows"]:
        name=spec["table"]; row=records(source[name])[spec["row"]]
        a.eq(row,spec["values"],f"new row {name} {spec['row']}")
    for name in changed:
        old=rows(parent[name]); new=rows(source[name]); cols=[x["name"] for x in source[name]["columns"]]
        a.eq(len(new)-len(old),sum(x["table"]==name for x in diff["added_rows"]),f"only declared added {name} rows")
        actual=[(i,cols[j]) for i,(r,s) in enumerate(zip(old,new)) for j,(u,v) in enumerate(zip(r,s)) if u!=v]
        expected=[(x["row"],x["column"]) for x in diff["modified_cells"] if x["table"]==name]
        a.eq(actual,expected,f"only declared modified {name} cells")
    for name in ("StationStructure","ItemStationStructure"):
        routes=records(source[name]); a.eq({(x["STID"],x["MSTID"]):x["DFRAC"] for x in routes},{(base,depot):.5 for base in ("BASE-01","BASE-02") for depot in ("DEPOT-01","DEPOT-02")},f"{name} symmetric route fractions")
    a.eq({x["STID"]:x["STSIZ"] for x in records(source["StockAllocation"])},{"DEPOT-01":1,"DEPOT-02":1,"BASE-01":1,"BASE-02":0},"opening stock source")
    installed={"simlox_exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),"manual":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),"dictionary":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
    for key,path in installed.items():
        field={"simlox_exe":"simlox_exe_sha256","manual":"manual_pdf_sha256","dictionary":"dictionary_sha256"}[key]
        a.eq(sha(path),contract["source"][field],f"installed {key}")
    a.eq(inv["run_id"],RUN.name,"run identity")
    a.eq(inv["execution_mode"],"ssh_cli_v1","SSH CLI")
    a.eq(inv["session_id"],0,"session zero")
    a.ok(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"],"SSH daemon ancestry")
    a.eq(inv["queue_mutex"],r"Global\SimloxIssue18NativeQueue","native mutex")
    a.eq((inv["gui"]["pid"],inv["gui"]["session_id"]),(13340,1),"GUI preserved identity")
    a.eq(inv["input_sha256"],sha(CASE/"native-input.json"),"invoked input")
    a.eq(closure["invocation_sha256"],sha(RUN/"invocation.json"),"invocation sealed")
    a.eq(closure["source_hashes_before"],closure["source_hashes_after"],"source unchanged during run")
    a.eq(closure["source_hashes_before"],inv["source_hashes_before"],"source invocation agreement")
    paths={"input":CASE/"native-input.json","parent":PARENT/"native-input.json","parent_closure":PRUN/"closure.json","parent_index":PARENT/"evidence-index.json","contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json","builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py","checker":CASE/"check_roundtrip.py","runner_script":CASE/"run_native_ssh.ps1","python":Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),**installed}
    for key,path in sorted(paths.items()): a.eq(closure["source_hashes_before"][key],sha(path),f"source seal {key}")
    a.eq(len(closure["raw"]),12,"twelve raw seals")
    for name,meta in sorted(closure["raw"].items()):
        path=RUN/name; a.ok(path.is_file(),f"raw exists {name}")
        if path.is_file():
            a.eq(path.stat().st_size,meta["bytes"],f"raw bytes {name}")
            a.eq(sha(path),meta["sha256"],f"raw SHA {name}")
    a.eq(sha(RUN/"input.json"),sha(CASE/"native-input.json"),"native source copy")
    a.eq([s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"],"five guarded steps")
    for step in steps:
        a.eq(step["exit_code"],0,f"{step['name']} exit")
        a.eq(step["status"],"completed",f"{step['name']} status")
        a.eq(step["error"],None,f"{step['name']} error")
        a.eq(step["gui_preserved"],True,f"{step['name']} GUI preserved")
    authored=sorted(name for name,t in source.items() if rows(t))
    a.eq(len(authored),22,"twenty-two row-containing tables")
    a.eq(set(export),set(source),"export table set")
    for name in authored: a.eq(export[name],source[name],f"authored native roundtrip {name}")
    a.ok((RUN/"model.sxo").stat().st_size>4,"usable SXO")
    a.eq(re.findall(r"\(error #(\d+)\)",conversion),[],"zero converter errors")
    a.eq(re.findall(r"\(warning #(\d+)\)",conversion),["108"],"warning 108 only")
    a.ok("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion,"converter summary")

    lines=log.splitlines()
    def event(time,part): a.ok(any(s.startswith(f"Time: {time} ") and part in s for s in lines),f"event {time} {part}")
    for depot,item in [("DEPOT-01",0),("DEPOT-02",1),("BASE-01",2)]:
        a.ok(f"Stock at: <TEACH-LRU-01,0,{depot},0> Level: 1 Items:<TEACH-LRU-01,0,{item}>" in log,f"opening {depot} item {item}")
    a.ok("Stock at: <TEACH-LRU-01,0,BASE-02,0> Level: 0 Items:" in log,"BASE-02 empty opening")
    # Each demand debit and failed-item return must name the same physical depot.
    pairs=[("10.7579","10.9246","BASE-01","DEPOT-01",0,3),
           ("11.5","11.8333","BASE-02","DEPOT-02",1,4),
           ("23.4473","23.614","BASE-01","DEPOT-02",4,5),
           ("35.5","35.6667","BASE-01","DEPOT-02",5,6)]
    for down,up,base,depot,spare,failed in pairs:
        event(down,f"<{depot},0> Take replacement item <TEACH-LRU-01,0,{spare}>".replace(f"<{depot},0>",f"<TEACH-LRU-01,0,{depot},0>"))
        event(down,f"transport request <<TEACH-LRU-01,0,{spare}>,<TEACH-LRU-01,0,{depot},0>,<TEACH-LRU-01,0,{base},0>> started")
        event(up,f"transport request <<TEACH-LRU-01,0,{failed}>,<TEACH-LRU-01,0,{base},0>,<TEACH-LRU-01,0,{depot},0>> started")
    a.eq({x[3] for x in pairs},{"DEPOT-01","DEPOT-02"},"both actual depots selected")
    for depot,item,start,finish in [("DEPOT-01",3,"13.9246","14.9246"),("DEPOT-02",4,"14.8333","15.8333"),("DEPOT-02",5,"26.614","27.614")]:
        event(start,f"<{depot},0> Start repair of item <TEACH-LRU-01,0,{item}>".replace(f"<{depot},0>",f"<TEACH-LRU-01,0,{depot},0>"))
        event(finish,f"<{depot},0> Finished repair of item <TEACH-LRU-01,0,{item}>".replace(f"<{depot},0>",f"<TEACH-LRU-01,0,{depot},0>"))
        event(finish,f"<{depot},0> Put back replacement item <TEACH-LRU-01,0,{item}>".replace(f"<{depot},0>",f"<TEACH-LRU-01,0,{depot},0>"))
    a.eq(log.count("Finished repair of item <TEACH-LRU-01,0,6>"),0,"last failed item unrepaired at horizon")
    event("11.5","<TEACH-LRU-01,0,BASE-02,0> Backorder added")
    event("12.5","<TEACH-LRU-01,0,BASE-02,0> Backorder removed, waiting time was 1")
    a.eq(log.count("Backorder added"),1,"one local backorder")
    a.eq(log.count("Backorder removed"),1,"one local backorder cleared")
    a.eq(log.count("<TEACH-LRU-01,0,DEPOT-01,0> Backorder added")+log.count("<TEACH-LRU-01,0,DEPOT-02,0> Backorder added"),0,"no depot backorders")
    for i in range(6):
        unit="TEACH-UNIT" if i%2==0 else "TEACH-UNIT-2"
        ident=f"<BASIC-MISSION,{unit},0,0,{i}>"
        event(str(7+12*(i//2)),f"{ident} mission created:")
        event(str(8+12*(i//2)),f"{ident} mission starting, duration: 3.5")
    for i,time in [(0,"9.8829"),(1,"11.1325"),(2,"22.5723"),(4,"34.7893")]:
        unit="TEACH-UNIT" if i%2==0 else "TEACH-UNIT-2"; event(time,f"<BASIC-MISSION,{unit},0,0,{i}> mission aborted:")
    for i,time in [(3,"23.5"),(5,"35.5")]: event(time,f"<BASIC-MISSION,TEACH-UNIT-2,0,0,{i}> mission success:")
    for phrase,count in [("mission created:",6),("mission starting, duration:",6),("mission aborted:",4),("mission success:",2),("mission cancelled:",0),("critical random failure added",4),("books resources",0)]: a.eq(log.count(phrase),count,f"count {phrase}")
    for time,item,air in [("9.8829",3,0),("11.1325",4,1),("22.5723",5,0),("34.7893",6,0)]:
        event(time,f"<TEACH-AIR-01,{air}> critical random failure added")
        a.ok(f"subitem failed: <TEACH-LRU-01,0,{item}>" in log,f"failed physical item {item}")
    for start,finish,task,air in [("10.7579","11.2579",0,0),("11.5","13.1667",1,1),("23.4473","23.9473",4,0),("35.5","36",6,0)]:
        event(start,f"system SURP task {task} on <TEACH-AIR-01,{air}> started")
        event(finish,f"system SURP task {task} on <TEACH-AIR-01,{air}> completed")
    event("36","<TEACH-UNIT at <BASE-01,0>> systems ready: 1")
    event("35.5","<TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1")

    a.eq(set(report),{"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},"report table set")
    a.eq(rows(report["ResultSummary"])[0],[1,0,36,0.9621521234512329,0,1,0,0.3333333432674408,0,0.9621521234512329,0],"complete result summary")
    systems=records(report["SystemResults"]); stock=records(report["StockTotalResults"])
    a.eq((len(systems),len(stock)),(72,72),"72 bins per report table")
    ready=[(0,7),(11.2579,19),(23.9473,31), (0,7),(13.1666666667,19),(23.5,31),(35.5,36)]
    missions=[(7,10.7579),(19,23.4473),(31,35.5),(7,11.5),(19,23.5),(31,35.5)]
    flights=[(8,10.7579),(20,23.4473),(32,35.5),(8,11.5),(20,23.5),(32,35.5)]
    unavailable=[(10.7579,11.2579),(11.5,13.1666666667),(23.4473,23.9473),(35.5,36)]
    work=[(10.7579,11.2579),(11.5,11.8333333333),(12.5,13.1666666667),(23.4473,23.9473),(35.5,36)]
    waiting=[(11.8333333333,12.5)]
    starts={21,23,46,71}; failures={19,22,45,69}; completed={22,26,47}; demands={21,23,46,71}
    for i,(sr,tr) in enumerate(zip(systems,stock)):
        lo=i/2; hi=(i+1)/2
        a.eq((sr["STINT"],sr["ETINT"],tr["STINT"],tr["ETINT"]),(lo,hi,lo,hi),f"bin {i} bounds")
        expected={key:0 for key in sr}
        mission=sum(occupancy(x,y,lo,hi) for x,y in missions)*2
        flight=sum(occupancy(x,y,lo,hi) for x,y in flights)*2
        down=sum(occupancy(x,y,lo,hi) for x,y in unavailable)*2
        expected.update(UNID="Total over all Units",SID="Total over all Systems",STINT=lo,ETINT=hi,NSYRY=sum(occupancy(x,y,lo,hi) for x,y in ready)*2,NSYMA=mission,NSYMO=flight,NSYMR=sum(occupancy(x,x+1,lo,hi) for x in (7,19,31))*4,NSYUA=down,NSYA=2-down,FTMO=flight/2,NSYRP=sum(occupancy(x,y,lo,hi) for x,y in work)*2,NSYWI=sum(occupancy(x,y,lo,hi) for x,y in waiting)*2,NREPT=int(i in completed),NFAIL=int(i in failures),STACC=flight,SYDT=1.6666666667 if i==23 else .5 if i in starts else None,NSYDT=int(i in starts))
        for key,value in expected.items():
            if isinstance(value,float): a.near(sr[key],value,f"system bin {i} {key}")
            else: a.eq(sr[key],value,f"system bin {i} {key}")
        bo=2*occupancy(11.5,12.5,lo,hi)
        expected_stock={key:0 for key in tr}
        expected_stock.update(STINT=lo,ETINT=hi,NBO=bo,NBOU=None,ROS=1 if i==23 else 0 if i in demands else None,ROST=1 if i==23 else 0 if i in demands else None,WT=1 if i==23 else 0 if i in demands else None,WTT=1 if i==23 else 0 if i in demands else None,WTS=1 if i==23 else None,PNB=1-bo,NDF=int(i in demands),NWT=int(i in demands))
        for key,value in expected_stock.items():
            if isinstance(value,float): a.near(tr[key],value,f"stock bin {i} {key}")
            else: a.eq(tr[key],value,f"stock bin {i} {key}")
    a.eq(sum(x["NFAIL"] for x in systems),4,"four failures in report")
    a.eq(sum(x["NREPT"] for x in systems),3,"three repairs completed within report horizon")
    a.near(sum(x["NBO"]*.5 for x in stock),1,"one local backorder hour")
    a.eq((systems[-1]["NSYRY"],systems[-1]["NSYUA"]),(1,1),"last half-hour one ready, one in repair")
    result={"schema":"simlox-independent-readonly-review/v1","case_id":"E12.var07","run_id":RUN.name,"passed":not a.bad,"verdict":"GO: bounded two-depot source-selected demand and failed-item routing" if not a.bad else "NO-GO: independent replay mismatch","checks_passed":a.good,"checks_total":a.good+len(a.bad),"failures":a.bad,"evidence":{"closure_sha256":sha(RUN/"closure.json"),"parent_closure_sha256":sha(PRUN/"closure.json"),"raw_seals":len(closure["raw"]),"authored_tables_exact_roundtrip":len(authored),"report_bins_each":72,"observed_demand_pairs":[{"base":base,"depot":depot,"spare_item_id":spare,"failed_item_id":failed,"downward_hour":down,"upward_hour":up} for down,up,base,depot,spare,failed in pairs],"depot_repaired_ids":{"DEPOT-01":[3],"DEPOT-02":[4,5]},"base02_backorder_hours":[11.5,12.5],"mission_outcomes":["abort","abort","abort","success","abort","success"],"terminal_event_ready_aircraft":2,"last_report_interval_ready_aircraft":1},"limits":["One fixed seed, two bases, two physical depots, one item group, and 36-hour horizon; four selected routes do not establish a 50/50 frequency law.","DEPOT-01 selection occurs once and DEPOT-02 three times. All four demand and failed-item pairs use matching depots, as directly named in native transport events.","Failed ID6 and downward spare ID5 remain in transit at h36; final report bin [35.5,36) has one ready aircraft, while event log records the second ready at the exact h36 boundary.","No per-station ItemResults export, GUI visual, resource allocation, or cross-engine claim."]}
    OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
    return result

if __name__ == "__main__":
    result=main(); print(json.dumps({key:result[key] for key in ("verdict","checks_passed","checks_total","failures")},indent=2)); sys.exit(0 if result["passed"] else 1)
