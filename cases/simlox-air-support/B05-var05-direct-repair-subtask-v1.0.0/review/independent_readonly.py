"""Independent read-only replay of B05.var05 direct <REPAIR> native evidence.

Uses Python standard library only. No author code or SIMLOX execution.
Writes only the JSON report beside this script, never the sealed run.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LIB = REPO / "cases/simlox-air-support"
CASE = LIB / "B05-var05-direct-repair-subtask-v1.0.0"
D01 = LIB / "D01-system-direct-repair-v1.0.0"
PARENT = D01 / "native-input.json"
RUN = CASE / "runs/b05-var05-direct-20260930-01"
D01_RUN = D01 / "runs/d01-v100-ssh-20260929-01"
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
SIMLOX = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
OUT = CASE / "review/independent-readonly-2026-09-30.json"
checks = {}
failures = []


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def eq(name, actual, expected):
    passed = actual == expected
    checks[name] = {"passed": passed}
    if not passed or len(str(actual)) < 180:
        checks[name].update({"observed": actual, "expected": expected})
    if not passed:
        failures.append(name)


def near(name, actual, expected, tolerance=0.00005):
    passed = len(actual)==len(expected) and all(abs(a-b)<=tolerance for a,b in zip(actual,expected))
    checks[name] = {"passed": passed, "observed": actual, "expected": expected, "tolerance": tolerance}
    if not passed:
        failures.append(name)


def read(path):
    raw=path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native report JSON has a trailing comma outside strings.
        out=[]
        quoted=escaped=False
        for i,c in enumerate(raw):
            if quoted:
                out.append(c)
                if escaped:
                    escaped=False
                elif c=="\\":
                    escaped=True
                elif c=='"':
                    quoted=False
            elif c=='"':
                quoted=True
                out.append(c)
            elif c=="," and raw[i+1:].lstrip().startswith(("]","}")):
                continue
            else:
                out.append(c)
        return json.loads("".join(out))


def tables(doc,root="model"):
    found={t["name"]:t for t in doc[root]["tables"]}
    assert len(found)==len(doc[root]["tables"])
    return found


def rows(doc,name,root="model"):
    t=tables(doc,root)[name]
    cols=[c["name"] for c in t["columns"]]
    assert len(cols)==len(set(cols))
    return [dict(zip(cols,r)) for i in t["instances"] for r in i["rows"]]


def delta(before,after):
    a,b=tables(before),tables(after)
    def body(t):
        return None if t is None else {k:v for k,v in t.items() if k!="name"}
    return {n:{"before":body(a.get(n)),"after":body(b.get(n))} for n in sorted(set(a)|set(b)) if a.get(n)!=b.get(n)}


def events(log,token):
    result=[]
    for line in log.splitlines():
        if token in line:
            m=re.match(r"Time: ([0-9.]+) (.*)",line)
            assert m,line
            result.append((float(m.group(1)),m.group(2)))
    return result


def times(log,token):
    return [t for t,_ in events(log,token)]


def filtered(log,token,phrase):
    return [t for t,s in events(log,token) if phrase in s]


def main():
    contract=read(CASE/"contract.json")
    diff=read(CASE/"exact-diff.json")
    parent=read(PARENT)
    source=read(CASE/"native-input.json")
    inp=read(RUN/"input.json")
    invocation=read(RUN/"invocation.json")
    closure=read(RUN/"closure.json")
    steps=read(RUN/"steps.json")
    exported=read(RUN/"roundtrip-raw.json")
    report=read(RUN/"report-raw.json")
    log=(RUN/"model.log").read_text(encoding="utf-8-sig")

    eq("contract identity",(contract["variant_id"],contract["version"],contract["publication_state"]),("B05.var05","1.0.0","not_published"))
    eq("D01 parent SHA",sha(PARENT),contract["parent_input_sha256"])
    eq("diff parent/input SHA",(diff["parent_sha256"],diff["input_sha256"]),(sha(PARENT),sha(CASE/"native-input.json")))
    eq("source/run input",source,inp)
    eq("run source SHA",sha(RUN/"input.json"),invocation["input_sha256"])
    eq("exact four-table delta",delta(parent,source),diff["differences"])
    eq("four changed tables",sorted(delta(parent,source)),["ProblemDescription","SystemRepair","TaskBreakDown","Tasks"])
    repair=rows(source,"SystemRepair")
    eq("nominal DIRPT and task ID",(repair[0]["DIRPT"],repair[0]["DIRPTID"]),(4,"B05-DIRP"))
    eq("direct repair breakdown",[(r["TID"],r["SEQ"],r["SUTID"],r["DURN"]) for r in rows(source,"TaskBreakDown")],[("B05-DIRP",1,"<REPAIR>",0.5)])
    eq("built-in REPAIR not separately defined","<REPAIR>" not in [r["SUTID"] for r in rows(source,"SubTaskType")],True)
    for name,path,want in [
        ("contract",CASE/"contract.json",invocation["contract_sha256"]),
        ("builder",CASE/"build.py",invocation["builder_sha256"]),
        ("roundtrip checker",CASE/"check_roundtrip.py",invocation["checker_sha256"]),
        ("runner",CASE/"run_native_ssh.ps1",invocation["runner_script_sha256"]),
        ("Python",PYTHON,invocation["python_sha256"]),
        ("SIMLOX",SIMLOX,invocation["simlox_exe_sha256"]),
        ("invocation",RUN/"invocation.json",closure["invocation_sha256"]),
    ]:
        eq(name+" SHA",sha(path),want)
    eq("invocation parent",invocation["parent_sha256"],contract["parent_input_sha256"])
    eq("source stable during run",closure["source_hashes_before"],closure["source_hashes_after"])
    eq("source before binding",closure["source_hashes_before"],invocation["source_hashes_before"])
    eq("run identity",(invocation["variant"],invocation["run_id"],invocation["original_run_dir"].lower(),closure["run_id"],closure["error"]),("direct-repair",RUN.name,str(RUN).lower(),RUN.name,None))
    eq("12 sealed raw files",len(closure["raw"]),12)
    for name,item in closure["raw"].items():
        p=RUN/name
        eq("seal "+name,(p.stat().st_size,sha(p)),(item["bytes"],item["sha256"]))
    eq("native artifacts nonempty",all((RUN/name).stat().st_size>0 for name in ("model.sxi","model.sxo","model.log","report-raw.json")),True)
    eq("SSH CLI session",(invocation["execution_mode"],invocation["session_id"],invocation["ssh_connection_present"],"sshd.exe" in invocation["ssh_ancestor_names"]),("ssh_cli_v1",0,True,True))
    eq("GUI identity record",(invocation["gui"]["pid"],invocation["gui"]["session_id"],invocation["gui"]["start_utc"]),(13340,1,"2026-09-28T10:09:56.8261381Z"))
    eq("queue mutex",invocation["queue_mutex"],"Global\\SimloxIssue18NativeQueue")
    eq("step names",[s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"])
    eq("step success/GUI",[(s["exit_code"],s["status"],s["gui_preserved"],s["error"]) for s in steps],[(0,"completed",True,None)]*5)
    eq("step order",all(steps[i]["completed_utc"]<=steps[i+1]["started_utc"] for i in range(4)),True)
    eq("planned native commands",[(s["name"],s["arguments"]) for s in steps[:4]],[(s["name"],s["arguments"]) for s in invocation["planned_commands"]])
    eq("import completed","Import completed!" in (RUN/"import.log").read_text(),True)
    eq("native export log",(RUN/"export.log").stat().st_size>0,True)
    eq("report export log","Generating Json-report" in (RUN/"report-export.log").read_text(),True)
    runlog=(RUN/"run.log").read_text()
    match=re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",runlog)
    eq("conversion summary",match.groups() if match else None,("0","2","0"))
    eq("warning IDs",re.findall(r"warning #(\d+)",runlog),["108","126"])
    populated={n:rows(inp,n) for n,t in tables(inp).items() if any(i["rows"] for i in t["instances"])}
    eq("16 populated tables",len(populated),16)
    eq("exact business roundtrip",populated,{n:rows(exported,n) for n in populated})

    tags=[f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>" for i in range(3)]
    near("notification hours",times(log,"mission ordered:"),[7,19,31])
    near("start hours",times(log,"mission starting,"),[8,20,32])
    near("critical failure hours",times(log,"critical random failure added"),[9.8829,33.8602])
    near("aborted hours",times(log,"mission aborted:"),[9.8829,33.8602])
    near("aborted completion hours",times(log,"aborted mission completed:"),[10,34])
    near("middle success/completion",times(log,"mission success:")+[t for t,s in events(log,"mission completed:") if "aborted mission completed:" not in s],[22,22])
    eq("mission tags",[re.search(r"<BASIC-MISSION,TEACH-UNIT,0,0,\d+>",s).group(0) for _,s in events(log,"mission created:")],tags)
    eq("first and third abort identity",[re.search(r"<BASIC-MISSION,TEACH-UNIT,0,0,\d+>",s).group(0) for _,s in events(log,"mission aborted:")],[tags[0],tags[2]])
    near("repair starts",filtered(log,"direct repair subtask","starts performing"),[10,34])
    near("repair completions",[t for t,s in events(log,"direct repair subtask") if s.endswith("completed")],[10.5,34.5])
    near("maintained arrivals",times(log,"Maintained system arrives"),[10.5,34.5])
    near("ready after repairs",times(log,"systems ready:"),[0,10.5,22,34.5])
    eq("direct repair subtask identities",[re.search(r"seqno (\d+) within system DIRP task (\d+)",s).groups() for _,s in events(log,"direct repair subtask") if "starts performing" in s],[("1","0"),("1","1")])
    eq("native 0.5h overrides nominal 4h",all("planned to last for 0.5 hours" in s for _,s in events(log,"direct repair subtask") if "starts performing" in s),True)
    eq("no cancellations",len(events(log,"mission cancelled:")),0)

    eq("report table names",[t["name"] for t in report["report"]["tables"]],["ProblemDescription","ResultSummary","SystemResults","StockTotalResults"])
    eq("report description",rows(report,"ProblemDescription","report"),rows(inp,"ProblemDescription"))
    summary=rows(report,"ResultSummary","report")
    eq("one summary row",len(summary),1)
    eq("summary horizon",(summary[0]["NREP"],summary[0]["RTILW"],summary[0]["RTIUP"]),(1,0,36))
    near("summary success fraction",[summary[0]["MSUF"]],[1/3])
    system=rows(report,"SystemResults","report")
    stock=rows(report,"StockTotalResults","report")
    eq("72 system bins",len(system),72)
    eq("72 stock bins",len(stock),72)
    for name,bins in (("system",system),("stock",stock)):
        eq(name+" half-hour continuity",[(r["STINT"],r["ETINT"]) for r in bins],[(i/2,(i+1)/2) for i in range(72)])
    eq("system identity",{(r["UNID"],r["SID"]) for r in system},{("Total over all Units","Total over all Systems")})
    eq("failure bins",{r["STINT"]:r["NFAIL"] for r in system if r["NFAIL"]},{9.5:1,33.5:1})
    eq("repair bins",{r["STINT"]:r["NSYRP"] for r in system if r["NSYRP"]},{10:1,34:1})
    eq("repair completion bins",{r["STINT"]:r["NREPT"] for r in system if r["NREPT"]},{10.5:1,34.5:1})
    eq("flight bins",{r["STINT"]:r["STACC"] for r in system if r["STACC"]},{8:1,8.5:1,9:1,9.5:1,20:1,20.5:1,21:1,21.5:1,32:1,32.5:1,33:1,33.5:1})
    near("flight integral",[sum(r["STACC"]*0.5 for r in system)],[6])
    eq("terminal ready",(system[-1]["ETINT"],system[-1]["NSYRY"],system[-1]["NSYMO"],system[-1]["NSYRP"]),(36,1,0,0))

    d01_report=read(D01_RUN/"report-raw.json")
    d01_log=(D01_RUN/"model.log").read_text(encoding="utf-8-sig")
    eq("published D01 source unchanged",sha(PARENT),"d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450")
    eq("D01 report tables except description",[t for t in report["report"]["tables"] if t["name"]!="ProblemDescription"],[t for t in d01_report["report"]["tables"] if t["name"]!="ProblemDescription"])
    near("same D01 failure hours",times(log,"critical random failure added"),times(d01_log,"critical random failure added"))
    near("same D01 repaired-ready hours",times(log,"Maintained system arrives"),times(d01_log,"Maintained system arrives"))
    eq("D01 published signoff present",(D01/"cli-scope-signoff-2026-09-29.md").exists(),True)
    eq("negative source hash control",hashlib.sha256((CASE/"native-input.json").read_bytes()+b"x").hexdigest()!=diff["input_sha256"],True)
    eq("negative repair duration control",not all("planned to last for 0.5 hours" in s.replace("0.5 hours","4 hours") for _,s in events(log,"direct repair subtask") if "starts performing" in s),True)
    eq("negative terminal control",system[-1]["NSYRY"]-1!=1,True)

    decision="GO_bounded_direct_REPAIR_native_cli_candidate" if not failures else "NO_GO"
    result={"schema":"simlox-b05-var05-v100-independent-readonly-review/v1","reviewer_script_sha256":sha(Path(__file__)),"passed":not failures,"decision":decision,"check_count":len(checks),"failures":failures,"checks":checks,"run_id":RUN.name,"closure_sha256":sha(RUN/"closure.json"),"observed":{"critical_failure_hours_printed":[9.8829,33.8602],"direct_REPAIR_work_hours":[[10,10.5],[34,34.5]],"nominal_DIRPT_hours":4,"mission_outcomes":["aborted","success","aborted"],"terminal_hour":36,"terminal_ready_count":1},"accepted_scope":"One fixed-seed one-aircraft direct system repair task using one native <REPAIR> subtask of 0.5 hour; observed repair duration overrides DIRPT=4 and matches the published D01 event/report behavior.","limits":["Only this direct system repair path and observed seed are supported; direct item repair, resources, additional subtasks and alternative timing are unverified.","No GUI-only or cross-engine claim, and no publication claim.","Native report JSON has a trailing comma; raw hashes are checked before independent tolerant parsing."]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False,default=list)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"decision":decision,"checks":len(checks),"failures":failures,"report":str(OUT)},indent=2))
    return not failures


if __name__=="__main__":
    sys.exit(0 if main() else 1)
