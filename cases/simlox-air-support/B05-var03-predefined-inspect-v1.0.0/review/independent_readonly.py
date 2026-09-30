"""Independent read-only B05.var03 v1.0.0 native evidence replay.

Standard library only; no author code or native executable is called.
The original run directories are read, never modified.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LIB = REPO / "cases/simlox-air-support"
CASE = LIB / "B05-var03-predefined-inspect-v1.0.0"
PARENT = LIB / "B02-serial-preparation-v1.0.2/native-input.json"
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
SIMLOX = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
OUT = CASE / "review/independent-readonly-2026-09-30.json"
VARIANTS = ("ordinary-control", "predefined-inspect")
checks = {}
failures = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eq(name, got, want):
    ok = got == want
    checks[name] = {"passed": ok}
    if not ok or len(str(got)) < 180:
        checks[name].update({"observed": got, "expected": want})
    if not ok:
        failures.append(name)


def near(name, got, want, tolerance=0.00005):
    ok = len(got)==len(want) and all(abs(a-b)<=tolerance for a,b in zip(got,want))
    checks[name] = {"passed": ok, "observed": got, "expected": want, "tolerance": tolerance}
    if not ok:
        failures.append(name)


def read(path):
    raw=path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native report has a trailing comma. Remove it outside strings only.
        output=[]
        quoted=escaped=False
        for i,c in enumerate(raw):
            if quoted:
                output.append(c)
                if escaped:
                    escaped=False
                elif c=="\\":
                    escaped=True
                elif c=='"':
                    quoted=False
            elif c=='"':
                quoted=True
                output.append(c)
            elif c=="," and raw[i+1:].lstrip().startswith(("]","}")):
                continue
            else:
                output.append(c)
        return json.loads("".join(output))


def tables(doc,root="model"):
    m={t["name"]:t for t in doc[root]["tables"]}
    assert len(m)==len(doc[root]["tables"])
    return m


def rows(doc,name,root="model"):
    t=tables(doc,root)[name]
    cols=[c["name"] for c in t["columns"]]
    assert len(cols)==len(set(cols))
    return [dict(zip(cols,row)) for i in t["instances"] for row in i["rows"]]


def difference(before,after):
    a,b=tables(before),tables(after)
    def body(t):
        return None if t is None else {k:v for k,v in t.items() if k!="name"}
    return {n:{"before":body(a.get(n)),"after":body(b.get(n))} for n in sorted(set(a)|set(b)) if a.get(n)!=b.get(n)}


def events(log,token):
    out=[]
    for line in log.splitlines():
        if token in line:
            m=re.match(r"Time: ([0-9.]+) (.*)",line)
            assert m,line
            out.append((float(m.group(1)),m.group(2)))
    return out


def times(log,token):
    return [t for t,_ in events(log,token)]


def select(log,token,contains):
    return [t for t,s in events(log,token) if contains in s]


def replay(variant,contract,source_diff,parent):
    short="ordinary" if variant=="ordinary-control" else "predefined"
    run=CASE/"runs"/f"b05-var03-{short}-20260930-01"
    source=read(CASE/f"{variant}-input.json")
    inp=read(run/"input.json")
    inv=read(run/"invocation.json")
    seal=read(run/"closure.json")
    steps=read(run/"steps.json")
    exported=read(run/"roundtrip-raw.json")
    report=read(run/"report-raw.json")
    log=(run/"model.log").read_text(encoding="utf-8-sig")
    key=variant+": "
    eq(key+"source SHA",sha(CASE/f"{variant}-input.json"),source_diff["input_sha256"][variant])
    eq(key+"source/run input",source,inp)
    eq(key+"run input SHA",sha(run/"input.json"),inv["input_sha256"])
    eq(key+"exact parent diff",difference(parent,source),source_diff["parent_differences"][variant])
    for n,path,want in [
        ("parent",PARENT,contract["parent_input_sha256"]),
        ("contract",CASE/"contract.json",inv["contract_sha256"]),
        ("builder",CASE/"build.py",inv["builder_sha256"]),
        ("roundtrip checker",CASE/"check_roundtrip.py",inv["checker_sha256"]),
        ("runner",CASE/"run_native_ssh.ps1",inv["runner_script_sha256"]),
        ("Python",PYTHON,inv["python_sha256"]),
        ("SIMLOX",SIMLOX,inv["simlox_exe_sha256"]),
        ("invocation",run/"invocation.json",seal["invocation_sha256"]),
    ]:
        eq(key+n+" SHA",sha(path),want)
    eq(key+"source before/after",seal["source_hashes_before"],seal["source_hashes_after"])
    eq(key+"invocation/closure binding",seal["source_hashes_before"],inv["source_hashes_before"])
    eq(key+"run identity",(inv["variant"],inv["run_id"],inv["original_run_dir"].lower(),seal["run_id"],seal["error"]),(variant,run.name,str(run).lower(),run.name,None))
    eq(key+"12 sealed raw files",len(seal["raw"]),12)
    for n,item in seal["raw"].items():
        p=run/n
        eq(key+"seal "+n,(p.stat().st_size,sha(p)),(item["bytes"],item["sha256"]))
    eq(key+"nonempty native artifacts",all((run/n).stat().st_size>0 for n in ("model.sxi","model.sxo","model.log","report-raw.json")),True)
    eq(key+"SSH CLI",(inv["execution_mode"],inv["session_id"],inv["ssh_connection_present"],"sshd.exe" in inv["ssh_ancestor_names"]),("ssh_cli_v1",0,True,True))
    eq(key+"GUI record",(inv["gui"]["pid"],inv["gui"]["session_id"],inv["gui"]["start_utc"]),(13340,1,"2026-09-28T10:09:56.8261381Z"))
    eq(key+"queue guard",inv["queue_mutex"],"Global\\SimloxIssue18NativeQueue")
    eq(key+"step names",[s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"])
    eq(key+"step success/GUI",[(s["exit_code"],s["status"],s["gui_preserved"],s["error"]) for s in steps],[(0,"completed",True,None)]*5)
    eq(key+"step order",all(steps[i]["completed_utc"]<=steps[i+1]["started_utc"] for i in range(4)),True)
    eq(key+"planned native commands",[(s["name"],s["arguments"]) for s in steps[:4]],[(s["name"],s["arguments"]) for s in inv["planned_commands"]])
    eq(key+"import completed","Import completed!" in (run/"import.log").read_text(),True)
    eq(key+"native export log",(run/"export.log").stat().st_size>0,True)
    eq(key+"report export","Generating Json-report" in (run/"report-export.log").read_text(),True)
    runlog=(run/"run.log").read_text()
    m=re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",runlog)
    eq(key+"conversion",m.groups() if m else None,("0","2","0"))
    eq(key+"warning IDs",re.findall(r"warning #(\d+)",runlog),["108","126"])
    populated={n:rows(inp,n) for n,t in tables(inp).items() if any(i["rows"] for i in t["instances"])}
    eq(key+"17 populated tables",len(populated),17)
    eq(key+"business roundtrip",populated,{n:rows(exported,n) for n in populated})
    eq(key+"SEQ1 source/roundtrip",[r for r in rows(inp,"TaskBreakDown") if r["SEQ"]==1],[r for r in rows(exported,"TaskBreakDown") if r["SEQ"]==1])
    tag="<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    near(key+"notice/create",times(log,"mission ordered:")+times(log,"mission created:"),[7,7])
    near(key+"SEQ1 positive work",select(log,"seqno 1 within system preparation task","starts performing"),[7])
    near(key+"SEQ1 completion",[t for t,s in events(log,"seqno 1 within system preparation task") if s.endswith("completed")],[7.16667])
    near(key+"SEQ2 positive work",select(log,"seqno 2 within system preparation task","starts performing"),[7.16667])
    near(key+"SEQ2 completion",[t for t,s in events(log,"seqno 2 within system preparation task") if s.endswith("completed")],[7.5])
    near(key+"preparation end",times(log,"preparation ended, mission:"),[7.5])
    near(key+"mission start/success/completion",times(log,"mission starting,")+times(log,"mission success:")+times(log,"mission completed:"),[8,10,10])
    eq(key+"mission and aircraft identity",all(tag in s for token in ("mission created:","mission starting,","mission success:","mission completed:") for _,s in events(log,token)) and all("<TEACH-AIR-01,0>" in s for token in ("mission allocates system:","mission starting,","mission completed:") for _,s in events(log,token)),True)
    eq(key+"no cancellation/abort",not re.search(r"mission (cancelled|aborted):",log,re.I),True)
    near(key+"ready changes",times(log,"nbr ready decreased at unit:")+times(log,"nbr ready increased at unit:"),[7,0,10])
    near(key+"systems ready",times(log,"systems ready:"),[0,10])
    eq(key+"log uses generic subtask label",not re.search(r"(?:inspect|inspection) subtask",log,re.I),True)
    eq(key+"report table names",[t["name"] for t in report["report"]["tables"]],["ProblemDescription","ResultSummary","SystemResults","StockTotalResults"])
    eq(key+"report description",rows(report,"ProblemDescription","report"),rows(inp,"ProblemDescription"))
    summary=rows(report,"ResultSummary","report")
    eq(key+"success summary",summary,[{"NREP":1,"RTILW":0,"RTIUP":36,"MTMF":1,"RSMTMF":0,"MSTF":1,"RSMSTF":0,"MSUF":1,"RSMSUF":0,"STMF":1,"RSSTMF":0}])
    system=rows(report,"SystemResults","report")
    stock=rows(report,"StockTotalResults","report")
    eq(key+"72 system bins",len(system),72)
    eq(key+"72 stock bins",len(stock),72)
    for n,bins in (("system",system),("stock",stock)):
        eq(key+n+" half-hour continuity",[(r["STINT"],r["ETINT"]) for r in bins],[(i/2,(i+1)/2) for i in range(72)])
    eq(key+"system identity",{(r["UNID"],r["SID"]) for r in system},{("Total over all Units","Total over all Systems")})
    eq(key+"four flight bins",{r["STINT"]:r["STACC"] for r in system if r["STACC"]},{8:1,8.5:1,9:1,9.5:1})
    near(key+"flight integral",[sum(r["STACC"]*0.5 for r in system)],[2])
    eq(key+"STACC/FTMO profile",[r["STACC"] for r in system],[r["FTMO"] for r in system])
    eq(key+"preparation bin",(system[14]["NSYMP"],system[14]["NPSTA"]),(1,1))
    eq(key+"terminal ready",(system[-1]["ETINT"],system[-1]["NSYRY"],system[-1]["NSYMA"],system[-1]["NSYMO"],system[-1]["NPSTA"]),(36,1,0,0,0))
    eq(key+"no failures",{r["NFAIL"] for r in system},{0})
    return {"run_id":run.name,"model_log_sha256":sha(run/"model.log"),"report":report,"summary":summary,"system":system,"stock":stock,"closure_sha256":sha(run/"closure.json")}


def main():
    contract=read(CASE/"contract.json")
    source_diff=read(CASE/"exact-diff.json")
    parent=read(PARENT)
    eq("contract identity",(contract["variant_id"],contract["version"],contract["publication_state"]),("B05.var03","1.0.0","not_published"))
    eq("parent/diff SHA",(sha(PARENT),source_diff["parent_sha256"]),(contract["parent_input_sha256"],contract["parent_input_sha256"]))
    ordinary=read(CASE/"ordinary-control-input.json")
    predefined=read(CASE/"predefined-inspect-input.json")
    eq("exact pair source delta",difference(ordinary,predefined),source_diff["pairwise_differences"])
    eq("pairwise changed tables",sorted(difference(ordinary,predefined)),["ProblemDescription","TaskBreakDown"])
    eq("SEQ1 source identity contrast",([r["SUTID"] for r in rows(ordinary,"TaskBreakDown") if r["SEQ"]==1],[r["SUTID"] for r in rows(predefined,"TaskBreakDown") if r["SEQ"]==1]),(["INSPECT"],["<INSPECT>"]))
    eq("SEQ2 common SERVICE",[[r["SUTID"] for r in rows(doc,"TaskBreakDown") if r["SEQ"]==2] for doc in (ordinary,predefined)],[["SERVICE"],["SERVICE"]])
    eq("built-in not defined in SubTaskType","<INSPECT>" not in [r["SUTID"] for r in rows(predefined,"SubTaskType")],True)
    result={v:replay(v,contract,source_diff,parent) for v in VARIANTS}
    a,b=result["ordinary-control"],result["predefined-inspect"]
    eq("entire model.log byte equality",a["model_log_sha256"],b["model_log_sha256"])
    eq("same result summary",a["summary"],b["summary"])
    eq("same 72 system bins",a["system"],b["system"])
    eq("same 72 stock bins",a["stock"],b["stock"])
    eq("report equality except PDESC",{n:rows(a["report"],n,"report") for n in ("ResultSummary","SystemResults","StockTotalResults")},{n:rows(b["report"],n,"report") for n in ("ResultSummary","SystemResults","StockTotalResults")})
    eq("full report table equality except PDESC",[t for t in a["report"]["report"]["tables"] if t["name"]!="ProblemDescription"],[t for t in b["report"]["report"]["tables"] if t["name"]!="ProblemDescription"])
    eq("negative source hash control",hashlib.sha256((CASE/"predefined-inspect-input.json").read_bytes()+b"x").hexdigest()!=source_diff["input_sha256"]["predefined-inspect"],True)
    eq("negative log hash control",hashlib.sha256((CASE/"runs"/"b05-var03-predefined-20260930-01"/"model.log").read_bytes()+b"x").hexdigest()!=a["model_log_sha256"],True)
    eq("negative terminal control",b["system"][-1]["NSYRY"]-1!=1,True)
    decision="GO_bounded_preparation_native_cli_candidate" if not failures else "NO_GO"
    output={"schema":"simlox-b05-var03-v100-independent-readonly-review/v1","reviewer_script_sha256":sha(Path(__file__)),"passed":not failures,"decision":decision,"check_count":len(checks),"failures":failures,"checks":checks,"run_ids":{v:result[v]["run_id"] for v in VARIANTS},"closure_sha256":{v:result[v]["closure_sha256"] for v in VARIANTS},"shared_model_log_sha256":a["model_log_sha256"],"observed":{"SEQ1_positive_work_hours":[7,7.16667],"SEQ2_positive_work_hours":[7.16667,7.5],"mission_flight_hours":[8,10],"mission_outcome":"success","terminal_hour":36,"terminal_ready_count":1},"accepted_scope":"One two-step mission preparation using a source-bound built-in <INSPECT> reference compared with ordinary custom INSPECT; both yield the same positive work and native CLI behavior.","limits":["The native event log calls both versions generic subtask; the <INSPECT> identity is proven by frozen source and native roundtrip, not by a log label.","Only this preparation use is tested; other task categories, inspection findings, resource behavior, GUI-only behavior and cross-engine parity remain unverified.","No publication claim.","Native report JSON contains a trailing comma; raw hashes are checked before independent tolerant parsing."]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_bytes((json.dumps(output,indent=2,ensure_ascii=False,default=list)+"\n").encode("utf-8"))
    print(json.dumps({"passed":output["passed"],"decision":decision,"checks":len(checks),"failures":failures,"report":str(OUT)},indent=2))
    return not failures


if __name__=="__main__":
    sys.exit(0 if main() else 1)
