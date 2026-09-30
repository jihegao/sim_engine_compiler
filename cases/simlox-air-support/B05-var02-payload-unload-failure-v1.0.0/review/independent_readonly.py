"""Independent read-only replay of the B05.var02 failure-branch sealed pair.

Only Python's standard library is used. No project builder, validator, runner,
or native executable is called; original run files are never written.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LIB = REPO / "cases/simlox-air-support"
CASE = LIB / "B05-var02-payload-unload-failure-v1.0.0"
PARENT = LIB / "B05-var02-payload-unload-success-v1.0.0/ordinary-control-input.json"
D01 = LIB / "D01-system-direct-repair-v1.0.0/native-input.json"
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
SIMLOX = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
OUT = CASE / "review/independent-readonly-2026-09-30.json"
VARIANTS = ("ordinary", "unloading")
checks: dict[str, dict] = {}
failures: list[str] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eq(name: str, observed, expected):
    passed = observed == expected
    checks[name] = {"passed": passed}
    if not passed or len(str(observed)) < 180:
        checks[name].update({"observed": observed, "expected": expected})
    if not passed:
        failures.append(name)


def close(name: str, observed, expected, tolerance=0.00005):
    passed = len(observed) == len(expected) and all(abs(a-b) <= tolerance for a,b in zip(observed,expected))
    checks[name] = {"passed": passed, "observed": observed, "expected": expected, "tolerance": tolerance}
    if not passed:
        failures.append(name)


def load(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # SIMLOX report JSON has a trailing comma. Normalize only outside strings.
        out = []
        quoted = escaped = False
        for i,c in enumerate(raw):
            if quoted:
                out.append(c)
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    quoted = False
            elif c == '"':
                quoted = True
                out.append(c)
            elif c == "," and raw[i+1:].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(c)
        return json.loads("".join(out))


def table_map(doc, root="model"):
    t = {x["name"]: x for x in doc[root]["tables"]}
    assert len(t) == len(doc[root]["tables"])
    return t


def rows(doc, name, root="model"):
    t = table_map(doc, root)[name]
    names = [x["name"] for x in t["columns"]]
    assert len(names) == len(set(names))
    return [dict(zip(names,r)) for i in t["instances"] for r in i["rows"]]


def delta(before, after):
    a,b = table_map(before),table_map(after)
    def body(t):
        return None if t is None else {k:v for k,v in t.items() if k != "name"}
    return {n:{"before":body(a.get(n)),"after":body(b.get(n))} for n in sorted(set(a)|set(b)) if a.get(n)!=b.get(n)}


def events(log, text):
    result=[]
    for line in log.splitlines():
        if text in line:
            m=re.match(r"Time: ([0-9.]+) (.*)",line)
            assert m,line
            result.append((float(m.group(1)),m.group(2)))
    return result


def times(log,text):
    return [t for t,_ in events(log,text)]


def filtered(log,text,fragment):
    return [t for t,s in events(log,text) if fragment in s]


def inspect(v,contract,diff,parent,d01):
    run=CASE/"runs"/f"b05-var02-failure-{v}-20260930-01"
    source=load(CASE/f"{v}-input.json" if v=="unloading" else CASE/"ordinary-control-input.json")
    inp=load(run/"input.json")
    inv=load(run/"invocation.json")
    seal=load(run/"closure.json")
    steps=load(run/"steps.json")
    export=load(run/"roundtrip-raw.json")
    report=load(run/"report-raw.json")
    log=(run/"model.log").read_text(encoding="utf-8-sig")
    key=v+": "
    source_name="ordinary-control" if v=="ordinary" else "unloading"
    eq(key+"source SHA",sha(CASE/f"{source_name}-input.json"),diff["input_sha256"][source_name])
    eq(key+"source/run input",source,inp)
    eq(key+"run input SHA",sha(run/"input.json"),inv["input_sha256"])
    eq(key+"exact parent delta",delta(parent,source),diff["parent_differences"][source_name])
    eq(key+"32 unique tables",len(table_map(source)),32)
    eq(key+"D01 repair row/columns",{k:v for k,v in table_map(source)["SystemRepair"].items() if k!="name"},{k:v for k,v in table_map(d01)["SystemRepair"].items() if k!="name"})
    eq(key+"system FRT",rows(source,"System")[0]["FRT"],300000)
    eq(key+"fixed seed",rows(source,"Control")[0]["RSEED"],"1")
    for name,path,want in [
        ("parent",PARENT,inv["parent_sha256"]),
        ("D01 source",D01,inv["failure_source_sha256"]),
        ("contract",CASE/"contract.json",inv["contract_sha256"]),
        ("builder",CASE/"build.py",inv["builder_sha256"]),
        ("roundtrip checker",CASE/"check_roundtrip.py",inv["checker_sha256"]),
        ("runner",CASE/"run_native_ssh.ps1",inv["runner_script_sha256"]),
        ("Python",PYTHON,inv["python_sha256"]),
        ("SIMLOX",SIMLOX,inv["simlox_exe_sha256"]),
        ("invocation",run/"invocation.json",seal["invocation_sha256"]),
    ]:
        eq(key+name+" SHA",sha(path),want)
    eq(key+"source stable",seal["source_hashes_before"],seal["source_hashes_after"])
    eq(key+"source hash binding",seal["source_hashes_before"],inv["source_hashes_before"])
    eq(key+"run binding",(inv["variant"],inv["run_id"],inv["original_run_dir"].lower(),seal["run_id"],seal["error"]),(source_name,run.name,str(run).lower(),run.name,None))
    eq(key+"12 sealed raw files",len(seal["raw"]),12)
    for n,item in seal["raw"].items():
        p=run/n
        eq(key+"seal "+n,(p.stat().st_size,sha(p)),(item["bytes"],item["sha256"]))
    eq(key+"native files nonempty",all((run/n).stat().st_size>0 for n in ("model.sxi","model.sxo","model.log","report-raw.json")),True)
    eq(key+"SSH CLI",(inv["execution_mode"],inv["session_id"],inv["ssh_connection_present"],"sshd.exe" in inv["ssh_ancestor_names"]),("ssh_cli_v1",0,True,True))
    eq(key+"GUI record",(inv["gui"]["pid"],inv["gui"]["session_id"],inv["gui"]["start_utc"]),(13340,1,"2026-09-28T10:09:56.8261381Z"))
    eq(key+"queue guard",inv["queue_mutex"],"Global\\SimloxIssue18NativeQueue")
    eq(key+"step names",[s["name"] for s in steps],["import","export","calc","jsonreport","check_import_export"])
    eq(key+"step success/GUI",[(s["exit_code"],s["status"],s["gui_preserved"],s["error"]) for s in steps],[(0,"completed",True,None)]*5)
    eq(key+"step order",all(steps[i]["completed_utc"]<=steps[i+1]["started_utc"] for i in range(4)),True)
    eq(key+"planned commands",[(s["name"],s["arguments"]) for s in steps[:4]],[(s["name"],s["arguments"]) for s in inv["planned_commands"]])
    eq(key+"import success","Import completed!" in (run/"import.log").read_text(),True)
    eq(key+"export log",(run/"export.log").stat().st_size>0,True)
    eq(key+"report export","Generating Json-report" in (run/"report-export.log").read_text(),True)
    runlog=(run/"run.log").read_text()
    m=re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",runlog)
    eq(key+"conversion",m.groups() if m else None,("0","2","0"))
    eq(key+"warning IDs",re.findall(r"warning #(\d+)",runlog),["108","126"])
    populated={n:rows(inp,n) for n,t in table_map(inp).items() if any(i["rows"] for i in t["instances"])}
    eq(key+"19 populated tables",len(populated),19)
    eq(key+"roundtrip business rows",populated,{n:rows(export,n) for n in populated})
    eq(key+"turnround source/roundtrip",rows(inp,"MissionTurnround"),rows(export,"MissionTurnround"))

    mission="<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    close(key+"notice/create/launch",times(log,"mission ordered:")+times(log,"mission created:")+times(log,"mission starting,"),[7,7,8])
    close(key+"PAYLOADING positive work",filtered(log,"payloading subtask","starts performing"),[7])
    close(key+"PAYLOADING completion",filtered(log,"payloading subtask","completed"),[7.16667])
    close(key+"preparation end",times(log,"preparation ended, mission:"),[7.5])
    eq(key+"mission identity",all(mission in s for token in ("mission created:","mission starting,","mission aborted:","aborted mission completed:") for _,s in events(log,token)),True)
    close(key+"critical failure",times(log,"critical random failure added"),[9.8829])
    close(key+"mission abort",times(log,"mission aborted:"),[9.8829])
    eq(key+"abort statement",f"aborts its mission {mission}" in log,True)
    close(key+"aborted completion",times(log,"aborted mission completed:"),[10])
    eq(key+"no mission success",len(events(log,"mission success:")),0)
    close(key+"turnround start/end",times(log,"turnround started, mission:")+times(log,"turnround ended, mission:"),[10,10.1667])
    close(key+"turnround positive work",filtered(log,"seqno 1 within system turnround task","starts performing"),[10])
    close(key+"turnround subtask completed",[t for t,s in events(log,"seqno 1 within system turnround task") if s.endswith("completed")],[10.1667])
    if v=="unloading":
        close(key+"built-in UNLOADING performed",filtered(log,"unloading subtask","starts performing"),[10])
        close(key+"built-in UNLOADING completed",[t for t,s in events(log,"unloading subtask") if s.endswith("completed")],[10.1667])
        eq(key+"UNLOADING not skipped",not any(s.endswith("skipped") for _,s in events(log,"unloading subtask")),True)
    close(key+"system arrival/repair start",times(log,"System arrives <TEACH-AIR-01,0>")+filtered(log,"direct repair subtask","starts performing"),[10.1667,10.1667])
    close(key+"direct repair end",[t for t,s in events(log,"direct repair subtask") if s.endswith("completed")],[10.6667])
    close(key+"maintained system arrives",times(log,"Maintained system arrives"),[10.6667])
    close(key+"ready increased",times(log,"nbr ready increased at unit:"),[0,10.1667,10.6667])
    close(key+"ready decreased",times(log,"nbr ready decreased at unit:"),[7,10.1667])
    close(key+"systems ready",times(log,"systems ready:"),[0,10.6667])

    eq(key+"report table names",[t["name"] for t in report["report"]["tables"]],["ProblemDescription","ResultSummary","SystemResults","StockTotalResults"])
    eq(key+"report description",rows(report,"ProblemDescription","report"),rows(inp,"ProblemDescription"))
    summary=rows(report,"ResultSummary","report")
    eq(key+"failure summary",summary,[{"NREP":1,"RTILW":0,"RTIUP":36,"MTMF":1,"RSMTMF":0,"MSTF":1,"RSMSTF":0,"MSUF":0,"RSMSUF":0,"STMF":1,"RSSTMF":0}])
    sy=rows(report,"SystemResults","report")
    stock=rows(report,"StockTotalResults","report")
    eq(key+"72 system bins",len(sy),72)
    eq(key+"72 stock bins",len(stock),72)
    for name,bins in (("system",sy),("stock",stock)):
        eq(key+name+" bin continuity",[(r["STINT"],r["ETINT"]) for r in bins],[(i/2,(i+1)/2) for i in range(72)])
    eq(key+"system identity",{(r["UNID"],r["SID"]) for r in sy},{("Total over all Units","Total over all Systems")})
    eq(key+"flight bins",{r["STINT"]:r["STACC"] for r in sy if r["STACC"]},{8:1,8.5:1,9:1,9.5:1})
    close(key+"flight integral",[sum(r["STACC"]*0.5 for r in sy)],[2])
    eq(key+"STACC and FTMO profiles",[r["STACC"] for r in sy],[r["FTMO"] for r in sy])
    eq(key+"one failure in 9.5 bin",{r["STINT"]:r["NFAIL"] for r in sy if r["NFAIL"]},{9.5:1})
    close(key+"repair exposure bins",[sy[20]["NSYRP"],sy[21]["NSYRP"]],[2/3,1/3])
    close(key+"post-repair ready bin",[sy[21]["NSYRY"]],[2/3])
    eq(key+"terminal ready state",(sy[-1]["ETINT"],sy[-1]["NSYRY"],sy[-1]["NSYMA"],sy[-1]["NSYMO"],sy[-1]["NSYRP"]),(36,1,0,0,0))
    return {"run_id":run.name,"summary":summary,"system_bins":sy,"stock_bins":stock,"log":log,"closure_sha256":sha(run/"closure.json")}


def main():
    contract=load(CASE/"contract.json")
    source_diff=load(CASE/"exact-diff.json")
    parent=load(PARENT)
    d01=load(D01)
    eq("contract identity",(contract["variant_id"],contract["version"],contract["publication_state"]),("B05.var02","1.0.0","not_published"))
    eq("parent SHA",sha(PARENT),contract["parent_input_sha256"])
    eq("D01 failure SHA",sha(D01),contract["failure_input_sha256"])
    eq("diff parent/D01 hashes",(source_diff["parent_sha256"],source_diff["failure_source_sha256"]),(sha(PARENT),sha(D01)))
    a=load(CASE/"ordinary-control-input.json")
    b=load(CASE/"unloading-input.json")
    eq("exact pair source diff",delta(a,b),source_diff["pairwise_differences"])
    eq("pairwise changed tables",sorted(delta(a,b)),["ProblemDescription","TaskBreakDown"])
    eq("turnround type contrast",([r["SUTID"] for r in rows(a,"TaskBreakDown") if r["TID"]=="TURN-FIXED"],[r["SUTID"] for r in rows(b,"TaskBreakDown") if r["TID"]=="TURN-FIXED"]),(["SERVICE"],["<UNLOADING>"]))
    eq("PAYLOADING inherited",[[r["SUTID"] for r in rows(doc,"TaskBreakDown") if r["TID"]=="PREP-FIXED" and r["SEQ"]==1] for doc in (a,b)],[["<PAYLOADING>"],["<PAYLOADING>"]])
    results={v:inspect(v,contract,source_diff,parent,d01) for v in VARIANTS}
    x,y=results["ordinary"],results["unloading"]
    eq("same result summary",x["summary"],y["summary"])
    eq("same SystemResults bins",x["system_bins"],y["system_bins"])
    eq("same StockTotalResults bins",x["stock_bins"],y["stock_bins"])
    eq("negative source hash control",hashlib.sha256((CASE/"unloading-input.json").read_bytes()+b"x").hexdigest()!=source_diff["input_sha256"]["unloading"],True)
    eq("negative unloading-work control",not filtered(y["log"].replace("starts performing","does something else"),"unloading subtask","starts performing"),True)
    eq("negative terminal control",y["system_bins"][-1]["NSYRY"]-1!=1,True)
    decision="GO_bounded_failure_branch_native_cli_candidate" if not failures else "NO_GO"
    output={"schema":"simlox-b05-var02-failure-v100-independent-readonly-review/v1","reviewer_script_sha256":sha(Path(__file__)),"passed":not failures,"decision":decision,"check_count":len(checks),"failures":failures,"checks":checks,"run_ids":{v:results[v]["run_id"] for v in VARIANTS},"closure_sha256":{v:results[v]["closure_sha256"] for v in VARIANTS},"observed":{"PAYLOADING_work_hours":[7,7.16667],"mission_start_hour":8,"critical_failure_and_abort_hour_printed":9.8829,"aborted_mission_completion_hour":10,"positive_turnround_work_hours_both_variants":[10,10.1667],"direct_repair_hours_printed":[10.1667,10.6667],"terminal_hour":36,"terminal_ready_count":1},"accepted_scope":"One fixed-seed one-aircraft payloaded mission with an observed critical system failure; positive built-in UNLOADING work after abort matches equal-duration ordinary SERVICE control under sealed native CLI runs.","limits":["The one failure timing and success/failure branch contrast do not establish all payload or failure-state rules.","Payload quantity and internal state are not directly observed.","No GUI-only mechanism, resource contention, cross-engine parity or publication is established.","Native JSON report contains a trailing comma; raw hashes are checked before tolerant independent parsing."]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_bytes((json.dumps(output,indent=2,ensure_ascii=False,default=list)+"\n").encode("utf-8"))
    print(json.dumps({"passed":output["passed"],"decision":decision,"checks":len(checks),"failures":failures,"report":str(OUT)},indent=2))
    return not failures


if __name__=="__main__":
    sys.exit(0 if main() else 1)
