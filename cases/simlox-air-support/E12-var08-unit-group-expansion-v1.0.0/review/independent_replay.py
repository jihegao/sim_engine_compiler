"""Independent read-only replay of E12.var08 group-owned missions."""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
ROOT=CASE.parent
PARENT=ROOT/"E12-var05-base02-zero-opening-stock-v1.0.0"
DONOR=ROOT/"A17-multi-unit-group-v1.0.0"
RUN=CASE/"runs"/"e12-var08-unit-group-expansion-v100-ssh-20261004-01"
PRUN=PARENT/"runs"/"e12-var05-base02-zero-stock-v100-ssh-20261003-01"
OUT=Path(__file__).with_name("independent-verdict.json")
class Audit:
 def __init__(self):self.good=0;self.bad=[]
 def ok(self,condition,name):
  if condition:self.good+=1
  else:self.bad.append(name)
 def eq(self,got,expected,name):self.ok(got==expected,f"{name}: {got!r} != {expected!r}")
 def near(self,got,expected,name,tol=.00025):self.ok(isinstance(got,(int,float)) and abs(got-expected)<=tol,f"{name}: {got!r} != {expected!r}")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p,native=False):
 s=p.read_text(encoding="utf-8-sig")
 return json.loads(re.sub(r",\s*([}\]])",r"\1",s) if native else s)
def tables(p,root="model"):return {t["name"]:t for t in load(p,root=="report")[root]["tables"]}
def rows(t):return [r for inst in t["instances"] for r in inst.get("rows",[])]
def records(t):
 names=[x["name"] for x in t["columns"]]
 return [dict(zip(names,r)) for r in rows(t)]
def ov(a,b,lo,hi):return max(0.0,min(b,hi)-max(a,lo))

