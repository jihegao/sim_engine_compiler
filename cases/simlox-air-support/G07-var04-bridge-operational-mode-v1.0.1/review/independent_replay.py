"""Independent read-only raw replay of the G07.var04 0.75 bridge-block mode."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "g07-var04-br75-v101-ssh-20261003-01"
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
    out = []
    quoted = escaped = False
    for i,c in enumerate(data):
        if quoted:
            out.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            out.append(c)
            quoted = True
        elif c == ",":
            j = i+1
            while j < len(data) and data[j].isspace():
                j += 1
            if j == len(data) or data[j] not in "}]":
                out.append(c)
        else:
            out.append(c)
    return json.loads("".join(out))

def tables(doc, root):
    return {t["name"]:t for t in doc[root]["tables"]}

def rows(t):
    return [r for inst in t["instances"] for r in inst["rows"]]

def records(t):
    cols = [c["name"] for c in t["columns"]]
    return [dict(zip(cols,r)) for r in rows(t)]

def near(a,b,tol=.0006):
    return isinstance(a,(float,int)) and math.isclose(a,b,abs_tol=tol)

def occupancy(a,b,start):
    return 2*max(0,min(b,start+.5)-max(a,start))

checks = 0
failures = []
def check(ok,label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)

contract = native_json(CASE/"contract.json")
parent_dir = CASES/contract["accepted_parent"]["package"]
parent_file = parent_dir/"brfirst-input.json"
parent_run = parent_dir/"runs"/contract["accepted_parent"]["run_id"]
diag_dir = CASES/contract["diagnostic_predecessor"]["package"]
diag_file = diag_dir/"brhalf-input.json"
diag_run = diag_dir/"runs"/contract["diagnostic_predecessor"]["run_id"]
source_file = CASE/"br75-input.json"
parent = tables(native_json(parent_file),"model")
source = tables(native_json(source_file),"model")
diagnostic = tables(native_json(diag_file),"model")
diff = native_json(CASE/"exact-diff.json")
check(sha(parent_file) == contract["accepted_parent"]["input_sha256"],"parent input SHA")
check(sha(parent_run/"closure.json") == contract["accepted_parent"]["native_closure_sha256"],
      "parent native closure SHA")
check(sha(diag_file) == contract["diagnostic_predecessor"]["input_sha256"],
      "excluded half-rate input SHA")
check(sha(diag_run/"closure.json") == contract["diagnostic_predecessor"]["native_closure_sha256"],
      "excluded half-rate closure SHA")
check(sha(source_file) == contract["input_sha256"],"child source SHA")
check(sha(CASE/"exact-diff.json") == contract["exact_diff_sha256"],"exact diff SHA")
for key in ("manual","dictionary","exe"):
    check(sha(EXTERNAL[key]) == contract["source"][f"{key}_sha256"],
          f"installed {key} SHA")
dictionary = EXTERNAL["dictionary"].read_text(encoding="utf-8-sig")
check("RBDBridge;10;BROPM;" in dictionary and "MaterielOperationalModes;5;USERT;" in dictionary,
      "installed BROPM/USERT dictionary fields")

changed = {name:{"before":parent.get(name),"after":source.get(name)}
           for name in parent.keys()|source.keys() if parent.get(name)!=source.get(name)}
check(changed == diff["changed"] and set(changed) ==
      {"ProblemDescription","OperationalModes","MaterielOperationalModes","RBDBridge"},
      "frozen exact four-table source delta")
for name in parent:
    if name not in changed:
        check(parent[name] == source[name],f"fixed {name}")
check(len(records(source["OperationalModes"])) == len(records(parent["OperationalModes"]))+1,
      "one added mode")
added_mode = [r for r in records(source["OperationalModes"])
              if r not in records(parent["OperationalModes"])]
check(len(added_mode)==1 and added_mode[0]["OPMID"]=="G07-BR-75", "added mode ID")
added_mom = [r for r in records(source["MaterielOperationalModes"])
             if r not in records(parent["MaterielOperationalModes"])]
check(len(added_mom)==1 and added_mom[0]["MID"]=="POS-B" and
      added_mom[0]["OPMID"]=="G07-BR-75" and near(added_mom[0]["USERT"],.75),
      "only POS-B new mode has USERT 0.75")
check(all(r in records(source["MaterielOperationalModes"])
          for r in records(parent["MaterielOperationalModes"])),
      "all full-rate mode rows preserved")
bridge = records(source["RBDBridge"])[0]
parent_bridge = records(parent["RBDBridge"])[0]
check({k:bridge[k] for k in bridge if k not in ("DESCR","BROPM")} ==
      {k:parent_bridge[k] for k in parent_bridge if k not in ("DESCR","BROPM")},
      "bridge slots and other mode refs identical")
check(parent_bridge["BROPM"]=="G04-OPS" and bridge["BROPM"]=="G07-BR-75" and
      bridge["BRBID"]=="POS-B", "only bridge-block mode ref changes")
check(all(bridge[k]=="G04-OPS" for k in ("ULOPM","LLOPM","UROPM","LROPM")),
      "four other bridge slots retain full-rate mode")
check(records(diagnostic["MaterielOperationalModes"])[-1]["USERT"]==.5 and
      records(diagnostic["RBDBridge"])[0]["BROPM"]!="G04-OPS",
      "half-rate diagnostic is distinct excluded source")

inv = native_json(RUN/"invocation.json")
closure = native_json(RUN/"closure.json")
check(sha(RUN/"invocation.json") == closure["invocation_sha256"],"invocation seal")
check(inv["run_id"]==closure["run_id"]==RUN.name,"run identity")
check(inv["execution_mode"]=="session0_ssh_cli" and inv["session_id"]==0 and
      "sshd.exe" in inv["ssh_ancestor_names"],"SSH session0")
check(inv["gui"]["pid"]==13340 and inv["gui"]["session_id"]==1 and
      inv["queue_mutex"]==r"Global\SimloxIssue18NativeQueue","GUI/queue guard")
check(inv["prelife_log_option_before"]==closure["prelife_log_option_after"]=="NO",
      "registry restored")
check(inv["source_hashes_before"]==closure["source_hashes_before"]==
      closure["source_hashes_after"],"before/after source stability")
paths={"input":source_file,"parent":parent_file,"parent_closure":parent_run/"closure.json",
       "diagnostic":diag_file,"diagnostic_closure":diag_run/"closure.json",
       "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
       "builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py",
       "checker":CASE/"check_roundtrip.py","runner":CASE/"run_native_ssh.ps1",**EXTERNAL}
for name,path in paths.items():
    check(sha(path)==closure["source_hashes_before"][name],f"source seal {name}")
check(len(closure["raw"])==13,"13 raw seals")
for name,meta in closure["raw"].items():
    path=RUN/name
    check(path.exists() and path.stat().st_size==meta["bytes"] and sha(path)==meta["sha256"],
          f"raw seal {name}")
check(sha(RUN/"input.json")==sha(source_file),"native input source copy")
steps=native_json(RUN/"steps.json")
check([s["name"] for s in steps]==["import","export","calc","jsonreport","check_import_export"],
      "five guarded steps")
for s in steps:
    check(s["exit_code"]==0 and s["status"]=="completed" and s["gui_preserved"],
          f"guarded {s['name']}")
check([s["arguments"] for s in steps[:4]]==
      [s["args"] for s in inv["planned_commands"]],"planned CLI matches actual")
check(closure["conversion"]["errors"]==0 and closure["conversion"]["notes"]==0 and
      closure["conversion"]["warning_codes"]==["108"],"zero errors; warning108")
check(closure["sxo_bytes"]>4 and closure["report_present"] and
      closure["native_outcome"]=="zero_error_reviewed_warnings","usable native result")
check(not re.search(r"\berror\s*#",(RUN/"run.log").read_text(encoding="utf-8-sig"),re.I),
      "no converter error text")
exported=tables(native_json(RUN/"roundtrip-raw.json"),"model")
populated=[name for name,t in source.items() if rows(t)]
check(len(populated)==22,"22 authored row-containing tables")
for name in populated:
    check(name in exported,f"exported {name}")
    if name in exported:
        check(source[name]["columns"]==exported[name]["columns"],f"exact {name} columns")
        check(source[name]["instances"]==exported[name]["instances"],f"exact {name} rows")

log=(RUN/"model.log").read_text(encoding="utf-8-sig")
parent_log=(parent_run/"model.log").read_text(encoding="utf-8-sig")
diag_log=(diag_run/"model.log").read_text(encoding="utf-8-sig")
def event(hour,fragment):
    return any(line.startswith(f"Time: {hour} ") and fragment in line for line in log.splitlines())
check(event(7,"mission allocates system: <TEACH-AIR-01,0>") and
      event(8,"mission starting, duration: 26"),"mission h8 start")
check(event(8.75316,"noncritical CM failure mode added") and
      "Failure Mode: FM-POS-A on materiel: <POS-A,0>" in log,"A first h8.75316 NC")
check(event(14.1679,"noncritical CM failure mode added") and
      "Failure Mode: FM-POS-B on materiel: <POS-B,0>" in log,"B second h14.1679 NC")
check(log.count("CM failure mode added")==2 and
      all(f"Failure Mode: FM-POS-{p}" not in log for p in "CDE"),
      "two observed failure modes only")
check("Time: 8.62763" in parent_log and "FM-POS-B on materiel" in parent_log and
      "Time: 16.7498" in parent_log and "FM-POS-A on materiel" in parent_log,
      "full-rate control B then A")
check("Time: 8.94145" in diag_log and "Time: 17.0636" in diag_log and
      "mission success" in diag_log,"excluded half-rate diagnostic A then B")
check(event(34,"mission success") and event(34,"mission completed") and
      "mission aborted" not in log,"successful mission h34")
for task,mode in enumerate(("FM-POS-A","FM-POS-B")):
    label=f"system CM task {task} on <TEACH-AIR-01,0>"
    check(event(34,label+" started") and event(34,label+" FMID: "+mode) and
          event(34.5,label+" completed"),f"CM {task} identity/time")
    check(f"< {label}, NC, 0.5>" in log,f"CM {task} noncritical")
check(event(34.5,"systems ready: 1") and "Item demand arrives" not in log,
      "terminal ready and no item demand")

report=tables(native_json(RUN/"report-raw.json"),"report")
parent_report=tables(native_json(parent_run/"report-raw.json"),"report")
check(set(report)=={"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},
      "report table set")
check(report["ResultSummary"]==parent_report["ResultSummary"],
      "same outcome summary as full-rate control")
summary=records(report["ResultSummary"])[0]
for name,want in (("NREP",1),("RTILW",0),("RTIUP",36),("MTMF",1),
                  ("MSTF",1),("MSUF",1),("STMF",1)):
    check(near(summary[name],want),f"summary {name}")
for name in ("RSMTMF","RSMSTF","RSMSUF","RSSTMF"):
    check(summary[name]==0,f"one-rep precision {name}")
system=records(report["SystemResults"])
stock=records(report["StockTotalResults"])
check(len(system)==len(stock)==72,"72 aligned System/Stock bins")
for i,(s,k) in enumerate(zip(system,stock)):
    start=i*.5
    end=start+.5
    check(s["STINT"]==k["STINT"]==start and s["ETINT"]==k["ETINT"]==end,
          f"aligned interval {i}")
    reserved=occupancy(7,8,start)
    flight=occupancy(8,34,start)
    repair=occupancy(34,34.5,start)
    expected={"NSYRY":1-reserved-flight-repair,"NSYMA":reserved+flight,
              "NSYMO":flight,"NSYMR":reserved,"NSYRP":repair,"NSYUA":repair,
              "NSYA":1-repair,"FTMO":flight,"STACC":flight,
              "NFAIL":int(start<=8.75316<end)+int(start<=14.1679<end)}
    for name,want in expected.items():
        check(near(s[name],want),f"system {name} bin {i}")
    check(s["NREPT"]==(2 if i==69 else 0) and
          s["NSYDT"]==(1 if i==68 else 0),f"repair/downtime markers bin {i}")
    check((near(s["SYDT"],.5) if i==68 else s["SYDT"] is None),
          f"downtime duration bin {i}")
    for name in ("NSYMC","NSYMP","NSYMT","NSYMS","NSYAL","NSYPM","NSYTP",
                 "NSYWR","NSYWI","NSYLA","NSYUH","NPMT","NDAM","NPMS",
                 "NROBT","NRCFG","STREQ","STF","STLOW","SYDTU","NSYSW",
                 "NPSTA","NPSUC"):
        check(s[name]==0,f"system {name} absent bin {i}")
    check(k["PNB"]==1 and all(v is None or v==0 for name,v in k.items()
                                    if name not in ("STINT","ETINT","PNB")),
          f"no stock movement bin {i}")
check(near(system[-1]["NSYRY"],1),"terminal ready report")
check(near(sum(s["NSYMO"] for s in system)*.5,26),"26 flight hours")
check(near(sum(s["NSYRP"] for s in system)*.5,.5),"half-hour CM occupancy")

result={
    "schema":"simlox-g07-var04-v101-independent-readonly/v1",
    "decision":"GO: bounded 0.75 bridge-block mode source acceptance and observed one-seed outcome"
               if not failures else "NO-GO: independent replay failed",
    "passed":not failures,"checks_passed":checks-len(failures),"checks_total":checks,
    "failures":failures,"raw_seals":len(closure["raw"]),
    "source_sha256":sha(source_file),"closure_sha256":sha(RUN/"closure.json"),
    "model_log_sha256":sha(RUN/"model.log"),"report_sha256":sha(RUN/"report-raw.json"),
    "observed":"POS-A h8.75316 then POS-B h14.1679, both noncritical; mission h8-34 succeeds; two NC half-hour CM and ready1 at horizon",
    "limits":["This seed does not supply a common stochastic draw or a monotonic usage-rate law. Full-rate B/A and excluded half-rate A/B timings differ.",
              "BROPM selection and POS-B USERT0.75 are source/roundtrip-bound; native log does not print item USERT or the active bridge path.",
              "One rate, bridge block, mode, mission, seed and replication; no other rates, online maintenance, GUI drawing or cross-engine claim."],
}
OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+"\n").encode("utf-8"))
print(json.dumps({"passed":result["passed"],"checks_passed":result["checks_passed"],
                  "checks_total":checks,"failures":failures,"output":str(OUT)}))
raise SystemExit(0 if not failures else 1)
