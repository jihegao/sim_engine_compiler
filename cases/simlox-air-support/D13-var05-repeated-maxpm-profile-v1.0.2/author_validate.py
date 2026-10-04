"""Author-side checks for sealed direct MAXPM LIMIT repetition evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

case = Path(__file__).resolve().parent
run = case / "runs/d13-repeated-maxpm-profile-v102-ssh-20261004-01"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    raw = path.read_text(encoding="utf-8-sig")
    out, quoted, escaped = [], False, False
    for i, char in enumerate(raw):
        if quoted:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            out.append(char)
        elif char == ",":
            j = i + 1
            while j < len(raw) and raw[j].isspace():
                j += 1
            if j == len(raw) or raw[j] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def tables(doc, key):
    return {t["name"]: t for t in doc[key]["tables"]}


def records(table):
    names = [c["name"] for c in table["columns"]]
    return [(i["instance_name"], dict(zip(names, row))) for i in table["instances"] for row in i["rows"]]


checks = 0
def check(ok, name):
    global checks
    checks += 1
    if not ok:
        raise AssertionError(name)


contract = read(case / "contract.json")
closure = read(run / "closure.json")
inv = read(run / "invocation.json")
steps = read(run / "steps.json")
check(contract["run_id"] == closure["run_id"] == inv["run_id"] == run.name, "run ID")
check(closure["error"] is None and len(closure["raw"]) == 22, "sealed 22-file successful run")
check(digest(run / "invocation.json") == closure["invocation_sha256"], "invocation seal")
check(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"], "session-0 SSH")
check(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native queue")
check(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "GUI identity")
check(len(steps) == 8 and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "eight guarded steps")
for name, seal in closure["raw"].items():
    path = run / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and digest(path) == seal["sha256"], "raw seal " + name)
for key, before in closure["source_hashes_before"].items():
    check(before == closure["source_hashes_after"][key] == inv["source_hashes_before"][key], "stable source " + key)
for arm in ("flat", "nested"):
    check(digest(case / f"{arm}-input.json") == contract["inputs_sha256"][arm], arm + " input pin")

inputs = {arm: tables(read(case / f"{arm}-input.json"), "model") for arm in ("flat", "nested")}
check({name for name in inputs["flat"] if inputs["flat"][name] != inputs["nested"][name]} == {"ProblemDescription", "Unit", "MaxPMProfile"}, "paired source table delta")
flat = [row for _, row in records(inputs["flat"]["MaxPMProfile"])]
repeat = [row for _, row in records(inputs["nested"]["MaxPMProfile"])]
check(len(flat) == 9 and len(repeat) == 3, "nine flat versus three repeated rows")
check(all(row["SPRID"] == "<LIMIT>" and row["IQTY"] == 3 and row["IINT"] == 12 for row in repeat), "direct LIMIT repetitions")
expanded = sorted((row["STIM"] + 12*k, row["ETIM"] + 12*k, row["MAXPM"]) for row in repeat for k in range(3))
check(expanded == sorted((row["STIM"], row["ETIM"], row["MAXPM"]) for row in flat), "source expansion")

reports = {}
for arm in ("flat", "nested"):
    authored = inputs[arm]
    exported = tables(read(run / f"{arm}-roundtrip-raw.json"), "model")
    check(set(authored) == set(exported), arm + " roundtrip table names")
    for name, table in authored.items():
        exported_rows = records(exported[name])
        for instance, row in records(table):
            if any(value is not None for value in row.values()):
                check(any(instance == actual_instance and all(actual.get(key) == value for key, value in row.items()) for actual_instance, actual in exported_rows), arm + " roundtrip " + name)
    converter = (run / f"{arm}-run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter and "(warning #331)" not in converter, arm + " converter")
    check((run / f"{arm}.sxo").stat().st_size > 4, arm + " SXO")
    event = (run / f"{arm}.log").read_text(encoding="utf-8-sig", errors="replace")
    for task, start, finish in ((0, 24.25, 25.25), (1, 24.75, 25.75)):
        check(bool(re.search(rf"Time: 24  system PM task {task} on <TEACH-AIR-01,[01]> started", event)), arm + f" task {task} created")
        check(bool(re.search(rf"Time: {start:g}  subtask {task} seqno 1 .* starts performing", event)), arm + f" task {task} physical start")
        check(bool(re.search(rf"Time: {finish:g}  system PM task {task} on <TEACH-AIR-01,[01]> completed", event)), arm + f" task {task} completed")
    for mission, start, finish in ((0, 8, 10), (1, 20, 22), (2, 32, 34)):
        ident = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission}>"
        check(f"Time: {start} {ident} mission starting" in event and f"Time: {finish} {ident} mission success" in event, arm + f" mission {mission}")
    reports[arm] = tables(read(run / f"{arm}-report-raw.json"), "report")
    for name in ("SystemResults", "StockTotalResults"):
        rows = [row for _, row in records(reports[arm][name])]
        check(len(rows) == 72, arm + " " + name + " 72 bins")
        check(all(math.isclose(float(row["STINT"]), i/2, abs_tol=0.0004) and math.isclose(float(row["ETINT"]), (i+1)/2, abs_tol=0.0004) for i, row in enumerate(rows)), arm + " " + name + " aligned bins")
    sys = [row for _, row in records(reports[arm]["SystemResults"])]
    check(math.isclose(sum(float(row["NSYPM"])*0.5 for row in sys), 2, abs_tol=0.0004), arm + " two PM work hours")
    check(math.isclose(sys[-1]["NSYRY"], 2, abs_tol=0.0004), arm + " two terminal ready")

check(digest(run / "flat.log") == digest(run / "nested.log"), "byte-identical event logs")
check({name for name in reports["flat"] if reports["flat"][name] != reports["nested"][name]} == {"ProblemDescription"}, "all non-description report tables equal")
result = {"schema": "simlox-d13-direct-limit-author-validation/v1", "run_id": run.name, "passed": True, "checks_passed": checks, "checks_total": checks, "closure_sha256": digest(run / "closure.json"), "event_log_sha256": digest(run / "flat.log"), "non_description_report_tables_equal": True, "scope": "Three direct repeated LIMIT rows equal nine explicit LIMIT rows for one seed, two aircraft, CAL24 and 36h."}
(case / "author-native-validation-2026-10-04.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"GO {checks}/{checks}")
