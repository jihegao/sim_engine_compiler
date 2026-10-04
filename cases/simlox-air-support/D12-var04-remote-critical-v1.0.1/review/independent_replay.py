"""Independent, read-only replay of sealed D12.var04 native evidence."""
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
RUN = CASE / "runs" / "d12-var04-remote-critical-v101-ssh-20261004-01"
OUT = CASE / "review" / "independent-verdict.json"
failures = []
checks = 0


def ck(test, description):
    global checks
    checks += 1
    if not test:
        failures.append(description)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def data(path):
    raw = path.read_text(encoding="utf-8-sig")
    # Native JSON may contain trailing commas. Remove them outside strings.
    output = []
    quoted = escaped = False
    for i, char in enumerate(raw):
        if quoted:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
            output.append(char)
        elif char == ',':
            j = i + 1
            while j < len(raw) and raw[j].isspace():
                j += 1
            if j >= len(raw) or raw[j] not in ']}':
                output.append(char)
        else:
            output.append(char)
    return json.loads(''.join(output))


def tables(document, key="model"):
    return {t["name"]: t for t in document[key]["tables"]}


def entries(table):
    cols = [c["name"] for c in table["columns"]]
    return [(instance["instance_name"], dict(zip(cols, row)))
            for instance in table["instances"] for row in instance["rows"]]


def report_rows(report, name):
    t = tables(report, "report")[name]
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for instance in t["instances"] for row in instance["rows"]]


def near(left, right, tolerance=3e-4):
    return math.isclose(float(left), float(right), abs_tol=tolerance, rel_tol=0)


def overlap(start, end, left, right):
    return max(0.0, min(end, right) - max(start, left))


