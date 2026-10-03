"""Independent read-only replay of E12.var05 BASE-02 zero opening stock."""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
PARENT=CASE.parent/"E12-var04-item-station-group-repair-v1.0.0"
RUN=CASE/"runs"/"e12-var05-base02-zero-stock-v100-ssh-20261003-01"
PRUN=PARENT/"runs"/"e12-var04-item-station-group-v100-ssh-20261003-01"
OUT=Path(__file__).with_name("independent-verdict.json")

class Audit:
 def __init__(self):self.passed=0;self.failures=[]
 def check(self,x,label):
  if x:self.passed+=1
  else:self.failures.append(label)
 def eq(self,x,y,label):self.check(x==y,f"{label}: expected {y!r}, got {x!r}")
 def near(self,x,y,label,tolerance=.00025):self.check(x is not None and abs(x-y)<=tolerance,f"{label}: expected {y!r}, got {x!r}")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def obj(p,native=False):
 s=p.read_text(encoding="utf-8-sig")
 return json.loads(re.sub(r",\s*([}\]])",r"\1",s) if native else s)
def tables(p,root="model"):return {t["name"]:t for t in obj(p,root=="report")[root]["tables"]}
def rows(t):return [r for inst in t["instances"] for r in inst.get("rows",[])]
def records(t):
 names=[c["name"] for c in t["columns"]]
 return [dict(zip(names,r)) for r in rows(t)]
def ov(a,b,lo,hi):return max(0.0,min(b,hi)-max(a,lo))

