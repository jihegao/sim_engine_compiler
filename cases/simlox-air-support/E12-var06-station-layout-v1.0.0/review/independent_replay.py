"""Independent read-only replay of E12.var06 station layout source and raw run."""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
PARENT=CASE.parent/"E12-var05-base02-zero-opening-stock-v1.0.0"
RUN=CASE/"runs"/"e12-var06-station-layout-v100-ssh-20261004-01"
PRUN=PARENT/"runs"/"e12-var05-base02-zero-stock-v100-ssh-20261003-01"
OUT=Path(__file__).with_name("independent-verdict.json")

class Audit:
 def __init__(self):self.passed=0;self.failures=[]
 def check(self,x,label):
  if x:self.passed+=1
  else:self.failures.append(label)
 def eq(self,x,y,label):self.check(x==y,f"{label}: expected {y!r}, got {x!r}")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def obj(p,native=False):
 s=p.read_text(encoding="utf-8-sig")
 return json.loads(re.sub(r",\s*([}\]])",r"\1",s) if native else s)
def tables(p,root="model"):return {t["name"]:t for t in obj(p,root=="report")[root]["tables"]}
def rows(t):return [r for inst in t["instances"] for r in inst.get("rows",[])]
def records(t):
 names=[c["name"] for c in t["columns"]]
 return [dict(zip(names,r)) for r in rows(t)]

