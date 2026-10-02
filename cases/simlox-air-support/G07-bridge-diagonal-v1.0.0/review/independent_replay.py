"""Independent, read-only raw replay for the G07.var01 bridge contrast."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
OUT = CASE / "review" / "independent-validation-2026-10-03.json"
RUNS = {arm: CASE / "runs" / f"g07-var01-{arm}-v100-ssh-20261003-01"
        for arm in ("bridge", "routes")}
EXTERNAL = {
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def native_json(path):
    """Read the native JSON dialect, which has trailing commas."""
    data = path.read_text(encoding="utf-8-sig")
    result = []
    quoted = escaped = False
    for i, char in enumerate(data):
        if quoted:
            result.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            result.append(char)
            quoted = True
        elif char == ",":
            nxt = i + 1
            while nxt < len(data) and data[nxt].isspace():
                nxt += 1
            if nxt == len(data) or data[nxt] not in "}]":
                result.append(char)
        else:
            result.append(char)
    return json.loads("".join(result))

def tables(document, root):
    return {table["name"]: table for table in document[root]["tables"]}

def rows(table):
    return [row for inst in table["instances"] for row in inst["rows"]]

def records(table):
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]

def near(actual, expected, tol=0.0006):
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, abs_tol=tol)

def occupancy(start, end, bin_start):
    return max(0, min(end, bin_start + 0.5) - max(start, bin_start)) * 2

checks = 0
failures = []
def check(condition, label):
    global checks
    checks += 1
    if not condition:
        failures.append(label)

contract = native_json(CASE / "contract.json")
parent_file = CASES / contract["accepted_parent"]["package"] / "one-input.json"
parent_closure = parent_file.parent / "runs" / contract["accepted_parent"]["run_id"] / "closure.json"
donor_file = CASES / contract["schema_donor"]["package"] / "and-input.json"
parent = tables(native_json(parent_file), "model")
donor = tables(native_json(donor_file), "model")
diff = native_json(CASE / "exact-diff.json")
check(sha(parent_file) == contract["accepted_parent"]["input_sha256"], "accepted parent SHA")
check(sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"], "accepted parent closure")
check(sha(donor_file) == contract["schema_donor"]["input_sha256"], "schema donor SHA")
check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "frozen exact-diff SHA")
for key in ("exe", "manual", "dictionary"):
    check(sha(EXTERNAL[key]) == contract["source"][f"{key}_sha256"], f"installed {key} SHA")

dictionary = EXTERNAL["dictionary"].read_text(encoding="utf-8-sig")
bridge_fields = [line.split(";")[2] for line in dictionary.splitlines() if line.startswith("RBDBridge;")]
check(bridge_fields == ["RBID", "DESCR", "ULBID", "LLBID", "BRBID", "URBID", "LRBID",
                        "ULOPM", "LLOPM", "BROPM", "UROPM", "LROPM", "NOTE"],
      "installed dictionary 13-field bridge schema")

sources = {}
closures = {}
logs = {}
reports = {}
change_tables = {"ProblemDescription", "MaterielPosition", "MaterielStructure",
                 "MaterielOperationalModes", "RBDParallel", "RBDParallelStructure",
                 "RBDSeries", "RBDSeriesStructure", "RBDBridge"}
for arm, run in RUNS.items():
    source_file = CASE / f"{arm}-input.json"
    source = tables(native_json(source_file), "model")
    sources[arm] = source
    check(sha(source_file) == contract["input_sha256"][arm], f"{arm} frozen source SHA")
    changed = {name: {"before": parent.get(name), "after": source.get(name)}
               for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
    check(changed == diff["arms"][arm]["changed"], f"{arm} exact parent table diff")
    check(set(changed) == change_tables, f"{arm} changed table set")
    for name in ("RBDSeries", "RBDSeriesStructure"):
        check(source[name]["columns"] == donor[name]["columns"], f"{arm} donor {name} schema")
    check(source["FailureMode"] == parent["FailureMode"] and
          source["CMLocation"] == parent["CMLocation"] and
          source["Control"] == parent["Control"], f"{arm} fixed failure/CM/seed")
    mp = records(source["MaterielPosition"])
    check({x["MPID"] for x in mp} >= {"POS-A", "POS-B", "POS-C", "POS-D", "POS-E"},
          f"{arm} five physical positions")
    modes = records(source["MaterielOperationalModes"])
    check(modes[0]["RBID"] == ("G07-BRIDGE" if arm == "bridge" else "G07-SYS-ROOT"),
          f"{arm} root RBD binding")
    check({x["MID"] for x in modes[1:]} == {"POS-A", "POS-B", "POS-C", "POS-D", "POS-E"},
          f"{arm} position modes")

    invocation = native_json(run / "invocation.json")
    closure = native_json(run / "closure.json")
    closures[arm] = closure
    check(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation seal")
    check(invocation["run_id"] == closure["run_id"] == run.name, f"{arm} run identity")
    check(invocation["execution_mode"] == "session0_ssh_cli" and invocation["session_id"] == 0
          and "sshd.exe" in invocation["ssh_ancestor_names"], f"{arm} SSH session0")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1
          and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", f"{arm} GUI/queue")
    check(invocation["prelife_log_option_before"] == closure["prelife_log_option_after"] == "NO",
          f"{arm} registry restoration")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] ==
          closure["source_hashes_after"], f"{arm} source stability")
    paths = {"input": source_file, "parent": parent_file, "parent_closure": parent_closure,
             "schema_donor": donor_file, "contract": CASE / "contract.json",
             "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py",
             "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
             "runner": CASE / "run_native_ssh.ps1", **EXTERNAL}
    for key, path in paths.items():
        check(sha(path) == closure["source_hashes_before"][key], f"{arm} source seal {key}")
    check(len(closure["raw"]) == 13, f"{arm} 13 raw seals")
    for name, metadata in closure["raw"].items():
        path = run / name
        check(path.exists() and path.stat().st_size == metadata["bytes"] and
              sha(path) == metadata["sha256"], f"{arm} raw seal {name}")
    check(sha(run / "input.json") == sha(source_file), f"{arm} native source copy")
    steps = native_json(run / "steps.json")
    check([step["name"] for step in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"], f"{arm} five steps")
    for step in steps:
        check(step["exit_code"] == 0 and step["status"] == "completed" and
              step["gui_preserved"], f"{arm} guarded {step['name']}")
    check([step["arguments"] for step in steps[:4]] ==
          [step["args"] for step in invocation["planned_commands"]], f"{arm} planned CLI arguments")
    check(closure["conversion"]["errors"] == 0 and closure["conversion"]["notes"] == 0 and
          closure["conversion"]["warning_codes"] == ["108"], f"{arm} native diagnostics")
    check(closure["sxo_bytes"] > 4 and closure["report_present"] and
          closure["native_outcome"] == "zero_error_reviewed_warnings", f"{arm} usable outputs")
    check(not re.search(r"\berror\s*#", (run / "run.log").read_text(encoding="utf-8-sig"), re.I),
          f"{arm} no converter error text")
    exported = tables(native_json(run / "roundtrip-raw.json"), "model")
    populated = [name for name, table in source.items() if rows(table)]
    check(len(populated) == (22 if arm == "bridge" else 25), f"{arm} populated table count")
    for name in populated:
        check(name in exported, f"{arm} exported {name}")
        if name in exported:
            check(source[name]["columns"] == exported[name]["columns"], f"{arm} exact columns {name}")
            check(source[name]["instances"] == exported[name]["instances"], f"{arm} exact rows {name}")
    logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig")
    reports[arm] = tables(native_json(run / "report-raw.json"), "report")

bridge = sources["bridge"]
routes = sources["routes"]
check({name for name in bridge if bridge[name] != routes[name]} ==
      {"ProblemDescription", "MaterielOperationalModes", "RBDParallel", "RBDParallelStructure",
       "RBDSeries", "RBDSeriesStructure", "RBDBridge"}, "paired topology-only table contrast")
for name in bridge:
    if name not in {"ProblemDescription", "MaterielOperationalModes", "RBDParallel",
                    "RBDParallelStructure", "RBDSeries", "RBDSeriesStructure", "RBDBridge"}:
        check(bridge[name] == routes[name], f"paired fixed {name}")
bridge_rows = records(bridge["RBDBridge"])
check(len(bridge_rows) == 1 and {key: bridge_rows[0][key] for key in
      ("ULBID", "LLBID", "BRBID", "URBID", "LRBID")} ==
      {"ULBID": "POS-B", "LLBID": "POS-C", "BRBID": "POS-E",
       "URBID": "POS-D", "LRBID": "POS-A"}, "bridge five-block ordering")
check(all(bridge_rows[0][key] == "G04-OPS" for key in
          ("ULOPM", "LLOPM", "BROPM", "UROPM", "LROPM")), "bridge five modes")
check(not rows(bridge["RBDParallel"]) and not rows(bridge["RBDSeries"]),
      "bridge does not add alternative ordinary routes")
check(not rows(routes["RBDBridge"]), "routes arm contains no bridge")
check(records(routes["RBDParallel"])[0]["NBREQ"] == 1 and
      records(routes["RBDParallel"])[0]["NBOP"] == 2, "ordinary 1-of-2 routes")
route_series = {(x["RBID"], x["SRBID"]) for x in records(routes["RBDSeriesStructure"])}
check(route_series == {("G07-SYS-ROOT", "POS-E"), ("G07-SYS-ROOT", "G07-PAR-ROUTES"),
                       ("G07-UP", "POS-B"), ("G07-UP", "POS-D"),
                       ("G07-LOW", "POS-C"), ("G07-LOW", "POS-A")},
      "ordinary route series layout")
check({x["SRBID"] for x in records(routes["RBDParallelStructure"])} ==
      {"G07-UP", "G07-LOW"}, "ordinary upper/lower alternatives")
# With B and A failed, C+E+D remains healthy, matching LL+BR+UR only.
failed = {"POS-A", "POS-B"}
alive = {"POS-A", "POS-B", "POS-C", "POS-D", "POS-E"} - failed
paths = [{"POS-B", "POS-D"}, {"POS-B", "POS-E", "POS-A"},
         {"POS-C", "POS-A"}, {"POS-C", "POS-E", "POS-D"}]
check([path <= alive for path in paths] == [False, False, False, True],
      "four-path bridge source-bound state after B/A failures")
check(not ({"POS-B", "POS-D"} <= alive or {"POS-C", "POS-A"} <= alive),
      "ordinary routes broken after B/A failures")

def event(arm, time, fragment):
    return any(line.startswith(f"Time: {time} ") and fragment in line
               for line in logs[arm].splitlines())

for arm in RUNS:
    log = logs[arm]
    check(event(arm, 7, "mission allocates system: <TEACH-AIR-01,0>") and
          event(arm, 8, "mission starting, duration: 26"), f"{arm} common mission allocation/start")
    check(event(arm, 8.62763, "noncritical CM failure mode added") and
          "Failure Mode: FM-POS-B on materiel: <POS-B,0>" in log, f"{arm} first B failure")
    check(event(arm, 16.7498, "CM failure mode added") and
          "Failure Mode: FM-POS-A on materiel: <POS-A,0>" in log, f"{arm} second A failure")
    check(log.count("CM failure mode added") == 2, f"{arm} exactly two failures")
    check("Failure Mode: FM-POS-C" not in log and "Failure Mode: FM-POS-D" not in log and
          "Failure Mode: FM-POS-E" not in log, f"{arm} healthy C/D/E in event log")
    check("Item demand arrives" not in log and "Take replacement item" not in log,
          f"{arm} no item replacement demand")
    return_time = 34 if arm == "bridge" else 23.2498
    repair_end = 34.5 if arm == "bridge" else 23.7498
    for task, fm in enumerate(("FM-POS-B", "FM-POS-A")):
        text = f"system CM task {task} on <TEACH-AIR-01,0>"
        check(event(arm, return_time, text + " started") and
              event(arm, return_time, text + " FMID: " + fm) and
              event(arm, repair_end, text + " completed"), f"{arm} CM {task} exact identity/time")
        check(f"< {text}, {'NC' if arm == 'bridge' else 'C'}, 0.5>" in log,
              f"{arm} CM {task} criticality")
    check(event(arm, repair_end, "systems ready: 1"), f"{arm} terminal ready event")
check(event("bridge", 16.7498, "noncritical CM failure mode added") and
      event("bridge", 34, "mission success") and event("bridge", 34, "mission completed") and
      "mission aborted" not in logs["bridge"], "bridge A noncritical mission success")
check(event("routes", 16.7498, "critical CM failure mode added") and
      event("routes", 16.7498, "mission aborted") and
      event("routes", 23.2498, "aborted mission completed") and
      "mission success" not in logs["routes"], "routes A critical mission abort")

for arm, report in reports.items():
    check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults",
                          "StockTotalResults"}, f"{arm} report table set")
    summary = records(report["ResultSummary"])[0]
    for key, expected in (("NREP", 1), ("RTILW", 0), ("RTIUP", 36),
                          ("MSTF", 1), ("MSUF", int(arm == "bridge"))):
        check(near(summary[key], expected), f"{arm} summary {key}")
    flight_factor = 1 if arm == "bridge" else 0.5865303874015808
    check(near(summary["MTMF"], flight_factor) and near(summary["STMF"], flight_factor),
          f"{arm} mission/system time factors")
    for key in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF"):
        check(summary[key] == 0, f"{arm} one-rep summary precision {key}")
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    check(len(system) == len(stock) == 72, f"{arm} 72 aligned bins")
    return_time = 34 if arm == "bridge" else 23.2498
    repair_end = 34.5 if arm == "bridge" else 23.7498
    for i, (srow, krow) in enumerate(zip(system, stock)):
        start = i * 0.5
        end = start + 0.5
        check(srow["STINT"] == krow["STINT"] == start and
              srow["ETINT"] == krow["ETINT"] == end, f"{arm} interval {i}")
        reserved = occupancy(7, 8, start)
        flying = occupancy(8, return_time, start)
        repair = occupancy(return_time, repair_end, start)
        expected = {"NSYRY": 1-reserved-flying-repair, "NSYMA": reserved+flying,
                    "NSYMO": flying, "NSYMR": reserved, "NSYRP": repair,
                    "NSYUA": repair, "NSYA": 1-repair, "FTMO": flying,
                    "STACC": flying, "NFAIL": int(start <= 8.62763 < end)+
                    int(start <= 16.7498 < end)}
        for key, value in expected.items():
            check(near(srow[key], value), f"{arm} system {key} bin {i}")
        completion_bin = 69 if arm == "bridge" else 47
        downtime_bin = 68 if arm == "bridge" else 46
        check(srow["NREPT"] == (2 if i == completion_bin else 0),
              f"{arm} repair completion marker bin {i}")
        check(srow["NSYDT"] == (1 if i == downtime_bin else 0),
              f"{arm} system downtime marker bin {i}")
        check((near(srow["SYDT"], 0.5) if i == downtime_bin else srow["SYDT"] is None),
              f"{arm} system downtime duration bin {i}")
        for key in ("NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYAL", "NSYPM", "NSYTP",
                    "NSYWR", "NSYWI", "NSYLA", "NSYUH", "NPMT", "NDAM", "NPMS",
                    "NROBT", "NRCFG", "STREQ", "STF", "STLOW", "SYDTU", "NSYSW",
                    "NPSTA", "NPSUC"):
            check(srow[key] == 0, f"{arm} system {key} absent bin {i}")
        check(krow["PNB"] == 1 and all(value is None or value == 0 for key,value in krow.items()
                                             if key not in ("STINT", "ETINT", "PNB")),
              f"{arm} stock unchanged bin {i}")
    check(near(system[-1]["NSYRY"], 1), f"{arm} terminal report ready")
    check(near(sum(row["NSYMO"] for row in system)*0.5, return_time-8),
          f"{arm} integrated operating hours")
    check(near(sum(row["NSYRP"] for row in system)*0.5, 0.5),
          f"{arm} integrated repair occupancy")

result = {
    "schema": "simlox-g07-var01-independent-readonly/v1",
    "decision": "GO: bounded source-bound bridge diagonal salvage versus ordinary routes",
    "passed": not failures,
    "checks_passed": checks-len(failures),
    "checks_total": checks,
    "failures": failures,
    "raw_seals": sum(len(closure["raw"]) for closure in closures.values()),
    "runs": {arm: {"source_sha256": sha(CASE / f"{arm}-input.json"),
                   "closure_sha256": sha(run / "closure.json"),
                   "model_log_sha256": sha(run / "model.log"),
                   "report_sha256": sha(run / "report-raw.json")}
             for arm, run in RUNS.items()},
    "observed": {"matched_faults": "B h8.62763 then A h16.7498 in both arms",
                 "bridge": "A noncritical, mission success h34, two NC CM h34-34.5",
                 "routes": "A critical, abort h16.7498, return h23.2498, two C CM h23.2498-23.7498",
                 "terminal": "ready1 in both; no stock movement"},
    "limits": ["The event log does not identify the active bridge path. LL+BR+UR is inferred from the frozen five-block source, observed failed B/A and healthy C/D/E, and the mission outcome.",
               "One seed, one bridge combination, one mode and one replication. No full four-path truth table or population reliability estimate.",
               "No online repair, GUI RBD drawing or cross-engine claim."],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2) + "\n").encode("utf-8"))
print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                  "checks_total": checks, "failures": failures, "output": str(OUT)}))
raise SystemExit(0 if not failures else 1)
