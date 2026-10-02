"""Independent, read-only replay of the sealed G12.var03 native run.

Uses only Python's standard library and raw source/run evidence. It never calls
SIMLOX or any authored builder, checker, runner, or validator.
"""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
RUN = CASE / "runs" / "g12-var03-leaf-cm-pm-v100-ssh-20261003-01"
OUT = CASE / "review" / "independent-validation-2026-10-03.json"
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path):
    """Remove native trailing commas only outside JSON strings."""
    data = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = False
    escaped = False
    for i, char in enumerate(data):
        if quoted:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
            out.append(char)
        elif char == ",":
            j = i + 1
            while j < len(data) and data[j].isspace():
                j += 1
            if j >= len(data) or data[j] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


checks = 0
failures = []


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def close(actual, expected, tolerance=0.0001):
    return isinstance(actual, (float, int)) and math.isclose(actual, expected, abs_tol=tolerance)


def tables(document, root):
    return {t["name"]: t for t in document[root]["tables"]}


def rows(table):
    return [r for instance in table["instances"] for r in instance["rows"]]


def field(table, column, row=0):
    return rows(table)[row][next(i for i, c in enumerate(table["columns"]) if c["name"] == column)]


contract = native_json(CASE / "contract.json")
diff = native_json(CASE / "exact-diff.json")
source_path = CASE / "native-input.json"
source = tables(native_json(source_path), "model")
parent_dir = CASES / contract["accepted_parent"]["package"]
parent_path = parent_dir / "native-input.json"
parent = tables(native_json(parent_path), "model")
parent_closure = parent_dir / "runs" / "g12-var01-two-subsystems-v100-ssh-20261003-02" / "closure.json"
support_closure = CASES / contract["supporting_frequency_control"]["package"] / "runs" / contract["supporting_frequency_control"]["run_id"] / "closure.json"
check(sha(source_path) == contract["input"]["sha256"], "frozen input hash")
check(sha(parent_path) == contract["accepted_parent"]["input_sha256"], "accepted parent input hash")
check(sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"], "accepted parent closure hash")
check(sha(support_closure) == contract["supporting_frequency_control"]["native_closure_sha256"], "support closure hash")
check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen exact diff hash")
for label, path in (("exe", EXE), ("manual", MANUAL), ("dictionary", DICTIONARY)):
    check(sha(path) == contract["source"][f"{label}_sha256"], f"installed {label} hash")
actual_changed = {}
for name in sorted(parent.keys() | source.keys()):
    old, new = parent.get(name), source.get(name)
    if old != new:
        actual_changed[name] = {"before": old, "after": new}
check(actual_changed == diff["changed"], "exact parent/child table delta")
check(set(actual_changed) == {"Control", "ProblemDescription", "System", "SystemRepair"}, "four changed source tables")
check(field(source["Control"], "RSEED") == "2" and field(source["Control"], "NREPS") == 1, "seed and one replication")
check(field(source["System"], "FRT", 0) is None and field(source["System"], "FRT", 1) == 0 and field(source["System"], "FRT", 2) == 500000, "top/A/B failure rates")
check(field(source["SystemRepair"], "SID") == "TEACH-SUB-B" and field(source["SystemRepair"], "DIRPT") == 0.5 and field(source["SystemRepair"], "STID") == "BASE-01", "leaf-B direct repair source")
check(field(source["MaterielPM"], "MID") == "TEACH-SUB-A" and field(source["MaterielPM"], "PMID") == "CAL24" and field(source["MaterielPM"], "PMINT") == 24, "leaf-A calendar PM source")
check(field(source["PMLocation"], "ID") == "TEACH-SUB-A" and field(source["PMLocation"], "PMT") == 1 and field(source["PMLocation"], "STID") == "BASE-01", "leaf-A PM station and duration")
check({(field(source["SystemStructure"], "SID", i), field(source["SystemStructure"], "MSID", i)) for i in range(2)} == {("TEACH-SUB-A","TEACH-AIR-01"),("TEACH-SUB-B","TEACH-AIR-01")}, "both children linked to deployed top")

inv = native_json(RUN / "invocation.json")
closure = native_json(RUN / "closure.json")
check(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
check(inv["run_id"] == closure["run_id"] == RUN.name, "run identity")
check(inv["execution_mode"] == "session0_ssh_cli" and inv["session_id"] == 0, "SSH session zero")
check("sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "SSH ancestor and queue mutex")
check(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "guarded GUI identity")
check(inv["prelife_log_option_before"] == closure["prelife_log_option_after"] == "NO", "registry option restored")
check(closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"], "source stability")
source_paths = {
    "input": source_path, "parent": parent_path, "parent_closure": parent_closure,
    "support_closure": support_closure, "contract": CASE / "contract.json",
    "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py",
    "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
    "runner": CASE / "run_native_ssh.ps1", "python": PYTHON,
    "exe": EXE, "manual": MANUAL, "dictionary": DICTIONARY,
}
for label, path in source_paths.items():
    check(sha(path) == closure["source_hashes_before"][label], f"sealed source {label}")
for label, meta in closure["raw"].items():
    path = RUN / label
    check(path.exists() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"sealed raw {label}")
check(len(closure["raw"]) == 13, "13 native raw seals")
check(sha(RUN / "input.json") == sha(source_path), "run input is frozen source")
steps = native_json(RUN / "steps.json")
check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five native steps")
for step in steps:
    check(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] is True, f"completed guarded {step['name']}")
check([s["arguments"] for s in steps[:4]] == [s["args"] for s in inv["planned_commands"]], "invoked exact planned CLI")
check(closure["native_outcome"] == "zero_error_reviewed_warnings" and closure["sxo_bytes"] > 4 and closure["report_present"] is True, "native output usable")
check((RUN / "model.sxo").stat().st_size > 4 and (RUN / "model.log").stat().st_size > 0, "nonempty simulation output")
import_log = (RUN / "import.log").read_text(encoding="utf-8-sig")
run_log = (RUN / "run.log").read_text(encoding="utf-8-sig")
check(not re.search(r"\berror\s*#", import_log + run_log, re.I), "no converter/runtime numbered error")
check(closure["conversion"]["errors"] == 0 and closure["conversion"]["notes"] == 0 and closure["conversion"]["warning_codes"] == ["108", "2053", "2053"], "classified converter diagnostics")
check(closure["conversion"]["calc_exit_code"] == 0, "calculation exit zero")

exported = tables(native_json(RUN / "roundtrip-raw.json"), "model")
populated = [name for name, table in source.items() if rows(table)]
check(len(populated) == 22, "22 authored row-containing tables")
for name in populated:
    check(name in exported, f"export contains {name}")
    if name in exported:
        check(exported[name]["columns"] == source[name]["columns"], f"authored columns {name}")
        check(exported[name]["instances"] == source[name]["instances"], f"authored instances and rows {name}")

log = (RUN / "model.log").read_text(encoding="utf-8-sig")
def has(t, fragment):
    return f"Time: {t} " in log and any(line.startswith(f"Time: {t} ") and fragment in line for line in log.splitlines())

fail_times = [8.49322, 8.58686, 20.5929]
for t in fail_times:
    check(has(t, "critical random failure added"), f"child connection-path failure time {t}")
check(log.count("connection path: TEACH-AIR-01 - TEACH-AIR-01 - TEACH-SUB-B") >= 3, "native B connection path shown")
check("connection path: TEACH-AIR-01 - TEACH-AIR-01 - TEACH-SUB-A" not in log, "no A failure logged")
for t, mission in ((8,0),(20,1),(32,2)):
    check(has(t, f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission}> mission starting"), f"mission {mission} launch")
for t, mission in ((8.49322,0),(20.5929,1)):
    check(has(t, f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission}> mission aborted"), f"mission {mission} abort")
check(has(34, "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission success"), "third mission success")
check(has(8.98644, "<BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed") and has(21.0929, "<BASIC-MISSION,TEACH-UNIT,0,0,1> aborted mission completed"), "failed mission returns")
for task, start, end in ((0,8.98644,9.48644),(1,8.98644,9.48644),(2,21.0929,21.5929)):
    phrase = f"system DIRP task {task} on <TEACH-AIR-01,0>"
    check(has(start, f"{phrase} started") and has(end, f"{phrase} completed"), f"direct repair task {task} interval")
    check(has(start, f"within {phrase} starts performing, planned to last for 0.5 hours"), f"direct repair task {task} positive half-hour work")
for task, start, end in ((3,24,25),(4,49,50)):
    phrase = f"system PM task {task} on <TEACH-AIR-01,0>"
    check(has(start, f"{phrase} started") and has(start, f"{phrase} PMID: CAL24") and has(end, f"{phrase} completed"), f"leaf-A CAL24 PM {task}")
    check(has(start, f"within {phrase} starts performing, planned to last for 1 hours"), f"PM {task} positive one-hour work")
check(has(50, "systems ready: 1") and "Stock initiated" in log and "Level: 0 Items:" in log, "terminal ready and empty leaf stock")
check("books resources" not in log and "issues item" not in log and "BackOrder" not in log, "no resource or stock demand logged")
first_abort = log.index("Time: 8.49322 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted")
first_return = log.index("Time: 8.98644 <BASIC-MISSION,TEACH-UNIT,0,0,0> aborted mission completed")
first_repair = log.index("Time: 8.98644  system DIRP task 0")
first_repair_end = log.index("Time: 9.48644  system DIRP task 0")
second_abort = log.index("Time: 20.5929 <BASIC-MISSION,TEACH-UNIT,0,0,1> mission aborted")
second_return = log.index("Time: 21.0929 <BASIC-MISSION,TEACH-UNIT,0,0,1> aborted mission completed")
second_repair = log.index("Time: 21.0929  system DIRP task 2")
check(first_abort < first_return < first_repair < first_repair_end < second_abort < second_return < second_repair, "individual abort/return/CM chronology")

report = tables(native_json(RUN / "report-raw.json"), "report")
check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "selected report tables")
summary = report["ResultSummary"]
for name, expected in (("NREP",1),("RTILW",0),("RTIUP",60),("MSTF",1),("MSUF",1/3)):
    check(close(field(summary,name),expected,0.0001), f"summary {name}")
check(close(field(summary,"MTMF"),field(summary,"STMF")), "mission/system mean-time metric agreement")
check(close(field(summary,"MTMF"),0.6798944473266602) and all(close(field(summary,n),0) for n in ("RSMTMF","RSMSTF","RSMSUF","RSSTMF")), "summary fixed one-rep factors")
system, stock = report["SystemResults"], report["StockTotalResults"]
sr, kr = rows(system), rows(stock)
check(len(sr) == len(kr) == 120, "120 system and stock half-hour bins")

def overlap(a,b,c,d):
    return max(0.0,min(b,d)-max(a,c)) / (d-c)

reserved = [(7,8),(19,20),(31,32)]
operating = [(8,8.98644),(20,21.0929),(32,34)]
repair = [(8.98644,9.48644),(21.0929,21.5929)]
pm = [(24,25),(49,50)]
for index, (srow,krow) in enumerate(zip(sr,kr)):
    s, e = index / 2, (index+1)/2
    sf = {c["name"]: srow[i] for i,c in enumerate(system["columns"])}
    kf = {c["name"]: krow[i] for i,c in enumerate(stock["columns"])}
    check(close(sf["STINT"],s) and close(sf["ETINT"],e), f"system interval {index}")
    check(close(kf["STINT"],s) and close(kf["ETINT"],e), f"stock interval {index}")
    want_reserved = sum(overlap(a,b,s,e) for a,b in reserved)
    want_operating = sum(overlap(a,b,s,e) for a,b in operating)
    want_repair = sum(overlap(a,b,s,e) for a,b in repair)
    want_pm = sum(overlap(a,b,s,e) for a,b in pm)
    want_ready = 1-want_reserved-want_operating-want_repair-want_pm
    for name,want in (("NSYMR",want_reserved),("NSYMO",want_operating),("NSYMA",want_reserved+want_operating),("FTMO",want_operating),("STACC",want_operating),("NSYRP",want_repair),("NSYPM",want_pm),("NSYRY",want_ready),("NSYA",want_ready+want_reserved+want_operating),("NSYUA",want_repair+want_pm)):
        check(close(sf[name],want), f"system {name} bin {index}: {sf[name]} vs {want}")
    for name, times in (("NFAIL",fail_times),("NREPT",[9.48644,9.48644,21.5929]),("NPMS",[24,49]),("NPMT",[25,50])):
        want = sum(s <= t < e for t in times)
        check(sf[name] == want, f"system {name} events bin {index}")
    down_start = (s in (8.5,21,24,49))
    check(sf["NSYDT"] == int(down_start), f"system downtime start count bin {index}")
    check((sf["SYDT"] is None) if not down_start else close(sf["SYDT"], 1 if s in (24,49) else 0.5), f"system downtime event duration bin {index}")
    for name in ("NSYMC","NSYMS","NSYMT","NSYAL","NSYTP","NSYWR","NSYWI","NSYLA","NSYUH","NDAM","NROBT","NRCFG","STREQ","STF","STLOW","SYDTU","NSYSW","NPSTA","NPSUC"):
        check(sf[name] == 0, f"system {name} zero bin {index}")
    check(kf["PNB"] == 1 and all((v is None or v == 0) for key,v in kf.items() if key not in ("STINT","ETINT","PNB")), f"stock zero movement bin {index}")
check(close(sum(row[next(i for i,c in enumerate(system["columns"]) if c["name"]=="NSYMO")] for row in sr)*0.5, sum(b-a for a,b in operating),0.00005), "integrated actual mission operating hours")
check(close(sum(row[next(i for i,c in enumerate(system["columns"]) if c["name"]=="NSYRP")] for row in sr)*0.5,1.0,0.00005), "integrated system repair occupancy 1 hour (two parallel tasks first wave)")
check(close(sum(row[next(i for i,c in enumerate(system["columns"]) if c["name"]=="NSYPM")] for row in sr)*0.5,2.0,0.00005), "integrated PM occupancy 2 hours")
check(close(field(system,"NSYRY",119),1), "terminal ready system")

result = {
    "schema":"simlox-g12-var03-independent-readonly/v1",
    "decision":"GO: bounded one-seed child-B connection-path failure, composite mission impact, leaf repair and leaf-A PM",
    "passed":not failures,
    "checks_passed":checks-len(failures),
    "checks_total":checks,
    "failures":failures,
    "raw_seals":len(closure["raw"]),
    "source_sha256":sha(source_path),
    "closure_sha256":sha(RUN/"closure.json"),
    "model_log_sha256":sha(RUN/"model.log"),
    "report_sha256":sha(RUN/"report-raw.json"),
    "observed":{
        "failure_times":fail_times,
        "direct_repair_tasks":[[0,8.98644,9.48644],[1,8.98644,9.48644],[2,21.0929,21.5929]],
        "pm_intervals":[[24,25],[49,50]],
        "mission_outcomes":["abort 8.49322/return 8.98644","abort 20.5929/return 21.0929","success/return 34"],
        "terminal_ready":1,
    },
    "limits":[
        "One seed, one replication and one two-child composite; no rate or population inference.",
        "The log names the child-B connection path but direct repair task targets the deployed TEACH-AIR-01; it does not identify a separate physical child instance or sibling-stop timeline.",
        "First-wave two half-hour direct repair tasks overlap, so report system repair occupancy is one half-hour in that wave, not the sum of both task-hours.",
        "No resources or stock items are exercised; other child types, wrong-level repair and GUI-only behavior are untested.",
    ],
}
OUT.write_bytes((json.dumps(result,indent=2,sort_keys=True)+"\n").encode("utf-8"))
print(json.dumps({"passed":result["passed"],"checks_passed":result["checks_passed"],"checks_total":checks,"failures":failures,"output":str(OUT)}))
raise SystemExit(0 if not failures else 1)