def main():
 a=Audit();contract=obj(CASE/"contract.json");diff=obj(CASE/"exact-diff.json")
 source=tables(CASE/"native-input.json");parent=tables(PARENT/"native-input.json")
 export=tables(RUN/"roundtrip-raw.json");report=tables(RUN/"report-raw.json","report");preport=tables(PRUN/"report-raw.json","report")
 inv=obj(RUN/"invocation.json");closure=obj(RUN/"closure.json");steps=obj(RUN/"steps.json")
 log=(RUN/"model.log").read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
 converter=(RUN/"run.log").read_text(encoding="utf-8-sig",errors="replace")
 a.eq(contract["variant_id"],"E12.var06","contract variant")
 a.eq(sha(CASE/"native-input.json"),contract["native_input_sha256"],"child input pin")
 a.eq(sha(CASE/"exact-diff.json"),contract["exact_diff_sha256"],"diff pin")
 a.eq(sha(PARENT/"native-input.json"),contract["accepted_parent"]["input_sha256"],"parent input pin")
 a.eq(sha(PRUN/"closure.json"),contract["accepted_parent"]["native_closure_sha256"],"parent closure pin")
 a.eq(sha(PARENT/"evidence-index.json"),contract["accepted_parent"]["evidence_index_sha256"],"parent index pin")
 a.eq(diff["parent_sha256"],sha(PARENT/"native-input.json"),"diff parent")
 a.eq(diff["source_sha256"],sha(CASE/"native-input.json"),"diff child")
 a.eq(len(source),32,"32 source tables")
 a.eq(set(source),set(parent),"same table set")
 changed=sorted(n for n in source if source[n]!=parent[n])
 a.eq(changed,diff["changed_tables"],"exact two-table source delta")
 a.eq(diff["unchanged_parent_tables"],30,"30 unchanged tables")
 for n in sorted(source):
  a.eq(source[n]["columns"],parent[n]["columns"],f"schema {n}")
  if n not in changed:a.eq(source[n],parent[n],f"untouched table {n}")
 a.eq(len(diff["changed_cells"]),7,"seven changed cells")
 for change in diff["changed_cells"]:
  n=change["table"];p=rows(parent[n]);c=rows(source[n]);j=next(i for i,x in enumerate(source[n]["columns"]) if x["name"]==change["column"])
  a.eq(p[change["row"]][j],change["before"],f"parent {n}.{change['column']}")
  a.eq(c[change["row"]][j],change["after"],f"child {n}.{change['column']}")
 for n in changed:
  p=rows(parent[n]);c=rows(source[n]);actual=[(i,j) for i,(x,y) in enumerate(zip(p,c)) for j,(u,v) in enumerate(zip(x,y)) if u!=v]
  expected=[(x["row"],next(i for i,col in enumerate(source[n]["columns"]) if col["name"]==x["column"])) for x in diff["changed_cells"] if x["table"]==n]
  a.eq(actual,expected,f"only declared {n} cells changed")
 a.eq([(r["STID"],r["LEVL"],r["LINDX"]) for r in records(source["Station"])],[("BASE-01","BASE",2),("BASE-02","BASE",1),("DEPOT-01","DEPOT",1)],"layout source")
 links=records(source["StationStructure"])
 a.check(any(r["STID"]=="BASE-01" and r["MSTID"]=="DEPOT-01" for r in links),"BASE-01 support edge to DEPOT")
 a.check(any(r["STID"]=="BASE-02" and r["MSTID"]=="DEPOT-01" for r in links),"BASE-02 support edge to DEPOT")
 levels={r["STID"]:r["LEVL"] for r in records(source["Station"])}
 a.check(all(levels[r["STID"]]!=levels[r["MSTID"]] for r in links if r["STID"] in levels and r["MSTID"] in levels),"direct support edges cross layout levels")
 dictionary=Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
 lines=dictionary.read_text(encoding="utf-8-sig",errors="replace").splitlines()
 a.check(any(x.startswith("Station;6;LEVL;Level in support org.") for x in lines),"dictionary support-org level")
 a.check(any(x.startswith("Station;7;LINDX;Level index in support org.") and "Non-negative integer" in x for x in lines),"dictionary layout index")
 installed={"simlox_exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),"manual":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),"dictionary":dictionary}
 for key,p in installed.items():
  field={"simlox_exe":"simlox_exe_sha256","manual":"manual_pdf_sha256","dictionary":"dictionary_sha256"}[key]
  a.eq(sha(p),contract["source"][field],f"installed {key} pin")
 a.eq(inv["run_id"],RUN.name,"run ID")
 a.eq(inv["execution_mode"],"ssh_cli_v1","SSH CLI")
 a.eq(inv["session_id"],0,"session zero")
 a.check(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"],"SSH ancestry")
 a.eq(inv["queue_mutex"],r"Global\SimloxIssue18NativeQueue","mutex")
 a.eq((inv["gui"]["pid"],inv["gui"]["session_id"]),(13340,1),"GUI identity")
 a.eq(inv["input_sha256"],sha(CASE/"native-input.json"),"invoked input")
 a.eq(closure["invocation_sha256"],sha(RUN/"invocation.json"),"invocation seal")
 a.eq(closure["source_hashes_before"],closure["source_hashes_after"],"source stable")
 a.eq(closure["source_hashes_before"],inv["source_hashes_before"],"source invocation/closure agreement")
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
 a.eq(set(export),set(source),"export table set")
 for n in authored:a.eq(export[n],source[n],f"exact authored roundtrip {n}")
 a.check((RUN/"model.sxo").stat().st_size>4,"valid SXO")
 a.eq(re.findall(r"\(error #(\d+)\)",converter),[],"Errors0")
 a.eq(re.findall(r"\(warning #(\d+)\)",converter),["108"],"warning108 only")
 a.check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter,"converter summary")

 a.eq(sha(RUN/"model.log"),sha(PRUN/"model.log"),"byte-identical native event and physical ledger")
 def event(hour,phrase):a.check(any(x.startswith(f"Time: {hour} ") and phrase in x for x in log.splitlines()),f"event h{hour} {phrase}")
 a.check("Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log,"depot physical ID0 opening")
 a.check("Time: 0 <TEACH-LRU-01,0,BASE-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>" in log,"BASE-01 physical ID1 opening")
 a.check("Time: 0 <TEACH-LRU-01,0,BASE-02,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,BASE-02,0> Level: 0 Items:" in log,"BASE-02 zero opening")
 for h,aircraft in [("9.8829",0),("11.1325",1),("22.5723",0),("34.7893",0)]:event(h,f"<TEACH-AIR-01,{aircraft}> critical random failure added")
 for phrase,count in [("mission created:",6),("mission starting, duration:",6),("mission aborted:",4),("mission success:",2),("mission cancelled:",0),("Backorder added",2),("Backorder removed",2),("books resources",0)]:a.eq(log.count(phrase),count,f"event count {phrase}")
 event("11.5","<TEACH-LRU-01,0,BASE-02,0> Backorder added")
 event("11.5","<TEACH-LRU-01,0,DEPOT-01,0> Backorder added")
 event("14.9246","<TEACH-LRU-01,0,DEPOT-01,0> Backorder removed, waiting time was 3.42457")
 event("15.9246","<TEACH-LRU-01,0,BASE-02,0> Backorder removed, waiting time was 4.42457")
 for h,item in [("13.9246",2),("14.8333",3),("26.614",4)]:event(h,f"<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,{item}>")
 for h,item in [("14.9246",2),("15.8333",3),("27.614",4)]:event(h,f"<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,{item}>")
 event("16.5912","system SURP task 1 on <TEACH-AIR-01,1> completed")
 event("16.5912","<TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1 :<TEACH-AIR-01,1>")
 event("36","<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>")
 a.eq(set(report),{"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},"report tables")
 a.check(report["ProblemDescription"]!=preport["ProblemDescription"],"description differs")
 for n in ("ResultSummary","SystemResults","StockTotalResults"):a.eq(report[n],preport[n],f"entire {n} table equality")
 s=records(report["SystemResults"]);t=records(report["StockTotalResults"])
 ps=records(preport["SystemResults"]);pt=records(preport["StockTotalResults"])
 a.eq((len(s),len(t)),(72,72),"72 half-hour bins each")
 for i,(sr,tr) in enumerate(zip(s,t)):
  a.eq((sr["STINT"],sr["ETINT"],tr["STINT"],tr["ETINT"]),(i/2,(i+1)/2,i/2,(i+1)/2),f"bin {i} interval")
  for k in sorted(sr):a.eq(sr[k],ps[i][k],f"SystemResults bin {i} {k}")
  for k in sorted(tr):a.eq(tr[k],pt[i][k],f"StockTotalResults bin {i} {k}")
 a.eq((s[-1]["NSYRY"],s[-1]["NSYUA"]),(1,1),"last report bin ready1/unavailable1")
 a.eq(sum(x["NFAIL"] for x in s),4,"four system failure bins")
 result={"schema":"simlox-independent-readonly-review/v1","case_id":"E12.var06","run_id":RUN.name,"passed":not a.failures,"verdict":"GO: bounded LEVL/LINDX source and numeric business parity" if not a.failures else "NO-GO: independent replay mismatch","checks_passed":a.passed,"checks_total":a.passed+len(a.failures),"failures":a.failures,"evidence":{"closure_sha256":sha(RUN/"closure.json"),"parent_closure_sha256":sha(PRUN/"closure.json"),"raw_seals":len(closure["raw"]),"authored_tables_exact_roundtrip":len(authored),"event_log_sha256":sha(RUN/"model.log"),"report_bins_each":72,"station_layout":{"BASE-01":["BASE",2],"BASE-02":["BASE",1],"DEPOT-01":["DEPOT",1]}},"limits":["One seed, two bases, one item group and 36-hour horizon; numeric/event parity demonstrates no observed simulation change in this case, not universal calculation neutrality.","Installed manual pp323-324 describe support-organization plot semantics and LINDX ordering, but the CLI JSON report has no rendered plot; no visual layout observation is claimed.","No GUI visual or cross-engine parity claim; exact h36 ready event follows the final [35.5,36) report interval."]}
 OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
 return result

if __name__=="__main__":
 r=main();print(json.dumps({k:r[k] for k in ("verdict","checks_passed","checks_total","failures")},indent=2));sys.exit(0 if r["passed"] else 1)
