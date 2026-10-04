"""Independent read-only replay of D13.var03 dynamic MAXPM native evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
RUN = CASE / "runs" / "d13-dynamic-maxpm-v100-ssh-20261004-01"
OUT = CASE / "review" / "independent-verdict.json"
checks, failures = 0, []


def ck(value, name):
    global checks
    checks += 1
    if not value:
        failures.append(name)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    raw = path.read_text(encoding="utf-8-sig")
    text, quoted, escape = [], False, False
    for i, char in enumerate(raw):
        if quoted:
            text.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            text.append(char)
        elif char == ',':
            j = i + 1
            while j < len(raw) and raw[j].isspace():
                j += 1
            if j == len(raw) or raw[j] not in ']}':
                text.append(char)
        else:
            text.append(char)
    return json.loads(''.join(text))


def tables(document, root="model"):
    return {table["name"]: table for table in document[root]["tables"]}


def cells(table):
    columns = [col["name"] for col in table["columns"]]
    return [(instance["instance_name"], dict(zip(columns, row)))
            for instance in table["instances"] for row in instance["rows"]]


def report_rows(report, name):
    table = tables(report, "report")[name]
    cols = [col["name"] for col in table["columns"]]
    return [dict(zip(cols, row)) for instance in table["instances"] for row in instance["rows"]]


def close(a, b, tolerance=4e-4):
    return math.isclose(float(a), float(b), abs_tol=tolerance, rel_tol=0)


def occupied(start, end, left, right):
    return max(0., min(end, right) - max(start, left))


contract, closure = read(CASE / "contract.json"), read(RUN / "closure.json")
inv, steps = read(RUN / "invocation.json"), read(RUN / "steps.json")
ck(contract["run_id"] == closure["run_id"] == inv["run_id"] == RUN.name, "run identity")
ck(sha(CASE / "contract.json") == "d7a3551e3fbc1d2708c446ab769ae961e5eb26787a631d93ff66b2e9a2ff9078", "frozen contract")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
ck(closure["error"] is None and closure["publication_state"] == "not_published", "closure status")
ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"], "session-zero SSH ancestry")
ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native queue mutex")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "preserved GUI identity")
ck(len(steps) == 8, "eight guarded steps")
for arm in ("rise", "hold"):
    for phase in ("import", "export", "calc", "report"):
        step = next((s for s in steps if s["name"] == f"{arm}_{phase}"), None)
        ck(step is not None and step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"{arm} {phase} step")
        if phase == "calc" and step:
            ck("-threads 1" in step["arguments"], f"{arm} serial calc")

parent_pkg = ROOT / contract["dependency"]["parent_package"]
paths = {
    "contract": CASE / "contract.json", "rise": CASE / "rise-input.json", "hold": CASE / "hold-input.json",
    "parent_input": parent_pkg / "native-input.json",
    "parent_closure": parent_pkg / "runs" / "d13-maxpm-two-v100-ssh-20260930-01" / "closure.json",
    "parent_signoff": parent_pkg / "cli-scope-signoff-2026-09-30.md",
    "build.py": CASE / "build.py", "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
for key, digest in sorted(closure["source_hashes_before"].items()):
    ck(digest == closure["source_hashes_after"].get(key) == inv["source_hashes_before"].get(key), f"source stable {key}")
    if key in paths:
        ck(paths[key].is_file() and sha(paths[key]) == digest, f"source disk hash {key}")
for key in ("rise", "hold"):
    ck(closure["source_hashes_before"][key] == contract["inputs_sha256"][key], f"contract input pin {key}")
for key in ("parent_input", "parent_closure", "parent_signoff"):
    ck(closure["source_hashes_before"][key] == contract["dependency"][key + "_sha256"], f"contract parent pin {key}")
ck(closure["source_hashes_before"]["manual"] == contract["manual"]["sha256"], "manual pin")
ck(len(closure["raw"]) == 22, "22 raw seals")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    ck(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw hash and size {name}")

parent = tables(read(paths["parent_input"]))
source = {arm: tables(read(CASE / f"{arm}-input.json")) for arm in ("rise", "hold")}
ck(set(parent) | {"MaxPMProfile"} == set(source["rise"]) == set(source["hold"]), "added profile table")
ck({name for name in parent if parent[name] != source["rise"][name]} == {"ProblemDescription", "Unit"}, "parent source changes")
ck({name for name in source["rise"] if source["rise"][name] != source["hold"][name]} == {"ProblemDescription", "MaxPMProfile"}, "pair only final profile and description")
for arm, final_limit in (("rise", 2), ("hold", 1)):
    unit = [row for _, row in cells(source[arm]["Unit"]) if row.get("UNID") == "TEACH-UNIT"]
    ck(len(unit) == 1 and unit[0]["MAXPM"] == 0 and unit[0]["MAXPMP"] == "CAP24", f"{arm} profile reference")
    profile = [row for _, row in cells(source[arm]["MaxPMProfile"]) if row.get("PRID") == "CAP24"]
    ck(len(profile) == 3, f"{arm} three profile periods")
    ck([(row["STIM"], row["ETIM"], row["MAXPM"]) for row in profile] == [(0, 24.25, 0), (24.25, 24.75, 1), (24.75, 36, final_limit)], f"{arm} exact disjoint limits")

observed = {}
spans = {"rise": ((24.25, 25.25), (24.75, 25.75)), "hold": ((24.25, 25.25), (25.25, 26.25))}
completion_bins = {"rise": (50, 51), "hold": (50, 52)}
for arm in ("rise", "hold"):
    authored, exported = source[arm], tables(read(RUN / f"{arm}-roundtrip-raw.json"))
    ck(set(authored) == set(exported), f"{arm} roundtrip tables")
    for name, table in sorted(authored.items()):
        actual = cells(exported[name])
        for instance, row in cells(table):
            if any(value is not None for value in row.values()):
                ck(any(i == instance and all(got.get(col) == value for col, value in row.items()) for i, got in actual), f"{arm} populated row/cells {name}/{instance}/{row}")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, f"{arm} zero converter errors")
    ck("(warning #108)" in runlog and "(warning #126)" in runlog, f"{arm} classified warnings")
    ck((RUN / f"{arm}.sxo").stat().st_size > 4, f"{arm} usable SXO")
    log = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    report = read(RUN / f"{arm}-report-raw.json")
    sys, stock, summary = (report_rows(report, name) for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
    ck(len(sys) == len(stock) == 72 and len(summary) == 1, f"{arm} report rows")
    for index, (system_row, stock_row) in enumerate(zip(sys, stock)):
        for row, table_name in ((system_row, "system"), (stock_row, "stock")):
            ck(close(row["STINT"], index / 2) and close(row["ETINT"], (index + 1) / 2), f"{arm} {table_name} bin {index}")
        ck(close(system_row["NSYA"] + system_row["NSYUA"], 2), f"{arm} aircraft conservation bin {index}")
        ck(all(stock_row[key] is None or close(stock_row[key], 0) for key in ("NBO", "NBOU", "NDF", "NDD", "NDR", "NDP")), f"{arm} no stock demand bin {index}")
        left, right = index / 2, (index + 1) / 2
        expected_pm = sum(occupied(a, b, left, right) for a, b in spans[arm]) / .5
        ck(close(system_row["NSYPM"], expected_pm), f"{arm} event-derived PM occupancy bin {index}")
        ck(close(system_row["NPMS"], 2 if index == 48 else 0), f"{arm} PM task creation marker bin {index}")
        ck(close(system_row["NPMT"], (index in completion_bins[arm])), f"{arm} PM task completion marker bin {index}")
    ck(close(sum(float(row["NSYPM"]) * .5 for row in sys), 2), f"{arm} two worker-free PM hours")
    ck(close(sum(float(row["NSYMO"]) * .5 for row in sys), 6), f"{arm} three two-hour flights")
    ck(close(sys[-1]["NSYRY"], 2) and close(sys[-1]["NSYA"], 2), f"{arm} terminal ready two")
    ck(close(summary[0]["NREP"], 1) and close(summary[0]["MSTF"], 1) and close(summary[0]["MSUF"], 1), f"{arm} successful mission summary")
    for mission, (start, end) in enumerate(((8, 10), (20, 22), (32, 34))):
        ident = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mission}>"
        ck(f"Time: {start} {ident} mission starting" in log and f"Time: {end} {ident} mission success" in log, f"{arm} mission identity {mission}")
    for task, (start, end) in enumerate(spans[arm]):
        ck(bool(re.search(rf"Time: 24  system PM task {task} on <TEACH-AIR-01,[01]> started", log)), f"{arm} task {task} created h24")
        ck(bool(re.search(rf"Time: 24  system PM task {task} on <TEACH-AIR-01,[01]> PMID: CAL24", log)), f"{arm} task {task} PM identity")
        ck(bool(re.search(rf"Time: {start:g}  subtask {task} seqno 1 .* starts performing", log)), f"{arm} task {task} physical start")
        ck(bool(re.search(rf"Time: {end:g}  system PM task {task} on <TEACH-AIR-01,[01]> completed", log)), f"{arm} task {task} physical completion")
    work_times = [float(value) for value in re.findall(r"^Time: ([0-9.]+)  subtask [01] seqno 1 .* starts performing", log, re.MULTILINE)]
    ck(len(work_times) == 2 and min(work_times) >= 24.25, f"{arm} exactly two PM work starts, none before h24.25")
    observed[arm] = (log, sys, stock, summary)

rise_log, rise_sys, rise_stock, rise_summary = observed["rise"]
hold_log, hold_sys, hold_stock, hold_summary = observed["hold"]
ck("Time: 24.75  subtask 1 seqno 1" in rise_log and "Time: 24.75  subtask 1 seqno 1" not in hold_log, "second PM starts at raised capacity only")
ck("Time: 25.25  subtask 1 seqno 1" in hold_log, "second PM waits for capacity release")
ck(rise_stock == hold_stock and rise_summary == hold_summary, "stock and mission summary equality")

result = {
    "case": "D13.var03 v1.0.0", "run_id": RUN.name,
    "passed": not failures, "verdict": "GO — bounded timed MAXPM physical-work contrast" if not failures else "NO-GO",
    "checks_passed": checks - len(failures), "checks_total": checks, "failures": failures,
    "observed": {"shared": "Both arms create two CAL24 task objects at h24; no physical PM work precedes h24.25.", "rise": "Task0 works h24.25–25.25 and task1 overlaps h24.75–25.75 after MAXPM rises to two.", "hold": "Task0 works h24.25–25.25; task1 waits and works h25.25–26.25 while MAXPM stays one.", "mission_terminal": "Three h8/20/32 missions succeed, six aircraft-flight hours, and two aircraft are ready at h36 in each arm."},
    "limits": ["One seed, two aircraft, one 24-hour PM and one nonoverlapping 0-to-1-to-2/1 profile; no general boundary, overlap-error, or GUI claim.", "The log proves physical work timing, not hidden capacity counter internals."],
    "sha256": {"contract": sha(CASE / "contract.json"), "closure": sha(RUN / "closure.json"), "rise_report": sha(RUN / "rise-report-raw.json"), "hold_report": sha(RUN / "hold-report-raw.json")},
}
OUT.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{result['verdict']}: {result['checks_passed']}/{result['checks_total']}")
for failure in failures[:25]:
    print("FAIL", failure)
