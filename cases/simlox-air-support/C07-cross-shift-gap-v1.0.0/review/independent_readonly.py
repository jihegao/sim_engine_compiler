"""Independent read-only standard-library replay of sealed C07 cross-shift runs."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "C07-offshift-boundary-v1.0.0" / "draos-y-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
RUNS = {"Y": "c07-cross-y-20260930-01", "N": "c07-cross-n-20260930-01"}
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def tables(doc, root="model"):
    sequence = doc[root]["tables"]
    keys = [table["name"] for table in sequence]
    return {table["name"]: table for table in sequence}, len(keys) == len(set(keys))


def rows(table):
    return [entry for instance in table["instances"] for entry in instance["rows"]]


def fields(table):
    return [column["name"] for column in table["columns"]]


def row(table):
    return dict(zip(fields(table), rows(table)[0]))


def intervals(table):
    return {item["STINT"]: item for item in (dict(zip(fields(table), entry)) for entry in rows(table))}


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def expected_series(chunks):
    out = {}
    for start, end, value in chunks:
        for half in range(int(start * 2), int(end * 2) + 1):
            out[half / 2] = value
    return out


def subtask(aircraft):
    return f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    parent, unique_parent = tables(load(PARENT))
    check("accepted C07 offshift Y parent fingerprint", unique_parent and len(parent) == 35 and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_sha256"] == "fc7ca3caeefee1190a8497c8e5a32a463a96d17c426d4d97ee57673b49405a94")
    check("contract identity and candidate state", contract["schema"] == "simlox-c07-cross-shift-contract/v1" and contract["case_id"] == "C07" and contract["version"] == "1.0.0-candidate" and contract["parent_case"] == "C07.var01.first_day_offshift_draos.1.0.0" and contract["publication_state"] == "not_published")
    check("manual fingerprint and source pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_pages"] == [227, 418, 419, 420, 421, 422, 423])
    check("declared pair change scope", set(contract["changed_tables_within_pair"]) == set(diff["pair_changed_tables"]) == {"Control", "ProblemDescription"})
    sources = {}
    results = {}
    index_path = CASE / "evidence-index.json"
    index = load(index_path) if index_path.exists() else None
    if index is not None:
        index_entries = {entry["variant"]: entry for entry in index["runs"]}
        check("evidence index identity and unique Y/N entries", index["schema"] == "simlox-c07-cross-shift-evidence-index/v1" and index["relative_raw_root"] == "runs/" and index["raw_publication"] == "local_sealed_not_committed" and len(index["runs"]) == len(index_entries) == 2 and set(index_entries) == {"draos-y", "draos-n"})
        previous_contract = load(CASE.parent / "C07-offshift-boundary-v1.0.0" / "contract.json")
        check("evidence index manual/native hashes and dictionary declaration", index["source_manual_sha256"] == sha(MANUAL) and index["source_dictionary_sha256"] == previous_contract["source_dictionary_sha256"] and index["simlox_exe_sha256"] == sha(EXE))
    else:
        index_entries = {}

    for choice, run_id in RUNS.items():
        variant = "draos-" + choice.lower()
        tag = choice + ": "
        source_path = CASE / f"{variant}-input.json"
        run = CASE / "runs" / run_id
        source, unique = tables(load(source_path))
        sources[choice] = source
        check(tag + "unique 35-table source", unique and len(source) == 35)
        check(tag + "frozen source and run byte identity", sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant] == diff["children"][choice]["sha256"])
        changed = {name for name in parent | source if parent.get(name) != source.get(name)}
        check(tag + "exact parent table delta", changed == set(diff["children"][choice]["changed_tables"]), sorted(changed))
        check(tag + "every unlisted parent table unchanged", all(parent.get(name) == source.get(name) for name in parent | source if name not in changed))
        check(tag + "description and exact DRAOS delta", rows(source["ProblemDescription"]) == [[f"C07 long crew work across 08-09 shift and 09-10 gap; DRAOS={choice}"]] and {key for key in row(parent["Control"]) | row(source["Control"]) if row(parent["Control"]).get(key) != row(source["Control"]).get(key)} == (set() if choice == "Y" else {"DRAOS"}) and row(source["Control"])["DRAOS"] == choice)
        check(tag + "two explicit one-crew shifts with positive gap", rows(source["ShiftProfile"]) == [["CREW-DAY", "DAY-OPEN", 8, 9, 1, None, None], ["CREW-DAY", "DAY-OPEN", 10, 11, 1, None, None]] and rows(source["ShiftResource"]) == [["DAY-OPEN", "BASE-01", "P-CREW", 1, None, None]] and rows(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]])
        check(tag + "two-hour INSPECT source and 12-hour mission", rows(source["TaskBreakDown"]) == [["PREP-FIXED", 1, "INSPECT", 2, None, None]] and rows(source["MissionPreparation"]) == [["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 2, "PREP-FIXED", None, None]] and row(source["OperationProfile"])["STIM"] == 12 and rows(source["SubTaskResource"]) == rows(parent["SubTaskResource"]))
        check(tag + "exact mission, schedule, and task source rows", rows(source["MissionType"]) == [["BASIC-MISSION", "One-hour two-aircraft shared-crew formation", 2, 2, None, 1, None, 1, 0.25, 0.25, None, 1, 4.5, None, None, None, None]] and rows(source["OperationProfile"]) == [["BASIC-SCHEDULE", "BASIC-MISSION", 12, "SCHEDULED", 1, None, 0, None, 1, None, None, None]] and rows(source["Tasks"]) == [["PREP-FIXED", "Two-hour crew-dependent mission preparation", None, None, None]])

        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(tag + "invocation identity and original path", invocation["case_id"] == "C07" and invocation["variant"] == variant and invocation["run_id"] == closure["run_id"] == run_id and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(PARENT))
        check(tag + "session-zero SSH and mutex guard", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(tag + "GUI identity preserved", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
        paths = {"input": run / "input.json", "parent": PARENT, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
        seals = invocation["source_hashes_before"]
        check(tag + "current source and runtime hashes equal frozen before seals", all(path.exists() and sha(path) == seals[key] for key, path in paths.items()))
        check(tag + "before/after source seals and invocation hash", closure["source_hashes_before"] == closure["source_hashes_after"] == seals and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[key + "_sha256"] == seals[key] for key in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == seals["python"])
        raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(tag + "complete sealed raw inventory", raw_names == set(closure["raw"]))
        for filename, meta in closure["raw"].items():
            path = run / filename
            check(tag + "raw byte seal " + filename, path.exists() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"])
        check(tag + "five ordered successful steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps))
        check(tag + "planned command equality and step chronology", all(steps[i]["arguments"] == invocation["planned_commands"][i]["arguments"] for i in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"] and all(stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))
        original, unique_original = tables(load(run / "input.json"))
        roundtrip, unique_roundtrip = tables(load(run / "roundtrip-raw.json"))
        populated = {name for name, table in original.items() if rows(table)}
        check(tag + "24 populated tables and unique roundtrip", unique_original and unique_roundtrip and len(populated) == 24)
        for name in sorted(populated):
            check(tag + "exact native roundtrip " + name, original[name] == roundtrip.get(name))
        imported = (run / "import.log").read_text(errors="replace")
        exported = (run / "export.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(tag + "35-form import/export", "Number of forms inserted: 35" in imported and "Import completed!" in imported and "Export completed!" in exported)
        check(tag + "zero conversion errors and two known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted)
        check(tag + "JSON report export", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check(tag + "one mission orders two systems", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1 and log.count("mission allocates system:") == 2)
        check(tag + "explicit 8-9 and 10-11 shift transitions", all(f"Time: {time}  resource shift {number} starting at <P-CREW at <BASE-01,0>>" in log for time, number in ((8, 1), (9, 2), (10, 3), (11, 4))))
        offshift = 2 if choice == "Y" else 0
        check(tag + "off-shift gap crew capacity", f"Time: 0  resource shift 0 starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW {offshift}" in log and f"Time: 9  resource shift 2 starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW {offshift}" in log)
        check(tag + "one-crew active shifts", all(f"Time: {time}  resource shift {number} starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW 1" in log for time, number in ((8, 1), (10, 3))))
        for aircraft in (0, 1):
            sub = subtask(aircraft)
            check(tag + f"aircraft {aircraft} prep request at 7.5", f"Time: 7.5  {sub} started" in log and f"Time: 7.5  {sub} requests resources" in log)
            check(tag + f"aircraft {aircraft} initial off-shift test", f"Time: 7.5  {sub} resource availability test\n  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 {'OK' if choice == 'Y' else 'failed'}" in log)
        a0, a1 = subtask(0), subtask(1)
        if choice == "Y":
            check(tag + "aircraft 0 continuous positive work through shift/gap", all(f"Time: {time}  {a0} starts performing, planned to last for {duration} hours" in log for time, duration in ((7.5, 2), (8, 1.5), (9, 0.5))) and f"Time: 9.5  {a0} completed" in log and f"Time: 9.5 <TEACH-AIR-01,0> preparation ended" in log)
            check(tag + "aircraft 1 positive work, shift stop, gap resumption", f"Time: 7.5  {a1} starts performing, planned to last for 2 hours" in log and f"Time: 8  {a1} is stopped due to shift change, time left= 1.5" in log and f"Time: 9  {a1} resource received" in log and f"Time: 9  {a1} starts performing, planned to last for 1.5 hours" in log and f"Time: 10  {a1} starts performing, planned to last for 0.5 hours" in log and f"Time: 10.5  {a1} completed" in log)
            check(tag + "mission launches 12 and succeeds 13", "Time: 12 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 13 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "Time: 13 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and "mission cancelled" not in log)
            check(tag + "typed crew bookings at gap and returns", log.count("<P-CREW at <BASE-01,0>> allocated to maintenance task: 1") == 6 and log.count("<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1") == 2)
            results[choice] = {"aircraft_0": "works 7.5-9.5", "aircraft_1": "works 7.5-8, stops with 1.5h left, resumes 9-10.5", "mission": "success 12-13"}
        else:
            check(tag + "aircraft 0 positive work, gap stop and resume", f"Time: 8  {a0} starts performing, planned to last for 2 hours" in log and f"Time: 9  {a0} is stopped due to shift change, time left= 1" in log and f"Time: 10  {a0} resource received" in log and f"Time: 10  {a0} starts performing, planned to last for 1 hours" in log and f"Time: 11  {a0} completed" in log)
            check(tag + "aircraft 1 zero-progress booking at 11", f"Time: 11  {a1} resource received" in log and f"Time: 11  {a1} starts performing, planned to last for 2 hours" in log and f"Time: 11  {a1} is stopped due to shift change, time left= 2" in log and f"Time: 13  {a1} resource waiting stopped" in log and f"Time: 13  {a1} stopped" in log and f"Time: 11  {a1} completed" not in log)
            check(tag + "mission cancels at 13 with no launch", "Time: 13 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:" in log and "mission starting" not in log and "mission success" not in log and "mission completed" not in log)
            check(tag + "typed crew booking/release around interrupted work", log.count("<P-CREW at <BASE-01,0>> allocated to maintenance task: 1") == 3 and log.count("<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1") == 1)
            results[choice] = {"aircraft_0": "works 8-9, stops with 1h left, resumes 10-11", "aircraft_1": "books and starts at 11 but stops same timestamp with 2h left", "mission": "cancelled 13"}
        check(tag + "both aircraft terminal ready at 13", "Time: 13 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :" in log and "<TEACH-AIR-01,0>" in log and "<TEACH-AIR-01,1>" in log)

        report, removed = load_report(run / "report-raw.json")
        rt, unique_report = tables(report, "report")
        check(tag + "six report tables and structural parse", unique_report and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
        summary = row(rt["ResultSummary"])
        success = 1 if choice == "Y" else 0
        check(tag + "mission summary matches outcome", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == success)
        resource_total = row(rt["ResourceResultsTotal"])
        work_hours, wait_hours = (4, 1) if choice == "Y" else (2, 7)
        check(tag + "total resource work and waiting", resource_total["NR"] == resource_total["NRN"] == 2 and abs(resource_total["NRUM"] * 36 - work_hours) < 1e-5 and abs(resource_total["NRW"] * 36 - wait_hours) < 1e-5 and resource_total["NRMA"] == resource_total["NRMO"] == 0)
        resource = intervals(rt["ResourceResults"])
        system = intervals(rt["SystemResults"])
        stock = intervals(rt["StockTotalResults"])
        check(tag + "72 complete half-hour bins", all(len(ledger) == 72 and all(ledger[i / 2]["ETINT"] == (i + 1) / 2 for i in range(72)) for ledger in (resource, system, stock)))
        if choice == "Y":
            expected_use = expected_series([(7.5, 7.5, 2), (8, 8.5, 1), (9, 9, 2), (9.5, 10, 1)])
            expected_wait = expected_series([(8, 8.5, 1)])
            expected_available = expected_series([(0, 7.5, 2), (8, 8.5, 1), (9, 9.5, 2), (10, 10.5, 1), (11, 35.5, 2)])
            expected_prep = expected_series([(7.5, 9, 2), (9.5, 10, 1)])
            expected_operation = expected_series([(12, 12.5, 2)])
        else:
            expected_use = expected_series([(8, 8.5, 1), (10, 10.5, 1)])
            expected_wait = expected_series([(7.5, 7.5, 2), (8, 8.5, 1), (9, 9.5, 2), (10, 12.5, 1)])
            expected_available = expected_series([(8, 8.5, 1), (10, 10.5, 1)])
            expected_prep = expected_series([(7.5, 10.5, 2), (11, 12.5, 1)])
            expected_operation = {}
        expected_ready = expected_series([(0, 7, 2), (13, 35.5, 2)])
        expected_assigned = expected_series([(7.5, 12.5, 2)])
        for field, ledger, expected in (("NRUM", resource, expected_use), ("NRW", resource, expected_wait), ("NRA", resource, expected_available), ("NSYMP", system, expected_prep), ("NSYMO", system, expected_operation), ("NSYRY", system, expected_ready), ("NSYMA", system, expected_assigned)):
            check(tag + "exact 72-bin " + field + " ledger", all(abs(ledger[i / 2][field] - expected.get(i / 2, 0)) < 1e-6 for i in range(72)))
        check(tag + "two nominal crew and zero mission bookings", all(resource[i / 2]["NR"] == resource[i / 2]["NRN"] == 2 and resource[i / 2]["NRMA"] == resource[i / 2]["NRMO"] == 0 for i in range(72)))
        check(tag + "zero stock events and terminal ready", all(all(stock[i / 2][field] == 0 for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for i in range(72)) and system[35.5]["NSYRY"] == 2 and resource[35.5]["NRW"] == resource[35.5]["NRUM"] == 0)

        if index is not None:
            indexed = index_entries[variant]
            check(tag + "index identity and original path", indexed["run_id"] == run_id and Path(indexed["original_run_dir"]).resolve() == run.resolve())
            check(tag + "index raw hashes", indexed["input_sha256"] == sha(run / "input.json") and indexed["closure_sha256"] == sha(run / "closure.json") and indexed["model_log_sha256"] == sha(run / "model.log") and indexed["report_raw_sha256"] == sha(run / "report-raw.json"))
            if "raw" in indexed:
                check(tag + "index full raw inventory", indexed["raw"] == closure["raw"])

    pair_changes = {name for name in sources["Y"] | sources["N"] if sources["Y"].get(name) != sources["N"].get(name)}
    check("pair changes exactly Control and description", pair_changes == {"Control", "ProblemDescription"})
    y_control, n_control = row(sources["Y"]["Control"]), row(sources["N"]["Control"])
    check("pair Control changes only DRAOS", {name for name in y_control | n_control if y_control.get(name) != n_control.get(name)} == {"DRAOS"})
    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C07.cross_shift_gap", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures),
        "failures": failures, "decision": "GO_bounded_positive_cross_shift_gap" if not failures else "NO_GO",
        "observations": results,
        "accepted_scope": "In one two-shift first-day schedule, DRAOS=Y exposes two nominal crew outside the 8-9 and 10-11 one-crew shifts. Aircraft 1 works for 0.5h, pauses at 8 with 1.5h left, resumes at 9 across the nominal 9-10 gap, and completes at 10.5; the 12-13 mission succeeds. DRAOS=N permits one hour of work on aircraft 0 at 8-9, pauses it at 9 with one hour left, resumes 10-11, while aircraft 1 remains unprepared; the mission cancels at 13.",
        "metric_interpretation": "ResourceResults.NRW measures waiting demand, not booked work. Y records 4 crew-hours of work and 1 resource-hour of waiting; N records 2 crew-hours of work and 7 resource-hours of waiting. Exact 72-bin resource/system/stock ledgers are replayed.",
        "limits": ["N aircraft 1 books and starts at hour 11 but stops at the same timestamp with the full two-hour duration left. This does not demonstrate positive work or positive pause/resume for that aircraft.", "Only two explicit first-day shifts, one seed, one resource type, two aircraft, and one nominal allocation are covered; no recurring schedule, overlap, absent ShiftResource row, MAXUT, or broader DRAOS rule is established.", "The evidence index's dictionary fingerprint matches the previous C07 contract declaration, but its original dictionary file is unavailable for independent hashing; the installed manual PDF is hashed.", "The reviewer did not run native SIMLOX or observe SSH/GUI live; those guards are checked from sealed metadata."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
