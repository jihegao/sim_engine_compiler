"""Independent standard-library replay of the sealed E13 ENROB Y/N pair."""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path

OUT=Path(__file__).with_name("independent-verdict.json")
ROOT=Path(__file__).resolve().parents[2]
E=ROOT/"E13-var01-two-item-robbing-probe-v0.1.2"
N=ROOT/"E13-var01-two-item-no-robbing-control-v0.1.3"
P=ROOT/"E03-two-aircraft-shared-spare-v1.0.0"
V10=ROOT/"E13-var01-two-item-robbing-probe-v0.1.0"
V11=ROOT/"E13-var01-two-item-robbing-probe-v0.1.1"
ER=E/"runs"/"e13-var01-two-item-probe-v012-ssh-20261004-01"
NR=N/"runs"/"e13-var01-no-robbing-control-v013-ssh-20261004-01"
PR=P/"runs"/"e03-v100-ssh-20260929-01"
class Audit:
 def __init__(self):self.passed=0;self.failures=[]
 def ok(self,test,label):
  if test:self.passed+=1
  else:self.failures.append(label)
 def eq(self,got,want,label):self.ok(got==want,f"{label}: {got!r} != {want!r}")
 def near(self,got,want,label,tol=.00025):self.ok(isinstance(got,(float,int)) and abs(got-want)<=tol,f"{label}: {got!r} != {want!r}")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p,native=False):
 s=p.read_text(encoding="utf-8-sig")
 return json.loads(re.sub(r",\s*([}\]])",r"\1",s) if native else s)
def tables(p,root="model"):return {t["name"]:t for t in load(p,root=="report")[root]["tables"]}
def rows(t):return [r for inst in t["instances"] for r in inst.get("rows",[])]
def records(t):
 names=[c["name"] for c in t["columns"]]
 return [dict(zip(names,r)) for r in rows(t)]
def area(a,b,lo,hi):return max(0,min(b,hi)-max(a,lo))

