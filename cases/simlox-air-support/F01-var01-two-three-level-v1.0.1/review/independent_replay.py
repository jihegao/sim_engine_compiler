"""Independent read-only replay of F01.var01 two- and three-level evidence."""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
ROOT=CASE.parent
E05=ROOT/"E05-local-repair-reissue-v1.0.0"
G01=ROOT/"G01-var01-lru-sru-v1.0.1"
OLD=ROOT/"F01-var01-nested-reissue-v1.0.0"
RUNS={"two":CASE/"runs"/"f01-var01-two-v101-ssh-20261004-01","three":CASE/"runs"/"f01-var01-three-v101-ssh-20261004-01"}
E05RUN=E05/"runs"/"e05-v100-ssh-20260929-01"
G01RUN=G01/"runs"/"g01-var01-v101-ssh-20261001-01"
OLDRUN=OLD/"runs"/"f01-var01-nested-v100-ssh-20261004-01"
OUT=Path(__file__).with_name("independent-verdict.json")
class Audit:
 def __init__(self):self.good=0;self.bad=[]
 def ok(self,value,name):
  if value:self.good+=1
  else:self.bad.append(name)
 def eq(self,got,want,name):self.ok(got==want,f"{name}: {got!r} != {want!r}")
 def near(self,got,want,name,tol=.0003):self.ok(isinstance(got,(int,float)) and abs(got-want)<=tol,f"{name}: {got!r} != {want!r}")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p,native=False):
 s=p.read_text(encoding="utf-8-sig")
 return json.loads(re.sub(r",\s*([}\]])",r"\1",s) if native else s)
def tablemap(p,root="model"):return {x["name"]:x for x in load(p,root=="report")[root]["tables"]}
def rows(t):return [row for inst in t["instances"] for row in inst.get("rows",[])]
def recs(t):
 cols=[c["name"] for c in t["columns"]]
 return [dict(zip(cols,row)) for row in rows(t)]
def overlap(a,b,lo,hi):return max(0,min(b,hi)-max(a,lo))

