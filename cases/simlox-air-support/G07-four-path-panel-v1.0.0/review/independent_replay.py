"""Standalone read-only raw replay of G07's four new bridge-slot assignments."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
CASES = CASE.parent
OUT = CASE / "review" / "independent-validation-2026-10-03.json"
ARMS = ("ulur", "lllr", "ulbrlr", "allbroken")
RUNS = {a: CASE / "runs" / f"g07-panel-{a}-v100-ssh-20261003-01" for a in ARMS}
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
    for i, c in enumerate(data):
        if quoted:
            output.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            output.append(c)
            quoted = True
        elif c == ",":
            nxt = i + 1
            while nxt < len(data) and data[nxt].isspace():
                nxt += 1
            if nxt == len(data) or data[nxt] not in "}]":
                output.append(c)
        else:
            output.append(c)
    return json.loads("".join(output))

def tables(doc, root):
    return {table["name"]: table for table in doc[root]["tables"]}

def rows(table):
    return [r for inst in table["instances"] for r in inst["rows"]]

def records(table):
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]

def near(a, b, tol=0.0006):
    return isinstance(a, (float, int)) and math.isclose(a, b, abs_tol=tol)

def occupancy(a, b, start):
    return 2 * max(0, min(b, start + .5) - max(a, start))

checks = 0
failures = []
def check(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)

contract = native_json(CASE / "contract.json")
parent = CASES / contract["accepted_parent"]["package"]
parent_file = parent / "bridge-input.json"
parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
parent_source = tables(native_json(parent_file), "model")
parent_log = (parent_run / "model.log").read_bytes()
parent_report = tables(native_json(parent_run / "report-raw.json"), "report")
diff = native_json(CASE / "exact-diff.json")
check(sha(parent_file) == contract["accepted_parent"]["input_sha256"], "accepted parent input SHA")
check(sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"],
      "accepted parent closure SHA")
check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff SHA")
for key in ("manual", "dictionary", "exe"):
    check(sha(EXTERNAL[key]) == contract["source"][f"{key}_sha256"], f"installed {key} SHA")
dictionary = EXTERNAL["dictionary"].read_text(encoding="utf-8-sig")
fields = [line.split(";")[2] for line in dictionary.splitlines() if line.startswith("RBDBridge;")]
check(fields == ["RBID", "DESCR", "ULBID", "LLBID", "BRBID", "URBID", "LRBID",
                 "ULOPM", "LLOPM", "BROPM", "UROPM", "LROPM", "NOTE"],
      "installed 13-field bridge dictionary schema")

paths = ["UL+UR", "LL+LR", "UL+BR+LR", "LL+BR+UR"]
path_slots = [{"ULBID", "URBID"}, {"LLBID", "LRBID"},
              {"ULBID", "BRBID", "LRBID"}, {"LLBID", "BRBID", "URBID"}]
expected_live = {"ulur": [True, False, False, False],
                 "lllr": [False, True, False, False],
                 "ulbrlr": [False, False, True, False],
                 "allbroken": [False, False, False, False]}
expected_slots = {
    "ulur": {"ULBID": "POS-C", "LLBID": "POS-B", "BRBID": "POS-A", "URBID": "POS-D", "LRBID": "POS-E"},
    "lllr": {"ULBID": "POS-B", "LLBID": "POS-C", "BRBID": "POS-A", "URBID": "POS-E", "LRBID": "POS-D"},
    "ulbrlr": {"ULBID": "POS-C", "LLBID": "POS-A", "BRBID": "POS-D", "URBID": "POS-B", "LRBID": "POS-E"},
    "allbroken": {"ULBID": "POS-B", "LLBID": "POS-A", "BRBID": "POS-E", "URBID": "POS-C", "LRBID": "POS-D"},
}
check(len(paths) == len(path_slots) == 4, "predeclared four-path rule")
sources = {}
closures = {}
logs = {}
reports = {}
for arm, run in RUNS.items():
    source_file = CASE / f"{arm}-input.json"
    source = tables(native_json(source_file), "model")
    sources[arm] = source
    check(sha(source_file) == contract["input_sha256"][arm], f"{arm} source SHA")
    changed = {name: {"before": parent_source.get(name), "after": source.get(name)}
               for name in parent_source.keys() | source.keys()
               if parent_source.get(name) != source.get(name)}
    check(changed == diff["arms"][arm]["changed"], f"{arm} exact parent diff")
    check(set(changed) == {"ProblemDescription", "RBDBridge"}, f"{arm} only slot/description delta")
    for name in source:
        if name not in ("ProblemDescription", "RBDBridge"):
            check(source[name] == parent_source[name], f"{arm} unchanged business table {name}")
    bridge = records(source["RBDBridge"])
    check(len(bridge) == 1, f"{arm} one bridge row")
    if bridge:
        row = bridge[0]
        check({slot: row[slot] for slot in expected_slots[arm]} == expected_slots[arm],
              f"{arm} exact five slot mapping")
        check(row["RBID"] == "G07-BRIDGE" and all(row[k] == "G04-OPS" for k in
              ("ULOPM", "LLOPM", "BROPM", "UROPM", "LROPM")),
              f"{arm} common bridge RBD/mode")
        alive = {"POS-C", "POS-D", "POS-E"}
        functional = [{row[slot] for slot in path} <= alive for path in path_slots]
        check(functional == expected_live[arm], f"{arm} source-bound four-path truth row")
        check(sum(functional) == int(arm != "allbroken"), f"{arm} unique path or zero")

    invocation = native_json(run / "invocation.json")
    closure = native_json(run / "closure.json")
    closures[arm] = closure
    check(sha(run / "invocation.json") == closure["invocation_sha256"], f"{arm} invocation seal")
    check(invocation["run_id"] == closure["run_id"] == run.name, f"{arm} run identity")
    check(invocation["execution_mode"] == "session0_ssh_cli" and
          invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"],
          f"{arm} SSH session0")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and
          invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", f"{arm} GUI/queue")
    check(invocation["prelife_log_option_before"] == closure["prelife_log_option_after"] == "NO",
          f"{arm} registry restoration")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] ==
          closure["source_hashes_after"], f"{arm} frozen source stability")
    source_paths = {"input": source_file, "parent": parent_file,
                    "parent_closure": parent_run / "closure.json", "contract": CASE / "contract.json",
                    "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py",
                    "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
                    "runner": CASE / "run_native_ssh.ps1", **EXTERNAL}
    for name, path in source_paths.items():
        check(sha(path) == closure["source_hashes_before"][name], f"{arm} source seal {name}")
    check(len(closure["raw"]) == 13, f"{arm} 13 raw seals")
    for name, metadata in closure["raw"].items():
        path = run / name
        check(path.exists() and path.stat().st_size == metadata["bytes"] and
              sha(path) == metadata["sha256"], f"{arm} raw seal {name}")
    check(sha(run / "input.json") == sha(source_file), f"{arm} native source copied")
    steps = native_json(run / "steps.json")
    check([step["name"] for step in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"], f"{arm} five steps")
    for step in steps:
        check(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"],
              f"{arm} guarded step {step['name']}")
    check([step["arguments"] for step in steps[:4]] ==
          [command["args"] for command in invocation["planned_commands"]],
          f"{arm} planned CLI arguments")
    check(closure["conversion"]["errors"] == 0 and closure["conversion"]["notes"] == 0 and
          closure["conversion"]["warning_codes"] == ["108"], f"{arm} native diagnostics")
    check(closure["sxo_bytes"] > 4 and closure["report_present"] and
          closure["native_outcome"] == "zero_error_reviewed_warnings", f"{arm} usable outputs")
    check(not re.search(r"\berror\s*#", (run / "run.log").read_text(encoding="utf-8-sig"), re.I),
          f"{arm} no converter error text")
    exported = tables(native_json(run / "roundtrip-raw.json"), "model")
    populated = [name for name, table in source.items() if rows(table)]
    check(len(populated) == 22, f"{arm} 22 row-containing authored tables")
    for name in populated:
        check(name in exported, f"{arm} exported {name}")
        if name in exported:
            check(source[name]["columns"] == exported[name]["columns"], f"{arm} exact columns {name}")
            check(source[name]["instances"] == exported[name]["instances"], f"{arm} exact rows {name}")
    logs[arm] = (run / "model.log").read_text(encoding="utf-8-sig")
    reports[arm] = tables(native_json(run / "report-raw.json"), "report")

def event(arm, hour, fragment):
    return any(line.startswith(f"Time: {hour} ") and fragment in line
               for line in logs[arm].splitlines())

for arm in ARMS:
    success = arm != "allbroken"
    log = logs[arm]
    check(event(arm, 7, "mission allocates system: <TEACH-AIR-01,0>") and
          event(arm, 8, "mission starting, duration: 26"), f"{arm} mission activation/start")
    check(event(arm, 8.62763, "noncritical CM failure mode added") and
          "Failure Mode: FM-POS-B on materiel: <POS-B,0>" in log,
          f"{arm} matched first B failure")
    check(event(arm, 16.7498, ("noncritical" if success else "critical")+
                " CM failure mode added") and
          "Failure Mode: FM-POS-A on materiel: <POS-A,0>" in log,
          f"{arm} matched second A failure and criticality")
    check(log.count("CM failure mode added") == 2 and "Failure Mode: FM-POS-C" not in log and
          "Failure Mode: FM-POS-D" not in log and "Failure Mode: FM-POS-E" not in log,
          f"{arm} only B/A fail; C/D/E remain healthy")
    check("Item demand arrives" not in log and "Take replacement item" not in log,
          f"{arm} no item replacement")
    return_time = 34 if success else 23.2498
    repair_end = 34.5 if success else 23.7498
    if success:
        check(event(arm, 34, "mission success") and event(arm, 34, "mission completed") and
              "mission aborted" not in log, f"{arm} mission success")
        check((RUNS[arm] / "model.log").read_bytes() == parent_log,
              f"{arm} byte-identical event log to accepted diagonal path")
    else:
        check(event(arm, 16.7498, "mission aborted") and
              event(arm, 23.2498, "aborted mission completed") and
              "mission success" not in log, f"{arm} abort/return")
    for task, fm in enumerate(("FM-POS-B", "FM-POS-A")):
        text = f"system CM task {task} on <TEACH-AIR-01,0>"
        check(event(arm, return_time, text+" started") and
              event(arm, return_time, text+" FMID: "+fm) and
              event(arm, repair_end, text+" completed"), f"{arm} CM task {task} identity/timing")
        check(f"< {text}, {'NC' if success else 'C'}, 0.5>" in log,
              f"{arm} CM task {task} criticality")
    check(event(arm, repair_end, "systems ready: 1"), f"{arm} ready after CM")

for arm in ARMS:
    success = arm != "allbroken"
    report = reports[arm]
    check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults",
                          "StockTotalResults"}, f"{arm} report table set")
    if success:
        for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
            check(report[name] == parent_report[name], f"{arm} {name} equals accepted path")
    summary = records(report["ResultSummary"])[0]
    for key, expected in (("NREP", 1), ("RTILW", 0), ("RTIUP", 36), ("MSTF", 1),
                          ("MSUF", int(success)),
                          ("MTMF", 1 if success else .5865303874015808),
                          ("STMF", 1 if success else .5865303874015808)):
        check(near(summary[key], expected), f"{arm} summary {key}")
    for key in ("RSMTMF", "RSMSTF", "RSMSUF", "RSSTMF"):
        check(summary[key] == 0, f"{arm} one-rep precision {key}")
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    check(len(system) == len(stock) == 72, f"{arm} 72 aligned bins")
    return_time = 34 if success else 23.2498
    repair_end = 34.5 if success else 23.7498
    for i, (sr, kr) in enumerate(zip(system, stock)):
        start = i*.5
        end = start+.5
        check(sr["STINT"] == kr["STINT"] == start and sr["ETINT"] == kr["ETINT"] == end,
              f"{arm} interval {i}")
        reserved = occupancy(7, 8, start)
        flying = occupancy(8, return_time, start)
        repair = occupancy(return_time, repair_end, start)
        expected = {"NSYRY": 1-reserved-flying-repair, "NSYMA": reserved+flying,
                    "NSYMO": flying, "NSYMR": reserved, "NSYRP": repair,
                    "NSYUA": repair, "NSYA": 1-repair, "FTMO": flying,
                    "STACC": flying, "NFAIL": int(start <= 8.62763 < end)+
                    int(start <= 16.7498 < end)}
        for key, value in expected.items():
            check(near(sr[key], value), f"{arm} system {key} bin {i}")
        completion_bin = 69 if success else 47
        downtime_bin = 68 if success else 46
        check(sr["NREPT"] == (2 if i == completion_bin else 0),
              f"{arm} repair marker bin {i}")
        check(sr["NSYDT"] == (1 if i == downtime_bin else 0),
              f"{arm} downtime marker bin {i}")
        check((near(sr["SYDT"], .5) if i == downtime_bin else sr["SYDT"] is None),
              f"{arm} downtime duration bin {i}")
        for key in ("NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYAL", "NSYPM", "NSYTP",
                    "NSYWR", "NSYWI", "NSYLA", "NSYUH", "NPMT", "NDAM", "NPMS",
                    "NROBT", "NRCFG", "STREQ", "STF", "STLOW", "SYDTU", "NSYSW",
                    "NPSTA", "NPSUC"):
            check(sr[key] == 0, f"{arm} system {key} absent bin {i}")
        check(kr["PNB"] == 1 and all(v is None or v == 0 for k,v in kr.items()
                                         if k not in ("STINT", "ETINT", "PNB")),
              f"{arm} stock no movement bin {i}")
    check(near(system[-1]["NSYRY"], 1), f"{arm} terminal ready bin")
    check(near(sum(r["NSYMO"] for r in system)*.5, return_time-8),
          f"{arm} integrated operating hours")
    check(near(sum(r["NSYRP"] for r in system)*.5, .5),
          f"{arm} integrated CM occupancy")

result = {
    "schema": "simlox-g07-four-path-independent-readonly/v1",
    "decision": "GO: bounded fixed-fault four-path bridge panel" if not failures else "NO-GO: independent replay failed",
    "passed": not failures,
    "checks_passed": checks-len(failures),
    "checks_total": checks,
    "failures": failures,
    "raw_seals": sum(len(c["raw"]) for c in closures.values()),
    "runs": {arm: {"source_sha256": sha(CASE / f"{arm}-input.json"),
                   "closure_sha256": sha(run / "closure.json"),
                   "model_log_sha256": sha(run / "model.log"),
                   "report_sha256": sha(run / "report-raw.json")}
             for arm,run in RUNS.items()},
    "observed": {"common": "B h8.62763 noncritical, A h16.7498 in all arms",
                 "three_new_unique_paths": "UL+UR, LL+LR, UL+BR+LR each have A noncritical and mission success h34",
                 "accepted_parent": "LL+BR+UR has matching successful event/report output",
                 "allbroken": "A critical, abort h16.7498, return h23.2498",
                 "terminal": "Two half-hour system CM tasks, ready1 and no stock movement in each arm"},
    "limits": ["Active path is inferred from the sealed slot mapping, manual four-path rule, failed B/A and healthy C/D/E; the native log does not label an active path.",
               "Five fixed-seed B/A slot arrangements, including the accepted parent, do not cover other fault combinations or a complete truth table.",
               "One mode, seed and replication; no population reliability, bridge online repair, nested bridge, GUI drawing or cross-engine claim."],
}
OUT.write_bytes((json.dumps(result, sort_keys=True, indent=2)+"\n").encode("utf-8"))
print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                  "checks_total": checks, "failures": failures, "output": str(OUT)}))
raise SystemExit(0 if not failures else 1)
