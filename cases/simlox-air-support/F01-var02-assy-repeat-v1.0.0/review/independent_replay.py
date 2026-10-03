"""Independent read-only replay of F01.var02 ASSY repeated replacement."""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
ROOT=CASE.parent
PARENT=ROOT/"F01-var01-two-three-level-v1.0.1"
DONOR=ROOT/"G01-var04-assy-structure-v1.0.0"
RUN=CASE/"runs"/"f01-var02-assy-v100-ssh-20261004-01"
PRUN=PARENT/"runs"/"f01-var01-three-v101-ssh-20261004-01"
DRUN=DONOR/"runs"/"g01-var04-assy-v100-ssh-20261001-01"
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
def tables(p,root="model"):return {x["name"]:x for x in load(p,root=="report")[root]["tables"]}
def rows(t):return [r for inst in t["instances"] for r in inst.get("rows",[])]
def records(t):
 names=[c["name"] for c in t["columns"]]
 return [dict(zip(names,r)) for r in rows(t)]
def ov(a,b,lo,hi):return max(0,min(b,hi)-max(a,lo))

def main():
 a=Audit();contract=load(CASE/"contract.json");diff=load(CASE/"exact-diff.json")
 source=tables(CASE/"native-input.json");parent=tables(PARENT/"three-level-input.json");donor=tables(DONOR/"native-input.json")
 export=tables(RUN/"roundtrip-raw.json");report=tables(RUN/"report-raw.json","report");preport=tables(PRUN/"report-raw.json","report")
 inv=load(RUN/"invocation.json");closure=load(RUN/"closure.json");steps=load(RUN/"steps.json")
 log=(RUN/"model.log").read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
 plog=(PRUN/"model.log").read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
 converter=(RUN/"run.log").read_text(encoding="utf-8-sig",errors="replace")
 a.eq(contract["variant_id"],"F01.var02","contract variant")
 a.eq(sha(CASE/"native-input.json"),contract["native_input_sha256"],"child source pin")
 a.eq(sha(CASE/"exact-diff.json"),contract["exact_diff_sha256"],"diff pin")
 for label,path,run,pin in [("parent",PARENT/"three-level-input.json",PRUN,"accepted_behavior_parent"),("donor",DONOR/"native-input.json",DRUN,"accepted_structural_reference")]:
  meta=contract[pin];a.eq(sha(path),meta["input_sha256"],f"{label} source pin")
  a.eq(sha(run/"closure.json"),meta["closure_sha256"],f"{label} closure pin")
  index=path.parent/"evidence-index.json";a.eq(sha(index),meta["evidence_index_sha256"],f"{label} index pin")
 for name,left,left_path in [("assy_from_f01_var01",parent,PARENT/"three-level-input.json"),("rate_from_g01_var04",donor,DONOR/"native-input.json")]:
  spec=diff[name];a.eq(spec["left_sha256"],sha(left_path),f"{name} left hash")
  a.eq(spec["right_sha256"],sha(CASE/"native-input.json"),f"{name} right hash")
  changed=sorted(n for n in left if left[n]!=source[n]);a.eq(changed,sorted(x["table"] for x in spec["changed_tables"]),f"{name} exact changed tables")
  a.eq(spec["unchanged_tables"],len(left)-len(changed),f"{name} fixed table count")
  for n in sorted(left):
   a.eq(left[n]["columns"],source[n]["columns"],f"{name} {n} schema")
   if n not in changed:a.eq(left[n],source[n],f"{name} fixed {n}")
  for t in spec["changed_tables"]:
   a.eq(rows(left[t["table"]]),t["before_rows"],f"{name} {t['table']} old rows")
   a.eq(rows(source[t["table"]]),t["after_rows"],f"{name} {t['table']} new rows")
 a.eq(len(source),31,"31 authored tables")
 items={r["IID"]:r for r in records(source["Item"])}
 a.eq(items["TEACH-ASSY-01"]["TYPE"],"ASSY","structural ASSY item")
 a.eq((items["TEACH-ASSY-01"]["FRT"],items["TEACH-ASSY-01"]["OPID"]),(None,None),"ASSY has no failure clock")
 links={(r["IID"],r["MID"]) for r in records(source["ItemStructure"])}
 a.eq(links,{("TEACH-ASSY-01","TEACH-AIR-01"),("TEACH-LRU-01","TEACH-ASSY-01"),("TEACH-SRU-01","TEACH-LRU-01")},"four physical levels with ASSY wrapper")
 for n,keys in [("StockAllocation",("IID",)),("ItemRepair",("IID",)),("ItemReplacement",("MID","IID"))]:
  a.ok(all("TEACH-ASSY-01" not in tuple(r[k] for k in keys) for r in records(source[n])),f"ASSY absent from {n} logistics")
 repl={(r["MID"],r["IID"]):r for r in records(source["ItemReplacement"])}
 a.eq(set(repl),{("TEACH-AIR-01","TEACH-LRU-01"),("TEACH-LRU-01","TEACH-SRU-01")},"direct system/LRU and LRU/SRU replacement rows")
 a.eq(repl[("TEACH-AIR-01","TEACH-LRU-01")]["SURPT"],.5,"direct aircraft LRU SURP")
 a.eq(repl[("TEACH-LRU-01","TEACH-SRU-01")]["SURPT"],.75,"nested LRU SRU SURP")
 a.eq(records(source["ItemRepair"])[0]["SURPT"],1.5,"general LRU SURP remains 1.5")
 installed={"simlox_exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),"manual":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),"dictionary":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
 for key,p in installed.items():
  field={"simlox_exe":"simlox_exe_sha256","manual":"manual_pdf_sha256","dictionary":"dictionary_sha256"}[key]
  a.eq(sha(p),contract["source"][field],f"installed {key}")
 a.eq(inv["run_id"],RUN.name,"run identity")
 a.eq(inv["execution_mode"],"ssh_cli_v1","SSH CLI")
 a.eq(inv["session_id"],0,"session zero")
 a.ok(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"],"SSH daemon ancestry")
 a.eq(inv["queue_mutex"],r"Global\SimloxIssue18NativeQueue","native mutex")
 a.eq((inv["gui"]["pid"],inv["gui"]["session_id"]),(13340,1),"GUI identity")
 a.eq(inv["input_sha256"],sha(CASE/"native-input.json"),"invoked source")
 a.eq(closure["invocation_sha256"],sha(RUN/"invocation.json"),"invocation seal")
 a.eq(closure["source_hashes_before"],closure["source_hashes_after"],"source stability")
 a.eq(closure["source_hashes_before"],inv["source_hashes_before"],"source invocation match")
 paths={"input":CASE/"native-input.json","parent":PARENT/"three-level-input.json","parent_closure":PRUN/"closure.json","parent_evidence_index":PARENT/"evidence-index.json","structural_reference":DONOR/"native-input.json","structural_reference_closure":DRUN/"closure.json","structural_reference_evidence_index":DONOR/"evidence-index.json","exact_diff":CASE/"exact-diff.json","contract":CASE/"contract.json","builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py","checker":CASE/"check_roundtrip.py","python":Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),"runner_script":CASE/"run_native_ssh.ps1",**installed}
 for key,p in sorted(paths.items()):a.eq(closure["source_hashes_before"][key],sha(p),f"source seal {key}")
 a.eq(len(closure["raw"]),12,"12 raw seals")
 for n,meta in sorted(closure["raw"].items()):
  p=RUN/n;a.ok(p.is_file(),f"raw exists {n}")
  if p.is_file():a.eq(p.stat().st_size,meta["bytes"],f"raw bytes {n}");a.eq(sha(p),meta["sha256"],f"raw SHA {n}")
 a.eq(sha(RUN/"input.json"),sha(CASE/"native-input.json"),"raw input copy")
 a.eq([s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"],"five native steps")
 for s in steps:
  a.eq(s["exit_code"],0,f"{s['name']} exit")
  a.eq(s["status"],"completed",f"{s['name']} status")
  a.eq(s["error"],None,f"{s['name']} error")
  a.eq(s["gui_preserved"],True,f"{s['name']} GUI preserved")
 authored=sorted(n for n,t in source.items() if rows(t));a.eq(len(authored),21,"21 row-containing tables")
 a.eq(set(export),set(source),"native export table set")
 for n in authored:a.eq(export[n],source[n],f"authored roundtrip {n}")
 a.ok((RUN/"model.sxi").stat().st_size>4 and (RUN/"model.sxo").stat().st_size>4,"usable SXI/SXO")
 a.eq(re.findall(r"\(error #(\d+)\)",converter),[],"converter errors zero")
 a.eq(re.findall(r"\(warning #(\d+)\)",converter),["108"],"warning108 only")
 a.ok("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter,"converter summary")

 lines=log.splitlines()
 def event(hour,part):a.ok(any(line.startswith(f"Time: {hour} ") and part in line for line in lines),f"event {hour} {part}")
 a.ok("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>" in log,"opening LRU1 stock")
 a.ok("Stock at: <TEACH-SRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-SRU-01,0,0>" in log,"opening SRU0 stock")
 for mid,ordered,start in [(0,"7","8"),(1,"19","20"),(2,"31","32")]:
  ident=f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
  event(ordered,f"{ident} mission created:")
  event(start,f"{ident} mission starting, duration: 2 : <TEACH-AIR-01,0>")
 for mid,h in [(0,"8.47072"),(1,"20.8247")]:event(h,f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}> mission aborted:")
 event("34","<BASIC-MISSION,TEACH-UNIT,0,0,2> mission success:")
 for h in ("8.47072","20.8247"):event(h,"<TEACH-AIR-01,0> critical random failure added")
 for phrase,count in [("mission created:",3),("mission aborted:",2),("mission success:",1),("critical random failure added",2),("Backorder added",0),("books resources",0),("requests resources: no resources needed",10)]:a.eq(log.count(phrase),count,f"count {phrase}")
 for start,end,task in [("8.94145","9.44145",0),("21.3247","21.8247",3)]:
  event(start,f"system SURP task {task} on <TEACH-AIR-01,0> started")
  event(end,f"system SURP task {task} on <TEACH-AIR-01,0> completed")
 for h in ("9.44145","21.8247","34"):event(h,"<TEACH-UNIT at <BASE-01,0>> systems ready: 1")
 def failure_path(hour,item):
  return any(line.startswith(f"Time: {hour} <TEACH-AIR-01,0> critical random failure added") and any(f"subitem failed: <TEACH-LRU-01,0,{item}> connection path: TEACH-AIR-01 - TEACH-AIR-01 - TEACH-ASSY-01 - TEACH-LRU-01" in next_line for next_line in lines[i+1:i+4]) for i,line in enumerate(lines))
 cycles=[("8.47072","8.94145","9.10812","9.85812","9.48312","10.4831",2,1,3,0,1),
         ("20.8247","21.3247","21.4913","22.2413","21.8663","22.8663",4,2,5,3,4)]
 for fail,issue,lstart,lend,sstart,send,lfailed,lspare,sfailed,sspare,task in cycles:
  a.ok(failure_path(fail,lfailed),f"ASSY in LRU failure path {lfailed}")
  event(issue,f"<TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,{lspare}> from stock")
  a.ok(f"Item requiring maintenance arrives <TEACH-LRU-01,0,{lfailed}> from position <TEACH-AIR-01,BASE-01,0> subitem failed: <TEACH-SRU-01,0,{sfailed}>" in log,f"SRU{sfailed} nested in LRU{lfailed}")
  event(lstart,f"item SURP task {task} on <TEACH-LRU-01,0,{lfailed}> started")
  event(lstart,f"<TEACH-SRU-01,0,BASE-01,0> Take replacement item <TEACH-SRU-01,0,{sspare}> from stock")
  event(lend,f"item SURP task {task} on <TEACH-LRU-01,0,{lfailed}> completed")
  event(lend,f"<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,{lfailed}> to stock")
  event(sstart,f"<TEACH-SRU-01,0,BASE-01,0> Start repair of item <TEACH-SRU-01,0,{sfailed}>")
  event(send,f"<TEACH-SRU-01,0,BASE-01,0> Finished repair of item <TEACH-SRU-01,0,{sfailed}>")
  event(send,f"<TEACH-SRU-01,0,BASE-01,0> Put back replacement item <TEACH-SRU-01,0,{sfailed}> to stock")
  a.near(float(lend)-float(lstart),.75,f"LRU{lfailed} .75-hour SURP",.0001)
  a.near(float(send)-float(sstart),1,f"SRU{sfailed} one-hour DIRP",.0001)
 a.ok("TEACH-ASSY-01" not in "\n".join(x for x in lines if any(y in x for y in ("Take replacement","Put back replacement","Start repair","Finished repair","Backorder","SURP task","DIRP task","subitem received"))),"ASSY absent from logistical events")
 a.eq(log.count("TEACH-ASSY-01"),4,"ASSY appears only in four LRU connection-path lines")
 a.ok("Time: 9.85812 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,2>" in log and "Time: 21.3247 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,2>" in log,"repaired physical LRU2 reissued")
 a.ok("Time: 10.4831 <TEACH-SRU-01,0,BASE-01,0> Put back replacement item <TEACH-SRU-01,0,3>" in log and "Time: 21.4913 <TEACH-SRU-01,0,BASE-01,0> Take replacement item <TEACH-SRU-01,0,3>" in log,"repaired physical SRU3 reissued")

 a.eq(set(report),{"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},"report table set")
 a.eq(rows(report["ResultSummary"])[0],[1,0,36,0.7110209465026855,0,1,0,0.3333333432674408,0,0.7110209465026855,0],"summary")
 system=records(report["SystemResults"]);stock=records(report["StockTotalResults"])
 a.eq((len(system),len(stock)),(72,72),"72 bins each")
 mission=[(7,8.9414495528),(19,21.3246759772),(31,34)]
 flight=[(8,8.9414495528),(20,21.3246759772),(32,34)]
 ready=[(0,7),(9.4414495528,19),(21.8246759772,31),(34,36)]
 repair=[(8.9414495528,9.4414495528),(21.3246759772,21.8246759772)]
 for i,(sr,tr) in enumerate(zip(system,stock)):
  lo=i/2;hi=(i+1)/2
  a.eq((sr["STINT"],sr["ETINT"],tr["STINT"],tr["ETINT"]),(lo,hi,lo,hi),f"bin {i} boundaries")
  flown=2*sum(ov(x,y,lo,hi) for x,y in flight);down=2*sum(ov(x,y,lo,hi) for x,y in repair)
  exp={k:0 for k in sr}
  exp.update(UNID="Total over all Units",SID="Total over all Systems",STINT=lo,ETINT=hi,NSYRY=2*sum(ov(x,y,lo,hi) for x,y in ready),NSYMA=2*sum(ov(x,y,lo,hi) for x,y in mission),NSYMO=flown,NSYMR=2*sum(ov(x,x+1,lo,hi) for x in (7,19,31)),NSYUA=down,NSYA=1-down,FTMO=flown,NSYRP=down,NREPT=int(i in (18,43)),NFAIL=int(i in (16,41)),STACC=flown,SYDT=.5 if i in (17,42) else None,NSYDT=int(i in (17,42)))
  for k,v in exp.items():
   if isinstance(v,float):a.near(sr[k],v,f"System bin {i} {k}")
   else:a.eq(sr[k],v,f"System bin {i} {k}")
  st={k:0 for k in tr}
  st.update(STINT=lo,ETINT=hi,NBO=0,NBOU=None,ROS=0 if i in (17,42) else None,ROST=0 if i in (17,42) else None,WT=0 if i in (17,42) else None,WTT=0 if i in (17,42) else None,WTS=None,PNB=1,NDF=int(i in (17,42)),NWT=int(i in (17,42)))
  for k,v in st.items():
   if isinstance(v,float):a.near(tr[k],v,f"Stock bin {i} {k}")
   else:a.eq(tr[k],v,f"Stock bin {i} {k}")
 a.eq(sum(x["NFAIL"] for x in system),2,"two system failure markers")
 a.eq(sum(x["NREPT"] for x in system),2,"two system repair completions")
 a.eq(sum(x["NBO"] for x in stock),0,"zero backorders")
 a.eq((system[-1]["NSYRY"],system[-1]["NSYUA"]),(1,0),"terminal ready one")
 normalized=log.replace(" - TEACH-ASSY-01 - TEACH-LRU-01"," - TEACH-LRU-01")
 a.eq(normalized,plog,"normalized entire event log equals accepted parent")
 a.eq(log.count(" - TEACH-ASSY-01 - TEACH-LRU-01"),4,"four exact path insertions")
 a.ok(report["ProblemDescription"]!=preport["ProblemDescription"],"description changed")
 for name in ("ResultSummary","SystemResults","StockTotalResults"):
  x=report[name];y=preport[name];a.eq(x["columns"],y["columns"],f"parent {name} schema")
  for i,(r,s) in enumerate(zip(rows(x),rows(y))):
   for j,(v,w) in enumerate(zip(r,s)):a.eq(v,w,f"parent {name} row {i} col {j}")
 result={"schema":"simlox-independent-readonly-review/v1","case_id":"F01.var02","run_id":RUN.name,"passed":not a.bad,"verdict":"GO: bounded inert ASSY wrapper around repeated LRU/SRU reissue" if not a.bad else "NO-GO: independent replay mismatch","checks_passed":a.good,"checks_total":a.good+len(a.bad),"failures":a.bad,"evidence":{"closure_sha256":sha(RUN/"closure.json"),"parent_closure_sha256":sha(PRUN/"closure.json"),"raw_seals":len(closure["raw"]),"row_containing_tables":len(authored),"failure_hours":[8.47072,20.8247],"reissued_repaired_lru_id":2,"reissued_repaired_sru_id":3,"assy_path_occurrences":4,"assy_logistics_events":0,"report_bins_each":72,"normalized_log_equal_parent":True,"non_description_report_cells_equal_parent":True,"terminal_ready_aircraft":1},"limits":["One structural ASSY wrapper, one aircraft, one base, one LRU/SRU chain, seed 1 and 36-hour horizon; no ASSY branching, quantity variation, remote support, resource scarcity, PM or explicit CM.","ASSY is observed in connection paths but has no configured failure rate, stock, demand, repair or task target in this run. This is a bounded inert-structure observation, not a universal ASSY rule.","Repeated physical LRU2 and SRU3 reissue is confirmed from native item identities; parent log/report parity is additional evidence, not a substitute for those checks.","The default StockTotalResults records system LRU demand bins but does not separately expose nested SRU stock issues. Issue #403's general nested replacement boundary remains open.","No GUI visual or cross-engine claim."]}
 OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
 return result

if __name__=="__main__":
 r=main();print(json.dumps({k:r[k] for k in ("verdict","checks_passed","checks_total","failures")},indent=2));sys.exit(0 if r["passed"] else 1)
