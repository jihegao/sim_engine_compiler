"""Independent, read-only C09.var04 replay using only Python's standard library.

This script reads frozen source and native run files. It imports no author module
and writes only its deterministic report beside itself.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
OUT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
PARENT = ROOT / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"
TEMPLATE = ROOT / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
RUNS = {arm: CASE / "runs" / f"c09-var04-{arm}-20261002-01"
        for arm in ("local", "remote", "remote-disabled")}
SOURCE_PATHS = {
    "parent": PARENT,
    "repair_template": TEMPLATE,
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "checker": CASE / "check_roundtrip.py",
    "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
CHANGED = {
    "local": {"ProblemDescription", "System", "Station", "SystemRepair", "Tasks", "TaskResource", "Resource", "ResourceAllocation", "TaskBreakDown"},
    "remote": {"ProblemDescription", "System", "Station", "SystemRepair", "Tasks", "TaskResource", "Resource", "ResourceAllocation", "TaskBreakDown", "ResourceRemoteSupport"},
    "remote-disabled": {"ProblemDescription", "System", "Station", "SystemRepair", "Tasks", "TaskResource", "Resource", "ResourceAllocation", "TaskBreakDown", "ResourceRemoteSupport"},
}
WORK = {
    "local": [(8.53243, 9.03243), (9.03243, 9.53243)],
    "remote": [(8.78243, 9.28243), (9.28243, 9.78243)],
    "remote-disabled": [],
}
checks = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path, native=False):
    content = path.read_text(encoding="utf-8-sig")
    if native:  # SIMLOX exports a trailing comma after its last table.
        content = re.sub(r",(?=\s*[}\]])", "", content)
    return json.loads(content)


def check(name, okay, detail=None):
    checks.append({"name": name, "pass": bool(okay), **({"detail": detail} if detail is not None else {})})


def tables(document, root="model"):
    return {table["name"]: table for table in document[root]["tables"]}


def column(table, name):
    return [field["name"] for field in table["columns"]].index(name)


def rows(table):
    return [(instance["instance_name"], row)
            for instance in table["instances"] for row in instance["rows"]]


def records(table):
    names = [field["name"] for field in table["columns"]]
    return [dict(zip(names, row)) for _, row in rows(table)]


def nonblank(table):
    return [row for _, row in rows(table) if any(value is not None for value in row)]


def event_times(text, expression):
    return [float(value) for value in re.findall(expression, text)]


def near(a, b, tolerance=1e-5):
    return math.isclose(a, b, rel_tol=0, abs_tol=tolerance)


def main():
    contract = parse(CASE / "contract.json")
    parent_tables = tables(parse(PARENT))
    check("accepted C03 parent SHA", sha(PARENT) == contract["parent_input_sha256"])
    check("accepted D01 repair template SHA", sha(TEMPLATE) == contract["repair_template_input_sha256"])
    check("installed manual SHA", sha(SOURCE_PATHS["manual"]) == contract["manual_sha256"])
    check("installed dictionary SHA", sha(SOURCE_PATHS["dictionary"]) == contract["dictionary_sha256"])
    current_hashes = {key: sha(path) for key, path in SOURCE_PATHS.items()}
    sources = {arm: tables(parse(CASE / f"{arm}-input.json")) for arm in RUNS}
    for arm, source_tables in sources.items():
        changed = {name for name in source_tables if source_tables[name] != parent_tables.get(name)}
        check(f"{arm} exact changed table set", changed == CHANGED[arm], sorted(changed))
        check(f"{arm} no removed parent table", set(parent_tables) <= set(source_tables))
        check(f"{arm} System FRT", nonblank(source_tables["System"])[0][column(source_tables["System"], "FRT")] == 2_000_000)
        repairs = nonblank(source_tables["SystemRepair"])
        check(f"{arm} direct system repair row", len(repairs) == 1 and repairs[0][column(source_tables["SystemRepair"], "DIRPT")] == .5 and repairs[0][column(source_tables["SystemRepair"], "DIRPTID")] == "C09-DIRP")
        breakdown = [r for r in nonblank(source_tables["TaskBreakDown"]) if r[column(source_tables["TaskBreakDown"], "TID")] == "C09-DIRP"]
        check(f"{arm} built-in REPAIR subtask", len(breakdown) == 1 and breakdown[0][column(source_tables["TaskBreakDown"], "SUTID")] == "<REPAIR>" and breakdown[0][column(source_tables["TaskBreakDown"], "DURN")] == .5)
        resource = [r for r in nonblank(source_tables["ResourceAllocation"]) if r[column(source_tables["ResourceAllocation"], "RID")] == "P-MECH"]
        check(f"{arm} one mechanic at expected station", len(resource) == 1 and resource[0][column(source_tables["ResourceAllocation"], "RQTY")] == 1 and resource[0][column(source_tables["ResourceAllocation"], "STID")] == ("BASE-01" if arm == "local" else "BASE-02"))
        request = [r for r in nonblank(source_tables["TaskResource"]) if r[column(source_tables["TaskResource"], "TID")] == "C09-DIRP"]
        check(f"{arm} mechanic request and ENRMS", len(request) == 1 and request[0][column(source_tables["TaskResource"], "RID")] == "P-MECH" and request[0][column(source_tables["TaskResource"], "QTY")] == 1 and request[0][column(source_tables["TaskResource"], "ENRMS")] == ("N" if arm == "remote-disabled" else "Y"))
        if arm != "local":
            route = source_tables["ResourceRemoteSupport"]
            check(f"{arm} exact remote route", nonblank(route) == [["P-MECH", "BASE-01", "BASE-02", .25, .5, .125, None]])
        else:
            check("local has no remote route", "ResourceRemoteSupport" not in source_tables)
    check("local versus remote changes only station, route, description", {name for name in sources["remote"] if sources["remote"][name] != sources["local"].get(name)} == {"ProblemDescription", "ResourceAllocation", "ResourceRemoteSupport"})
    check("remote versus disabled changes only ENRMS and description", {name for name in sources["remote-disabled"] if sources["remote-disabled"][name] != sources["remote"].get(name)} == {"ProblemDescription", "TaskResource"})

    gui_identity = None
    raw_count = 0
    outcomes = {}
    for arm, run in RUNS.items():
        source = CASE / f"{arm}-input.json"
        invocation, closure, steps = (parse(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        check(f"{arm} frozen source SHA", sha(source) == contract["input_sha256"][arm] == sha(run / "input.json"))
        check(f"{arm} invocation seal", sha(run / "invocation.json") == closure["invocation_sha256"])
        check(f"{arm} run identity", invocation["run_id"] == closure["run_id"] == run.name and invocation["variant"] == arm)
        check(f"{arm} session-0 SSH", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"])
        check(f"{arm} global native mutex", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        identity = (invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"])
        if gui_identity is None: gui_identity = identity
        check(f"{arm} GUI PID/start continuity", identity == gui_identity and identity[:2] == (13340, 1) and all(s["gui_preserved"] for s in steps))
        check(f"{arm} five successful steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["exit_code"] == 0 and s["status"] == "completed" for s in steps))
        check(f"{arm} unchanged sealed source", closure["source_hashes_before"] == closure["source_hashes_after"] and closure["error"] is None)
        for key, expected in closure["source_hashes_before"].items():
            actual = sha(source) if key == "input" else sha(Path(invocation["planned_check"]["executable"])) if key == "python" else current_hashes[key]
            check(f"{arm} source seal {key}", actual == expected)
        raw_count += len(closure["raw"])
        check(f"{arm} twelve raw seals", len(closure["raw"]) == 12)
        for name, seal in closure["raw"].items():
            path = run / name
            check(f"{arm} raw seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        check(f"{arm} raw seal completeness", set(closure["raw"]) == {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})

        authored = sources[arm]
        exported = tables(parse(run / "roundtrip-raw.json", native=True))
        populated = [name for name, table in authored.items() if rows(table)]
        check(f"{arm} populated source table count", len(populated) == (22 if arm == "local" else 23))
        for name in populated:
            before, after = authored[name], exported.get(name)
            check(f"{arm} exact roundtrip {name}", after is not None and [c["name"] for c in before["columns"]] == [c["name"] for c in after["columns"]] and rows(before) == rows(after))
        native_log = (run / "run.log").read_text(encoding="utf-8-sig")
        conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", native_log)
        check(f"{arm} converter summary present", conversion is not None)
        totals = tuple(map(int, conversion.groups())) if conversion else None
        check(f"{arm} zero-error converter diagnostics", totals == (0, 2, 0 if arm == "local" else 1) and "(warning #108)" in native_log and "(warning #126)" in native_log and ("(notice #292)" in native_log) == (arm != "local"))
        check(f"{arm} nonempty simulation/report", (run / "model.sxo").stat().st_size > 1000 and (run / "report-raw.json").stat().st_size > 1000)

        log = (run / "model.log").read_text(encoding="utf-8-sig")
        start = event_times(log, r"Time: ([0-9.]+)\s+direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,[01]> starts performing")
        end = event_times(log, r"Time: ([0-9.]+)\s+direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,[01]> completed")
        check(f"{arm} exact repair work timing", list(zip(start, end)) == WORK[arm], list(zip(start, end)))
        check(f"{arm} two simultaneous failure repair tasks", len(re.findall(r"Time: 8\.53243\s+system DIRP task \d+ on <TEACH-AIR-01,[01]> started", log)) == 2)
        if arm == "remote":
            markers = (
                (8.53243, "remote resource transport task 3 starts with 1 resources, transportation time: 0.25"),
                (8.78243, "remote resource transport task 3 arrives with 1 resources"),
                (9.78243, "return resource transport task 0 starts with 1 resources, transportation time: 0.5"),
                (10.2824, "return resource transport task 0 arrives with 1 resources"),
            )
            check("remote exact forward/return task events", all(f"Time: {time:g}  {description}" in log for time, description in markers))
            check("remote BASE-02 to BASE-01 borrowing and return", "starting from  <P-MECH at <BASE-02,0>> aiming for  <P-MECH at" in log and "starting from  <P-MECH at <BASE-01,0>> aiming for  <P-MECH at" in log and "<P-MECH at <BASE-02,0>> return transport arrives: 1" in log)
        else:
            check(f"{arm} no remote transport", "remote resource transport task" not in log and "return resource transport task" not in log)

        report = tables(parse(run / "report-raw.json", native=True), "report")
        system, stock, resource = (records(report[name]) for name in ("SystemResults", "StockTotalResults", "ResourceResults"))
        check(f"{arm} aligned 72 half-hour report bins", all(len(x) == 72 for x in (system, stock, resource)) and all(s["STINT"] == t["STINT"] == r["STINT"] == i / 2 and s["ETINT"] == t["ETINT"] == r["ETINT"] == (i + 1) / 2 for i, (s, t, r) in enumerate(zip(system, stock, resource))))
        check(f"{arm} two native failures", sum(s["NFAIL"] for s in system) == 2)
        check(f"{arm} completed repair count", sum(s["NREPT"] for s in system) == (0 if arm == "remote-disabled" else 2))
        check(f"{arm} terminal ready count", near(system[-1]["NSYRY"], 0 if arm == "remote-disabled" else 2))
        check(f"{arm} zero spare demand/backorder", all((s["NBO"] or 0) == (s["NDD"] or 0) == 0 for s in stock))
        balance_error = max(abs(r["NR"] + r["NRRT"] - r["NRN"]) for r in resource)
        check(f"{arm} aggregate resource conservation", balance_error < 2e-6 and all(near(r["NRN"], 3) for r in resource), balance_error)
        transit_hours = sum(r["NRRT"] * .5 for r in resource)
        check(f"{arm} travel resource-hours", near(transit_hours, .75 if arm == "remote" else 0), transit_hours)
        check(f"{arm} report terminal transport cleared", near(resource[-1]["NRRT"], 0) and near(resource[-1]["NR"], 3))
        outcomes[arm] = {"run_id": run.name, "input_sha256": sha(source), "report_sha256": sha(run / "report-raw.json"), "event_log_sha256": sha(run / "model.log"), "converter_errors_warnings_notes": totals, "row_containing_tables": len(populated), "failures": sum(s["NFAIL"] for s in system), "completed_repairs": sum(s["NREPT"] for s in system), "repair_work_intervals": list(zip(start, end)), "resource_transit_hours": transit_hours, "resource_conservation_max_abs_error": balance_error, "terminal_ready": system[-1]["NSYRY"]}
    check("36 raw SHA seals", raw_count == 36)
    failed = [item for item in checks if not item["pass"]]
    report = {"schema": "independent-c09-var04-readonly/v1", "reviewer": "a17_static_reviewer", "verdict": "GO bounded fixed-seed CLI evidence" if not failed else "NO-GO", "checks_passed": len(checks) - len(failed), "checks_total": len(checks), "failures": failed, "raw_seals": raw_count, "outcomes": outcomes, "limits": ["One native replication and fixed seed per arm; no population borrowing frequency estimate.", "ResourceResults is aggregated over resources and stations; station-level transit identity comes from the event log.", "The converter implicitly creates P-MECH at receiving BASE-01 in remote arms (notice #292).", "Only direct primary system repair is exercised; no secondary, replacement, cost, GUI or cross-engine claim."]}
    OUT.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": report["verdict"], "checks": f"{report['checks_passed']}/{report['checks_total']}", "failures": failed, "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUT)}, indent=2))


if __name__ == "__main__": main()