def main():
 a=Audit();contract=load(CASE/"contract.json");diff=load(CASE/"exact-diff.json")
 e05=tablemap(E05/"native-input.json");g01=tablemap(G01/"native-input.json")
 source={arm:tablemap(CASE/f"{arm}-level-input.json") for arm in RUNS}
 a.eq(contract["variant_id"],"F01.var01","variant pin")
 a.eq(sha(CASE/"two-level-input.json"),contract["two_level_input_sha256"],"two input pin")
 a.eq(sha(CASE/"three-level-input.json"),contract["three_level_input_sha256"],"three input pin")
 a.eq(sha(CASE/"exact-diff.json"),contract["exact_diff_sha256"],"diff pin")
 for parent,path,run,key in [("two",E05,E05RUN,"accepted_two_level_parent"),("three",G01,G01RUN,"accepted_three_level_parent")]:
  spec=contract[key]
  a.eq(sha(path/"native-input.json"),spec["input_sha256"],f"{parent} parent source")
  a.eq(sha(run/"closure.json"),spec["native_closure_sha256"],f"{parent} parent closure")
 a.eq(sha(G01/"evidence-index.json"),contract["accepted_three_level_parent"]["evidence_index_sha256"],"G01 index pin")
 a.eq(sha(OLD/"native-input.json"),contract["preceding_unpublished_diagnostic"]["input_sha256"],"excluded v1.0.0 input")
 a.eq(sha(OLDRUN/"closure.json"),contract["preceding_unpublished_diagnostic"]["closure_sha256"],"excluded v1.0.0 run")
 specs=[("two_from_e05",e05,source["two"]),("three_from_g01",g01,source["three"]),("three_from_two",source["two"],source["three"])]
 for name,left,right in specs:
  spec=diff[name];a.eq(spec["left_sha256"],sha((E05/"native-input.json") if name=="two_from_e05" else (G01/"native-input.json") if name=="three_from_g01" else CASE/"two-level-input.json"),f"{name} left hash")
  a.eq(spec["right_sha256"],sha(CASE/("two-level-input.json" if name=="two_from_e05" else "three-level-input.json")),f"{name} right hash")
  changed=sorted(k for k in left if left[k]!=right[k]);a.eq(changed,sorted(x["table"] for x in spec["changed_tables"]),f"{name} exact changed tables")
  a.eq(spec["unchanged_tables"],len(left)-len(changed),f"{name} fixed count")
  for table in sorted(left):
   a.eq(left[table]["columns"],right[table]["columns"],f"{name} {table} schema")
   if table not in changed:a.eq(left[table],right[table],f"{name} fixed {table}")
  for rowset in spec["changed_tables"]:
   table=rowset["table"]
   a.eq(rows(left[table]),rowset["before_rows"],f"{name} {table} before rows")
   a.eq(rows(right[table]),rowset["after_rows"],f"{name} {table} after rows")
 a.eq({r["IID"]:r["FRT"] for r in recs(source["three"]["Item"])},{"TEACH-LRU-01":1200000,"TEACH-SRU-01":1200000},"three-level item failure rates")
 a.eq(recs(source["three"]["System"])[0]["FRT"],1200000,"system failure rate")
 a.eq({r["IID"]:r["STSIZ"] for r in recs(source["three"]["StockAllocation"])},{"TEACH-LRU-01":1,"TEACH-SRU-01":1},"three-level opening stocks")
 a.eq(recs(source["three"]["ItemRepair"])[0]["SURPT"],1.5,"general LRU SURP 1.5")
 a.eq(recs(source["three"]["ItemReplacement"])[0]["SURPT"],.75,"specific LRU/SRU SURP .75")
 a.eq(recs(source["three"]["ItemRepair"])[1]["DIRPT"],1.0,"SRU direct repair one hour")
 installed={"simlox_exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),"manual":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),"dictionary":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
 for k,p in installed.items():
  field={"simlox_exe":"simlox_exe_sha256","manual":"manual_pdf_sha256","dictionary":"dictionary_sha256"}[k]
  a.eq(sha(p),contract["source"][field],f"installed {k}")
 evidence={}
 for arm,run in RUNS.items():
  input_path=CASE/f"{arm}-level-input.json";export=tablemap(run/"roundtrip-raw.json");report=tablemap(run/"report-raw.json","report")
  inv=load(run/"invocation.json");closure=load(run/"closure.json");steps=load(run/"steps.json")
  converter=(run/"run.log").read_text(encoding="utf-8-sig",errors="replace")
  log=(run/"model.log").read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
  evidence[arm]={"report":report,"log":log,"closure":closure}
  a.eq(inv["run_id"],run.name,f"{arm} run ID")
  a.eq(inv["execution_mode"],"ssh_cli_v1",f"{arm} SSH CLI")
  a.eq(inv["session_id"],0,f"{arm} session zero")
  a.ok(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"],f"{arm} SSH daemon")
  a.eq(inv["queue_mutex"],r"Global\SimloxIssue18NativeQueue",f"{arm} mutex")
  a.eq((inv["gui"]["pid"],inv["gui"]["session_id"]),(13340,1),f"{arm} GUI preserved")
  a.eq(inv["input_sha256"],sha(input_path),f"{arm} invoked input")
  a.eq(closure["invocation_sha256"],sha(run/"invocation.json"),f"{arm} invocation seal")
  a.eq(closure["source_hashes_before"],closure["source_hashes_after"],f"{arm} source stable")
  a.eq(closure["source_hashes_before"],inv["source_hashes_before"],f"{arm} source invocation agreement")
  paths={"input":input_path,"two_input":CASE/"two-level-input.json","three_input":CASE/"three-level-input.json","parent":G01/"native-input.json","parent_closure":G01RUN/"closure.json","parent_evidence_index":G01/"evidence-index.json","exposure_reference":E05/"native-input.json","exposure_reference_closure":E05RUN/"closure.json","preceding_diagnostic_closure":OLDRUN/"closure.json","exact_diff":CASE/"exact-diff.json","contract":CASE/"contract.json","builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py","checker":CASE/"check_roundtrip.py","python":Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),"runner_script":CASE/"run_native_ssh.ps1",**installed}
  for k,p in sorted(paths.items()):a.eq(closure["source_hashes_before"][k],sha(p),f"{arm} source seal {k}")
  a.eq(len(closure["raw"]),12,f"{arm} twelve raw seals")
  for n,meta in sorted(closure["raw"].items()):
   p=run/n;a.ok(p.is_file(),f"{arm} raw exists {n}")
   if p.is_file():a.eq(p.stat().st_size,meta["bytes"],f"{arm} raw bytes {n}");a.eq(sha(p),meta["sha256"],f"{arm} raw SHA {n}")
  a.eq(sha(run/"input.json"),sha(input_path),f"{arm} run input copy")
  a.eq([s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"],f"{arm} five steps")
  for step in steps:
   a.eq(step["exit_code"],0,f"{arm} {step['name']} exit")
   a.eq(step["status"],"completed",f"{arm} {step['name']} status")
   a.eq(step["error"],None,f"{arm} {step['name']} error")
   a.eq(step["gui_preserved"],True,f"{arm} {step['name']} GUI preserved")
  authored=sorted(n for n,t in source[arm].items() if rows(t))
  a.eq(len(authored),20 if arm=="two" else 21,f"{arm} row-containing source tables")
  a.eq(set(export),set(source[arm]),f"{arm} native export tables")
  for n in authored:a.eq(export[n],source[arm][n],f"{arm} authored roundtrip {n}")
  a.ok((run/"model.sxi").stat().st_size>4 and (run/"model.sxo").stat().st_size>4,f"{arm} usable SXI and SXO")
  a.eq(re.findall(r"\(error #(\d+)\)",converter),[],f"{arm} conversion errors zero")
  a.eq(re.findall(r"\(warning #(\d+)\)",converter),["108"],f"{arm} warning108 only")
  a.ok("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter,f"{arm} converter summary")
  lines=log.splitlines()
  def event(hour,part):a.ok(any(line.startswith(f"Time: {hour} ") and part in line for line in lines),f"{arm} event {hour} {part}")
  for mid,ordered,start in [(0,"7","8"),(1,"19","20"),(2,"31","32")]:
   ident=f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
   event(ordered,f"{ident} mission created:")
   event(start,f"{ident} mission starting, duration: 2 : <TEACH-AIR-01,0>")
  for mid,h in [(0,"8.47072"),(1,"20.8247")]:event(h,f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}> mission aborted:")
  event("34","<BASIC-MISSION,TEACH-UNIT,0,0,2> mission success:")
  for h in ("8.47072","20.8247"):event(h,"<TEACH-AIR-01,0> critical random failure added")
  for phrase,count in [("mission created:",3),("mission aborted:",2),("mission success:",1),("critical random failure added",2),("Backorder added",0),("books resources",0)]:a.eq(log.count(phrase),count,f"{arm} count {phrase}")
  a.eq(log.count("requests resources: no resources needed"),6 if arm=="two" else 10,f"{arm} every maintenance subtask requires no resource")
  for start,end,task in [("8.94145","9.44145",0),("21.3247","21.8247",2 if arm=="two" else 3)]:
   event(start,f"system SURP task {task} on <TEACH-AIR-01,0> started")
   event(end,f"system SURP task {task} on <TEACH-AIR-01,0> completed")
  for h in ("9.44145","21.8247","34"):event(h,"<TEACH-UNIT at <BASE-01,0>> systems ready: 1")
  if arm=="two":
   a.ok("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log,"two opening LRU0")
   for fail,removed,spare,issue,finish in [("8.47072",1,0,"8.94145","10.1081"),("20.8247",2,1,"21.3247","22.4913")]:
    a.ok(f"subitem failed: <TEACH-LRU-01,0,{removed}>" in log,f"two LRU failure ID{removed}")
    event(issue,f"<TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,{spare}> from stock")
    event("9.10812" if removed==1 else "21.4913",f"<TEACH-LRU-01,0,BASE-01,0> Start repair of item <TEACH-LRU-01,0,{removed}>")
    event(finish,f"<TEACH-LRU-01,0,BASE-01,0> Finished repair of item <TEACH-LRU-01,0,{removed}>")
    event(finish,f"<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{removed}> to stock")
   a.eq(log.count("item SURP task"),0,"two no nested item SURP")
   a.eq(log.count("TEACH-SRU-01"),0,"two no SRU physical events")
  else:
   a.ok("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>" in log,"three opening LRU1")
   a.ok("Stock at: <TEACH-SRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-SRU-01,0,0>" in log,"three opening SRU0")
   cycles=[("8.47072","8.94145","9.10812","9.85812","9.48312","10.4831",2,1,3,0,1),
           ("20.8247","21.3247","21.4913","22.2413","21.8663","22.8663",4,2,5,3,4)]
   for fail,issue,lstart,lend,sstart,send,lfailed,lspare,sfailed,sspare,task in cycles:
    a.ok(f"subitem failed: <TEACH-LRU-01,0,{lfailed}>" in log,f"three LRU failure ID{lfailed}")
    event(issue,f"<TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,{lspare}> from stock")
    event(lstart,f"<TEACH-LRU-01,0,BASE-01,0> Start repair of item <TEACH-LRU-01,0,{lfailed}>")
    event(lstart,f"item SURP task {task} on <TEACH-LRU-01,0,{lfailed}> started")
    a.ok(f"Item requiring maintenance arrives <TEACH-LRU-01,0,{lfailed}> from position <TEACH-AIR-01,BASE-01,0> subitem failed: <TEACH-SRU-01,0,{sfailed}>" in log,f"nested failed SRU{sfailed} inside LRU{lfailed}")
    event(lstart,f"<TEACH-SRU-01,0,BASE-01,0> Take replacement item <TEACH-SRU-01,0,{sspare}> from stock")
    event(lend,f"item SURP task {task} on <TEACH-LRU-01,0,{lfailed}> completed")
    event(lend,f"<TEACH-LRU-01,0,BASE-01,0> Finished repair of item <TEACH-LRU-01,0,{lfailed}>")
    event(lend,f"<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{lfailed}> to stock")
    event(sstart,f"<TEACH-SRU-01,0,BASE-01,0> Start repair of item <TEACH-SRU-01,0,{sfailed}>")
    event(send,f"<TEACH-SRU-01,0,BASE-01,0> Finished repair of item <TEACH-SRU-01,0,{sfailed}>")
    event(send,f"<TEACH-SRU-01,0,BASE-01,0> Put back replacement item <TEACH-SRU-01,0,{sfailed}> to stock")
    a.near(float(lend)-float(lstart),.75,f"three LRU{lfailed} uses .75 specific SURP",.0001)
    a.near(float(send)-float(sstart),1,f"three SRU{sfailed} uses one-hour DIRP",.0001)
   a.ok(float("9.85812")<float("21.3247"),"repaired LRU2 returned before later reissue")
  a.eq(set(report),{"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},f"{arm} report table set")
  a.eq(rows(report["ResultSummary"])[0],[1,0,36,0.7110209465026855,0,1,0,0.3333333432674408,0,0.7110209465026855,0],f"{arm} summary")
  system=recs(report["SystemResults"]);stock=recs(report["StockTotalResults"])
  a.eq((len(system),len(stock)),(72,72),f"{arm} 72 report bins each")
  missions=[(7,8.9414495528),(19,21.3246759772),(31,34)]
  flights=[(8,8.9414495528),(20,21.3246759772),(32,34)]
  ready=[(0,7),(9.4414495528,19),(21.8246759772,31),(34,36)]
  repair=[(8.9414495528,9.4414495528),(21.3246759772,21.8246759772)]
  for i,(sr,tr) in enumerate(zip(system,stock)):
   lo=i/2;hi=(i+1)/2
   a.eq((sr["STINT"],sr["ETINT"],tr["STINT"],tr["ETINT"]),(lo,hi,lo,hi),f"{arm} bin {i} interval")
   operating=2*sum(overlap(x,y,lo,hi) for x,y in flights);down=2*sum(overlap(x,y,lo,hi) for x,y in repair)
   expected={k:0 for k in sr}
   expected.update(UNID="Total over all Units",SID="Total over all Systems",STINT=lo,ETINT=hi,NSYRY=2*sum(overlap(x,y,lo,hi) for x,y in ready),NSYMA=2*sum(overlap(x,y,lo,hi) for x,y in missions),NSYMO=operating,NSYMR=2*sum(overlap(x,x+1,lo,hi) for x in (7,19,31)),NSYUA=down,NSYA=1-down,FTMO=operating,NSYRP=down,NREPT=int(i in (18,43)),NFAIL=int(i in (16,41)),STACC=operating,SYDT=.5 if i in (17,42) else None,NSYDT=int(i in (17,42)))
   for k,v in expected.items():
    if isinstance(v,float):a.near(sr[k],v,f"{arm} System bin {i} {k}")
    else:a.eq(sr[k],v,f"{arm} System bin {i} {k}")
   expstock={k:0 for k in tr}
   expstock.update(STINT=lo,ETINT=hi,NBO=0,NBOU=None,ROS=0 if i in (17,42) else None,ROST=0 if i in (17,42) else None,WT=0 if i in (17,42) else None,WTT=0 if i in (17,42) else None,WTS=None,PNB=1,NDF=int(i in (17,42)),NWT=int(i in (17,42)))
   for k,v in expstock.items():
    if isinstance(v,float):a.near(tr[k],v,f"{arm} Stock bin {i} {k}")
    else:a.eq(tr[k],v,f"{arm} Stock bin {i} {k}")
  a.eq(sum(x["NFAIL"] for x in system),2,f"{arm} two failures")
  a.eq(sum(x["NREPT"] for x in system),2,f"{arm} two system repairs")
  a.eq(sum(x["NBO"] for x in stock),0,f"{arm} no report backorder")
  a.eq((system[-1]["NSYRY"],system[-1]["NSYUA"]),(1,0),f"{arm} terminal ready")
 for name in ("ResultSummary","SystemResults","StockTotalResults"):
  x=evidence["two"]["report"][name];y=evidence["three"]["report"][name]
  a.eq(x["columns"],y["columns"],f"paired {name} schema")
  for i,(r,s) in enumerate(zip(rows(x),rows(y))):
   for j,(v,w) in enumerate(zip(r,s)):a.eq(v,w,f"paired {name} row {i} col {j}")
 a.ok(evidence["two"]["report"]["ProblemDescription"]!=evidence["three"]["report"]["ProblemDescription"],"paired description differs")
 result={"schema":"simlox-independent-readonly-review/v1","case_id":"F01.var01","passed":not a.bad,"verdict":"GO: bounded repeated two-/three-level local replacement and reissue" if not a.bad else "NO-GO: independent replay mismatch","checks_passed":a.good,"checks_total":a.good+len(a.bad),"failures":a.bad,"evidence":{"two_closure_sha256":sha(RUNS["two"]/"closure.json"),"three_closure_sha256":sha(RUNS["three"]/"closure.json"),"raw_seals_each":12,"row_containing_tables":{"two":20,"three":21},"two_lru_reissued_physical_id":1,"three_lru_reissued_physical_id":2,"three_sru_repaired_and_reissued_physical_id":3,"failure_hours_each":[8.47072,20.8247],"mission_outcomes_each":["abort","abort","success"],"report_bins_each":72,"all_non_description_report_cells_equal":True,"terminal_ready_aircraft_each":1},"limits":["One aircraft, one base, one LRU with optional SRU, seed 1 and 36-hour horizon; no more than three physical levels, ASSY, remote repair, resource scarcity, PM or explicit failure-mode CM.","Both arms show repaired physical LRU reissue after a later failure. The three-level arm also shows SRU replacement and one-hour SRU repair, with item-specific 0.75-hour LRU SURP overriding general 1.5 hours.","Matched event and aggregate report timelines in this seed do not establish structural causal equivalence or cross-seed stochastic parity. Default StockTotalResults counts system LRU demand bins; it does not separately expose physical nested SRU issues.","The unpublished v1.0.0 run failed its predeclared repeated-demand gate and is excluded. Issue #403's general nested replacement boundary remains open.","No GUI visual or cross-engine claim."]}
 OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
 return result

if __name__=="__main__":
 r=main();print(json.dumps({key:r[key] for key in ("verdict","checks_passed","checks_total","failures")},indent=2));sys.exit(0 if r["passed"] else 1)
