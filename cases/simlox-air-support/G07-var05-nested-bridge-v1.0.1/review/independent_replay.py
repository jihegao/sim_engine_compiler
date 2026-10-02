"""Independent read-only replay of G07.var05's nested bridge block."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "g07-var05-nested-v101-ssh-20261003-01"
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
    string = escaped = False
    for i,c in enumerate(data):
        if string:
            out.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                string = False
        elif c == '"':
            out.append(c)
            string = True
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
    return {t["name"]: t for t in doc[root]["tables"]}

def rows(table):
    return [r for inst in table["instances"] for r in inst["rows"]]

def records(table):
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns,r)) for r in rows(table)]

def near(actual, expected, tol=.0006):
    return isinstance(actual,(float,int)) and math.isclose(actual, expected, abs_tol=tol)

def occupancy(a,b,start):
    return 2*max(0,min(b,start+.5)-max(a,start))

checks = 0
failures = []
def check(ok,label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)

contract = native_json(CASE / "contract.json")
parent_dir = CASES / contract["accepted_parent"]["package"]
parent_file = parent_dir / "brfirst-input.json"
parent_run = parent_dir / "runs" / contract["accepted_parent"]["run_id"]
diagnostic_dir = CASES / contract["diagnostic_predecessor"]["package"]
diagnostic_file = diagnostic_dir / "nested-input.json"
diagnostic_run = diagnostic_dir / "runs" / contract["diagnostic_predecessor"]["run_id"]
source_file = CASE / "nested-input.json"
parent = tables(native_json(parent_file), "model")
source = tables(native_json(source_file), "model")
diagnostic = tables(native_json(diagnostic_file), "model")
diff = native_json(CASE / "exact-diff.json")
check(sha(parent_file) == contract["accepted_parent"]["input_sha256"], "parent input SHA")
check(sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"],
      "parent closure SHA")
check(sha(diagnostic_file) == contract["diagnostic_predecessor"]["input_sha256"],
      "excluded diagnostic input SHA")
check(sha(diagnostic_run / "closure.json") == contract["diagnostic_predecessor"]["native_closure_sha256"],
      "excluded diagnostic closure SHA")
check(sha(source_file) == contract["input_sha256"], "child source SHA")
check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen exact diff SHA")
for key in ("manual","dictionary","exe"):
    check(sha(EXTERNAL[key]) == contract["source"][f"{key}_sha256"],
          f"installed {key} SHA")
dictionary = EXTERNAL["dictionary"].read_text(encoding="utf-8-sig")
fields = [line.split(";")[2] for line in dictionary.splitlines() if line.startswith("RBDBridge;")]
check(fields == ["RBID","DESCR","ULBID","LLBID","BRBID","URBID","LRBID",
                 "ULOPM","LLOPM","BROPM","UROPM","LROPM","NOTE"],
      "installed bridge 13-field schema")
actual_delta = {name:{"before":parent.get(name),"after":source.get(name)}
                for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
check(actual_delta == diff["changed"] and set(actual_delta) ==
      {"ProblemDescription","MaterielPosition","MaterielStructure","MaterielOperationalModes",
       "RBDSeries","RBDSeriesStructure","RBDBridge"}, "exact seven-table delta")
for name in source:
    if name not in actual_delta:
        check(source[name] == parent[name], f"common {name}")

def bridge_row(t):
    rr = records(t["RBDBridge"])
    check(len(rr) == 1, "single bridge row")
    return rr[0]

slots = ("ULBID","LLBID","BRBID","URBID","LRBID")
br = bridge_row(source)
pr = records(parent["RBDBridge"])[0]
check(tuple(br[s] for s in slots) ==
      ("POS-E","POS-A","G07-BR-SERIES","POS-C","POS-D"),
      "nested series replaces only bridge slot")
check(tuple(pr[s] for s in slots) ==
      ("POS-E","POS-A","POS-B","POS-C","POS-D"), "accepted direct B bridge slot")
check(br["RBID"] == pr["RBID"] == "G07-BRIDGE" and br["BROPM"] is None and
      all(br[s] == "G04-OPS" for s in ("ULOPM","LLOPM","UROPM","LROPM")),
      "nested RBD omits BROPM; other modes preserved")
check(records(diagnostic["RBDBridge"])[0]["BROPM"] == "G04-OPS" and
      records(diagnostic["RBDBridge"])[0]["BRBID"] == "G07-BR-SERIES",
      "excluded diagnostic supplied invalid nested BROPM")
diagnostic_log = (diagnostic_run / "run.log").read_text(encoding="utf-8-sig")
check("(error #462)" in diagnostic_log and (diagnostic_run / "model.sxo").stat().st_size == 4 and
      not (diagnostic_run / "report-raw.json").exists(),
      "excluded v1.0.0 #462 invalid-output diagnostic")
check({r["MPID"] for r in records(source["MaterielPosition"])} ==
      {"POS-A","POS-B","POS-C","POS-D","POS-E","POS-F"}, "six physical positions")
check(("POS-F","TEACH-AIR-01") in
      {(r["MID"],r["MMID"]) for r in records(source["MaterielStructure"])} and
      ("TEACH-LRU-01","POS-F") in
      {(r["MID"],r["MMID"]) for r in records(source["MaterielStructure"])},
      "new F position has identical installed LRU")
check(any(r["MID"]=="POS-F" and r["OPMID"]=="G04-OPS" for r in
          records(source["MaterielOperationalModes"])), "F operating mode")
check(len(records(source["RBDSeries"])) == 1 and
      records(source["RBDSeries"])[0]["RBID"] == "G07-BR-SERIES", "one nested series block")
check({(r["RBID"],r["SRBID"],r["OPMID"],r["QTYPB"])
       for r in records(source["RBDSeriesStructure"])} ==
      {("G07-BR-SERIES","POS-B","G04-OPS",1),
       ("G07-BR-SERIES","POS-F","G04-OPS",1)}, "nested B+F requires both blocks")
check(source["FailureMode"] == parent["FailureMode"] and
      {r["MID"] for r in records(source["FailureMode"])} == {"POS-A","POS-B"},
      "only A/B retain failure modes; F healthy in model")
four_paths = (("ULBID","URBID"),("LLBID","LRBID"),
              ("ULBID","BRBID","LRBID"),("LLBID","BRBID","URBID"))
def live(row, failed):
    def good(slot):
        name=row[slot]
        return ("POS-B" not in failed and "POS-F" not in failed) if name=="G07-BR-SERIES" else name not in failed
    return [all(good(slot) for slot in path) for path in four_paths]
check(live(br,{"POS-B"}) == [True,True,False,False],
      "B failure disables nested bridge; direct routes survive")
check(live(br,{"POS-B","POS-A"}) == [True,False,False,False],
      "B/A leaves source-bound UL+UR")
check(live(pr,{"POS-B","POS-A"}) == [True,False,False,False],
      "parent B/A source path matches")

inv = native_json(RUN / "invocation.json")
closure = native_json(RUN / "closure.json")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
check(inv["run_id"] == closure["run_id"] == RUN.name, "run identity")
check(inv["execution_mode"] == "session0_ssh_cli" and inv["session_id"] == 0 and
      "sshd.exe" in inv["ssh_ancestor_names"], "session0 SSH")
check(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and
      inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "GUI and native mutex")
check(inv["prelife_log_option_before"] == closure["prelife_log_option_after"] == "NO",
      "registry restored")
check(inv["source_hashes_before"] == closure["source_hashes_before"] ==
      closure["source_hashes_after"], "frozen before/after source")
source_paths = {"input":source_file,"parent":parent_file,"parent_closure":parent_run/"closure.json",
                 "diagnostic":diagnostic_file,"diagnostic_closure":diagnostic_run/"closure.json",
                "contract":CASE/"contract.json","exact_diff":CASE/"exact-diff.json",
                "builder":CASE/"build.py","diff_builder":CASE/"describe_diff.py",
                "checker":CASE/"check_roundtrip.py","runner":CASE/"run_native_ssh.ps1",**EXTERNAL}
for name,path in source_paths.items():
    check(sha(path) == closure["source_hashes_before"][name], f"source seal {name}")
check(len(closure["raw"]) == 13, "13 raw seals")
for name,meta in closure["raw"].items():
    path = RUN/name
    check(path.exists() and path.stat().st_size == meta["bytes"] and
          sha(path) == meta["sha256"], f"raw seal {name}")
check(sha(RUN/"input.json") == sha(source_file), "native input copy")
steps = native_json(RUN/"steps.json")
check([s["name"] for s in steps] ==
      ["import","export","calc","jsonreport","check_import_export"], "five steps")
for step in steps:
    check(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"],
          f"guarded {step['name']}")
check([s["arguments"] for s in steps[:4]] ==
      [s["args"] for s in inv["planned_commands"]], "actual versus planned CLI")
check(closure["conversion"]["errors"] == 0 and closure["conversion"]["notes"] == 0 and
      closure["conversion"]["warning_codes"] == ["108"], "zero errors, reviewed warning")
check(closure["sxo_bytes"] > 4 and closure["report_present"] and
      closure["native_outcome"] == "zero_error_reviewed_warnings", "usable native results")
check(not re.search(r"\berror\s*#",(RUN/"run.log").read_text(encoding="utf-8-sig"),re.I),
      "no converter error in raw log")
exported = tables(native_json(RUN/"roundtrip-raw.json"),"model")
populated = [name for name,t in source.items() if rows(t)]
check(len(populated) == 24, "24 populated authored tables")
for name in populated:
    check(name in exported, f"exported {name}")
    if name in exported:
        check(source[name]["columns"] == exported[name]["columns"],f"exact {name} columns")
        check(source[name]["instances"] == exported[name]["instances"],f"exact {name} rows")

log = (RUN/"model.log").read_text(encoding="utf-8-sig")
parent_log = (parent_run/"model.log").read_text(encoding="utf-8-sig")
def event(hour,fragment):
    return any(line.startswith(f"Time: {hour} ") and fragment in line for line in log.splitlines())
check(event(7,"mission allocates system: <TEACH-AIR-01,0>") and
      event(8,"mission starting, duration: 26"), "mission h8 start")
for hour,mode,critical in ((8.62763,"FM-POS-B",False),(16.7498,"FM-POS-A",False)):
    check(event(hour,("critical" if critical else "noncritical")+" CM failure mode added") and
          f"Failure Mode: {mode} on materiel: <{'POS-B' if mode.endswith('B') else 'POS-A'},0>" in log,
          f"{mode} individual failure at {hour}")
check(log.count("CM failure mode added") == 2 and
      all(f"Failure Mode: FM-POS-{p}" not in log for p in "CDEF"),
      "two failures; C/D/E/F healthy in event log")
check(event(34,"mission success") and event(34,"mission completed") and
      "mission aborted" not in log, "mission succeeds h34")
check("mission success" in parent_log and
      (RUN/"model.log").read_bytes() == (parent_run/"model.log").read_bytes(),
      "byte-identical event log to accepted parent")
for task,mode in enumerate(("FM-POS-B","FM-POS-A")):
    text = f"system CM task {task} on <TEACH-AIR-01,0>"
    check(event(34,text+" started") and event(34,text+" FMID: "+mode) and
          event(34.5,text+" completed"),f"CM {task} physical identity/time")
    check(f"< {text}, NC, 0.5>" in log,f"CM {task} noncritical")
check(event(34.5,"systems ready: 1") and "Item demand arrives" not in log,
      "terminal ready and no item demand")

report = tables(native_json(RUN/"report-raw.json"),"report")
parent_report = tables(native_json(parent_run/"report-raw.json"),"report")
check(set(report) == {"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},
      "report table set")
for name in ("ResultSummary","SystemResults","StockTotalResults"):
    check(report[name] == parent_report[name],f"{name} matches accepted parent")
summary = records(report["ResultSummary"])[0]
for name,want in (("NREP",1),("RTILW",0),("RTIUP",36),("MTMF",1),("MSTF",1),
                  ("MSUF",1),("STMF",1)):
    check(near(summary[name],want),f"summary {name}")
for name in ("RSMTMF","RSMSTF","RSMSUF","RSSTMF"):
    check(summary[name] == 0,f"one-rep precision {name}")
system = records(report["SystemResults"])
stock = records(report["StockTotalResults"])
check(len(system) == len(stock) == 72,"72 aligned System/Stock bins")
for i,(s,k) in enumerate(zip(system,stock)):
    start = i*.5
    end = start+.5
    check(s["STINT"] == k["STINT"] == start and s["ETINT"] == k["ETINT"] == end,
          f"aligned interval {i}")
    reserved = occupancy(7,8,start)
    flight = occupancy(8,34,start)
    repair = occupancy(34,34.5,start)
    expected = {"NSYRY":1-reserved-flight-repair,"NSYMA":reserved+flight,
                "NSYMO":flight,"NSYMR":reserved,"NSYRP":repair,"NSYUA":repair,
                "NSYA":1-repair,"FTMO":flight,"STACC":flight,
                "NFAIL":int(start<=8.62763<end)+int(start<=16.7498<end)}
    for name,want in expected.items():
        check(near(s[name],want),f"system {name} bin {i}")
    check(s["NREPT"] == (2 if i == 69 else 0) and
          s["NSYDT"] == (1 if i == 68 else 0),f"repair/downtime markers bin {i}")
    check((near(s["SYDT"],.5) if i==68 else s["SYDT"] is None),
          f"downtime duration bin {i}")
    for name in ("NSYMC","NSYMP","NSYMT","NSYMS","NSYAL","NSYPM","NSYTP",
                 "NSYWR","NSYWI","NSYLA","NSYUH","NPMT","NDAM","NPMS",
                 "NROBT","NRCFG","STREQ","STF","STLOW","SYDTU","NSYSW",
                 "NPSTA","NPSUC"):
        check(s[name] == 0,f"system {name} absent bin {i}")
    check(k["PNB"] == 1 and all(v is None or v == 0 for name,v in k.items()
                                     if name not in ("STINT","ETINT","PNB")),
          f"stock unchanged bin {i}")
check(near(system[-1]["NSYRY"],1),"terminal ready report")
check(near(sum(x["NSYMO"] for x in system)*.5,26),"26 flight hours")
check(near(sum(x["NSYRP"] for x in system)*.5,.5),"half-hour system CM occupancy")

result = {
    "schema":"simlox-g07-var05-v101-independent-readonly/v1",
    "decision":"GO: bounded nested B+F bridge-series source acceptance and matched behavior" if not failures else
               "NO-GO: independent replay failed",
    "passed":not failures,"checks_passed":checks-len(failures),"checks_total":checks,
    "failures":failures,"raw_seals":len(closure["raw"]),
    "source_sha256":sha(source_file),"closure_sha256":sha(RUN/"closure.json"),
    "model_log_sha256":sha(RUN/"model.log"),"report_sha256":sha(RUN/"report-raw.json"),
    "observed":"B h8.62763 NC, A h16.7498 NC, mission succeeds h34; event log byte-identical to parent, two NC half-hour CM, ready1 and no stock movement",
    "limits":["The event log does not label nested RBD state or active bridge path. B+F series disablement after B failure and surviving UL+UR are source-bound inferences.",
              "F is a healthy added position without a failure mode; no F failure or alternate nested type was tested.",
              "One seed/mission/mode/replication; no GUI drawing, online maintenance, population reliability or cross-engine claim."],
}
OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+"\n").encode("utf-8"))
print(json.dumps({"passed":result["passed"],"checks_passed":result["checks_passed"],
                  "checks_total":checks,"failures":failures,"output":str(OUT)}))
raise SystemExit(0 if not failures else 1)
