"""Independent standard-library read-only replay of the C08 MAXUT run."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PREVIOUS = CASE.parent / "C07-repeat-nested-v1.0.0"
PARENT = PREVIOUS / "explicit-input.json"
CONTROL = PREVIOUS / "runs" / "c07-explicit-pair-20260930-01"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
RUN_ID = "c08-maxut-one-20260930-01"
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_report(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = escaped = False
    removed = 0
    for pos, char in enumerate(raw):
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
        elif char == "," and raw[pos + 1 :].lstrip().startswith(("}", "]")):
            removed += 1
        else:
            output.append(char)
    return json.loads("".join(output)), removed


def check(name, passed, detail=None):
    item = {"name": name, "passed": bool(passed)}
    if detail is not None:
        item["detail"] = detail
    CHECKS.append(item)


def tables(document, root="model"):
    sequence = document[root]["tables"]
    names = [table["name"] for table in sequence]
    return {table["name"]: table for table in sequence}, len(names) == len(set(names))


def rows(table):
    return [entry for instance in table["instances"] for entry in instance["rows"]]


def columns(table):
    return [column["name"] for column in table["columns"]]


def row(table):
    return dict(zip(columns(table), rows(table)[0]))


def bins(table):
    return {entry["STINT"]: entry for entry in (dict(zip(columns(table), source_row)) for source_row in rows(table))}


def series(ranges):
    wanted = {}
    for start, end, value in ranges:
        for half in range(int(start * 2), int(end * 2) + 1):
            wanted[half / 2] = value
    return wanted


def subtask(aircraft):
    return f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    source_path = CASE / "maxut-one-input.json"
    run = CASE / "runs" / RUN_ID
    parent, unique_parent = tables(load(PARENT))
    source, unique_source = tables(load(source_path))
    check("accepted C07 explicit parent fingerprint", unique_parent and len(parent) == 35 and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_sha256"] == "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e" and sha(CONTROL / "input.json") == sha(PARENT))
    check("contract identity and unpublished candidate", contract["schema"] == "simlox-c08-shift-maxut-contract/v1" and contract["case_id"] == "C08" and contract["variant_id"] == "C08.var02" and contract["version"] == "1.0.0-candidate" and contract["parent_publication_id"] == "C07.var04.repeat_nested_two_window.1.0.0" and contract["publication_state"] == "not_published")
    check("manual fingerprint and physical pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_physical_pages"] == [422, 423])
    check("unique 35-table source and frozen child SHA", unique_source and len(source) == 35 and sha(source_path) == sha(run / "input.json") == contract["input_sha256"] == diff["child_sha256"] == "00e660275ace4d71d41cdafa725da2b552baeea9604756d94ad6b07de846e9d5")
    changed = {name for name in parent | source if parent.get(name) != source.get(name)}
    check("exact two-table parent delta", changed == set(diff["changed_tables"]) == {"ProblemDescription", "ShiftResource"} and diff["unchanged_table_count"] == 33, sorted(changed))
    check("every unlisted parent table unchanged", all(parent.get(name) == source.get(name) for name in parent | source if name not in changed))
    parent_resource, child_resource = row(parent["ShiftResource"]), row(source["ShiftResource"])
    check("MAXUT alone changes unset to one hour", {name for name in parent_resource | child_resource if parent_resource.get(name) != child_resource.get(name)} == {"MAXUT"} and parent_resource["MAXUT"] is None and child_resource["MAXUT"] == 1 and child_resource["QTY"] == 2 and child_resource["STID"] == "BASE-01" and child_resource["RID"] == "P-CREW")
    check("description and retained explicit schedule", rows(source["ProblemDescription"]) == [["C08 shift MAXUT one hour per crew; DRAOS=N"]] and rows(source["ShiftProfile"]) == [["CREW-DAY", "DAY-OPEN", 23, 25, 1, None, None], ["CREW-DAY", "DAY-OPEN", 26, 28, 1, None, None]] and rows(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]] and row(source["Control"])["DRAOS"] == "N")

    invocation = load(run / "invocation.json")
    closure = load(run / "closure.json")
    steps = load(run / "steps.json")
    check("invocation run identity/path/source", invocation["case_id"] == "C08" and invocation["variant"] == "maxut-one" and invocation["run_id"] == closure["run_id"] == RUN_ID and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(PARENT))
    check("session-zero SSH and queue mutex", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    check("GUI identity preserved across steps", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
    paths = {"input": run / "input.json", "parent": PARENT, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
    seals = invocation["source_hashes_before"]
    check("all current source/runtime bytes match frozen before seals", all(path.exists() and sha(path) == seals[name] for name, path in paths.items()))
    check("before/after seals and invocation hash", closure["source_hashes_before"] == closure["source_hashes_after"] == seals and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[name + "_sha256"] == seals[name] for name in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == seals["python"])
    raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
    check("complete raw file inventory", raw_names == set(closure["raw"]))
    for filename, metadata in closure["raw"].items():
        path = run / filename
        check("raw byte seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
    evidence = load(CASE / "evidence-index.json")
    check("evidence index pinned bytes and identity", sha(CASE / "evidence-index.json") == "e40eed162902fbe50055618f0cc1495895e77264c98fa5e876618e2567cd50bc" and evidence["schema"] == "simlox-c08-shift-maxut-evidence-index/v1" and evidence["relative_raw_root"] == "runs/" and evidence["raw_publication"] == "local_sealed_not_committed" and evidence["excluded_diagnostic_run"] is None and len(evidence["runs"]) == 1)
    indexed = evidence["runs"][0]
    check("evidence index run and runtime fingerprints", indexed["variant"] == "maxut-one" and indexed["run_id"] == RUN_ID and Path(indexed["original_run_dir"]).resolve() == run.resolve() and indexed["input_sha256"] == sha(run / "input.json") and indexed["closure_sha256"] == sha(run / "closure.json") and indexed["run_log_sha256"] == sha(run / "run.log") and indexed["model_log_sha256"] == sha(run / "model.log") and indexed["report_raw_sha256"] == sha(run / "report-raw.json") and evidence["source_manual_sha256"] == sha(MANUAL) and evidence["simlox_exe_sha256"] == sha(EXE))
    check("evidence index complete raw byte reconciliation", indexed["raw"] == closure["raw"] == {name: {"bytes": (run / name).stat().st_size, "sha256": sha(run / name)} for name in raw_names})
    check("five ordered successful steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps))
    check("planned commands and step chronology", all(steps[i]["arguments"] == invocation["planned_commands"][i]["arguments"] for i in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"] and all(stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))

    original, original_unique = tables(load(run / "input.json"))
    roundtrip, roundtrip_unique = tables(load(run / "roundtrip-raw.json"))
    populated = {name for name, table in original.items() if rows(table)}
    all_null_placeholders = {name for name in populated if all(all(value is None for value in entry) for entry in rows(original[name]))}
    check("24 row-containing source tables and three all-null placeholders", original_unique and roundtrip_unique and len(populated) == 24 and all_null_placeholders == {"ControlParameters", "GlobalParameters", "OperationParameter"})
    for name in sorted(populated):
        check("exact native roundtrip " + name, original[name] == roundtrip.get(name))
    check("MAXUT one-hour row survives native roundtrip", row(roundtrip["ShiftResource"])["MAXUT"] == 1)
    imported = (run / "import.log").read_text(errors="replace")
    exported = (run / "export.log").read_text(errors="replace")
    converted = (run / "run.log").read_text(errors="replace")
    check("35-form import/export complete", "Number of forms inserted: 35" in imported and "Import completed!" in imported and "Export completed!" in exported)
    check("zero converter errors, known warnings #108/#126", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted)
    check("JSON report export complete and nonempty result", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace") and (run / "model.sxo").stat().st_size > 4)

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (CONTROL / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    check("nonempty log and one two-aircraft mission", len(log) > 1000 and log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1 and log.count("mission allocates system:") == 2)
    check("MAXUT changes event log from explicit control", sha(run / "model.log") != sha(CONTROL / "model.log") and "is stopped due to resource time-out" in log and "is stopped due to resource time-out" not in parent_log)
    check("23-25 and 26-28 shift events and capacity two", all(f"Time: {hour}  resource shift {shift} starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW {capacity}" in log for hour, shift, capacity in ((0, 0, 0), (23, 1, 2), (25, 2, 0), (26, 3, 2), (28, 4, 0))))
    check("utilization pool times out at 24.5", "Time: 24.5  <P-CREW at <BASE-01,0>> out of utilisation time" in log)
    for aircraft in (0, 1):
        sub = subtask(aircraft)
        check(f"aircraft {aircraft} positive work 23.5-24.5", f"Time: 23.5  {sub} started" in log and f"Time: 23.5  {sub} starts performing, planned to last for 2 hours" in log)
        check(f"aircraft {aircraft} time-out at 24.5 with one hour left", f"Time: 24.5  {sub} resource availability test\n  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed" in log and f"Time: 24.5  {sub} is stopped due to resource time-out, time left= 1" in log)
        check(f"aircraft {aircraft} next-shift reset and resume at 26", f"Time: 26  {sub} resource received" in log and f"Time: 26  {sub} starts performing, planned to last for 1 hours" in log)
        check(f"aircraft {aircraft} completes at 27", f"Time: 27  {sub} completed" in log and f"Time: 27  {sub} frees resources" in log and f"Time: 27 <TEACH-AIR-01,{aircraft}> preparation ended" in log)
    check("typed crew bookings and returns", log.count("<P-CREW at <BASE-01,0>> allocated to maintenance task: 1") == 4 and log.count("<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1") == 2)
    check("mission succeeds28-29; terminal ready2", "Time: 28 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and "mission cancelled" not in log and "Time: 29 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :" in log)

    report, removed = load_report(run / "report-raw.json")
    rt, report_unique = tables(report, "report")
    control_report, control_removed = load_report(CONTROL / "report-raw.json")
    control_rt, control_unique = tables(control_report, "report")
    check("six report tables and structural parse", report_unique and control_unique and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0 and control_removed > 0)
    changed_report = {name for name in rt | control_rt if rt.get(name) != control_rt.get(name)}
    check("control comparison limited to timing/resource and description", changed_report == {"ProblemDescription", "ResourceResults", "ResourceResultsTotal", "SystemResults"} and rt["ResultSummary"] == control_rt["ResultSummary"] and rt["StockTotalResults"] == control_rt["StockTotalResults"], sorted(changed_report))
    summary = row(rt["ResultSummary"])
    check("one successful mission summary", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1)
    total = row(rt["ResourceResultsTotal"])
    control_total = row(control_rt["ResourceResultsTotal"])
    check("four work hours, three wait hours versus control two", total["NR"] == total["NRN"] == 2 and abs(total["NRUM"] * 36 - 4) < 1e-5 and abs(total["NRW"] * 36 - 3) < 1e-5 and abs(control_total["NRUM"] * 36 - 4) < 1e-5 and abs(control_total["NRW"] * 36 - 2) < 1e-5 and total["NRMA"] == total["NRMO"] == 0)
    resource = bins(rt["ResourceResults"])
    system = bins(rt["SystemResults"])
    stock = bins(rt["StockTotalResults"])
    check("72 complete half-hour bins", all(len(ledger) == 72 and all(ledger[i / 2]["ETINT"] == (i + 1) / 2 for i in range(72)) for ledger in (resource, system, stock)))
    expected = {
        "NRUM": (resource, series([(23.5, 24, 2), (26, 26.5, 2)])),
        "NRW": (resource, series([(24.5, 25.5, 2)])),
        "NRA": (resource, series([(23, 24, 2), (26, 27.5, 2)])),
        "NSYRY": (system, series([(0, 23, 2), (29, 35.5, 2)])),
        "NSYMA": (system, series([(23.5, 28.5, 2)])),
        "NSYMP": (system, series([(23.5, 26.5, 2)])),
        "NSYMO": (system, series([(28, 28.5, 2)])),
    }
    for field, (ledger, wanted) in expected.items():
        check("exact 72-bin " + field + " ledger", all(abs(ledger[i / 2][field] - wanted.get(i / 2, 0)) < 1e-6 for i in range(72)))
    check("at most two crew-hours per shift from bins", sum(resource[hour]["NRUM"] * 0.5 for hour in (23, 23.5, 24, 24.5)) == 2 and sum(resource[hour]["NRUM"] * 0.5 for hour in (26, 26.5, 27, 27.5)) == 2)
    check("resource count two and zero mission booking", all(resource[i / 2]["NR"] == resource[i / 2]["NRN"] == 2 and resource[i / 2]["NRMA"] == resource[i / 2]["NRMO"] == 0 for i in range(72)))
    check("zero stock movement and terminal ready2", all(all(stock[i / 2][field] == 0 for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for i in range(72)) and resource[35.5]["NRUM"] == resource[35.5]["NRW"] == 0 and system[35.5]["NSYRY"] == 2)

    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1", "case_id": "C08.var02.shift_maxut", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_one_hour_per_crew_shift_maxut" if not failures else "NO_GO",
        "accepted_scope": "For this fixed-seed two-crew, two-window ShiftResource.MAXUT=1 input, both aircraft work 23.5-24.5, stop from resource time-out with one hour left each, resume with the next shift at 26, finish at 27 and complete the 28-29 mission. The MAXUT field is the only business source change from the accepted explicit control.",
        "metric_interpretation": "The report shows four crew-hours of positive work, two in each active shift. ResourceResults.NRW records three resource-hours of waiting, one more than the accepted control's two; it is not booked work. All 72 half-hour resource/system/stock bins and terminal readiness are checked.",
        "limits": ["One fixed-seed two-crew two-window MAXUT input on this installed executable. Daily MUTILF, station override, partial-pool utilization, exact-limit completion and general MAXUT policy remain unverified.", "SSH/GUI/queue continuity is replayed from sealed metadata; the reviewer did not rerun native SIMLOX."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