def main():
 a=Audit();contract=obj(CASE/"contract.json");diff=obj(CASE/"exact-diff.json")
 source=tables(CASE/"native-input.json");parent=tables(PARENT/"native-input.json")
 export=tables(RUN/"roundtrip-raw.json");report=tables(RUN/"report-raw.json","report")
 preport=tables(PRUN/"report-raw.json","report")
 inv=obj(RUN/"invocation.json");closure=obj(RUN/"closure.json");steps=obj(RUN/"steps.json")
 log=(RUN/"model.log").read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
 converter=(RUN/"run.log").read_text(encoding="utf-8-sig",errors="replace")
 a.eq(contract["variant_id"],"E12.var05","contract variant")
 a.eq(sha(CASE/"native-input.json"),contract["native_input_sha256"],"child input pin")
 a.eq(sha(CASE/"exact-diff.json"),contract["exact_diff_sha256"],"diff pin")
 a.eq(sha(PARENT/"native-input.json"),contract["accepted_parent"]["input_sha256"],"parent input pin")
 a.eq(sha(PRUN/"closure.json"),contract["accepted_parent"]["native_closure_sha256"],"parent closure pin")
 a.eq(sha(PARENT/"evidence-index.json"),contract["accepted_parent"]["evidence_index_sha256"],"parent index pin")
 a.eq(diff["parent_sha256"],sha(PARENT/"native-input.json"),"diff parent")
 a.eq(diff["source_sha256"],sha(CASE/"native-input.json"),"diff child")
 a.eq(len(source),32,"32 source tables")
 a.eq(set(source),set(parent),"same source table set")
 changed=sorted(n for n in source if source[n]!=parent[n])
 a.eq(changed,diff["changed_tables"],"exact two-table delta")
 a.eq(diff["unchanged_parent_tables"],30,"30 unchanged tables")
 for n in sorted(source):
  a.eq(source[n]["columns"],parent[n]["columns"],f"schema {n}")
  if n not in changed:a.eq(source[n],parent[n],f"unchanged table {n}")
 a.eq(len(diff["changed_cells"]),2,"two changed cells")
 for ch in diff["changed_cells"]:
  n=ch["table"];p=rows(parent[n]);c=rows(source[n]);j=next(i for i,x in enumerate(source[n]["columns"]) if x["name"]==ch["column"])
  a.eq(p[ch["row"]][j],ch["before"],f"parent {n}.{ch['column']}")
  a.eq(c[ch["row"]][j],ch["after"],f"child {n}.{ch['column']}")
 for n in changed:
  p=rows(parent[n]);c=rows(source[n]);actual=[(i,j) for i,(x,y) in enumerate(zip(p,c)) for j,(u,v) in enumerate(zip(x,y)) if u!=v]
  expect=[(x["row"],next(i for i,col in enumerate(source[n]["columns"]) if col["name"]==x["column"])) for x in diff["changed_cells"] if x["table"]==n]
  a.eq(actual,expect,f"only declared {n} cells change")
 a.eq([(r["STID"],r["STSIZ"]) for r in records(source["StockAllocation"])],[('BASE-01',1),('DEPOT-01',1),('BASE-02',0)],"asymmetric opening stock rows")
 installed={"simlox_exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),"manual":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),"dictionary":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
 for key,p in installed.items():
  field={"simlox_exe":"simlox_exe_sha256","manual":"manual_pdf_sha256","dictionary":"dictionary_sha256"}[key]
  a.eq(sha(p),contract["source"][field],f"installed {key} pin")
 a.eq(inv["run_id"],RUN.name,"run identity")
 a.eq(inv["execution_mode"],"ssh_cli_v1","SSH CLI")
 a.eq(inv["session_id"],0,"session zero")
 a.check(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"],"SSH ancestry")
 a.eq(inv["queue_mutex"],r"Global\SimloxIssue18NativeQueue","mutex")
 a.eq((inv["gui"]["pid"],inv["gui"]["session_id"]),(13340,1),"GUI identity")
 a.eq(inv["input_sha256"],sha(CASE/"native-input.json"),"invoked input")
 a.eq(closure["invocation_sha256"],sha(RUN/"invocation.json"),"invocation seal")
 a.eq(closure["source_hashes_before"],closure["source_hashes_after"],"source stable")
 a.eq(closure["source_hashes_before"],inv["source_hashes_before"],"source agreement")
 paths={"input":CASE/"native-input.json","parent":PARENT/"native-input.json","parent_closure":PRUN/"closure.json","parent_index":PARENT/"evidence-index.json","contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json","builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py","checker":CASE/"check_roundtrip.py","runner_script":CASE/"run_native_ssh.ps1","python":Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),**installed}
 for key,p in sorted(paths.items()):a.eq(closure["source_hashes_before"][key],sha(p),f"source seal {key}")
 a.eq(len(closure["raw"]),12,"12 raw seals")
 for n,meta in sorted(closure["raw"].items()):
  p=RUN/n;a.check(p.is_file(),f"raw exists {n}")
  if p.is_file():a.eq(p.stat().st_size,meta["bytes"],f"raw bytes {n}");a.eq(sha(p),meta["sha256"],f"raw SHA {n}")
 a.eq(sha(RUN/"input.json"),sha(CASE/"native-input.json"),"run input copy")
 a.eq([s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"],"five steps")
 for s in steps:
  a.eq(s["exit_code"],0,f"{s['name']} exit");a.eq(s["status"],"completed",f"{s['name']} completed")
  a.eq(s["error"],None,f"{s['name']} error");a.check(s["gui_preserved"] is True,f"{s['name']} GUI preserved")
 authored=sorted(n for n,t in source.items() if rows(t))
 a.eq(len(authored),22,"22 authored row tables")
 a.eq(set(export),set(source),"native export table set")
 for n in authored:a.eq(export[n],source[n],f"exact authored roundtrip {n}")
 a.check((RUN/"model.sxo").stat().st_size>4,"valid SXO")
 a.eq(re.findall(r"\(error #(\d+)\)",converter),[],"Errors0")
 a.eq(re.findall(r"\(warning #(\d+)\)",converter),["108"],"warning108 only")
 a.check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter,"converter summary")

 def event(hour,phrase):a.check(any(x.startswith(f"Time: {hour} ") and phrase in x for x in log.splitlines()),f"event h{hour} {phrase}")
 event("0","<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>")
 event("0","<TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1 :<TEACH-AIR-01,1>")
 a.check("Time: 0 <TEACH-LRU-01,0,BASE-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>" in log,"BASE-01 opening ID1")
 a.check("Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log,"DEPOT opening ID0")
 a.check("Time: 0 <TEACH-LRU-01,0,BASE-02,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-02,0> Level: 0 Items:" in log,"BASE-02 opening zero")
 for mid in range(6):
  unit="TEACH-UNIT" if mid%2==0 else "TEACH-UNIT-2";aircraft=mid%2
  ordered,start=(7,8) if mid<2 else (19,20) if mid<4 else (31,32)
  ident=f"<BASIC-MISSION,{unit},0,0,{mid}>"
  event(str(ordered),f"{ident} mission created:")
  event(str(ordered),f"{ident} mission allocates system: <TEACH-AIR-01,{aircraft}>")
  event(str(start),f"{ident} mission starting, duration: 3.5")
 for mid,h in [(0,"9.8829"),(1,"11.1325"),(2,"22.5723"),(4,"34.7893")]:
  unit="TEACH-UNIT" if mid%2==0 else "TEACH-UNIT-2";event(h,f"<BASIC-MISSION,{unit},0,0,{mid}> mission aborted:")
 for mid,h in [(3,"23.5"),(5,"35.5")]:event(h,f"<BASIC-MISSION,TEACH-UNIT-2,0,0,{mid}> mission success:")
 for phrase,count in [("mission created:",6),("mission starting, duration:",6),("mission aborted:",4),("mission success:",2),("mission cancelled:",0),("critical random failure added",4),("Backorder added",2),("Backorder removed",2),("books resources",0)]:a.eq(log.count(phrase),count,f"event count {phrase}")
 for h,aircraft,item in [("9.8829",0,2),("11.1325",1,3),("22.5723",0,4),("34.7893",0,5)]:
  event(h,f"<TEACH-AIR-01,{aircraft}> critical random failure added")
  a.check(f"subitem failed: <TEACH-LRU-01,0,{item}>" in log,f"failed physical ID{item}")
 for h,end,task,aircraft in [("10.7579","11.2579",0,0),("11.5","16.5912",1,1),("23.4473","23.9473",4,0),("35.5","36",6,0)]:
  event(h,f"system SURP task {task} on <TEACH-AIR-01,{aircraft}> started")
  event(end,f"system SURP task {task} on <TEACH-AIR-01,{aircraft}> completed")
 event("10.7579","<TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock")
 event("11.5","<TEACH-LRU-01,0,BASE-02,0> Backorder added")
 event("11.5","<TEACH-LRU-01,0,DEPOT-01,0> Backorder added")
 event("14.9246","<TEACH-LRU-01,0,DEPOT-01,0> Backorder removed, waiting time was 3.42457")
 event("15.9246","<TEACH-LRU-01,0,BASE-02,0> Backorder removed, waiting time was 4.42457")
 event("15.9246","fit subitem subtask 3 seqno 2 within system SURP task 1 on <TEACH-AIR-01,1> started")
 event("16.5912","fit subitem subtask 3 seqno 2 within system SURP task 1 on <TEACH-AIR-01,1> completed")
 for h,item,base in [("10.7579",0,"BASE-01"),("14.9246",2,"BASE-02"),("23.4473",3,"BASE-01"),("35.5",4,"BASE-01")]:event(h,f"transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,{base},0>> started")
 for h,item,base in [("10.9246",2,"BASE-01"),("11.8333",3,"BASE-02"),("23.614",4,"BASE-01"),("35.6667",5,"BASE-01")]:event(h,f"transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,{base},0>,<TEACH-LRU-01,0,DEPOT-01,0>> started")
 for h1,h2,item in [("13.9246","14.9246",2),("14.8333","15.8333",3),("26.614","27.614",4)]:
  event(h1,f"<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,{item}>")
  event(h2,f"<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,{item}>")
 event("11.7579","<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock")
 event("15.8333","<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,3> to stock")
 event("24.4473","<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,3> to stock")
 event("27.614","<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,4> to stock")
 event("16.5912","<TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1 :<TEACH-AIR-01,1>")
 event("35.5","<TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1 :<TEACH-AIR-01,1>")
 event("36","<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>")
 a.eq(log.count("Finished repair of item <TEACH-LRU-01,0,5>"),0,"last failed ID5 unfinished at horizon")

 a.eq(set(report),{"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},"report tables")
 a.eq(rows(report["ResultSummary"])[0],[1,0,36,0.9621521234512329,0,1,0,0.3333333432674408,0,0.9621521234512329,0],"complete summary")
 s=records(report["SystemResults"]);t=records(report["StockTotalResults"])
 a.eq((len(s),len(t)),(72,72),"72 half-hour bins each")
 ready0=[(0,7),(11.2579,19),(23.9473,31)]
 ready1=[(0,7),(16.5912,19),(23.5,31),(35.5,36)]
 missions0=[(7,10.7579),(19,23.4473),(31,35.5)]
 missions1=[(7,11.5),(19,23.5),(31,35.5)]
 flights0=[(8,10.7579),(20,23.4473),(32,35.5)]
 flights1=[(8,11.5),(20,23.5),(32,35.5)]
 unavailable=[(10.7579,11.2579),(11.5,16.5912),(23.4473,23.9473),(35.5,36)]
 repairwork=[(10.7579,11.2579),(11.5,11.8333333333),(15.9245657921,16.5912324588),(23.4473,23.9473),(35.5,36)]
 waiting=[(11.8333333333,15.9245657921)]
 fails={19,22,45,69};completed={22,33,47};began={21,23,46,71};demand={21,23,46,71}
 for i,(sr,tr) in enumerate(zip(s,t)):
  lo,hi=i/2,(i+1)/2
  a.eq((sr["STINT"],sr["ETINT"],tr["STINT"],tr["ETINT"]),(lo,hi,lo,hi),f"bin {i} interval")
  ready=2*sum(ov(x,y,lo,hi) for x,y in ready0+ready1)
  mission=2*sum(ov(x,y,lo,hi) for x,y in missions0+missions1)
  flight=2*sum(ov(x,y,lo,hi) for x,y in flights0+flights1)
  ua=2*sum(ov(x,y,lo,hi) for x,y in unavailable)
  work=2*sum(ov(x,y,lo,hi) for x,y in repairwork)
  wait=2*sum(ov(x,y,lo,hi) for x,y in waiting)
  expected={k:0 for k in sr}
  expected.update(UNID="Total over all Units",SID="Total over all Systems",STINT=lo,ETINT=hi,NSYRY=ready,NSYMA=mission,NSYMO=flight,NSYMR=4*sum(ov(x,x+1,lo,hi) for x in (7,19,31)),NSYUA=ua,NSYA=2-ua,FTMO=flight/2,NSYRP=work,NSYWI=wait,NREPT=int(i in completed),NFAIL=int(i in fails),STACC=flight,SYDT=5.0912322998046875 if i==23 else .5 if i in began else None,NSYDT=int(i in began))
  for k,v in expected.items():
   if isinstance(v,float):a.near(sr[k],v,f"SystemResults bin {i} {k}")
   else:a.eq(sr[k],v,f"SystemResults bin {i} {k}")
  bo=2*ov(11.5,15.9245657921,lo,hi)
  stock={k:0 for k in tr}
  stock.update(STINT=lo,ETINT=hi,NBO=bo,NBOU=None,ROS=1 if i==23 else 0 if i in demand else None,ROST=1 if i==23 else 0 if i in demand else None,WT=4.42456579208374 if i==23 else 0 if i in demand else None,WTT=4.42456579208374 if i==23 else 0 if i in demand else None,WTS=4.42456579208374 if i==23 else None,PNB=1-bo,NDF=int(i in demand),NWT=int(i in demand))
  for k,v in stock.items():
   if isinstance(v,float):a.near(tr[k],v,f"StockTotalResults bin {i} {k}")
   else:a.eq(tr[k],v,f"StockTotalResults bin {i} {k}")
 a.eq(sum(x["NFAIL"] for x in s),4,"four failures")
 a.eq(sum(x["NREPT"] for x in s),3,"three report-binned completed system repairs")
 a.near(sum(x["NBO"]*.5 for x in t),4.4245657921,"BASE-02 local backorder hours")
 a.eq((s[-1]["NSYRY"],s[-1]["NSYUA"]),(1,1),"h35.5-36 report ready1/unavailable1")
 a.eq(report["ResultSummary"],preport["ResultSummary"],"parent/child full summary equality")
 ps=records(preport["SystemResults"]);pt=records(preport["StockTotalResults"])
 a.eq([i for i,(x,y) in enumerate(zip(ps,s)) if x!=y],list(range(23,34)),"system differences limited to BASE-02 wait/repair bins")
 a.eq([i for i,(x,y) in enumerate(zip(pt,t)) if x!=y],list(range(23,32)),"stock differences limited to local BO bins")
 a.eq(sum(x["NBO"] for x in pt),0,"parent zero aggregate BO")
 a.check(report["ProblemDescription"]!=preport["ProblemDescription"],"report description changed")
 result={"schema":"simlox-independent-readonly-review/v1","case_id":"E12.var05","run_id":RUN.name,"passed":not a.failures,"verdict":"GO: bounded asymmetric BASE-02 zero-stock behavior" if not a.failures else "NO-GO: independent replay mismatch","checks_passed":a.passed,"checks_total":a.passed+len(a.failures),"failures":a.failures,"evidence":{"closure_sha256":sha(RUN/"closure.json"),"parent_closure_sha256":sha(PRUN/"closure.json"),"raw_seals":len(closure["raw"]),"authored_tables_exact_roundtrip":len(authored),"report_bins_each":72,"opening_physical_stock":{"DEPOT-01":[0],"BASE-01":[1],"BASE-02":[]},"first_wave_failed_ids":[2,3],"local_base02_backorder":[11.5,15.9246],"depot_backorder":[11.5,14.9246],"mission_outcomes":["abort","abort","abort","success","abort","success"],"changed_parent_system_bins":list(range(23,34)),"changed_parent_stock_bins":list(range(23,32))},"limits":["One seed, one item type, two bases and 36-hour horizon; altered opening stock changes physical IDs and may alter later random draws.","BASE-02's local stock backorder is observed and reflected in aggregate NBO; depot backorder is separately visible in model.log and not independently exposed as a station-specific report row.","At h36 the event log records both aircraft ready, while final [35.5,36) report interval is ready1/unavailable1; final failed item ID5 is still in transit.","No resource allocation, GUI visual or cross-engine claim."]}
 OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
 return result

if __name__=="__main__":
 r=main();print(json.dumps({k:r[k] for k in ("verdict","checks_passed","checks_total","failures")},indent=2));sys.exit(0 if r["passed"] else 1)
