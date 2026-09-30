"""Independent stdlib read-only replay of C10 calendar versus operation clocks."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT_CASE = CASE.parent / "C10-resource-failure-v1.0.0"
PARENT = PARENT_CASE / "oper-no-spare-input.json"
PARENT_RUN = PARENT_CASE / "runs" / "c10-oper-no-spare-20260930-01"
CHILD = CASE / "calendar-two-crew-input.json"
CHILD_RUN = CASE / "runs" / "c10-calendar-two-crew-20260930-01"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
CHECKS: list[dict] = []


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path):
    raw = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = escaped = False
    removed = 0
    for index, char in enumerate(raw):
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
        elif char == "," and raw[index + 1 :].lstrip().startswith(("}", "]")):
            removed += 1
        else:
            output.append(char)
    return json.loads("".join(output)), removed


def check(name, condition, detail=None):
    item = {"name": name, "passed": bool(condition)}
    if detail is not None:
        item["detail"] = detail
    CHECKS.append(item)


def tables(document, key="model"):
    source = document[key]["tables"]
    names = [table["name"] for table in source]
    return {table["name"]: table for table in source}, len(names) == len(set(names))


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def columns(table):
    return [column["name"] for column in table["columns"]]


def row(table):
    return dict(zip(columns(table), rows(table)[0]))


def bins(table):
    return {item["STINT"]: item for item in (dict(zip(columns(table), values)) for values in rows(table))}


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def integral(segments, start, end):
    return sum(max(0.0, min(right, end) - max(left, start)) * weight for left, right, weight in segments)


def averages(segments):
    return {index / 2: 2 * integral(segments, index / 2, (index + 1) / 2) for index in range(72)}


def point_events(times, weight=1):
    result = {index / 2: 0 for index in range(72)}
    for time in times:
        result[int(time * 2) / 2] += weight
    return result


def parse_timeline(log):
    """Parse event lines into resource-state and preparation intervals."""
    events = []
    work = []
    wait = []
    working = {}
    waiting = {}
    prep_start = {}
    prep_end = {}
    mission_start = mission_success = None
    for line in log.splitlines():
        match = re.match(r"Time: ([0-9.]+) (.*)", line)
        if not match:
            continue
        time = float(match.group(1))
        description = match.group(2)
        if "<P-CREW at <BASE-01,0>> Failed" in description:
            events.append((time, 1))
        elif "<P-CREW at <BASE-01,0>> Repaired" in description:
            events.append((time, -1))
        air = re.search(r"subtask ([01]) seqno 1 within system preparation task", description)
        if air:
            number = int(air.group(1))
            if "starts performing" in description:
                working[number] = time
            elif "is stopped due" in description:
                work.append((working.pop(number), time, 1))
                waiting[number] = time
            elif "resource received" in description:
                wait.append((waiting.pop(number), time, 1))
            elif description.endswith(" completed"):
                work.append((working.pop(number), time, 1))
        start = re.search(r"<TEACH-AIR-01,([01])> preparation started", description)
        end = re.search(r"<TEACH-AIR-01,([01])> preparation ended", description)
        if start:
            prep_start[int(start.group(1))] = time
        if end:
            prep_end[int(end.group(1))] = time
        if "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in description:
            mission_start = time
        if "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in description:
            mission_success = time
    failed = []
    count = 0
    last = 0.0
    low = high = 0
    for time, delta in events:
        failed.append((last, time, count))
        count += delta
        low = min(low, count)
        high = max(high, count)
        last = time
    failed.append((last, 36.0, count))
    prep = [(prep_start[n], prep_end[n], 1) for n in (0, 1)]
    ready_for_mission = [(prep_end[n], mission_start, 1) for n in (0, 1)]
    mission = [(mission_start, mission_success, 2)]
    return {"events": events, "failed": failed, "failed_at_horizon": count, "minimum_failed": low, "maximum_failed": high, "work": work, "wait": wait, "prep_start": prep_start, "prep_end": prep_end, "prep": prep, "ready_for_mission": ready_for_mission, "mission": mission, "mission_start": mission_start, "mission_success": mission_success, "unclosed_work": working, "unclosed_wait": waiting}


def ledger(label, actual, expected, tolerance=2e-4):
    check(label + " 72 contiguous half-hour bins", len(actual) == 72 and all(actual[index / 2]["ETINT"] == (index + 1) / 2 for index in range(72)))
    fields = set(actual[0]) - {"RID", "STID", "UNID", "SID", "STINT", "ETINT"}
    check(label + " field inventory", set(expected) <= fields)
    for field in sorted(fields):
        wanted = expected.get(field, {})
        if wanted is None:
            valid = all(actual[index / 2][field] is None for index in range(72))
        else:
            valid = all(isinstance(actual[index / 2][field], (int, float)) and abs(actual[index / 2][field] - wanted.get(index / 2, 0)) <= tolerance for index in range(72))
        check(label + " event-derived full " + field, valid)


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    parent, parent_unique = tables(read(PARENT))
    child, child_unique = tables(read(CHILD))
    parent_sha = "c334c1d6c0efa89f9ff70151a45180cac53b9ae05bf1a783219b566f41dbd62b"
    child_sha = "f05e8b157671eb95f96ed95f360d3e4dbcbc097e3508ba08511c0ab3799f13f7"
    check("accepted parent source and child source hashes", parent_unique and child_unique and len(parent) == len(child) == 32 and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_input_sha256"] == parent_sha and sha(CHILD) == sha(CHILD_RUN / "input.json") == contract["child_input_sha256"] == diff["child_input_sha256"] == child_sha)
    check("contract/diff identity and parent scope", contract["schema"] == "simlox-c10-clock-comparison-contract/v1" and contract["case_id"] == "C10" and contract["variant_id"] == "C10.var01" and contract["version"] == "1.0.0-candidate" and contract["parent_variant"] == "oper-no-spare" and contract["parent_native_run_id"] == PARENT_RUN.name and contract["publication_state"] == "not_published" and diff["schema"] == "simlox-c10-clock-comparison-diff/v1")
    check("accepted parent scope signoff", "accepted_bounded_cli_scope" in (PARENT_CASE / "cli-scope-signoff-2026-09-30.md").read_text(encoding="utf-8") and parent_sha in (PARENT_CASE / "cli-scope-signoff-2026-09-30.md").read_text(encoding="utf-8"))
    check("manual/dictionary fingerprints and field semantics", sha(MANUAL) == contract["source_manual_sha256"] and sha(DICTIONARY) == contract["source_dictionary_sha256"] and contract["source_manual_physical_pages"] == [221, 412, 416, 417, 754] and contract["source_dictionary_lines"] == [673, 679] and "OPERATION or CALENDAR" in DICTIONARY.read_text(encoding="utf-8-sig", errors="replace").splitlines()[676])
    changed = {name for name in parent | child if parent.get(name) != child.get(name)}
    before, after = row(parent["ResourceStationData"]), row(child["ResourceStationData"])
    check("exact two-table source delta", changed == {"ProblemDescription", "ResourceStationData"} and all(parent[name] == child[name] for name in parent if name not in changed) and {field for field in before | after if before.get(field) != after.get(field)} == {"RFTT"} and before["RFTT"] == "OPERATION" and after["RFTT"] == "CALENDAR")
    check("failure parameters and fixed mission retained", after["RMTBF"] == 0.5 and after["RMDT"] == 0.25 and after["SHPID"] is None and row(child["ResourceAllocation"])["RQTY"] == 2 and row(child["MissionPreparation"])["DURN"] == 0.5 and row(child["MissionType"])["NOS"] == row(child["MissionType"])["MNOS"] == 2 and row(child["Control"])["RSEED"] == "1" and row(child["Control"])["SIMPE"] == 36)

    results = {}
    for label, run, source_path, package, parent_path in (("operation", PARENT_RUN, PARENT, PARENT_CASE, CASE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"), ("calendar", CHILD_RUN, CHILD, CASE, PARENT)):
        prefix = label + ": "
        invocation = read(run / "invocation.json")
        closure = read(run / "closure.json")
        steps = read(run / "steps.json")
        check(prefix + "run identity/source", invocation["run_id"] == closure["run_id"] == run.name and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(parent_path) and invocation["case_id"] == "C10")
        check(prefix + "session0 SSH/mutex/GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and all(step["gui_preserved"] is True for step in steps))
        sealed = {"input": run / "input.json", "parent": parent_path, "contract": package / "contract.json", "builder": package / "build.py", "checker": package / "check_roundtrip.py", "runner_script": package / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
        before_seals = invocation["source_hashes_before"]
        check(prefix + "current source/runtime bytes match frozen seals", all(path.exists() and sha(path) == before_seals[name] for name, path in sealed.items()))
        check(prefix + "closure source and invocation seals", closure["source_hashes_before"] == closure["source_hashes_after"] == before_seals and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[key + "_sha256"] == before_seals[key] for key in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == before_seals["python"])
        raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "complete raw inventory", raw_names == set(closure["raw"]))
        for filename, metadata in closure["raw"].items():
            path = run / filename
            check(prefix + "raw byte seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
        check(prefix + "five ordered successful steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None and timestamp(step["started_utc"]) <= timestamp(step["completed_utc"]) for step in steps) and all(timestamp(steps[index]["completed_utc"]) <= timestamp(steps[index + 1]["started_utc"]) for index in range(4)))
        check(prefix + "planned command arguments executed", all(steps[index]["arguments"] == invocation["planned_commands"][index]["arguments"] for index in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"])
        original, original_unique = tables(read(run / "input.json"))
        exported, exported_unique = tables(read(run / "roundtrip-raw.json"))
        populated = {name for name in original if rows(original[name])}
        placeholders = {name for name in populated if all(all(value is None for value in record) for record in rows(original[name]))}
        check(prefix + "21 populated tables and 3 null placeholders", original_unique and exported_unique and len(populated) == 21 and placeholders == {"ControlParameters", "GlobalParameters", "OperationParameter"})
        for name in sorted(populated):
            check(prefix + "exact native roundtrip " + name, original[name] == exported.get(name))
        converted = (run / "run.log").read_text(errors="replace")
        check(prefix + "zero errors/warnings108,126 and report", "Number of forms inserted: 32" in (run / "import.log").read_text(errors="replace") and "Import completed!" in (run / "import.log").read_text(errors="replace") and "Export completed!" in (run / "export.log").read_text(errors="replace") and "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted and "Generating Json-report" in (run / "report-export.log").read_text(errors="replace") and (run / "model.sxo").stat().st_size > 4)
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        timeline = parse_timeline(log)
        check(prefix + "balanced task intervals and pool bounds", not timeline["unclosed_work"] and not timeline["unclosed_wait"] and timeline["minimum_failed"] == 0 and timeline["maximum_failed"] <= 2 and timeline["prep_start"] == {0: 7.5, 1: 7.5})
        report_doc, removed = native_report(run / "report-raw.json")
        report, report_unique = tables(report_doc, "report")
        check(prefix + "six parsed report tables", removed > 0 and report_unique and set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"})
        results[label] = {"log": log, "timeline": timeline, "report": report, "run": run}

    operation = results["operation"]
    calendar = results["calendar"]
    op_t = operation["timeline"]
    cal_t = calendar["timeline"]
    check("operation parent has no failure before 7.5", len(op_t["events"]) == 2 and op_t["events"][0] == (7.73494, 1) and op_t["events"][1] == (7.98494, -1) and op_t["failed_at_horizon"] == 0)
    check("calendar has 15 idle failures before 7.5", sum(delta == 1 and time < 7.5 for time, delta in cal_t["events"]) == 15 and cal_t["events"][0] == (0.234939, 1) and cal_t["events"][1] == (0.484939, -1) and all(time >= 7.5 for time, _ in op_t["events"]))
    check("calendar event counts and failed terminal crew", len(cal_t["events"]) == 165 and sum(delta == 1 for _, delta in cal_t["events"]) == 83 and sum(delta == -1 for _, delta in cal_t["events"]) == 82 and cal_t["failed_at_horizon"] == 1 and cal_t["events"][-1] == (35.9999, -1))
    check("operation active failure/wait and mission", op_t["work"] == [(7.5, 7.73494, 1), (7.5, 8.0, 1), (7.98494, 8.25, 1)] and op_t["wait"] == [(7.73494, 7.98494, 1)] and op_t["prep_end"] == {0: 8.25, 1: 8.0} and op_t["mission_start"] == 8.25 and op_t["mission_success"] == 9.25)
    check("calendar active failures/waits and delayed mission", cal_t["work"] == [(7.5, 7.57305, 1), (7.5, 7.78534, 1), (7.82305, 8.02239, 1), (8.03534, 8.05066, 1), (8.05066, 8.47761, 1)] and sorted(cal_t["wait"]) == [(7.57305, 8.05066, 1), (7.78534, 7.82305, 1), (8.02239, 8.03534, 1)] and cal_t["prep_end"] == {0: 8.47761, 1: 8.05066} and cal_t["mission_start"] == 8.47761 and cal_t["mission_success"] == 9.47761)
    check("both missions succeed and terminal aircraft ready", all("mission cancelled" not in result["log"] and "mission success:" in result["log"] and "systems ready: 2" in result["log"] for result in results.values()))

    for label, result in results.items():
        tag = label + ": "
        timeline, report = result["timeline"], result["report"]
        summary, total = row(report["ResultSummary"]), row(report["ResourceResultsTotal"])
        work = sum((right - left) * count for left, right, count in timeline["work"])
        wait = sum((right - left) * count for left, right, count in timeline["wait"])
        failed = sum((right - left) * count for left, right, count in timeline["failed"])
        check(tag + "summary and event-integrated totals", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1 and total["NR"] == total["NRN"] == 2 and abs(total["NRUM"] * 36 - work) < 2e-4 and abs(total["NRW"] * 36 - wait) < 2e-4 and abs(total["NRF"] * 36 - failed) < 2e-4)
        resource = bins(report["ResourceResults"])
        system = bins(report["SystemResults"])
        stock = bins(report["StockTotalResults"])
        work_bins = averages(timeline["work"])
        wait_bins = averages(timeline["wait"])
        fail_bins = averages(timeline["failed"])
        prep_bins = averages(timeline["prep"])
        ready_bins = averages(timeline["ready_for_mission"])
        mission_bins = averages(timeline["mission"])
        active_bins = {hour: prep_bins[hour] + ready_bins[hour] + mission_bins[hour] for hour in work_bins}
        expected_resource = {"NR": {index / 2: 2 for index in range(72)}, "NRN": {index / 2: 2 for index in range(72)}, "NRUM": work_bins, "NRW": wait_bins, "NRF": fail_bins, "NRA": {hour: 2 - value for hour, value in fail_bins.items()}}
        expected_system = {"NSYRY": {hour: 2 - value for hour, value in active_bins.items()}, "NSYMA": active_bins, "NSYMP": prep_bins, "NSYMR": ready_bins, "NSYMO": mission_bins, "NSYA": {index / 2: 2 for index in range(72)}, "FTMO": {hour: value / 2 for hour, value in mission_bins.items()}, "STACC": mission_bins, "SYDT": None, "NPSTA": point_events(timeline["prep_start"].values()), "NPSUC": point_events(timeline["prep_end"].values())}
        ledger(tag + "ResourceResults", resource, expected_resource)
        ledger(tag + "SystemResults", system, expected_system)
        ledger(tag + "StockTotalResults", stock, {"PNB": {index / 2: 1 for index in range(72)}, "NBOU": None, "ROS": None, "ROST": None, "WT": None, "WTT": None, "WTS": None})
        check(tag + "terminal report and failure distinction", system[35.5]["NSYRY"] == 2 and resource[35.5]["NR"] == resource[35.5]["NRN"] == 2 and resource[35.5]["NRUM"] == resource[35.5]["NRW"] == 0 and (resource[35.5]["NRF"] > 1 if label == "calendar" else resource[35.5]["NRF"] == 0))

    check("clock contrast in resource failures and waiting", row(calendar["report"]["ResourceResultsTotal"])["NRF"] > row(operation["report"]["ResourceResultsTotal"])["NRF"] and row(calendar["report"]["ResourceResultsTotal"])["NRW"] > row(operation["report"]["ResourceResultsTotal"])["NRW"] and row(calendar["report"]["ResourceResultsTotal"])["NRUM"] == row(operation["report"]["ResourceResultsTotal"])["NRUM"])

    if (CASE / "evidence-index.json").exists():
        evidence = read(CASE / "evidence-index.json")
        entries = [entry for entry in evidence["runs"] if entry["run_id"] == CHILD_RUN.name]
        parent_entry = evidence["parent_run"]
        check("calendar evidence index pinned identity", sha(CASE / "evidence-index.json") == "4d87e68a7cbae366f85c6aa23c718ab1ac1fe41bac252c4de0cc699f0c267134" and evidence["schema"] == "simlox-c10-clock-comparison-evidence-index/v1" and evidence["relative_raw_root"] == "runs/" and evidence["raw_publication"] == "local_sealed_not_committed" and len(entries) == len(evidence["runs"]) == 1 and evidence["source_manual_sha256"] == sha(MANUAL) and evidence["source_dictionary_sha256"] == sha(DICTIONARY) and evidence["simlox_exe_sha256"] == sha(EXE))
        check("calendar index accepted parent raw linkage", parent_entry["run_id"] == PARENT_RUN.name and Path(parent_entry["original_run_dir"]).resolve() == PARENT_RUN.resolve() and parent_entry["parent_package"] == PARENT_CASE.name and parent_entry["closure_sha256"] == sha(PARENT_RUN / "closure.json") and parent_entry["model_log_sha256"] == sha(PARENT_RUN / "model.log") and parent_entry["report_raw_sha256"] == sha(PARENT_RUN / "report-raw.json"))
        accepted_index = read(PARENT_CASE / "evidence-index.json")
        accepted_entries = [entry for entry in accepted_index["runs"] if entry["run_id"] == PARENT_RUN.name]
        check("accepted parent index pinned and full raw reconciliation", sha(PARENT_CASE / "evidence-index.json") == "a88318e208ba60419287de08f490865de9bc82f72ed22d4518a8f4a01087df88" and len(accepted_entries) == 1 and accepted_entries[0]["raw"] == read(PARENT_RUN / "closure.json")["raw"] == {name: {"bytes": (PARENT_RUN / name).stat().st_size, "sha256": sha(PARENT_RUN / name)} for name in read(PARENT_RUN / "closure.json")["raw"]})
        if entries:
            entry = entries[0]
            closure = read(CHILD_RUN / "closure.json")
            check("calendar evidence index raw hashes", entry["variant"] == "calendar-two-crew" and Path(entry["original_run_dir"]).resolve() == CHILD_RUN.resolve() and entry["input_sha256"] == sha(CHILD_RUN / "input.json") and entry["closure_sha256"] == sha(CHILD_RUN / "closure.json") and entry["run_log_sha256"] == sha(CHILD_RUN / "run.log") and entry["model_log_sha256"] == sha(CHILD_RUN / "model.log") and entry["report_raw_sha256"] == sha(CHILD_RUN / "report-raw.json") and entry["raw"] == closure["raw"] == {name: {"bytes": (CHILD_RUN / name).stat().st_size, "sha256": sha(CHILD_RUN / name)} for name in closure["raw"]})

    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1", "case_id": "C10.var01.calendar_operation_clock", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_calendar_vs_operation_clock" if not failures else "NO_GO",
        "accepted_scope": "With only ResourceStationData.RFTT changed, the fixed-seed calendar trace contains 15 P-CREW failures before the 7.5 preparations, whereas the operation-time parent has none. Calendar failures interrupt both preparations, delaying mission to 8.47761-9.47761; operation-time failure interrupts one, delaying mission to 8.25-9.25. Both succeed and return two aircraft ready. The calendar trace ends with one crew failed at hour 36.",
        "metric_interpretation": "Resource work/wait/failure and system preparation/ready/mission occupancy in every half-hour report bin are reconstructed from raw event intervals, allowing 0.0002 on bin averages for printed timestamp rounding. Other numeric/null fields and all stock bins are checked directly. NRF is failed-resource exposure, not a count of distinct crew.",
        "limits": ["One seed, one 0.5-hour MTBF, one 0.25-hour MDT, one 36-hour schedule and this executable. The log labels the P-CREW pool, not individual workers or internal clock counters; the conclusion is the observed timing contrast.", "Other seeds, off-shift spare behavior, GUI visuals and cross-engine equivalence remain unverified. Session/GUI/queue claims are replayed from sealed metadata; no native rerun."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
