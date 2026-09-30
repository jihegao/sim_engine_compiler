"""Independent read-only replay of B05.var02 v1.0.0 native CLI evidence.

Uses Python stdlib only. It never calls project builders, validators, runners,
or SIMLOX, and writes only the review report adjacent to this script.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LIB = REPO / "cases/simlox-air-support"
CASE = LIB / "B05-var02-payload-unload-success-v1.0.0"
PARENT = LIB / "B02-serial-preparation-v1.0.2/native-input.json"
OUT = CASE / "review/independent-readonly-2026-09-30.json"
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
SIMLOX = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
VARIANTS = ("ordinary-control", "unloading")
checks = {}
failures = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(name, actual, expected):
    good = actual == expected
    checks[name] = {"passed": good}
    if not good or len(str(actual)) <= 180:
        checks[name].update({"observed": actual, "expected": expected})
    if not good:
        failures.append(name)


def near(name, actual, expected, tolerance=0.00005):
    good = len(actual) == len(expected) and all(abs(a-b) <= tolerance for a,b in zip(actual,expected))
    checks[name] = {"passed": good, "observed": actual, "expected": expected, "tolerance": tolerance}
    if not good:
        failures.append(name)


def read_json(path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native report export has a trailing comma before a closing bracket.
        output = []
        quoted = escaped = False
        for i, ch in enumerate(raw):
            if quoted:
                output.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    quoted = False
            elif ch == '"':
                quoted = True
                output.append(ch)
            elif ch == "," and raw[i+1:].lstrip().startswith(("]", "}")):
                continue
            else:
                output.append(ch)
        return json.loads("".join(output))


def tables(doc, root="model"):
    found = {t["name"]:t for t in doc[root]["tables"]}
    assert len(found) == len(doc[root]["tables"])
    return found


def table_rows(doc, name, root="model"):
    t = tables(doc,root)[name]
    names = [c["name"] for c in t["columns"]]
    assert len(names) == len(set(names))
    return [dict(zip(names,r)) for i in t["instances"] for r in i["rows"]]


def diff(before, after):
    a,b = tables(before),tables(after)
    def body(t):
        return None if t is None else {k:v for k,v in t.items() if k != "name"}
    return {n:{"before":body(a.get(n)),"after":body(b.get(n))} for n in sorted(set(a)|set(b)) if a.get(n) != b.get(n)}


def events(log, token):
    result=[]
    for line in log.splitlines():
        if token in line:
            match=re.match(r"Time: ([0-9.]+) (.*)",line)
            assert match, line
            result.append((float(match.group(1)),match.group(2)))
    return result


def times(log,token):
    return [t for t,_ in events(log,token)]


def task_events(log,task,tail):
    return [t for t,s in events(log,f"within system {task} task") if tail in s]


def review(v,contract,source_diff,parent):
    run=CASE/"runs"/f"b05-var02-{v}-20260930-01"
    source=read_json(CASE/f"{v}-input.json")
    inp=read_json(run/"input.json")
    inv=read_json(run/"invocation.json")
    close=read_json(run/"closure.json")
    steps=read_json(run/"steps.json")
    roundtrip=read_json(run/"roundtrip-raw.json")
    report=read_json(run/"report-raw.json")
    log=(run/"model.log").read_text(encoding="utf-8-sig")
    key=v+": "
    verify(key+"source SHA",sha(CASE/f"{v}-input.json"),source_diff["input_sha256"][v])
    verify(key+"parent SHA",sha(PARENT),contract["parent_input_sha256"])
    verify(key+"source equals run input",inp,source)
    verify(key+"run input SHA",sha(run/"input.json"),inv["input_sha256"])
    verify(key+"exact parent diff",diff(parent,source),source_diff["parent_differences"][v])
    for name,path,expected in [
        ("contract",CASE/"contract.json",inv["contract_sha256"]),
        ("builder",CASE/"build.py",inv["builder_sha256"]),
        ("roundtrip checker",CASE/"check_roundtrip.py",inv["checker_sha256"]),
        ("runner",CASE/"run_native_ssh.ps1",inv["runner_script_sha256"]),
        ("Python",PYTHON,inv["python_sha256"]),
        ("SIMLOX",SIMLOX,inv["simlox_exe_sha256"]),
        ("invocation",run/"invocation.json",close["invocation_sha256"]),
    ]:
        verify(key+name+" SHA",sha(path),expected)
    verify(key+"source before/after",close["source_hashes_before"],close["source_hashes_after"])
    verify(key+"source hash binding",close["source_hashes_before"],inv["source_hashes_before"])
    verify(key+"run binding",(inv["variant"],inv["run_id"],inv["original_run_dir"].lower(),close["run_id"],close["error"]),(v,run.name,str(run).lower(),run.name,None))
    verify(key+"sealed file count",len(close["raw"]),12)
    for fname,item in close["raw"].items():
        p=run/fname
        verify(key+"seal "+fname,(p.stat().st_size,sha(p)),(item["bytes"],item["sha256"]))
    verify(key+"nonempty native outputs",all((run/n).stat().st_size>0 for n in ("model.sxi","model.sxo","model.log","report-raw.json")),True)
    verify(key+"CLI SSH session",(inv["execution_mode"],inv["session_id"],inv["ssh_connection_present"],"sshd.exe" in inv["ssh_ancestor_names"]),("ssh_cli_v1",0,True,True))
    verify(key+"GUI record",(inv["gui"]["pid"],inv["gui"]["session_id"],inv["gui"]["start_utc"]),(13340,1,"2026-09-28T10:09:56.8261381Z"))
    verify(key+"queue mutex",inv["queue_mutex"],"Global\\SimloxIssue18NativeQueue")
    verify(key+"step names",[s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"])
    verify(key+"steps status",[(s["exit_code"],s["status"],s["gui_preserved"],s["error"]) for s in steps],[(0,"completed",True,None)]*5)
    verify(key+"serial step times",all(steps[i]["completed_utc"]<=steps[i+1]["started_utc"] for i in range(4)),True)
    verify(key+"planned native commands",[(s["name"],s["arguments"]) for s in steps[:4]],[(s["name"],s["arguments"]) for s in inv["planned_commands"]])
    verify(key+"import completed","Import completed!" in (run/"import.log").read_text(),True)
    verify(key+"JSON export log nonempty",(run/"export.log").stat().st_size>0,True)
    verify(key+"report exported","Generating Json-report" in (run/"report-export.log").read_text(),True)
    runlog=(run/"run.log").read_text()
    m=re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",runlog)
    verify(key+"conversion summary",m.groups() if m else None,("0","2","0"))
    verify(key+"warning IDs",re.findall(r"warning #(\d+)",runlog),["108","126"])
    populated={n:table_rows(inp,n) for n,t in tables(inp).items() if any(i["rows"] for i in t["instances"])}
    verify(key+"18 populated tables",len(populated),18)
    verify(key+"business roundtrip",populated,{n:table_rows(roundtrip,n) for n in populated})
    verify(key+"MissionTurnround roundtrip",table_rows(inp,"MissionTurnround"),table_rows(roundtrip,"MissionTurnround"))
    verify(key+"preparation/turnround source rows",(table_rows(inp,"TaskBreakDown"),table_rows(inp,"MissionTurnround")),(table_rows(source,"TaskBreakDown"),table_rows(source,"MissionTurnround")))

    tag="<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    near(key+"ordered",times(log,"mission ordered:"),[7])
    near(key+"created",times(log,"mission created:"),[7])
    near(key+"prep start/end",times(log,"preparation started, mission:")+times(log,"preparation ended, mission:"),[7,7.5])
    near(key+"PAYLOADING performing",[t for t,s in events(log,"payloading subtask") if "starts performing" in s],[7])
    near(key+"PAYLOADING completed",[t for t,s in events(log,"payloading subtask") if s.endswith("completed")],[7.16667])
    near(key+"preparation SERVICE work",[t for t,s in events(log,"seqno 2 within system preparation task") if "starts performing" in s],[7.16667])
    near(key+"preparation SERVICE completed",[t for t,s in events(log,"seqno 2 within system preparation task") if s.endswith("completed")],[7.5])
    near(key+"mission start/success/completion",times(log,"mission starting,")+times(log,"mission success:")+times(log,"mission completed:"),[8,10,10])
    verify(key+"mission tag in lifecycle",all(tag in s for token in ("mission created:","mission starting,","mission success:","mission completed:") for _,s in events(log,token)),True)
    verify(key+"same aircraft allocation and flight",all("<TEACH-AIR-01,0>" in s for token in ("mission allocates system:","mission starting,","mission completed:") for _,s in events(log,token)),True)
    verify(key+"no cancellation/failure",not re.search(r"mission (cancelled|aborted|failed):",log,re.I),True)
    near(key+"turnround start",times(log,"turnround started, mission:"),[10])
    end=10.16667 if v=="ordinary-control" else 10
    near(key+"turnround end",times(log,"turnround ended, mission:"),[end])
    near(key+"system arrival",times(log,"System arrives <TEACH-AIR-01,0>"),[end])
    near(key+"ready increases",times(log,"nbr ready increased at unit:"),[0,end])
    near(key+"system ready notifications",times(log,"systems ready:"),[0,end])
    near(key+"turnround SEQ1 positive work",[t for t,s in events(log,"seqno 1 within system turnround task") if "starts performing" in s],[10] if v=="ordinary-control" else [])
    near(key+"turnround SEQ1 completion",[t for t,s in events(log,"seqno 1 within system turnround task") if s.endswith("completed")],[end] if v=="ordinary-control" else [])
    near(key+"UNLOADING skip",[t for t,s in events(log,"unloading subtask") if s.endswith("skipped")],[10] if v=="unloading" else [])
    if v=="unloading":
        verify(key+"no UNLOADING work",not any("starts performing" in s for _,s in events(log,"unloading subtask")),True)

    verify(key+"report tables",[t["name"] for t in report["report"]["tables"]],["ProblemDescription","ResultSummary","SystemResults","StockTotalResults"])
    verify(key+"report description",table_rows(report,"ProblemDescription","report"),table_rows(inp,"ProblemDescription"))
    summary=table_rows(report,"ResultSummary","report")
    verify(key+"summary row",summary,[{"NREP":1,"RTILW":0,"RTIUP":36,"MTMF":1,"RSMTMF":0,"MSTF":1,"RSMSTF":0,"MSUF":1,"RSMSUF":0,"STMF":1,"RSSTMF":0}])
    sy=table_rows(report,"SystemResults","report")
    stock=table_rows(report,"StockTotalResults","report")
    verify(key+"72 SystemResults bins",len(sy),72)
    verify(key+"72 StockTotalResults bins",len(stock),72)
    for n,r in (("system",sy),("stock",stock)):
        verify(key+n+" half-hour continuity",[(x["STINT"],x["ETINT"]) for x in r],[(i/2,(i+1)/2) for i in range(72)])
    verify(key+"one system identity",{(r["UNID"],r["SID"]) for r in sy},{("Total over all Units","Total over all Systems")})
    verify(key+"flight bins",{r["STINT"]:r["STACC"] for r in sy if r["STACC"]},{8:1,8.5:1,9:1,9.5:1})
    near(key+"flight integral",[sum(r["STACC"]*0.5 for r in sy)],[2])
    verify(key+"STACC/FTMO/NSYMO agree",([r["STACC"] for r in sy],[r["FTMO"] for r in sy]),([r["FTMO"] for r in sy],[r["NSYMO"] for r in sy]))
    bin10=sy[20]
    near(key+"10-10.5 readiness",[bin10["NSYRY"],bin10["NSYMA"]],[2/3,1/3] if v=="ordinary-control" else [1,0])
    verify(key+"terminal ready state",(sy[-1]["ETINT"],sy[-1]["NSYRY"],sy[-1]["NSYMA"],sy[-1]["NSYMO"],sy[-1]["NPSTA"]),(36,1,0,0,0))
    verify(key+"no system failures",{r["NFAIL"] for r in sy},{0})
    return {"run_id":run.name,"summary":summary,"system_bins":sy,"stock_bins":stock,"log":log,"closure_sha256":sha(run/"closure.json")}


def main():
    contract=read_json(CASE/"contract.json")
    source_diff=read_json(CASE/"exact-diff.json")
    parent=read_json(PARENT)
    verify("contract identity/scope",(contract["variant_id"],contract["version"],contract["publication_state"]),("B05.var02","1.0.0","not_published"))
    verify("diff parent SHA",source_diff["parent_sha256"],sha(PARENT))
    ordinary=read_json(CASE/"ordinary-control-input.json")
    unloading=read_json(CASE/"unloading-input.json")
    verify("exact pairwise source diff",diff(ordinary,unloading),source_diff["pairwise_differences"])
    verify("pairwise changed tables",sorted(diff(ordinary,unloading)),["ProblemDescription","TaskBreakDown"])
    verify("control turnround SUTID",[r["SUTID"] for r in table_rows(ordinary,"TaskBreakDown") if r["TID"]=="TURN-FIXED"],["SERVICE"])
    verify("built-in turnround SUTID",[r["SUTID"] for r in table_rows(unloading,"TaskBreakDown") if r["TID"]=="TURN-FIXED"],["<UNLOADING>"])
    verify("PAYLOADING in both preparation sources",[[r["SUTID"] for r in table_rows(doc,"TaskBreakDown") if r["TID"]=="PREP-FIXED" and r["SEQ"]==1] for doc in (ordinary,unloading)],[["<PAYLOADING>"],["<PAYLOADING>"]])
    verify("built-ins not redefined",not any(r["SUTID"] in ("<PAYLOADING>","<UNLOADING>") for r in table_rows(unloading,"SubTaskType")),True)
    result={v:review(v,contract,source_diff,parent) for v in VARIANTS}
    a,b=result["ordinary-control"],result["unloading"]
    verify("same mission summary",a["summary"],b["summary"])
    verify("same stock bins",a["stock_bins"],b["stock_bins"])
    differences=[]
    for i,(ra,rb) in enumerate(zip(a["system_bins"],b["system_bins"])):
        for field in ra:
            if ra[field]!=rb[field]:
                differences.append((i/2,field,ra[field],rb[field]))
    verify("system-bin pair differences",differences,[(10,"NSYRY",0.6666666865348816,1),(10,"NSYMA",0.3333333432674408,0),(10,"NSYMT",0.3333333432674408,0)])
    verify("negative source hash control",hashlib.sha256((CASE/"unloading-input.json").read_bytes()+b"x").hexdigest()!=source_diff["input_sha256"]["unloading"],True)
    verify("negative skip-event control",not any(s.endswith("skipped") for _,s in events(b["log"].replace(" skipped"," omitted"),"unloading subtask")),True)
    verify("negative readiness-bin control",b["system_bins"][20]["NSYRY"]-1!=1,True)
    decision="GO_bounded_success_branch_native_cli_candidate" if not failures else "NO_GO"
    output={"schema":"simlox-b05-var02-v100-independent-readonly-review/v1","reviewer_script_sha256":sha(Path(__file__)),"passed":not failures,"decision":decision,"check_count":len(checks),"failures":failures,"checks":checks,"run_ids":{v:result[v]["run_id"] for v in VARIANTS},"closure_sha256":{v:result[v]["closure_sha256"] for v in VARIANTS},"observed":{"PAYLOADING_work_hours":[7,7.16667],"preparation_end_hour":7.5,"mission_flight_hours":[8,10],"mission_outcome":"success","ordinary_turnround_work_hours":[10,10.16667],"UNLOADING_at_hour_10":"explicit native skipped marker; no positive work","ready_hour_printed":{"ordinary-control":10.1667,"unloading":10},"terminal_hour":36,"terminal_ready":1},"accepted_scope":"Successful one-aircraft BASIC mission following PAYLOADING; compare built-in UNLOADING skip at turnround with equal-duration ordinary SERVICE work in one sealed SIMLOX CLI pair.","limits":["Only the successful-mission branch is supported; positive UNLOADING after failure is untested.","Payload quantity and failure-state mechanics are not measured.","No publication, GUI-only behavior, resource mechanism, other built-ins or cross-engine equivalence is established.","Native report JSON contains a trailing comma; sealed bytes are checked before independent tolerant parsing."]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_bytes((json.dumps(output,indent=2,ensure_ascii=False,default=list)+"\n").encode("utf-8"))
    print(json.dumps({"passed":output["passed"],"decision":decision,"checks":len(checks),"failures":failures,"report":str(OUT)},indent=2))
    return not failures


if __name__=="__main__":
    sys.exit(0 if main() else 1)