def main():
 a=Audit(); cfg={"Y":(E,ER),"N":(N,NR)};parent=tables(P/"native-input.json")
 installed={"simlox_exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),"manual":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),"dictionary":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
 prior={"preceding_closure_one":V10/"runs"/"e13-var01-two-item-probe-v010-ssh-20261004-01"/"closure.json","preceding_closure_two":V11/"runs"/"e13-var01-two-item-probe-v011-ssh-20261004-01"/"closure.json"}
 data={}
 for arm,(package,run) in cfg.items():
  contract=load(package/"contract.json");diff=load(package/"exact-diff.json");source=tables(package/"native-input.json")
  export=tables(run/"roundtrip-raw.json");report=tables(run/"report-raw.json","report")
  inv=load(run/"invocation.json");closure=load(run/"closure.json");steps=load(run/"steps.json")
  log=(run/"model.log").read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
  converter=(run/"run.log").read_text(encoding="utf-8-sig",errors="replace")
  data[arm]={"source":source,"report":report,"log":log,"closure":closure}
  a.eq(sha(package/"native-input.json"),contract["native_input_sha256"],f"{arm} input pin")
  a.eq(sha(package/"exact-diff.json"),contract["exact_diff_sha256"],f"{arm} diff pin")
  a.eq(sha(P/"native-input.json"),contract["accepted_parent"]["input_sha256"],f"{arm} E03 input pin")
  a.eq(sha(PR/"closure.json"),contract["accepted_parent"]["native_closure_sha256"],f"{arm} E03 closure pin")
  a.eq(sha(P/"cli-scope-signoff-2026-09-29.md"),contract["accepted_parent"]["signoff_sha256"],f"{arm} E03 signoff pin")
  for index,key in enumerate(("preceding_closure_one","preceding_closure_two")):
   a.eq(sha(prior[key]),contract["preceding_diagnostics"][index]["closure_sha256"],f"{arm} excluded earlier diagnostic {index}")
  a.eq(diff["parent_sha256"],sha(P/"native-input.json"),f"{arm} diff parent")
  a.eq(diff["source_sha256"],sha(package/"native-input.json"),f"{arm} diff child")
  a.eq(len(source),31,f"{arm} table count")
  changed=sorted(n for n in source if source[n]!=parent[n]);a.eq(changed,diff["changed_tables"],f"{arm} exact changed tables")
  a.eq(diff["unchanged_parent_tables"],24,f"{arm} fixed tables")
  for name in sorted(source):
   a.eq(source[name]["columns"],parent[name]["columns"],f"{arm} {name} schema")
   if name not in changed:a.eq(source[name],parent[name],f"{arm} fixed {name}")
  a.eq(len(diff["modified_cells"]),6,f"{arm} six changed cells")
  a.eq(len(diff["added_rows"]),4,f"{arm} four added rows")
  for spec in diff["modified_cells"]:
   name=spec["table"];j=next(i for i,c in enumerate(source[name]["columns"]) if c["name"]==spec["column"])
   a.eq(rows(parent[name])[spec["row"]][j],spec["before"],f"{arm} old {name}.{spec['column']}")
   a.eq(rows(source[name])[spec["row"]][j],spec["after"],f"{arm} new {name}.{spec['column']}")
  for spec in diff["added_rows"]:a.eq(records(source[spec["table"]])[spec["row"]],spec["values"],f"{arm} added {spec['table']} row")
  for name in changed:
   old=rows(parent[name]);new=rows(source[name]);cols=[x["name"] for x in source[name]["columns"]]
   a.eq(len(new)-len(old),sum(x["table"]==name for x in diff["added_rows"]),f"{arm} only declared {name} row additions")
   actual=[(i,cols[j]) for i,(r,s) in enumerate(zip(old,new)) for j,(u,v) in enumerate(zip(r,s)) if u!=v]
   expected=[(x["row"],x["column"]) for x in diff["modified_cells"] if x["table"]==name]
   a.eq(actual,expected,f"{arm} only declared {name} cell edits")
  a.eq(records(source["Control"])[0]["ENROB"],arm,f"{arm} global ENROB")
  a.eq({r["IID"]:r["STSIZ"] for r in records(source["StockAllocation"])},{"TEACH-LRU-01":0,"TEACH-LRU-02":0},f"{arm} no opening spares")
  a.eq({r["IID"]:r["DIRPT"] for r in records(source["ItemRepair"])},{"TEACH-LRU-01":12,"TEACH-LRU-02":4},f"{arm} A-long B-short repair")
  for key,p in installed.items():
   field={"simlox_exe":"simlox_exe_sha256","manual":"manual_pdf_sha256","dictionary":"dictionary_sha256"}[key]
   a.eq(sha(p),contract["source"][field],f"{arm} installed {key}")
  a.eq(inv["run_id"],run.name,f"{arm} run identity")
  a.eq(inv["execution_mode"],"ssh_cli_v1",f"{arm} SSH mode")
  a.eq(inv["session_id"],0,f"{arm} SSH session zero")
  a.ok(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"],f"{arm} SSH daemon")
  a.eq(inv["queue_mutex"],r"Global\SimloxIssue18NativeQueue",f"{arm} mutex")
  a.eq((inv["gui"]["pid"],inv["gui"]["session_id"]),(13340,1),f"{arm} GUI identity")
  a.eq(inv["input_sha256"],sha(package/"native-input.json"),f"{arm} invoked source")
  a.eq(closure["invocation_sha256"],sha(run/"invocation.json"),f"{arm} invocation seal")
  a.eq(closure["source_hashes_before"],closure["source_hashes_after"],f"{arm} source stable")
  a.eq(closure["source_hashes_before"],inv["source_hashes_before"],f"{arm} invocation source agreement")
  paths={"input":package/"native-input.json","parent":P/"native-input.json","parent_closure":PR/"closure.json","parent_signoff":P/"cli-scope-signoff-2026-09-29.md","contract":package/"contract.json","exact_diff":package/"exact-diff.json","builder":package/"build.py","diff_builder":package/"describe_diff.py","checker":package/"check_roundtrip.py","runner_script":package/"run_native_ssh.ps1","python":Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),**prior,**installed}
  if arm=="N":
   paths.update(enabled_input=E/"native-input.json",enabled_closure=ER/"closure.json")
   a.eq(sha(E/"native-input.json"),contract["paired_enabled"]["input_sha256"],"N paired enabled input")
   a.eq(sha(ER/"closure.json"),contract["paired_enabled"]["closure_sha256"],"N paired enabled closure")
  for key,p in sorted(paths.items()):a.eq(closure["source_hashes_before"][key],sha(p),f"{arm} source seal {key}")
  a.eq(len(closure["raw"]),12,f"{arm} twelve raw seals")
  for name,meta in sorted(closure["raw"].items()):
   p=run/name;a.ok(p.is_file(),f"{arm} raw exists {name}")
   if p.is_file():a.eq(p.stat().st_size,meta["bytes"],f"{arm} raw bytes {name}");a.eq(sha(p),meta["sha256"],f"{arm} raw SHA {name}")
  a.eq(sha(run/"input.json"),sha(package/"native-input.json"),f"{arm} raw input copy")
  a.eq([s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"],f"{arm} five steps")
  for step in steps:
   a.eq(step["exit_code"],0,f"{arm} {step['name']} exit")
   a.eq(step["status"],"completed",f"{arm} {step['name']} status")
   a.eq(step["error"],None,f"{arm} {step['name']} error")
   a.eq(step["gui_preserved"],True,f"{arm} {step['name']} GUI preserved")
  authored=sorted(n for n,t in source.items() if rows(t));a.eq(len(authored),20,f"{arm} twenty row-containing tables")
  a.eq(set(export),set(source),f"{arm} export table set")
  for name in authored:a.eq(export[name],source[name],f"{arm} authored roundtrip {name}")
  a.ok((run/"model.sxo").stat().st_size>4,f"{arm} usable SXO")
  a.eq(re.findall(r"\(error #(\d+)\)",converter),[],f"{arm} conversion errors zero")
  a.eq(re.findall(r"\(warning #(\d+)\)",converter),["108"],f"{arm} warning108 only")
  a.ok("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter,f"{arm} converter summary")
  lines=log.splitlines()
  def event(hour,fragment):a.ok(any(line.startswith(f"Time: {hour} ") and fragment in line for line in lines),f"{arm} event {hour} {fragment}")
  for item in ("TEACH-LRU-01","TEACH-LRU-02"):
   a.ok(f"Stock at: <{item},0,BASE-01,0> Level: 0 Items:" in log,f"{arm} zero opening {item} stock")
  for mid,air in ((0,0),(1,1)):
   ident=f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
   event("7",f"{ident} mission created:")
   event("7",f"{ident} mission allocates system: <TEACH-AIR-01,{air}>")
   event("8",f"{ident} mission starting, duration: 2 : <TEACH-AIR-01,{air}>")
   event(("8.09414","8.15663")[mid],f"{ident} mission aborted:")
  event("8.09414","<TEACH-AIR-01,0> critical random failure added")
  event("8.15663","<TEACH-AIR-01,1> critical random failure added")
  a.ok("subitem failed: <TEACH-LRU-01,0,0>" in log,f"{arm} donor A0 failure")
  a.ok("subitem failed: <TEACH-LRU-02,0,1>" in log,f"{arm} recipient B1 failure")
  event("8.18829","system SURP task 0 on <TEACH-AIR-01,0> started")
  event("8.31325","system SURP task 1 on <TEACH-AIR-01,1> started")
  for start,end,item,task in [("8.35496","20.355","TEACH-LRU-01,0,0",2),("8.47992","12.4799","TEACH-LRU-02,0,1",3)]:
   event(start,f"Start repair of item <{item}>")
   event(end,f"Finished repair of item <{item}>")
   event(start,f"item DIRP task {task} on <{item}> started")
  for hour,item,wait in [("8.18829","TEACH-LRU-01",None),("8.31325","TEACH-LRU-02",None)]:event(hour,f"<{item},0,BASE-01,0> Backorder added")
  for hour,item,wait in [("20.355","TEACH-LRU-01","12.1667"),("12.4799","TEACH-LRU-02","4.16667")]:event(hour,f"<{item},0,BASE-01,0> Backorder removed, waiting time was {wait}")
  a.eq(log.count("Backorder added"),2,f"{arm} two item backorders")
  a.eq(log.count("Backorder removed"),2,f"{arm} two backorders cleared")
  event("20.355","system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,0>")
  event("20.6883","system SURP task 0 on <TEACH-AIR-01,0> completed")
  event("20.6883","System ready <TEACH-AIR-01,0>")
  event("20.6883","systems ready: 2 :<TEACH-AIR-01,1>,<TEACH-AIR-01,0>")
  for phrase,count in [("mission created:",2),("mission aborted:",2),("mission success:",0),("critical random failure added",2),("books resources",0)]:a.eq(log.count(phrase),count,f"{arm} count {phrase}")
  if arm=="Y":
   for hour,fragment in [("8.47992","system SURP task 1 on <TEACH-AIR-01,1> starts to rob"),("8.47992","robbing task 4 on <TEACH-AIR-01,0> started"),("8.64659","remove subitem subtask 6 seqno 1 within robbing task 4 on <TEACH-AIR-01,0> completed"),("8.64659","system SURP task 1 on <TEACH-AIR-01,1> subitem received <TEACH-LRU-02,0,2>"),("8.97992","system SURP task 1 on <TEACH-AIR-01,1> completed"),("8.97992","System ready <TEACH-AIR-01,1>"),("12.4799","robbing task 4 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-02,0,1>"),("12.8133","robbing task 4 on <TEACH-AIR-01,0> completed")]:event(hour,fragment)
   a.eq(log.count("starts to rob"),1,"Y one rob initiation")
   a.eq(sum(line=="Time: 8.47992  robbing task 4 on <TEACH-AIR-01,0> started" for line in lines),1,"Y one donor rob task")
  else:
   a.eq(log.count("robbing task"),0,"N no rob task")
   a.eq(log.count("starts to rob"),0,"N no rob initiation")
   event("12.4799","system SURP task 1 on <TEACH-AIR-01,1> subitem received <TEACH-LRU-02,0,1>")
   event("12.8133","system SURP task 1 on <TEACH-AIR-01,1> completed")
   event("12.8133","System ready <TEACH-AIR-01,1>")
  a.eq(set(report),{"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},f"{arm} report tables")
  a.eq(rows(report["ResultSummary"])[0],[1,0,36,0.12538555264472961,0,1,0,0,0,0.12538555264472961,0],f"{arm} result summary")
  system=records(report["SystemResults"]);stock=records(report["StockTotalResults"])
  a.eq((len(system),len(stock)),(72,72),f"{arm} report bins")
  ready1=8.97992 if arm=="Y" else 12.8133
  release1=ready1
  work=[(8.18829,8.3549566667),(20.355,20.6883333333)]
  wait=[(8.3549566667,20.355)]
  if arm=="Y":
   work +=[(8.31325,8.9799166667),(12.4799,12.8132333333)]
   wait +=[]
  else:
   work +=[(8.31325,8.4799166667),(12.4799,12.8132333333)]
   wait +=[(8.4799166667,12.4799)]
  if arm=="Y":
   # The donor's robbing fit occupies its system work state; remove is hidden by the main SURP wait state.
   wait=[(8.3549566667,12.4799),(12.8132333333,20.355)]
  for i,(sr,tr) in enumerate(zip(system,stock)):
   lo=i/2;hi=(i+1)/2
   a.eq((sr["STINT"],sr["ETINT"],tr["STINT"],tr["ETINT"]),(lo,hi,lo,hi),f"{arm} bin {i} bounds")
   # Native operating/mission occupancy continues through the aircraft's aborted return.
   flights=[(8,8.18829),(8,8.31325)];missions=[(7,8.18829),(7,8.31325)]
   available=2-2*(area(8.18829,20.6883,lo,hi)+area(8.31325,release1,lo,hi))
   expected={k:0 for k in sr}
   flight=2*sum(area(x,y,lo,hi) for x,y in flights)
   expected.update(UNID="Total over all Units",SID="Total over all Systems",STINT=lo,ETINT=hi,NSYRY=4*area(0,7,lo,hi)+2*area(ready1,20.6883,lo,hi)+4*area(20.6883,36,lo,hi),NSYMA=2*sum(area(x,y,lo,hi) for x,y in missions),NSYMO=flight,NSYMR=4*area(7,8,lo,hi),NSYUA=2-available,NSYA=available,FTMO=flight/2,NSYRP=2*sum(area(x,y,lo,hi) for x,y in work),NSYWI=2*sum(area(x,y,lo,hi) for x,y in wait),NREPT=int(i in ({17,25,41} if arm=="Y" else {25,41})),NFAIL=2 if i==16 else 0,NROBT=1 if arm=="Y" and i==16 else 0,STACC=flight,SYDT=(6.583333492279053 if arm=="Y" else 8.5) if i==16 else None,NSYDT=2 if i==16 else 0)
   for k,v in expected.items():
    if isinstance(v,float):a.near(sr[k],v,f"{arm} System bin {i} {k}")
    else:a.eq(sr[k],v,f"{arm} System bin {i} {k}")
   bo=2*(area(8.18829,20.355,lo,hi)+area(8.31325,12.4799,lo,hi))
   pnb=2*sum(area(x,y,lo,hi) for x,y in [(0,8.18829),(20.355,36)])
   st={k:0 for k in tr}
   st.update(STINT=lo,ETINT=hi,NBO=bo,NBOU=None,ROS=1 if i==16 else None,ROST=1 if i==16 else None,WT=8.166666984558105 if i==16 else None,WTT=8.166666984558105 if i==16 else None,WTS=8.166666984558105 if i==16 else None,PNB=pnb,NDF=2 if i==16 else 0,NWT=2 if i==16 else 0)
   for k,v in st.items():
    if isinstance(v,float):a.near(tr[k],v,f"{arm} Stock bin {i} {k}")
    else:a.eq(tr[k],v,f"{arm} Stock bin {i} {k}")
  a.eq(sum(x["NROBT"] for x in system),int(arm=="Y"),f"{arm} NROBT total")
  a.eq(sum(x["NFAIL"] for x in system),2,f"{arm} two report failures")
  a.eq(system[-1]["NSYRY"],2,f"{arm} terminal report ready two")
  a.eq(sum(x["NBO"]*.5 for x in stock)>0,True,f"{arm} positive stock backorder time")

 yes=data["Y"];no=data["N"]
 for name in sorted(yes["source"]):
  if name in ("Control","ProblemDescription"):continue
  a.eq(yes["source"][name],no["source"][name],f"pair fixed {name}")
 for name,field in (("Control","ENROB"),("ProblemDescription","PDESC")):
  yp=yes["source"][name];np=no["source"][name]
  a.eq(yp["columns"],np["columns"],f"pair {name} schema")
  cols=[x["name"] for x in yp["columns"]]
  actual=[(i,cols[j]) for i,(r,s) in enumerate(zip(rows(yp),rows(np))) for j,(x,y) in enumerate(zip(r,s)) if x!=y]
  a.eq(actual,[(0,field)],f"pair only {name}.{field}")
 a.eq(sha(ER/"closure.json"),load(N/"contract.json")["paired_enabled"]["closure_sha256"],"paired enabled closure")
 yl=yes["log"].splitlines();nl=no["log"].splitlines()
 a.eq(yl[:111],nl[:111],"same complete predecision log through B item repair start")
 yr=yes["report"];nr=no["report"]
 a.eq(yr["ResultSummary"],nr["ResultSummary"],"paired summary equality")
 a.eq(yr["StockTotalResults"],nr["StockTotalResults"],"all 72 paired stock rows equal")
 sy=rows(yr["SystemResults"]);sn=rows(nr["SystemResults"])
 a.eq([i for i,(x,y) in enumerate(zip(sy,sn)) if x!=y],list(range(16,26)),"system differences only during robbing benefit")
 a.ok(yr["ProblemDescription"]!=nr["ProblemDescription"],"paired report descriptions differ")
 result={"schema":"simlox-independent-readonly-review/v1","case_id":"E13.var01","passed":not a.failures,"verdict":"GO: bounded matched ENROB Y/N robbing contrast" if not a.failures else "NO-GO: independent replay mismatch","checks_passed":a.passed,"checks_total":a.passed+len(a.failures),"failures":a.failures,"evidence":{"enabled_closure_sha256":sha(ER/"closure.json"),"disabled_closure_sha256":sha(NR/"closure.json"),"raw_seals_each":12,"roundtrip_tables_each":20,"donor_aircraft":0,"recipient_aircraft":1,"robbed_physical_item":"TEACH-LRU-02,0,2","recipient_ready_hours":{"Y":8.97992,"N":12.8133},"donor_ready_hours":{"Y":20.6883,"N":20.6883},"NROBT_total":{"Y":1,"N":0},"result_summary_equal":True,"stock_report_all_72_rows_equal":True,"system_report_changed_bins":list(range(16,26))},"limits":["One fixed seed, two traditional item types, two aircraft in one unit/base, zero opening stock, no resources and 36-hour horizon; no general robbing-rate law.","The native log identifies donor rob task on aircraft0 and receipt of physical B item2 by aircraft1; removal of B2 from donor is inferred from the task's remove subtask and immediate identity-matched receipt, not an explicit donor-item-removal sentence.","NROBT exists in SystemResults; there is no NRB column in the selected default report, so no numerical NRB claim is made.","StockTotalResults aggregate rows are identical even though physical B2 moves between aircraft; event identities and SystemResults expose the contrast.","No explicit failure-mode/CM-task, resource scarcity, GUI visual or cross-engine claim. Earlier v0.1.0/v0.1.1 diagnostics are excluded."]}
 OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
 return result

if __name__=="__main__":
 result=main();print(json.dumps({key:result[key] for key in ("verdict","checks_passed","checks_total","failures")},indent=2));sys.exit(0 if result["passed"] else 1)