def main():
 a=Audit(); contract=load(CASE/"contract.json");diff=load(CASE/"exact-diff.json")
 source=tables(CASE/"native-input.json");parent=tables(PARENT/"native-input.json");donor=tables(DONOR/"native-input.json")
 export=tables(RUN/"roundtrip-raw.json");report=tables(RUN/"report-raw.json","report");preport=tables(PRUN/"report-raw.json","report")
 inv=load(RUN/"invocation.json");closure=load(RUN/"closure.json");steps=load(RUN/"steps.json")
 log=(RUN/"model.log").read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
 converter=(RUN/"run.log").read_text(encoding="utf-8-sig",errors="replace")
 a.eq(contract["variant_id"],"E12.var08","contract variant")
 for p,key in [(CASE/"native-input.json","native_input_sha256"),(CASE/"exact-diff.json","exact_diff_sha256")]:a.eq(sha(p),contract[key],f"contract {key}")
 ap=contract["accepted_parent"]
 for p,key in [(PARENT/"native-input.json","input_sha256"),(PRUN/"closure.json","native_closure_sha256"),(PARENT/"evidence-index.json","evidence_index_sha256")]:a.eq(sha(p),ap[key],f"parent {key}")
 a.eq(sha(DONOR/"native-input.json"),contract["a17_schema_reference_sha256"],"A17 schema donor")
 for n in ("UnitGroup","UnitGroupMember"):a.eq(source[n]["columns"],donor[n]["columns"],f"A17 {n} schema")
 a.eq(diff["parent_sha256"],sha(PARENT/"native-input.json"),"diff parent")
 a.eq(diff["source_sha256"],sha(CASE/"native-input.json"),"diff child")
 a.eq(len(parent),32,"parent table count")
 a.eq(len(source),34,"child table count")
 a.eq(set(source)-set(parent),{"UnitGroup","UnitGroupMember"},"only two added tables")
 for n,t in sorted(diff["added_tables"].items()):a.eq(source[n],t,f"exact added {n}")
 a.eq(sorted(n for n in parent if source[n]!=parent[n]),diff["changed_existing_tables"],"three modified existing tables")
 a.eq(diff["unchanged_parent_tables"],29,"29 parent tables fixed")
 for n in sorted(parent):
  a.eq(source[n]["columns"],parent[n]["columns"],f"schema {n}")
  if n not in diff["changed_existing_tables"]:a.eq(source[n],parent[n],f"fixed table {n}")
 a.eq(len(diff["modified_cells"]),5,"five modified cells")
 for spec in diff["modified_cells"]:
  n=spec["table"];j=next(i for i,x in enumerate(source[n]["columns"]) if x["name"]==spec["column"])
  a.eq(rows(parent[n])[spec["row"]][j],spec["before"],f"old {n}.{spec['column']}")
  a.eq(rows(source[n])[spec["row"]][j],spec["after"],f"new {n}.{spec['column']}")
 for spec in diff["removed_rows"]:a.eq(rows(parent[spec["table"]])[spec["row"]],spec["values"],f"removed parent {spec['table']} row")
 for n in diff["changed_existing_tables"]:
  old=rows(parent[n]);new=rows(source[n]);cols=[x["name"] for x in source[n]["columns"]]
  a.eq(len(old)-len(new),sum(x["table"]==n for x in diff["removed_rows"]),f"only declared removed {n} row")
  actual=[(i,cols[j]) for i,(r,s) in enumerate(zip(old,new)) for j,(x,y) in enumerate(zip(r,s)) if x!=y]
  expected=[(x["row"],x["column"]) for x in diff["modified_cells"] if x["table"]==n]
  a.eq(actual,expected,f"only declared modified {n} cells")
 a.eq(records(source["UnitGroupMember"]),[{"UGID":"TEACH-GROUP","USTID":"TEACH-UNIT","PRI":1,"XTIME":0.0,"NOTE":None},{"UGID":"TEACH-GROUP","USTID":"TEACH-UNIT-2","PRI":1,"XTIME":0.0,"NOTE":None}],"two equal-priority explicit members")
 a.eq([r["IQTY"] for r in records(source["OperationProfile"])],[2,2,2],"two orders per wave")
 a.eq([r["USTID"] for r in records(source["Operations"])],["TEACH-GROUP"],"group owns schedule")
 installed={"simlox_exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),"manual":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),"dictionary":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
 for key,p in installed.items():
  field={"simlox_exe":"simlox_exe_sha256","manual":"manual_pdf_sha256","dictionary":"dictionary_sha256"}[key]
  a.eq(sha(p),contract["source"][field],f"installed {key}")
 a.eq(inv["run_id"],RUN.name,"run ID")
 a.eq(inv["execution_mode"],"ssh_cli_v1","SSH native mode")
 a.eq(inv["session_id"],0,"session zero")
 a.ok(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"],"SSH daemon ancestry")
 a.eq(inv["queue_mutex"],r"Global\SimloxIssue18NativeQueue","native mutex")
 a.eq((inv["gui"]["pid"],inv["gui"]["session_id"]),(13340,1),"GUI identity")
 a.eq(inv["input_sha256"],sha(CASE/"native-input.json"),"invoked source")
 a.eq(closure["invocation_sha256"],sha(RUN/"invocation.json"),"invocation seal")
 a.eq(closure["source_hashes_before"],closure["source_hashes_after"],"source stability")
 a.eq(closure["source_hashes_before"],inv["source_hashes_before"],"source invocation agreement")
 paths={"input":CASE/"native-input.json","parent":PARENT/"native-input.json","parent_closure":PRUN/"closure.json","parent_index":PARENT/"evidence-index.json","contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json","builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py","checker":CASE/"check_roundtrip.py","runner_script":CASE/"run_native_ssh.ps1","python":Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),**installed}
 for k,p in sorted(paths.items()):a.eq(closure["source_hashes_before"][k],sha(p),f"source seal {k}")
 a.eq(len(closure["raw"]),12,"12 raw seals")
 for n,meta in sorted(closure["raw"].items()):
  p=RUN/n;a.ok(p.is_file(),f"raw exists {n}")
  if p.is_file():a.eq(p.stat().st_size,meta["bytes"],f"raw bytes {n}");a.eq(sha(p),meta["sha256"],f"raw SHA {n}")
 a.eq(sha(RUN/"input.json"),sha(CASE/"native-input.json"),"run input copy")
 a.eq([s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"],"five native steps")
 for s in steps:
  a.eq(s["exit_code"],0,f"{s['name']} exit");a.eq(s["status"],"completed",f"{s['name']} status")
  a.eq(s["error"],None,f"{s['name']} error");a.eq(s["gui_preserved"],True,f"{s['name']} GUI preserved")
 authored=sorted(n for n,t in source.items() if rows(t));a.eq(len(authored),24,"24 row-containing tables")
 a.eq(set(export),set(source),"native export table set")
 for n in authored:a.eq(export[n],source[n],f"exact authored roundtrip {n}")
 a.ok((RUN/"model.sxo").stat().st_size>4,"usable SXO")
 a.eq(re.findall(r"\(error #(\d+)\)",converter),[],"converter errors zero")
 a.eq(re.findall(r"\(warning #(\d+)\)",converter),["108"],"warning 108 only")
 a.ok("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter,"converter summary")

 lines=log.splitlines()
 def event(time,part):a.ok(any(s.startswith(f"Time: {time} ") and part in s for s in lines),f"event {time} {part}")
 for base,air in [("BASE-01",0),("BASE-02",1)]:
  unit="TEACH-UNIT" if air==0 else "TEACH-UNIT-2"
  event("0",f"<{unit} at <{base},0>> systems ready: 1 :<TEACH-AIR-01,{air}>")
 for stid,item in [("DEPOT-01",0),("BASE-01",1)]:a.ok(f"Stock at: <TEACH-LRU-01,0,{stid},0> Level: 1 Items:<TEACH-LRU-01,0,{item}>" in log,f"opening {stid} item {item}")
 a.ok("Stock at: <TEACH-LRU-01,0,BASE-02,0> Level: 0 Items:" in log,"BASE-02 opening zero")
 for wave in range(3):
  assigned=[]
  for air in (0,1):
   mid=wave*2+air;ident=f"<BASIC-MISSION,TEACH-GROUP,0,0,{mid}>";hour=str(7+12*wave)
   event(hour,f"{ident} mission created:")
   event(hour,f"{ident} mission allocates system: <TEACH-AIR-01,{air}>")
   unit="TEACH-UNIT" if air==0 else "TEACH-UNIT-2";base="BASE-01" if air==0 else "BASE-02"
   event(hour,f"<TEACH-AIR-01,{air}> nbr ready decreased at unit: <{unit} at <{base},0>>")
   event(str(8+12*wave),f"{ident} mission starting, duration: 3.5 : <TEACH-AIR-01,{air}>")
   assigned.append(air)
  a.eq(assigned,[0,1],f"wave {wave} distinct member aircraft")
 a.eq(log.count("<TEACH-GROUP> mission ordered: BASIC-MISSION"),6,"six group-owned orders")
 for mid,h in [(0,"9.8829"),(1,"11.1325"),(2,"22.5723"),(4,"34.7893")]:event(h,f"<BASIC-MISSION,TEACH-GROUP,0,0,{mid}> mission aborted:")
 for mid,h in [(3,"23.5"),(5,"35.5")]:event(h,f"<BASIC-MISSION,TEACH-GROUP,0,0,{mid}> mission success:")
 for phrase,count in [("mission created:",6),("mission allocates system:",6),("mission starting, duration:",6),("mission aborted:",4),("mission success:",2),("mission cancelled:",0),("critical random failure added",4),("books resources",0)]:a.eq(log.count(phrase),count,f"event count {phrase}")
 for h,air,item in [("9.8829",0,2),("11.1325",1,3),("22.5723",0,4),("34.7893",0,5)]:
  event(h,f"<TEACH-AIR-01,{air}> critical random failure added")
  a.ok(f"subitem failed: <TEACH-LRU-01,0,{item}>" in log,f"failed physical item {item}")
 for start,finish,task,air in [("10.7579","11.2579",0,0),("11.5","16.5912",1,1),("23.4473","23.9473",4,0),("35.5","36",6,0)]:
  event(start,f"system SURP task {task} on <TEACH-AIR-01,{air}> started")
  event(finish,f"system SURP task {task} on <TEACH-AIR-01,{air}> completed")
 for h,base,item in [("10.7579","BASE-01",1),("23.4473","BASE-01",0),("35.5","BASE-01",3)]:event(h,f"<TEACH-LRU-01,0,{base},0> Take replacement item <TEACH-LRU-01,0,{item}> from stock")
 for h,base,item in [("10.7579","BASE-01",0),("14.9246","BASE-02",2),("23.4473","BASE-01",3),("35.5","BASE-01",4)]:event(h,f"transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,{base},0>> started")
 for h,base,item in [("10.9246","BASE-01",2),("11.8333","BASE-02",3),("23.614","BASE-01",4),("35.6667","BASE-01",5)]:event(h,f"transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,{base},0>,<TEACH-LRU-01,0,DEPOT-01,0>> started")
 for h,item in [("11.7579",0),("24.4473",3)]:event(h,f"<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{item}> to stock")
 for start,finish,item in [("13.9246","14.9246",2),("14.8333","15.8333",3),("26.614","27.614",4)]:
  event(start,f"<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,{item}>")
  event(finish,f"<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,{item}>")
 for h,item in [("15.8333",3),("27.614",4)]:event(h,f"<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,{item}> to stock")
 for h,stid in [("11.5","BASE-02"),("11.5","DEPOT-01")]:event(h,f"<TEACH-LRU-01,0,{stid},0> Backorder added")
 for h,stid,wait in [("14.9246","DEPOT-01","3.42457"),("15.9246","BASE-02","4.42457")]:event(h,f"<TEACH-LRU-01,0,{stid},0> Backorder removed, waiting time was {wait}")
 a.eq(log.count("Backorder added"),2,"base and depot backorders")
 a.eq(log.count("Backorder removed"),2,"both backorders cleared")
 event("16.5912","<TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1")
 event("35.5","<TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1")
 event("36","<TEACH-UNIT at <BASE-01,0>> systems ready: 1")
 a.eq(log.count("Finished repair of item <TEACH-LRU-01,0,5>"),0,"last failed item still in transit")

 a.eq(set(report),{"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},"report table set")
 a.ok(report["ProblemDescription"]!=preport["ProblemDescription"],"description changed")
 for n in ("ResultSummary","SystemResults","StockTotalResults"):
  a.eq(report[n]["columns"],preport[n]["columns"],f"parent {n} schema")
  x=rows(report[n]);y=rows(preport[n]);a.eq(len(x),len(y),f"parent {n} row count")
  for i,(u,v) in enumerate(zip(x,y)):
   for j,(p,q) in enumerate(zip(u,v)):a.eq(p,q,f"parent parity {n} row {i} col {j}")
 a.eq(rows(report["ResultSummary"])[0],[1,0,36,0.9621521234512329,0,1,0,0.3333333432674408,0,0.9621521234512329,0],"summary values")
 system=records(report["SystemResults"]);stock=records(report["StockTotalResults"])
 a.eq((len(system),len(stock)),(72,72),"72 bins each")
 ready=[(0,7),(11.2579,19),(23.9473,31),(0,7),(16.5912324588,19),(23.5,31),(35.5,36)]
 missions=[(7,10.7578991055),(19,23.4472958446),(31,35.5),(7,11.5),(19,23.5),(31,35.5)]
 flights=[(8,10.7578991055),(20,23.4472958446),(32,35.5),(8,11.5),(20,23.5),(32,35.5)]
 unavailable=[(10.7578991055,11.2578991055),(11.5,16.5912324588),(23.4472958446,23.9472958446),(35.5,36)]
 work=[(10.7578991055,11.2578991055),(11.5,11.8333333333),(15.9245657921,16.5912324588),(23.4472958446,23.9472958446),(35.5,36)]
 wait=[(11.8333333333,15.9245657921)]
 failures={19,22,45,69};starts={21,23,46,71};completions={22,33,47};demands={21,23,46,71}
 for i,(sr,tr) in enumerate(zip(system,stock)):
  lo=i/2;hi=(i+1)/2
  a.eq((sr["STINT"],sr["ETINT"],tr["STINT"],tr["ETINT"]),(lo,hi,lo,hi),f"bin {i} bounds")
  ma=2*sum(ov(x,y,lo,hi) for x,y in missions);flight=2*sum(ov(x,y,lo,hi) for x,y in flights);down=2*sum(ov(x,y,lo,hi) for x,y in unavailable)
  expected={key:0 for key in sr}
  expected.update(UNID="Total over all Units",SID="Total over all Systems",STINT=lo,ETINT=hi,NSYRY=2*sum(ov(x,y,lo,hi) for x,y in ready),NSYMA=ma,NSYMO=flight,NSYMR=4*sum(ov(x,x+1,lo,hi) for x in (7,19,31)),NSYUA=down,NSYA=2-down,FTMO=flight/2,NSYRP=2*sum(ov(x,y,lo,hi) for x,y in work),NSYWI=2*sum(ov(x,y,lo,hi) for x,y in wait),NREPT=int(i in completions),NFAIL=int(i in failures),STACC=flight,SYDT=5.0912322998046875 if i==23 else .5 if i in starts else None,NSYDT=int(i in starts))
  for key,value in expected.items():
   if isinstance(value,float):a.near(sr[key],value,f"System bin {i} {key}")
   else:a.eq(sr[key],value,f"System bin {i} {key}")
  bo=2*ov(11.5,15.9245657921,lo,hi)
  expected_stock={key:0 for key in tr}
  expected_stock.update(STINT=lo,ETINT=hi,NBO=bo,NBOU=None,ROS=1 if i==23 else 0 if i in demands else None,ROST=1 if i==23 else 0 if i in demands else None,WT=4.42456579208374 if i==23 else 0 if i in demands else None,WTT=4.42456579208374 if i==23 else 0 if i in demands else None,WTS=4.42456579208374 if i==23 else None,PNB=1-bo,NDF=int(i in demands),NWT=int(i in demands))
  for key,value in expected_stock.items():
   if isinstance(value,float):a.near(tr[key],value,f"Stock bin {i} {key}")
   else:a.eq(tr[key],value,f"Stock bin {i} {key}")
 a.eq(sum(x["NFAIL"] for x in system),4,"four failed aircraft missions")
 a.eq(sum(x["NREPT"] for x in system),3,"three repair completions inside horizon")
 a.near(sum(x["NBO"]*.5 for x in stock),4.4245657921,"base backorder hours")
 a.eq((system[-1]["NSYRY"],system[-1]["NSYUA"]),(1,1),"last interval ready one, repairing one")
 result={"schema":"simlox-independent-readonly-review/v1","case_id":"E12.var08","run_id":RUN.name,"passed":not a.bad,"verdict":"GO: bounded explicit two-member group expansion" if not a.bad else "NO-GO: independent replay mismatch","checks_passed":a.good,"checks_total":a.good+len(a.bad),"failures":a.bad,"evidence":{"closure_sha256":sha(RUN/"closure.json"),"parent_closure_sha256":sha(PRUN/"closure.json"),"raw_seals":len(closure["raw"]),"row_containing_tables":len(authored),"mission_owner":"TEACH-GROUP","member_aircraft_per_wave":[[0,1],[0,1],[0,1]],"mission_outcomes":["abort","abort","abort","success","abort","success"],"report_bins_each":72,"all_non_description_report_cells_equal_parent":True,"local_base02_backorder":[11.5,15.9246],"depot_backorder":[11.5,14.9246],"terminal_event_ready_aircraft":2,"last_report_bin_ready_aircraft":1},"limits":["One fixed seed, two equal-priority explicit members, zero member XTIME, one aircraft per member and three scheduled paired waves; no priority or fairness law.","The group owns mission orders while member unit and physical aircraft identities are separately logged. Aggregate default reports do not expose per-member rows.","Group source and native report match the accepted unit-owned parent's non-description report cells in this seed; other group configurations and stochastic parity are untested.","Final [35.5,36) bin has one ready and one repairing aircraft; the event log records both ready exactly at h36, with the last failed item still in transit.","No GUI visual or cross-engine claim."]}
 OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
 return result

if __name__=="__main__":
 r=main();print(json.dumps({key:r[key] for key in ("verdict","checks_passed","checks_total","failures")},indent=2));sys.exit(0 if r["passed"] else 1)
