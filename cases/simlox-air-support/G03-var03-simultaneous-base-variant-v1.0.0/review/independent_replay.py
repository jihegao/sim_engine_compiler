"""Independent read-only replay of G03.var03 sealed native evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "g03-var03-simultaneous-v100-ssh-20261003-01"
OUT = CASE / "review" / "independent-validation-2026-10-03.json"
EXTERNAL = {
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path):
    data = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = escaped = False
    for i, char in enumerate(data):
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            output.append(char)
            quoted = True
        elif char == ",":
            j = i + 1
            while j < len(data) and data[j].isspace():
                j += 1
            if j == len(data) or data[j] not in "}]":
                output.append(char)
        else:
            output.append(char)
    return json.loads("".join(output))


def tables(document, root):
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def field(table, column, index=0):
    c = next(i for i, value in enumerate(table["columns"]) if value["name"] == column)
    return rows(table)[index][c]


checks = 0
failures = []


def check(value, label):
    global checks
    checks += 1
    if not value:
        failures.append(label)


def near(actual, expected, tol=0.00001):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=tol)


contract = native_json(CASE / "contract.json")
source_path = CASE / "native-input.json"
source = tables(native_json(source_path), "model")
parent_dir = CASES / contract["accepted_parent"]["package"]
parent_path = parent_dir / "add-extra-input.json"
parent_run = parent_dir / "runs" / contract["accepted_parent"]["run_id"]
parent_closure = parent_run / "closure.json"
diff = native_json(CASE / "exact-diff.json")
check(sha(parent_path) == contract["accepted_parent"]["input_sha256"], "accepted add-extra input SHA")
check(sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"], "accepted add-extra closure SHA")
check(sha(source_path) == contract["input"]["sha256"], "frozen child input SHA")
check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen diff SHA")
for name in ("exe", "manual", "dictionary"):
    check(sha(EXTERNAL[name]) == contract["source"][f"{name}_sha256"], f"installed {name} SHA")
parent = tables(native_json(parent_path), "model")
changed = {name:{"before":parent.get(name),"after":source.get(name)} for name in parent.keys()|source.keys() if parent.get(name)!=source.get(name)}
check(changed == diff["changed"], "exact parent/child table delta")
check(set(changed) == {"ProblemDescription", "Unit", "SystemDeployment", "Operations"}, "only four changed tables")
check(len(rows(source["Unit"])) == len(rows(source["SystemDeployment"])) == len(rows(source["Operations"])) == 2, "two complete unit/deployment/schedule bindings")
check({(field(source["SystemDeployment"],"SID",i),field(source["SystemDeployment"],"USTID",i)) for i in range(2)} == {("TEACH-VAR-ADD","TEACH-UNIT"),("TEACH-AIR-01","TEACH-BASE-UNIT")}, "separate physical deployments")
check(field(source["System"],"BSID",1)=="TEACH-AIR-01" and field(source["Item"],"FRT",0)==0 and field(source["Item"],"FRT",1)==300000, "BSID variant and source item rates")
check(field(source["StockAllocation"],"IID")=="TEACH-LRU-ADD" and field(source["StockAllocation"],"STSIZ")==1, "one local added-LRU spare")

inv = native_json(RUN / "invocation.json")
closure = native_json(RUN / "closure.json")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation SHA seal")
check(inv["run_id"] == closure["run_id"] == RUN.name, "run ID")
check(inv["execution_mode"] == "session0_ssh_cli" and inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"], "session-zero SSH")
check(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "GUI and host mutex")
check(inv["prelife_log_option_before"] == closure["prelife_log_option_after"] == "NO", "registry option restored")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"], "source unchanged during run")
source_files = {
    "input":source_path,"parent":parent_path,"parent_closure":parent_closure,
    "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
    "builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py",
    "checker":CASE/"check_roundtrip.py","runner":CASE/"run_native_ssh.ps1",**EXTERNAL,
}
for name,path in source_files.items():
    check(sha(path) == closure["source_hashes_before"][name], f"source seal {name}")
check(len(closure["raw"]) == 13, "13 native raw files")
for name,meta in closure["raw"].items():
    path = RUN/name
    check(path.exists() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw seal {name}")
check(sha(RUN/"input.json") == sha(source_path), "run input equals frozen input")
steps = native_json(RUN/"steps.json")
check([s["name"] for s in steps] == ["import","export","calc","jsonreport","check_import_export"], "native five steps")
for step in steps:
    check(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"], f"guarded {step['name']}")
check([s["arguments"] for s in steps[:4]] == [s["args"] for s in inv["planned_commands"]], "planned CLI commands used")
check(closure["conversion"]["errors"] == 0 and closure["conversion"]["notes"] == 0 and closure["conversion"]["warning_codes"] == ["108","2053"], "converter diagnostics")
check(closure["native_outcome"] == "zero_error_reviewed_warnings" and closure["sxo_bytes"] > 4 and closure["report_present"], "valid calculated outputs")
check(not re.search(r"\berror\s*#",(RUN/"import.log").read_text(encoding="utf-8-sig")+(RUN/"run.log").read_text(encoding="utf-8-sig"),re.I), "no numbered converter/runtime error")

exported = tables(native_json(RUN/"roundtrip-raw.json"),"model")
populated = [name for name,table in source.items() if rows(table)]
check(len(populated)==18, "18 authored row-containing tables")
for name in populated:
    check(name in exported, f"export {name} exists")
    if name in exported:
        check(exported[name]["columns"] == source[name]["columns"], f"{name} authored columns")
        check(exported[name]["instances"] == source[name]["instances"], f"{name} authored rows")

log = (RUN/"model.log").read_text(encoding="utf-8-sig")
def event(time, fragment):
    return any(line.startswith(f"Time: {time} ") and fragment in line for line in log.splitlines())

for mission,unit,system,start,end in (
    (0,"TEACH-UNIT","TEACH-VAR-ADD,0",8,10),(1,"TEACH-BASE-UNIT","TEACH-AIR-01,1",8,10),
    (2,"TEACH-UNIT","TEACH-VAR-ADD,0",20,22),(3,"TEACH-BASE-UNIT","TEACH-AIR-01,1",20,22),
    (4,"TEACH-UNIT","TEACH-VAR-ADD,0",32,34),(5,"TEACH-BASE-UNIT","TEACH-AIR-01,1",32,34),
):
    ident=f"<BASIC-MISSION,{unit},0,0,{mission}>"
    check(event(start,f"{ident} mission starting, duration: 2 : <{system}>"),f"mission {mission} assigned correct physical system")
    outcome="aborted mission completed" if mission==0 else "mission completed"
    check(event(end,f"{ident} {outcome}"),f"mission {mission} end")
    if mission!=0:
        check(event(end,f"{ident} mission success"),f"mission {mission} success")
check(event(9.8829,"<TEACH-VAR-ADD,0> critical random failure added") and event(9.8829,"<BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted"), "variant first mission failure and abort")
check("subitem failed: <TEACH-LRU-ADD,0,1> connection path: TEACH-VAR-ADD - TEACH-VAR-ADD - TEACH-LRU-ADD" in log, "specific failed mounted added LRU")
check("<TEACH-AIR-01,1> critical random failure added" not in log and "TEACH-LRU-BASE,0,1> connection path" not in log, "base failure absent")
for time,fragment in (
    (10,"Take replacement item <TEACH-LRU-ADD,0,0> from stock"),
    (10,"system SURP task 0 on <TEACH-VAR-ADD,0> started"),
    (10.25,"remove subitem subtask 0 seqno 0 within system SURP task 0 on <TEACH-VAR-ADD,0> completed"),
    (10.25,"Start repair of item <TEACH-LRU-ADD,0,1>"),
    (10.5,"system SURP task 0 on <TEACH-VAR-ADD,0> completed"),
    (11.25,"item DIRP task 1 on <TEACH-LRU-ADD,0,1> completed"),
    (11.25,"Put back replacement item <TEACH-LRU-ADD,0,1> to stock"),
):
    check(event(time,fragment), f"physical stock/repair event {time}: {fragment}")
check(log.index("Time: 9.8829 <TEACH-VAR-ADD,0> critical random failure") < log.index("Time: 10 <TEACH-LRU-ADD,0,BASE-01,0> Take replacement item") < log.index("Time: 10.5  system SURP task 0") < log.index("Time: 11.25  item DIRP task 1"), "variant failure/issue/SURP/repair order")
check(event(34,"<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-VAR-ADD,0>") and event(34,"<TEACH-BASE-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,1>"), "both physical systems terminal ready")

report = tables(native_json(RUN/"report-raw.json"),"report")
check(set(report)=={"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},"native report tables")
summary=report["ResultSummary"]
for name,want in (("NREP",1),("RTILW",0),("RTIUP",36),("MTMF",1),("MSTF",1),("MSUF",5/6),("STMF",1)):
    check(near(field(summary,name),want),f"ResultSummary {name}")
system,stock=report["SystemResults"],report["StockTotalResults"]
sr,kr=rows(system),rows(stock)
check(len(sr)==len(kr)==72,"72 aligned system and stock intervals")
for i,(srow,krow) in enumerate(zip(sr,kr)):
    s=i/2
    sv={c["name"]:srow[n] for n,c in enumerate(system["columns"])}
    kv={c["name"]:krow[n] for n,c in enumerate(stock["columns"])}
    check(near(sv["STINT"],s) and near(sv["ETINT"],s+.5) and near(kv["STINT"],s) and near(kv["ETINT"],s+.5),f"aligned bin {i}")
    mission=any(a<=s<b for a,b in ((8,10),(20,22),(32,34)))
    reserved=any(a<=s<b for a,b in ((7,8),(19,20),(31,32)))
    repair=(s==10)
    ready=0 if (mission or reserved) else (1 if repair else 2)
    for name,want in (("NSYRY",ready),("NSYMA",2 if mission or reserved else 0),("NSYMO",2 if mission else 0),("NSYMR",2 if reserved else 0),("NSYRP",int(repair)),("NSYUA",int(repair)),("NSYA",1 if repair else 2),("FTMO",int(mission)),("STACC",2 if mission else 0),("NFAIL",int(s==9.5)),("NREPT",int(s==10.5)),("NSYDT",int(repair))):
        check(sv[name]==want,f"SystemResults {name} bin {i}")
    check((sv["SYDT"] is None) if not repair else near(sv["SYDT"],.5),f"SystemResults SYDT bin {i}")
    for name in ("NSYMC","NSYMP","NSYMT","NSYMS","NSYAL","NSYPM","NSYTP","NSYWR","NSYWI","NSYLA","NSYUH","NPMT","NDAM","NPMS","NROBT","NRCFG","STREQ","STF","STLOW","SYDTU","NSYSW","NPSTA","NPSUC"):
        check(sv[name]==0,f"SystemResults {name} zero bin {i}")
    check(kv["PNB"]==1 and kv["NDF"]==int(s==10) and kv["NWT"]==int(s==10),f"StockTotalResults demand/work bin {i}")
    for name in ("ROS","ROST","WT","WTT"):
        check(kv[name] == (0 if s==10 else None),f"StockTotalResults {name} no-wait metric bin {i}")
    for name in ("NBO","NDD","NDR","NDP","NLD"):
        check(kv[name]==0,f"StockTotalResults {name} zero bin {i}")
    check(kv["NBOU"] is None and kv["WTS"] is None,f"StockTotalResults empty fields bin {i}")
check(near(sum(field(system,"NSYMO",i) for i in range(72))*.5,12),"12 aggregate operating system-hours")
check(near(sum(field(system,"NSYRP",i) for i in range(72))*.5,.5),"half-hour aggregate SURP occupancy")
check(field(system,"NSYRY",71)==2 and field(stock,"NBO",71)==0,"terminal two ready/no backorder")

result={
    "schema":"simlox-g03-var03-independent-readonly/v1",
    "decision":"GO: bounded simultaneous separate base and BSID add-variant observation",
    "passed":not failures,"checks_passed":checks-len(failures),"checks_total":checks,"failures":failures,
    "raw_seals":len(closure["raw"]),"source_sha256":sha(source_path),"closure_sha256":sha(RUN/"closure.json"),
    "model_log_sha256":sha(RUN/"model.log"),"report_sha256":sha(RUN/"report-raw.json"),
    "observed":{"physical_systems":["TEACH-VAR-ADD,0 in TEACH-UNIT","TEACH-AIR-01,1 in TEACH-BASE-UNIT"],
                "mission_outcomes":["variant abort h9.8829, return h10","base success h10","variant/base success h22","variant/base success h34"],
                "item_path":"failed mounted TEACH-LRU-ADD ID1; stock ID0 issue h10; SURP h10-10.5; ID1 direct repair h10.25-11.25 and stock return",
                "terminal_ready":2},
    "limits":["One BSID add variant, one base, one station, one seed and one replication; no frequency inference.",
              "Report is aggregate, so physical mission and failure attribution comes from the model event log.",
              "No CBSID runtime conversion, simultaneous add/exclude, GUI visual or cross-engine claim."],
}
OUT.write_bytes((json.dumps(result,indent=2,sort_keys=True)+"\n").encode("utf-8"))
print(json.dumps({"passed":result["passed"],"checks_passed":result["checks_passed"],"checks_total":checks,"failures":failures,"output":str(OUT)}))
raise SystemExit(0 if not failures else 1)
