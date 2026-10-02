"""Independent read-only replay of G07.var03's bridge-block-first run."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "g07-var03-brfirst-v100-ssh-20261003-01"
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
parent_file = parent_dir / "allbroken-input.json"
parent_run = parent_dir / "runs" / contract["accepted_parent"]["run_id"]
comparator_file = parent_dir / "ulur-input.json"
comparator_run = parent_dir / "runs" / contract["accepted_comparator"]["run_id"]
source_file = CASE / "brfirst-input.json"
parent = tables(native_json(parent_file), "model")
source = tables(native_json(source_file), "model")
comparator = tables(native_json(comparator_file), "model")
diff = native_json(CASE / "exact-diff.json")
check(sha(parent_file) == contract["accepted_parent"]["input_sha256"], "parent input SHA")
check(sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"],
      "parent closure SHA")
check(sha(comparator_file) == contract["accepted_comparator"]["input_sha256"],
      "successful comparator input SHA")
check(sha(comparator_run / "closure.json") == contract["accepted_comparator"]["native_closure_sha256"],
      "successful comparator closure SHA")
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
      {"ProblemDescription","RBDBridge"}, "exact one-table business delta")
for name in source:
    if name not in ("ProblemDescription","RBDBridge"):
        check(source[name] == parent[name] == comparator[name], f"common {name}")

def bridge_row(t):
    rr = records(t["RBDBridge"])
    check(len(rr) == 1, "single bridge row")
    return rr[0]

slots = ("ULBID","LLBID","BRBID","URBID","LRBID")
br = bridge_row(source)
pr = records(parent["RBDBridge"])[0]
cr = records(comparator["RBDBridge"])[0]
check(tuple(br[s] for s in slots) == ("POS-E","POS-A","POS-B","POS-C","POS-D"),
      "B bridge block first, A lower left")
check(tuple(pr[s] for s in slots) == ("POS-B","POS-A","POS-E","POS-C","POS-D"),
      "accepted all-broken mapping")
check(tuple(cr[s] for s in slots) == ("POS-C","POS-B","POS-A","POS-D","POS-E"),
      "accepted second bridge-block comparator mapping")
check(br["RBID"] == pr["RBID"] == cr["RBID"] == "G07-BRIDGE" and
      all(br[s] == "G04-OPS" for s in ("ULOPM","LLOPM","BROPM","UROPM","LROPM")),
      "same RBD identity and five operational modes")
four_paths = (("ULBID","URBID"),("LLBID","LRBID"),
              ("ULBID","BRBID","LRBID"),("LLBID","BRBID","URBID"))
def live(row, failed):
    return [not any(row[s] in failed for s in path) for path in four_paths]
check(live(br,{"POS-B"}) == [True,True,False,False],
      "bridge block B failure preserves two direct paths")
check(live(br,{"POS-B","POS-A"}) == [True,False,False,False],
      "B/A leaves only upper direct path")
check(live(pr,{"POS-B","POS-A"}) == [False,False,False,False],
      "matched parent B/A breaks all paths")
check(live(cr,{"POS-B","POS-A"}) == [True,False,False,False],
      "comparator B/A leaves upper path")

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
                "comparator":comparator_file,"comparator_closure":comparator_run/"closure.json",
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
check(len(populated) == 22, "22 populated authored tables")
for name in populated:
    check(name in exported, f"exported {name}")
    if name in exported:
        check(source[name]["columns"] == exported[name]["columns"],f"exact {name} columns")
        check(source[name]["instances"] == exported[name]["instances"],f"exact {name} rows")

log = (RUN/"model.log").read_text(encoding="utf-8-sig")
parent_log = (parent_run/"model.log").read_text(encoding="utf-8-sig")
comparator_log = (comparator_run/"model.log").read_text(encoding="utf-8-sig")
def event(hour,fragment):
    return any(line.startswith(f"Time: {hour} ") and fragment in line for line in log.splitlines())
check(event(7,"mission allocates system: <TEACH-AIR-01,0>") and
      event(8,"mission starting, duration: 26"), "mission h8 start")
for hour,mode,critical in ((8.62763,"FM-POS-B",False),(16.7498,"FM-POS-A",False)):
    check(event(hour,("critical" if critical else "noncritical")+" CM failure mode added") and
          f"Failure Mode: {mode} on materiel: <{'POS-B' if mode.endswith('B') else 'POS-A'},0>" in log,
          f"{mode} individual failure at {hour}")
check(log.count("CM failure mode added") == 2 and "Failure Mode: FM-POS-C" not in log and
      "Failure Mode: FM-POS-D" not in log and "Failure Mode: FM-POS-E" not in log,
      "two failures; C/D/E healthy")
check(event(34,"mission success") and event(34,"mission completed") and
      "mission aborted" not in log, "mission succeeds h34")
check("mission aborted" in parent_log and "critical CM failure mode added" in parent_log and
      "mission success" in comparator_log, "accepted failed/successful controls")
check((RUN/"model.log").read_bytes() == (comparator_run/"model.log").read_bytes(),
      "byte-identical event log to accepted unique-path control")
for task,mode in enumerate(("FM-POS-B","FM-POS-A")):
    text = f"system CM task {task} on <TEACH-AIR-01,0>"
    check(event(34,text+" started") and event(34,text+" FMID: "+mode) and
          event(34.5,text+" completed"),f"CM {task} physical identity/time")
    check(f"< {text}, NC, 0.5>" in log,f"CM {task} noncritical")
check(event(34.5,"systems ready: 1") and "Item demand arrives" not in log,
      "terminal ready and no item demand")

report = tables(native_json(RUN/"report-raw.json"),"report")
comp_report = tables(native_json(comparator_run/"report-raw.json"),"report")
check(set(report) == {"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},
      "report table set")
for name in ("ResultSummary","SystemResults","StockTotalResults"):
    check(report[name] == comp_report[name],f"{name} matches accepted success control")
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
    "schema":"simlox-g07-var03-independent-readonly/v1",
    "decision":"GO: bounded first bridge-block failure preserves direct routes" if not failures else
               "NO-GO: independent replay failed",
    "passed":not failures,"checks_passed":checks-len(failures),"checks_total":checks,
    "failures":failures,"raw_seals":len(closure["raw"]),
    "source_sha256":sha(source_file),"closure_sha256":sha(RUN/"closure.json"),
    "model_log_sha256":sha(RUN/"model.log"),"report_sha256":sha(RUN/"report-raw.json"),
    "observed":"B in BR fails h8.62763 NC, A in LL fails h16.7498 NC, mission succeeds h34; two NC half-hour CM and terminal ready1, no stock movement",
    "limits":["The log does not label active bridge paths; the surviving UL+UR path is a source-bound inference from the sealed slots and observed B/A faults.",
              "One seed, mission, mode and failure order; not a full bridge truth table or population estimate.",
              "No bridge online maintenance, nested bridge, GUI drawing or cross-engine claim."],
}
OUT.write_bytes((json.dumps(result,sort_keys=True,indent=2)+"\n").encode("utf-8"))
print(json.dumps({"passed":result["passed"],"checks_passed":result["checks_passed"],
                  "checks_total":checks,"failures":failures,"output":str(OUT)}))
raise SystemExit(0 if not failures else 1)
