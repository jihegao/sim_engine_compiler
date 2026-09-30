"""Independent read-only replay of B05.var04 converter rejection.

Python standard library only. It does not run SIMLOX or import author code.
It writes one JSON report in this review directory and never edits raw runs.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LIB = REPO / "cases/simlox-air-support"
CASE = LIB / "B05-var04-replacement-order-v1.0.0"
E01 = LIB / "E01-local-spare-explicit-replacement-v1.0.0"
PARENT = E01 / "native-input.json"
POSITIVE = E01 / "runs/e01-v100-ssh-20260929-01"
RUN = CASE / "runs/b05-var04-reversed-20260930-01"
PDF = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
SIMLOX = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
OUT = CASE / "review/independent-readonly-2026-09-30.json"
checks = {}
failures = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name, observed, expected):
    passed = observed == expected
    checks[name] = {"passed": passed}
    if not passed or len(str(observed)) < 180:
        checks[name].update({"observed": observed, "expected": expected})
    if not passed:
        failures.append(name)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table_map(doc):
    found = {t["name"]:t for t in doc["model"]["tables"]}
    assert len(found)==len(doc["model"]["tables"])
    return found


def rows(doc,name):
    t=table_map(doc)[name]
    cols=[c["name"] for c in t["columns"]]
    assert len(cols)==len(set(cols))
    return [dict(zip(cols,r)) for i in t["instances"] for r in i["rows"]]


def delta(before,after):
    a,b=table_map(before),table_map(after)
    def body(t):
        return None if t is None else {k:v for k,v in t.items() if k!="name"}
    return {n:{"before":body(a.get(n)),"after":body(b.get(n))} for n in sorted(set(a)|set(b)) if a.get(n)!=b.get(n)}


def main():
    contract=load(CASE/"contract.json")
    diff=load(CASE/"exact-diff.json")
    parent=load(PARENT)
    source=load(CASE/"native-input.json")
    inp=load(RUN/"input.json")
    inv=load(RUN/"invocation.json")
    closure=load(RUN/"closure.json")
    steps=load(RUN/"steps.json")
    exported=load(RUN/"roundtrip-raw.json")
    runlog=(RUN/"run.log").read_text(encoding="utf-8-sig")

    check("contract identity",(contract["variant_id"],contract["version"],contract["publication_state"]),("B05.var04","1.0.0","not_published"))
    check("E01 parent SHA",sha(PARENT),contract["parent_input_sha256"])
    check("E01 accepted signoff",(E01/"cli-scope-signoff-2026-09-29.md").exists(),True)
    check("exact diff source SHA",(diff["parent_sha256"],diff["input_sha256"]),(sha(PARENT),sha(CASE/"native-input.json")))
    check("source equals run input",source,inp)
    check("run input SHA",sha(RUN/"input.json"),inv["input_sha256"])
    check("exact changed table bodies",delta(parent,source),diff["differences"])
    check("only PDESC and TaskBreakDown changed",sorted(delta(parent,source)),["ProblemDescription","TaskBreakDown"])
    def sequence(doc):
        return [(r["SEQ"],r["SUTID"],r["DURN"]) for r in rows(doc,"TaskBreakDown") if r["TID"]=="E01-SURP"]
    check("positive E01 sequence",sequence(parent),[(1,"<REMOVE>",1/6),(2,"<REPLACE>",1/3)])
    check("reversed child whole pairs",sequence(source),[(1,"<REPLACE>",1/3),(2,"<REMOVE>",1/6)])
    check("unchanged E01-SURP task link",rows(source,"SystemRepair"),rows(parent,"SystemRepair"))
    check("manual PDF SHA",sha(PDF),contract["source"]["manual_sha256"])
    for name,path,want in [
        ("contract",CASE/"contract.json",inv["contract_sha256"]),
        ("builder",CASE/"build.py",inv["builder_sha256"]),
        ("roundtrip checker",CASE/"check_roundtrip.py",inv["checker_sha256"]),
        ("runner",CASE/"run_native_ssh.ps1",inv["runner_script_sha256"]),
        ("Python",PYTHON,inv["python_sha256"]),
        ("SIMLOX",SIMLOX,inv["simlox_exe_sha256"]),
        ("invocation",RUN/"invocation.json",closure["invocation_sha256"]),
    ]:
        check(name+" SHA",sha(path),want)
    check("parent invocation binding",inv["parent_sha256"],sha(PARENT))
    check("source stable during run",closure["source_hashes_before"],closure["source_hashes_after"])
    check("source hash map binding",closure["source_hashes_before"],inv["source_hashes_before"])
    check("run identity",(inv["variant"],inv["run_id"],inv["original_run_dir"].lower(),closure["run_id"],closure["error"]),("reversed-replacement",RUN.name,str(RUN).lower(),RUN.name,None))
    check("nine sealed raw files",len(closure["raw"]),9)
    for n,item in closure["raw"].items():
        p=RUN/n
        check("seal "+n,(p.stat().st_size,sha(p)),(item["bytes"],item["sha256"]))
    check("SSH CLI",(inv["execution_mode"],inv["session_id"],inv["ssh_connection_present"],"sshd.exe" in inv["ssh_ancestor_names"]),("ssh_cli_v1",0,True,True))
    check("GUI identity record",(inv["gui"]["pid"],inv["gui"]["session_id"],inv["gui"]["start_utc"]),(13340,1,"2026-09-28T10:09:56.8261381Z"))
    check("queue mutex",inv["queue_mutex"],"Global\\SimloxIssue18NativeQueue")
    check("step names",[s["name"] for s in steps],["import","export","calc","check_import_export"])
    check("step exit/status/GUI",[(s["exit_code"],s["status"],s["gui_preserved"],s["error"]) for s in steps],[(0,"completed",True,None),(0,"completed",True,None),(0,"expected_rejection",True,None),(0,"completed",True,None)])
    check("step chronology",all(steps[i]["completed_utc"]<=steps[i+1]["started_utc"] for i in range(3)),True)
    check("planned native commands",[(s["name"],s["arguments"]) for s in steps[:3]],[(s["name"],s["arguments"]) for s in inv["planned_commands"]])
    check("import completed","Import completed!" in (RUN/"import.log").read_text(),True)
    check("export log nonempty",(RUN/"export.log").stat().st_size>0,True)
    populated={n:rows(inp,n) for n,t in table_map(inp).items() if any(i["rows"] for i in t["instances"])}
    check("20 populated source tables",len(populated),20)
    check("exact populated roundtrip",populated,{n:rows(exported,n) for n in populated})
    check("roundtrip invalid breakdown unchanged",rows(exported,"TaskBreakDown"),rows(inp,"TaskBreakDown"))

    check("warning IDs",re.findall(r"warning #(\d+)",runlog),["108"])
    check("error IDs",re.findall(r"error #(\d+)",runlog),["163"])
    check("exact converter diagnostic",'rec 1: (error #163) Invalid subtask breakdown of sub replacement task: E01-SURP' in runlog,True)
    m=re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)",runlog)
    check("one conversion error",m.groups() if m else None,("1","1","0"))
    check("no simulation start/result save",not any(s in runlog for s in ("Starting simulation...","Saving results ...","Total execution time:")),True)
    check("four-byte SXO",(RUN/"model.sxo").stat().st_size,4)
    check("four-byte SXO signature",(RUN/"model.sxo").read_bytes().hex(),"8bc53301")
    check("no event log",not (RUN/"model.log").exists(),True)
    check("no native report",not (RUN/"report-raw.json").exists(),True)
    check("no report-export log",not (RUN/"report-export.log").exists(),True)
    check("positive E01 conversion",bool(re.search(r"Input conversion completed\. Errors: 0,",(POSITIVE/"run.log").read_text())),True)
    check("positive E01 outputs",all((POSITIVE/n).stat().st_size>4 for n in ("model.sxo","model.log","report-raw.json")),True)
    check("negative diagnostic control",'Invalid subtask breakdown of sub replacement task: E01-SURP' not in runlog.replace("Invalid subtask breakdown","Other breakdown"),True)
    check("negative source hash control",hashlib.sha256((CASE/"native-input.json").read_bytes()+b"x").hexdigest()!=diff["input_sha256"],True)

    # Separately inspected installed manual (matching SHA above): printed pp.
    # 400, 401 and 402 explicitly require <REMOVE> before <REPLACE>.
    decision="GO_negative_converter_rejection_only" if not failures else "NO_GO"
    result={"schema":"simlox-b05-var04-v100-independent-readonly-review/v1","reviewer_script_sha256":sha(Path(__file__)),"passed":not failures,"decision":decision,"check_count":len(checks),"failures":failures,"checks":checks,"run_id":RUN.name,"closure_sha256":sha(RUN/"closure.json"),"manual_review":{"manual_sha256":sha(PDF),"printed_pages_checked":[400,401,402],"finding":"The built-in <REMOVE> and <REPLACE> subtasks are mandatory for subitem replacement and must appear in that order; the sequence number defines order."},"observed":{"source_sequence":["SEQ1 <REPLACE> 20 min","SEQ2 <REMOVE> 10 min"],"native_error_id":163,"native_diagnostic":"Invalid subtask breakdown of sub replacement task: E01-SURP","conversion_errors":1,"calculation_process_exit_code":0,"sxo_bytes":4,"report_present":False},"accepted_scope":"One converter-level negative test of reversed E01 local-spare replacement order. Native import/export succeeds, calculation rejects the invalid breakdown, and no simulation behavior is accepted.","limits":["Process exit code zero does not override the explicit conversion error or missing report.","Other omission, repetition, extra subtasks, repair routes, GUI-only behavior and cross-engine parity are unverified.","The manually read PDF ordering rule is recorded as reviewer observation; this standard-library replay verifies the installed PDF's SHA-256 but does not parse PDF text."]}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False,default=list)+"\n").encode("utf-8"))
    print(json.dumps({"passed":result["passed"],"decision":decision,"checks":len(checks),"failures":failures,"report":str(OUT)},indent=2))
    return not failures


if __name__=="__main__":
    sys.exit(0 if main() else 1)
