"""Independent read-only replay of E12.var03 group/default repair override."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE=Path(__file__).resolve().parent.parent
PARENT=CASE.parent/"E12-var02-two-fault-group-v1.0.0"
RUN=CASE/"runs"/"e12-var03-base02-override-v100-ssh-20261003-01"
PRUN=PARENT/"runs"/"e12-var02-two-fault-group-v100-ssh-20261003-01"
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
    a=Audit()
    contract=obj(CASE/"contract.json");diff=obj(CASE/"exact-diff.json")
    parent=tables(PARENT/"native-input.json");source=tables(CASE/"native-input.json")
    export=tables(RUN/"roundtrip-raw.json")
    report=tables(RUN/"report-raw.json","report");preport=tables(PRUN/"report-raw.json","report")
    inv=obj(RUN/"invocation.json");closure=obj(RUN/"closure.json");steps=obj(RUN/"steps.json")
    log=(RUN/"model.log").read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
    plog=(PRUN/"model.log").read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
    converter=(RUN/"run.log").read_text(encoding="utf-8-sig",errors="replace")
    a.eq(contract["variant_id"],"E12.var03","contract variant")
    a.eq(sha(CASE/"native-input.json"),contract["native_input_sha256"],"child input pin")
    a.eq(sha(CASE/"exact-diff.json"),contract["exact_diff_sha256"],"diff pin")
    a.eq(sha(PARENT/"native-input.json"),contract["accepted_parent"]["input_sha256"],"parent input pin")
    a.eq(sha(PRUN/"closure.json"),contract["accepted_parent"]["native_closure_sha256"],"parent closure pin")
    a.eq(sha(PARENT/"evidence-index.json"),contract["accepted_parent"]["evidence_index_sha256"],"parent index pin")
    a.eq(diff["parent_sha256"],sha(PARENT/"native-input.json"),"diff parent")
    a.eq(diff["source_sha256"],sha(CASE/"native-input.json"),"diff child")
    a.eq(len(source),32,"32 source tables")
    a.eq(set(source),set(parent),"source table set")
    changed=sorted(n for n in source if source[n]!=parent[n])
    a.eq(changed,diff["changed_tables"],"exact four-table delta")
    a.eq(diff["unchanged_parent_tables"],28,"28 unchanged tables")
    for n in sorted(source):
        a.eq(source[n]["columns"],parent[n]["columns"],f"schema {n}")
        if n not in changed:a.eq(source[n],parent[n],f"untouched table {n}")
    a.eq(len(diff["changes"]),4,"four diff entries")
    for change in diff["changes"]:
        n=change["table"];before=rows(parent[n]);after=rows(source[n]);added=change["added_rows"]
        a.eq(len(before),change["before_rows"],f"{n} parent row count")
        a.eq(len(after),change["after_rows"],f"{n} child row count")
        if n=="ProblemDescription":
            p,c=records(parent[n])[0],records(source[n])[0]
            a.eq(p["PDESC"],change["description_before"],"old PDESC")
            a.eq(c["PDESC"],change["description_after"],"new PDESC")
            pp=dict(p);pp["PDESC"]=c["PDESC"]
            a.eq(pp,c,"PDESC-only description delta")
        else:
            a.eq(after[:len(before)],before,f"{n} parent row prefix unchanged")
            a.eq(after[len(before):],added,f"{n} exact appended rows")
    repairs=records(source["SystemRepair"])
    a.eq([(r["STID"],r["SURPT"],r["SURPTID"]) for r in repairs],[("BASE-GRP",.5,"E01-SURP"),("BASE-02",1.0,"E12-BASE02-SURP")],"group default plus one individual override")
    a.eq([(r["STID"],r["GSTID"]) for r in records(source["Station"]) if r["STID"].startswith("BASE")],[("BASE-01","BASE-GRP"),("BASE-02","BASE-GRP")],"both bases retain common group")
    a.eq([(r["SEQ"],r["SUTID"],r["DURN"]) for r in records(source["TaskBreakDown"]) if r["TID"]=="E12-BASE02-SURP"],[(1,"<REMOVE>",1/3),(2,"<REPLACE>",2/3)],"override task stages")

    installed={"simlox_exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),"manual":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),"dictionary":Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
    for key,p in installed.items():
        field={"simlox_exe":"simlox_exe_sha256","manual":"manual_pdf_sha256","dictionary":"dictionary_sha256"}[key]
        a.eq(sha(p),contract["source"][field],f"installed {key}")
    a.eq(inv["run_id"],RUN.name,"run identity")
    a.eq(inv["execution_mode"],"ssh_cli_v1","SSH CLI")
    a.eq(inv["session_id"],0,"session zero")
    a.check(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"],"SSH ancestry")
    a.eq(inv["queue_mutex"],r"Global\SimloxIssue18NativeQueue","queue mutex")
    a.eq((inv["gui"]["pid"],inv["gui"]["session_id"]),(13340,1),"GUI identity")
    a.eq(inv["input_sha256"],sha(CASE/"native-input.json"),"invoked input")
    a.eq(closure["invocation_sha256"],sha(RUN/"invocation.json"),"invocation seal")
    a.eq(closure["source_hashes_before"],closure["source_hashes_after"],"stable source")
    a.eq(closure["source_hashes_before"],inv["source_hashes_before"],"source invocation/closure agreement")
    paths={"input":CASE/"native-input.json","parent":PARENT/"native-input.json","parent_closure":PRUN/"closure.json","parent_index":PARENT/"evidence-index.json","contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json","builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py","checker":CASE/"check_roundtrip.py","runner_script":CASE/"run_native_ssh.ps1","python":Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),**installed}
    for key,p in sorted(paths.items()):a.eq(closure["source_hashes_before"][key],sha(p),f"source seal {key}")
    a.eq(len(closure["raw"]),12,"12 raw seals")
    for n,meta in sorted(closure["raw"].items()):
        p=RUN/n;a.check(p.is_file(),f"raw exists {n}")
        if p.is_file():a.eq(p.stat().st_size,meta["bytes"],f"raw bytes {n}");a.eq(sha(p),meta["sha256"],f"raw hash {n}")
    a.eq(sha(RUN/"input.json"),sha(CASE/"native-input.json"),"run input copy")
    a.eq([s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"],"five steps")
    for s in steps:
        a.eq(s["exit_code"],0,f"{s['name']} exit")
        a.eq(s["status"],"completed",f"{s['name']} completed")
        a.eq(s["error"],None,f"{s['name']} error")
        a.check(s["gui_preserved"] is True,f"{s['name']} GUI preserved")
    authored=sorted(n for n,t in source.items() if rows(t))
    a.eq(len(authored),22,"22 authored row tables")
    a.eq(set(export),set(source),"roundtrip table set")
    for n in authored:a.eq(export[n],source[n],f"exact roundtrip {n}")
    a.check((RUN/"model.sxo").stat().st_size>4,"usable SXO")
    a.eq(re.findall(r"\(error #(\d+)\)",converter),[],"no converter errors")
    a.eq(re.findall(r"\(warning #(\d+)\)",converter),["108"],"warning108 only")
    a.check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter,"converter summary")

    def event(hour,phrase):a.check(any(x.startswith(f"Time: {hour} ") and phrase in x for x in log.splitlines()),f"event h{hour} {phrase}")
    for hour,aircraft,task,end in [("10.7579",0,0,"11.2579"),("11.5",1,1,"12.5"),("23.4473",0,4,"23.9473"),("35.5",0,6,"36")]:
        event(hour,f"system SURP task {task} on <TEACH-AIR-01,{aircraft}> started")
        event(end,f"system SURP task {task} on <TEACH-AIR-01,{aircraft}> completed")
    a.eq(len(re.findall(r"^Time: \S+  system SURP task \d+ on <TEACH-AIR-01,1> started$",log,re.MULTILINE)),1,"exactly one BASE-02 system repair")
    a.eq(len(re.findall(r"^Time: \S+  system SURP task \d+ on <TEACH-AIR-01,0> started$",log,re.MULTILINE)),3,"exactly three BASE-01 system repairs")
    for hour,phrase in [("10.7579","remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.166667 hours"),("10.9246","fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.333333 hours"),("11.5","remove subitem subtask 2 seqno 1 within system SURP task 1 on <TEACH-AIR-01,1> starts performing, planned to last for 0.333333 hours"),("11.8333","fit subitem subtask 3 seqno 2 within system SURP task 1 on <TEACH-AIR-01,1> starts performing, planned to last for 0.666667 hours")]:event(hour,phrase)
    for hour,aircraft in [("9.8829",0),("11.1325",1),("22.5723",0),("34.7893",0)]:event(hour,f"<TEACH-AIR-01,{aircraft}> critical random failure added")
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
    for phrase,count in [("mission created:",6),("mission starting, duration:",6),("mission aborted:",4),("mission success:",2),("mission cancelled:",0),("Backorder added",1),("Backorder removed",1),("books resources",0)]:a.eq(log.count(phrase),count,f"event count {phrase}")
    for h,base,item in [("10.7579","BASE-01",1),("11.5","BASE-02",2),("23.4473","BASE-01",0),("35.5","BASE-01",4)]:event(h,f"<TEACH-LRU-01,0,{base},0> Take replacement item <TEACH-LRU-01,0,{item}> from stock")
    event("11.5","<TEACH-LRU-01,0,DEPOT-01,0> Backorder added")
    event("14.9246","<TEACH-LRU-01,0,DEPOT-01,0> Backorder removed, waiting time was 3.42457")
    for h,item,base in [("10.7579",0,"BASE-01"),("14.9246",3,"BASE-02"),("23.4473",4,"BASE-01"),("35.5",5,"BASE-01")]:event(h,f"transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,{base},0>> started")
    for h,item,base in [("10.9246",3,"BASE-01"),("11.8333",4,"BASE-02"),("23.614",5,"BASE-01"),("35.6667",6,"BASE-01")]:event(h,f"transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,{base},0>,<TEACH-LRU-01,0,DEPOT-01,0>> started")
    for h1,h2,item in [("13.9246","14.9246",3),("14.8333","15.8333",4),("26.614","27.614",5)]:
        event(h1,f"<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,{item}>")
        event(h2,f"<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,{item}>")
    event("15.9246","<TEACH-LRU-01,0,BASE-02,0> Put back replacement item <TEACH-LRU-01,0,3> to stock")
    event("24.4473","<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,4> to stock")
    event("36","<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>")
    event("35.5","<TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1 :<TEACH-AIR-01,1>")
    a.eq(log.count("Finished repair of item <TEACH-LRU-01,0,6>"),0,"ID6 in transit at horizon")
    a.check("Time: 11.5  system SURP task 1 on <TEACH-AIR-01,1> started" in plog and "Time: 12  system SURP task 1 on <TEACH-AIR-01,1> completed" in plog,"parent BASE-02 half-hour control")
    a.check("Time: 11.5  system SURP task 1 on <TEACH-AIR-01,1> started" in log and "Time: 12.5  system SURP task 1 on <TEACH-AIR-01,1> completed" in log,"child BASE-02 one-hour override")

    a.eq(set(report),{"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},"report tables")
    a.check(report["ProblemDescription"]!=preport["ProblemDescription"],"report description changed")
    a.eq(report["ResultSummary"],preport["ResultSummary"],"full summary parity")
    a.eq(report["StockTotalResults"],preport["StockTotalResults"],"full stock table parity")
    s=records(report["SystemResults"]);p=records(preport["SystemResults"]);t=records(report["StockTotalResults"])
    a.eq((len(s),len(p),len(t)),(72,72,72),"72-bin reports")
    expected={23:{"SYDT":(0.5,1)},24:{"NSYRY":(2,1),"NSYUA":(0,1),"NSYA":(2,1),"NSYRP":(0,1),"NREPT":(1,0)},25:{"NREPT":(0,1)}}
    seen={}
    for i,(row,old,stock) in enumerate(zip(s,p,t)):
        a.eq((row["STINT"],row["ETINT"],stock["STINT"],stock["ETINT"]),(i/2,(i+1)/2,i/2,(i+1)/2),f"bin {i} grid")
        changes={k:(old[k],row[k]) for k in row if old[k]!=row[k]}
        a.eq(changes,expected.get(i,{}),f"exact SystemResults cell delta bin {i}")
        if changes:seen[i]=changes
        a.eq(stock,records(preport["StockTotalResults"])[i],f"Stock row {i} parity")
    a.eq(sorted(seen),[23,24,25],"only three changed SystemResults rows")
    a.eq((s[-1]["NSYRY"],s[-1]["NSYUA"]),(1,1),"h35.5-36 report ready1/unavailable1")
    a.eq(sum(r["NFAIL"] for r in s),4,"four failure bins")
    a.eq(sum(r["NREPT"] for r in s),3,"three pre-boundary repair completions")
    result={"schema":"simlox-independent-readonly-review/v1","case_id":"E12.var03","run_id":RUN.name,"passed":not a.failures,"verdict":"GO: bounded BASE-02 individual-over-group SystemRepair precedence" if not a.failures else "NO-GO: independent replay mismatch","checks_passed":a.passed,"checks_total":a.passed+len(a.failures),"failures":a.failures,"evidence":{"closure_sha256":sha(RUN/"closure.json"),"parent_closure_sha256":sha(PRUN/"closure.json"),"raw_seals":len(closure["raw"]),"authored_tables_exact_roundtrip":len(authored),"report_bins_each":72,"changed_system_bin_indices":sorted(seen),"base01_group_repair_hours":.5,"base02_individual_repair_hours":1.0,"mission_outcomes":["abort","abort","abort","success","abort","success"]},"limits":["Only one BASE-02 repair demand under one seed; supports row selection precedence in this source topology, not a general GSTID rule.","The override changes task plan and SURPT together, so timing-field-only precedence is not isolated.","No duplicate/mixed task observed; source identity of selected row is inferred from matching duration and stage plan because native task log does not print SystemRepair.STID.","The final h35.5-36 report bin has one ready system; h36 event records the second ready at the boundary. Failed item ID6 is still in transit.","Resource bookings are absent; stock/support rows stay individual. No GUI visual or cross-engine claim."]}
    OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
    return result

if __name__=="__main__":
    result=main();print(json.dumps({k:result[k] for k in ("verdict","checks_passed","checks_total","failures")},indent=2));sys.exit(0 if result["passed"] else 1)