contract = data(CASE / "contract.json")
closure = data(RUN / "closure.json")
inv = data(RUN / "invocation.json")
steps = data(RUN / "steps.json")
ck(contract["run_id"] == RUN.name == closure["run_id"] == inv["run_id"], "run identity")
ck(sha(CASE / "contract.json") == "c1eb0ef6939780269f074fa35b0b53d97cc1e279c749d67c1f89c4ca9058a43e", "frozen contract")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation hash")
ck(closure["error"] is None and closure["publication_state"] == "not_published", "successful unpublished closure")
ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"], "session-zero SSH ancestry")
ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native queue mutex")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "preserved GUI identity")
ck(len(steps) == 8, "eight native steps")
for arm in ("local", "remote"):
    for phase in ("import", "export", "calc", "report"):
        step = next((s for s in steps if s["name"] == f"{arm}_{phase}"), None)
        ck(step is not None and step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"], f"{arm} {phase} guarded completion")
        if phase == "calc" and step:
            ck("-threads 1" in step["arguments"], f"{arm} serial calculation")

paths = {
    "contract": CASE / "contract.json",
    "local": CASE / "local-input.json",
    "remote": CASE / "remote-input.json",
    "diagnostic_closure": ROOT / "D12-var04-remote-critical-v1.0.0" / "runs" / "d12-var04-remote-critical-v100-ssh-20261004-01" / "closure.json",
    "parent_input": ROOT / "D12-var01-active-small-v1.0.0" / "linked-input.json",
    "parent_closure": ROOT / "D12-var01-active-small-v1.0.0" / "runs" / "d12-var01-active-small-v100-ssh-20261004-01" / "closure.json",
    "parent_signoff": ROOT / "D12-var01-active-small-v1.0.0" / "cli-scope-signoff-2026-10-04.md",
    "build.py": CASE / "build.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
for key, digest in sorted(closure["source_hashes_before"].items()):
    ck(digest == inv["source_hashes_before"].get(key) == closure["source_hashes_after"].get(key), f"stable source seal {key}")
    if key in paths:
        ck(paths[key].is_file() and sha(paths[key]) == digest, f"current source hash {key}")
ck(closure["source_hashes_before"]["local"] == contract["inputs_sha256"]["local"], "contract local pin")
ck(closure["source_hashes_before"]["remote"] == contract["inputs_sha256"]["remote"], "contract remote pin")
ck(closure["source_hashes_before"]["parent_input"] == contract["dependency"]["input_sha256"], "contract parent input pin")
ck(closure["source_hashes_before"]["diagnostic_closure"] == contract["excluded_diagnostic"]["closure_sha256"], "excluded v1.0.0 pin")
ck(len(closure["raw"]) == 22, "22 sealed raw files")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    ck(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")

parent = tables(data(paths["parent_input"]))
source = {arm: tables(data(CASE / f"{arm}-input.json")) for arm in ("local", "remote")}
ck(set(source["local"]) == set(parent) == set(source["remote"]), "stable table names")
parent_delta = {name for name in parent if parent[name] != source["local"][name]}
ck(parent_delta == {"Control", "MaterielPM", "OperationProfile", "PMLocation", "ProblemDescription", "ResourceAllocation", "ResultCollection", "Station", "StationStructure", "SubTaskResource", "TaskBreakDown", "Tasks"}, "parent-to-local table delta")
pair_delta = {name for name in source["local"] if source["local"][name] != source["remote"][name]}
ck(pair_delta == {"PMLocation", "ProblemDescription"}, "location-only paired business delta")
for arm, station in (("local", "BASE-01"), ("remote", "BASE-02")):
    pm = entries(source[arm]["PMLocation"])
    ck(any(row.get("PMID") == "CAL24" and row.get("STID") == station for _, row in pm), f"{arm} CAL24 station")
    resources = [row for _, row in entries(source[arm]["ResourceAllocation"]) if row.get("RID") == "P-MAINT"]
    ck(sorted((row.get("STID"), row.get("RQTY")) for row in resources) == [("BASE-01", 2), ("BASE-02", 2)], f"{arm} matched two-worker capacities")
    pms = [row for _, row in entries(source[arm]["MaterielPM"]) if row.get("PMID") in ("CAL24", "BIG24P75")]
    ck(len(pms) == 2, f"{arm} paired PM records")

observed = {}
for arm in ("local", "remote"):
    authored = source[arm]
    exported = tables(data(RUN / f"{arm}-roundtrip-raw.json"))
    ck(set(authored) == set(exported), f"{arm} roundtrip table set")
    for name, table in sorted(authored.items()):
        expected = [(instance, row) for instance, row in entries(table) if any(value is not None for value in row.values())]
        actual = entries(exported[name])
        for instance, row in expected:
            ck(any(found_instance == instance and all(found_row.get(col) == value for col, value in row.items()) for found_instance, found_row in actual), f"{arm} authored row/cells {name}/{instance}/{row}")
    runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
    ck("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, f"{arm} converter zero errors")
    ck("(warning #108)" in runlog and "(warning #126)" in runlog, f"{arm} classified warnings")
    ck((RUN / f"{arm}.sxo").stat().st_size > 4, f"{arm} valid native output")
    log = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig")
    report = data(RUN / f"{arm}-report-raw.json")
    system = report_rows(report, "SystemResults")
    resource = report_rows(report, "ResourceResults")
    stock = report_rows(report, "StockTotalResults")
    summary = report_rows(report, "ResultSummary")
    ck(len(system) == len(resource) == len(stock) == 60 and len(summary) == 1, f"{arm} 60-bin report")
    for index, (sys, res, stk) in enumerate(zip(system, resource, stock)):
        for row, label in ((sys, "System"), (res, "Resource"), (stk, "Stock")):
            ck(near(row["STINT"], index / 2) and near(row["ETINT"], (index + 1) / 2), f"{arm} {label} bin {index}")
        ck(near(sys["NSYA"] + sys["NSYUA"], 2), f"{arm} aircraft conservation bin {index}")
        ck(near(res["NR"], 4) and near(res["NRA"], 4), f"{arm} four available resource identities bin {index}")
        ck(all(stk[key] is None or near(stk[key], 0) for key in ("NBO", "NBOU", "NDF", "NDD", "NDR", "NDP")), f"{arm} no stock demand bin {index}")
    ck(near(system[-1]["NSYRY"], 2) and near(system[-1]["NSYPM"], 0), f"{arm} terminal two ready")
    ck(near(summary[0]["NREP"], 1) and near(summary[0]["MSTF"], 1) and near(summary[0]["MSUF"], 1), f"{arm} successful single mission summary")
    ck("Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log and "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log, f"{arm} mission identity/timing")
    for task in (0, 1):
        ck(bool(re.search(rf"Time: [0-9.]+  system PM task {task} on <TEACH-AIR-01,[01]> PMID: CAL24", log)), f"{arm} CAL24 task identity {task}")
    for task in (2, 3):
        ck(bool(re.search(rf"Time: [0-9.]+  system PM task {task} on <TEACH-AIR-01,[01]> PMID: BIG24P75", log)), f"{arm} BIG24P75 task identity {task}")
    observed[arm] = (log, system, resource, stock, summary)

for arm, details in {
    "local": {"small": (24, 24.75), "big": (24.75, 25.75), "worker_hours": 3.5, "stops": 2},
    "remote": {"small": (24.25, 25.25), "big": (25.5, 26.5), "worker_hours": 4, "stops": 0},
}.items():
    log, system, resource, _, _ = observed[arm]
    for task in (0, 1):
        start, end = details["small"]
        ck(bool(re.search(rf"Time: {start:g}  system PM task {task} on <TEACH-AIR-01,[01]> started", log)), f"{arm} small start task {task}")
        verb = "stopped" if arm == "local" else "completed"
        ck(bool(re.search(rf"Time: {end:g}  system PM task {task} on <TEACH-AIR-01,[01]> {verb}", log)), f"{arm} small {verb} task {task}")
        ck(bool(re.search(rf"Time: {start:g}  subtask {task} seqno 1 .* starts performing", log)), f"{arm} small worker work task {task}")
    for task in (2, 3):
        start, end = details["big"]
        ck(bool(re.search(rf"Time: {start:g}  system PM task {task} on <TEACH-AIR-01,[01]> started", log)), f"{arm} big start task {task}")
        ck(bool(re.search(rf"Time: {end:g}  system PM task {task} on <TEACH-AIR-01,[01]> completed", log)), f"{arm} big completion task {task}")
    ck(len(re.findall(r"^Time: [0-9.]+  system PM task [01] on <TEACH-AIR-01,[01]> stopped$", log, re.MULTILINE)) == details["stops"], f"{arm} observed small task stop count")
    ck(near(sum(float(row["NRUM"]) * .5 for row in resource), details["worker_hours"]), f"{arm} integrated worker hours")
    for index, (sys, res) in enumerate(zip(system, resource)):
        left, right = index / 2, (index + 1) / 2
        small = overlap(*details["small"], left, right)
        big = overlap(*details["big"], left, right)
        work = 2 * (small + big) / .5
        ck(near(res["NRUM"], work), f"{arm} event-derived worker bin {index}")
        ck(near(sys["NSYPM"], work), f"{arm} event-derived PM bin {index}")
        expected_transport = 0 if arm == "local" else 2 * (overlap(24, 24.25, left, right) + overlap(25.25, 25.5, left, right)) / .5
        ck(near(sys["NSYTP"], expected_transport), f"{arm} transport occupancy bin {index}")

local_log, _, _, local_stock, local_summary = observed["local"]
remote_log, _, _, remote_stock, remote_summary = observed["remote"]
ck("Time: 24.75  system PM task 0" in local_log and "Time: 24.75  system PM task 1" in local_log, "local h24.75 stop boundary")
ck("Time: 24.75  system PM task" not in remote_log and "Time: 24.75  subtask" not in remote_log, "no logged remote stop attempt at due time")
for task in (0, 1, 3, 4):
    ck(bool(re.search(rf"Time: (24\.25|25\.5)  transport task {task} arrives", remote_log)), f"remote physical transit arrival {task}")
ck([row for row in local_stock] == [row for row in remote_stock], "stock reports identical")
ck(local_summary == remote_summary, "summary reports identical")

verdict = {
    "case": "D12.var04 v1.0.1",
    "run_id": RUN.name,
    "decision": "GO — bounded installed-CLI local-stop versus remote-continuation observation" if not failures else "NO-GO",
    "passed": not failures,
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "observed": {
        "local": "Two CAL24 tasks work at BASE-01 h24–24.75, are explicitly stopped, and two BIG24P75 tasks work h24.75–25.75.",
        "remote": "Two CAL24 tasks travel to BASE-02, work h24.25–25.25 to completion, return by h25.5, then two BIG24P75 tasks work h25.5–26.5.",
        "worker_hours_local_remote": [3.5, 4.0],
        "terminal_ready_aircraft": 2,
    },
    "limits": ["The remote log does not record a stop attempt; only uninterrupted work and deferred BIG24P75 start are observed.", "One seed, two aircraft, two workers per station, one linked PM pair and 0.25-hour transport; no general remote PM or GUI behavior claim.", "v1.0.0 one-worker diagnostic is excluded."],
    "sha256": {"contract": sha(CASE / "contract.json"), "closure": sha(RUN / "closure.json"), "local_report": sha(RUN / "local-report-raw.json"), "remote_report": sha(RUN / "remote-report-raw.json")},
}
OUT.write_text(json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{verdict['decision']}: {verdict['checks_passed']}/{verdict['checks_total']}")
for failure in failures[:25]:
    print("FAIL", failure)
