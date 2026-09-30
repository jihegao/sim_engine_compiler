"""Independent standard-library read-only replay of sealed C07 long-gap run."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "C07-cross-day-v1.0.0" / "cross-day-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
RUN_ID = "c07-long-gap-20260930-01"
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
    keys = [table["name"] for table in sequence]
    return {table["name"]: table for table in sequence}, len(keys) == len(set(keys))


def rows(table):
    return [entry for instance in table["instances"] for entry in instance["rows"]]


def fields(table):
    return [column["name"] for column in table["columns"]]


def row(table):
    return dict(zip(fields(table), rows(table)[0]))


def bins(table):
    return {entry["STINT"]: entry for entry in (dict(zip(fields(table), source_row)) for source_row in rows(table))}


def series(ranges):
    result = {}
    for start, end, value in ranges:
        for half in range(int(start * 2), int(end * 2) + 1):
            result[half / 2] = value
    return result


def subtask(aircraft):
    return f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    index = load(CASE / "evidence-index.json")
    source_path = CASE / "long-gap-input.json"
    run = CASE / "runs" / RUN_ID
    parent, parent_unique = tables(load(PARENT))
    source, source_unique = tables(load(source_path))
    check("accepted C07 cross-day parent fingerprint", parent_unique and len(parent) == 35 and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_sha256"] == "b3780ff767af1653372e8dbd3f367f1fef9829b5fbf324cf6f354a19df558046")
    check("contract identity and unpublished candidate", contract["schema"] == "simlox-c07-long-gap-contract/v1" and contract["case_id"] == "C07" and contract["variant_id"] == "C07.var03" and contract["version"] == "1.0.0-candidate" and contract["parent_publication_id"] == "C07.var03.elapsed_day_boundary.1.0.0" and contract["publication_state"] == "not_published")
    check("installed manual fingerprint and pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_physical_pages"] == [227, 266, 296, 418, 419, 420, 421])
    check("evidence index identity and single accepted run", index["schema"] == "simlox-c07-long-gap-evidence-index/v1" and index["relative_raw_root"] == "runs/" and index["raw_publication"] == "local_sealed_not_committed" and len(index["runs"]) == 1 and index["runs"][0]["variant"] == "long-gap" and index["excluded_diagnostic_run"] is None)
    check("index manual/native hashes and dictionary declaration", index["source_manual_sha256"] == sha(MANUAL) and index["simlox_exe_sha256"] == sha(EXE) and index["source_dictionary_sha256"] == load(CASE.parent / "C07-offshift-boundary-v1.0.0" / "contract.json")["source_dictionary_sha256"])
    check("unique 35-table source and frozen input SHA", source_unique and len(source) == 35 and sha(source_path) == sha(run / "input.json") == contract["input_sha256"] == diff["input_sha256"] == "f22349f7a53ebd78355398fdef44cdb0685ac568563107726f33a05bcc3ee042")
    changed = {name for name in parent | source if parent.get(name) != source.get(name)}
    check("exact six-table parent change set", changed == set(contract["changed_tables"]) == set(diff["changed_tables"]) == {"Control", "MissionType", "OperationProfile", "ProblemDescription", "ResultCollection", "ShiftProfile"}, sorted(changed))
    check("every unlisted parent table unchanged", all(parent.get(name) == source.get(name) for name in parent | source if name not in changed))
    control, parent_control = row(source["Control"]), row(parent["Control"])
    check("Control SIMPE and result end only", {name for name in control | parent_control if control.get(name) != parent_control.get(name)} == {"SIMPE", "RCEND"} and control["SIMPE"] == control["RCEND"] == 180 and control["DRAOS"] == "N" and control["RSEED"] == "1")
    mission, parent_mission = row(source["MissionType"]), row(parent["MissionType"])
    check("MissionType NOPER-only delta", {name for name in mission | parent_mission if mission.get(name) != parent_mission.get(name)} == {"NOPER"} and mission["NOPER"] == 51.5)
    profile, parent_profile = row(source["OperationProfile"]), row(parent["OperationProfile"])
    check("OperationProfile planned hour 171 only", {name for name in profile | parent_profile if profile.get(name) != parent_profile.get(name)} == {"STIM"} and profile["STIM"] == 171)
    check("exact description, result end and shift windows", rows(source["ProblemDescription"]) == [["C07 two explicit crew shifts separated by 48 elapsed hours; DRAOS=N"]] and rows(source["ResultCollection"]) == [["MISSION", 0.5, 0, 180, None, None], ["SYSTEM", 0.5, 0, 180, None, None]] and rows(source["ShiftProfile"]) == [["CREW-DAY", "DAY-OPEN", 119, 120, 1, None, None], ["CREW-DAY", "DAY-OPEN", 168, 170, 1, None, None]])
    check("two crew and two-hour INSPECT preparation retained", rows(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]] and rows(source["ShiftResource"]) == [["DAY-OPEN", "BASE-01", "P-CREW", 2, None, None]] and rows(source["TaskBreakDown"]) == [["PREP-FIXED", 1, "INSPECT", 2, None, None]] and rows(source["MissionPreparation"]) == [["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 2, "PREP-FIXED", None, None]])

    invocation = load(run / "invocation.json")
    closure = load(run / "closure.json")
    steps = load(run / "steps.json")
    check("invocation run identity, original path and hashes", invocation["case_id"] == "C07" and invocation["variant"] == "long-gap" and invocation["run_id"] == closure["run_id"] == RUN_ID and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(PARENT))
    check("session-zero SSH and queue mutex", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    check("GUI identity preserved across steps", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
    paths = {"input": run / "input.json", "parent": PARENT, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
    seals = invocation["source_hashes_before"]
    check("all current source/runtime bytes match before seals", all(path.exists() and sha(path) == seals[name] for name, path in paths.items()))
    check("before/after source seals and invocation hash", closure["source_hashes_before"] == closure["source_hashes_after"] == seals and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[name + "_sha256"] == seals[name] for name in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == seals["python"])
    raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
    check("complete raw file inventory", raw_names == set(closure["raw"]))
    indexed = index["runs"][0]
    check("index run path and core raw byte hashes", indexed["run_id"] == RUN_ID and Path(indexed["original_run_dir"]).resolve() == run.resolve() and indexed["input_sha256"] == sha(run / "input.json") and indexed["closure_sha256"] == sha(run / "closure.json") and indexed["model_log_sha256"] == sha(run / "model.log") and indexed["report_raw_sha256"] == sha(run / "report-raw.json"))
    check("index full raw inventory matches closure", indexed["raw"] == closure["raw"])
    for filename, metadata in closure["raw"].items():
        path = run / filename
        check("raw byte seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
    check("five ordered successful native/check steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps))
    check("planned commands and step chronology", all(steps[i]["arguments"] == invocation["planned_commands"][i]["arguments"] for i in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"] and all(stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))

    original, original_unique = tables(load(run / "input.json"))
    roundtrip, roundtrip_unique = tables(load(run / "roundtrip-raw.json"))
    populated = {name for name, table in original.items() if rows(table)}
    check("24 populated business tables and unique native roundtrip", original_unique and roundtrip_unique and len(populated) == 24)
    for name in sorted(populated):
        check("exact native roundtrip " + name, original[name] == roundtrip.get(name))
    imported = (run / "import.log").read_text(errors="replace")
    exported = (run / "export.log").read_text(errors="replace")
    converted = (run / "run.log").read_text(errors="replace")
    check("35-form import/export complete", "Number of forms inserted: 35" in imported and "Import completed!" in imported and "Export completed!" in exported)
    check("zero conversion errors and two known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted)
    check("JSON report export complete", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    check("nonempty log and one two-aircraft mission", len(log) > 1000 and log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1 and log.count("mission allocates system:") == 2)
    check("elapsed day markers through 168", all(f"Time: {hour}  Start of day no {day}" in log for hour, day in ((0, 0), (24, 1), (48, 2), (72, 3), (96, 4), (120, 5), (144, 6), (168, 7))))
    check("explicit 119-120 and 168-170 shifts with 48h gap", all(f"Time: {hour}  resource shift {shift} starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW {capacity}" in log for hour, shift, capacity in ((0, 0, 0), (119, 1, 2), (120, 2, 0), (168, 3, 2), (170, 4, 0))))
    for aircraft in (0, 1):
        sub = subtask(aircraft)
        check(f"aircraft {aircraft} request and positive work 119.5-120", f"Time: 119.5  {sub} started" in log and f"Time: 119.5  {sub} requests resources" in log and f"Time: 119.5  {sub} starts performing, planned to last for 2 hours" in log)
        check(f"aircraft {aircraft} stop at 120 with 1.5h left", f"Time: 120  {sub} resource availability test\n  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed" in log and f"Time: 120  {sub} is stopped due to shift change, time left= 1.5" in log)
        check(f"aircraft {aircraft} resource and work resume at 168", f"Time: 168  {sub} resource received" in log and f"Time: 168  {sub} starts performing, planned to last for 1.5 hours" in log)
        check(f"aircraft {aircraft} completes at 169.5", f"Time: 169.5  {sub} completed" in log and f"Time: 169.5  {sub} frees resources" in log and f"Time: 169.5 <TEACH-AIR-01,{aircraft}> preparation ended" in log)
    check("typed crew bookings and returns", log.count("<P-CREW at <BASE-01,0>> allocated to maintenance task: 1") == 4 and log.count("<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1") == 2)
    check("mission succeeds 171-172 and terminal ready2", "Time: 171 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 172 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "Time: 172 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and "mission cancelled" not in log and "Time: 172 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :" in log)

    report, removed = load_report(run / "report-raw.json")
    rt, report_unique = tables(report, "report")
    check("six report tables and structural parse", report_unique and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
    summary = row(rt["ResultSummary"])
    check("one successful mission over 180 hours", summary["NREP"] == 1 and summary["RTIUP"] == 180 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1)
    total = row(rt["ResourceResultsTotal"])
    check("resource total 4 crew-hours work, 96 waiting", total["NR"] == total["NRN"] == 2 and abs(total["NRUM"] * 180 - 4) < 1e-5 and abs(total["NRW"] * 180 - 96) < 1e-5 and total["NRMA"] == total["NRMO"] == 0)
    resource = bins(rt["ResourceResults"])
    system = bins(rt["SystemResults"])
    stock = bins(rt["StockTotalResults"])
    check("360 complete half-hour bins", all(len(ledger) == 360 and all(ledger[i / 2]["ETINT"] == (i + 1) / 2 for i in range(360)) for ledger in (resource, system, stock)))
    expected = {
        "NRUM": (resource, series([(119.5, 119.5, 2), (168, 169, 2)])),
        "NRW": (resource, series([(120, 167.5, 2)])),
        "NRA": (resource, series([(119, 119.5, 2), (168, 169.5, 2)])),
        "NSYRY": (system, series([(0, 119, 2), (172, 179.5, 2)])),
        "NSYMA": (system, series([(119.5, 171.5, 2)])),
        "NSYMP": (system, series([(119.5, 169, 2)])),
        "NSYMO": (system, series([(171, 171.5, 2)])),
    }
    for field, (ledger, wanted) in expected.items():
        check("exact 360-bin " + field + " ledger", all(abs(ledger[i / 2][field] - wanted.get(i / 2, 0)) < 1e-6 for i in range(360)))
    check("two nominal crew and no mission resource booking", all(resource[i / 2]["NR"] == resource[i / 2]["NRN"] == 2 and resource[i / 2]["NRMA"] == resource[i / 2]["NRMO"] == 0 for i in range(360)))
    check("zero stock movements, no terminal wait, two ready", all(all(stock[i / 2][field] == 0 for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for i in range(360)) and resource[179.5]["NRUM"] == resource[179.5]["NRW"] == 0 and system[179.5]["NSYRY"] == 2)

    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1", "case_id": "C07.var03.long_gap", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_weekend_sized_elapsed_gap" if not failures else "NO_GO",
        "accepted_scope": "In a 180-hour fixed-seed DRAOS=N model with explicit 119-120 and 168-170 two-crew shifts, both aircraft work 119.5-120, stop at 120 with 1.5h left, wait through the 48-hour inactive interval, resume 168-169.5 and succeed on the 171-172 mission.",
        "metric_interpretation": "ResourceResults.NRW measures waiting demand, not booked work. The 360 half-hour bins show four crew-hours of positive work and 96 resource-hours of waiting; exact system and stock ledgers and terminal readiness are checked.",
        "limits": ["The 120-168 inactive interval is weekend-sized but has no weekday or date anchor. It does not prove a calendar-weekend rule or weekly recurrence.", "Only two explicit non-repeating shifts, one station, one resource type, one seed and DRAOS=N are covered. Nested/overlapping shifts, DRAOS=Y, MAXUT, GUI behavior and cross-engine equivalence are unverified.", "The index dictionary fingerprint matches a prior C07 contract declaration, but the original dictionary file is unavailable for independent hashing; the installed manual PDF is hashed.", "SSH/GUI/queue continuity is replayed from sealed metadata; this reviewer did not rerun native SIMLOX."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
