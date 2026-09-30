"""Independent, read-only replay of the sealed C07 DRAOS Y/N evidence.

Uses only the Python standard library. Never calls SIMLOX or author code.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
RUNS = {"Y": "c07-draos-y-20260930-02", "N": "c07-draos-n-20260930-01"}
CHECKS: list[dict] = []


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_report(path: Path):
    """Remove SIMLOX's structural trailing commas, leaving strings intact."""
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    removed = 0
    for pos, char in enumerate(raw):
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
        elif char == "," and raw[pos + 1 :].lstrip().startswith(("}", "]")):
            removed += 1
        else:
            out.append(char)
    return json.loads("".join(out)), removed


def check(name: str, passed: bool, detail=None):
    item = {"name": name, "passed": bool(passed)}
    if detail is not None:
        item["detail"] = detail
    CHECKS.append(item)


def tables(doc, section="model"):
    sequence = doc[section]["tables"]
    keys = [item["name"] for item in sequence]
    return {item["name"]: item for item in sequence}, len(keys) == len(set(keys))


def values(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def names(table):
    return [col["name"] for col in table["columns"]]


def record(table, row=0):
    return dict(zip(names(table), values(table)[row]))


def by_start(table):
    return {row["STINT"]: row for row in (dict(zip(names(table), entry)) for entry in values(table))}


def moment(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def main():
    contract = read_json(CASE / "contract.json")
    diff = read_json(CASE / "exact-diff.json")
    parent, unique_parent = tables(read_json(PARENT))
    parent_hash = digest(PARENT)
    check("C03 accepted parent fingerprint", unique_parent and len(parent) == 31 and parent_hash == contract["parent_input_sha256"] == diff["parent_sha256"] == "83b454bd145621f36571a87cdf8abcbccc184f07ab8f9ad5f3111651c78881e0")
    check("contract identity and unpublished candidate", contract["schema"] == "simlox-c07-offshift-contract/v1" and contract["case_id"] == "C07" and contract["version"] == "1.0.0-candidate" and contract["parent_case"] == "C03.shared_crew.1.0.2" and contract["publication_state"] == "not_published")
    check("manual fingerprint and cited pages", MANUAL.exists() and digest(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_pages"] == [227, 417, 418, 419, 421, 422, 423])
    expected_parent_delta = {"Control", "ProblemDescription", "ResourceStationData", "Shift", "ShiftProfile", "ShiftResource"}
    check("declared parent and pair change scopes", set(contract["changed_tables_from_parent"]) == expected_parent_delta and set(contract["changed_tables_within_pair"]) == {"Control", "ProblemDescription"} and set(diff["pair_changed_tables"]) == {"Control", "ProblemDescription"})

    sources = {}
    report_tables = {}
    observations = {}
    index_path = CASE / "evidence-index.json"
    index = read_json(index_path) if index_path.exists() else None
    if index is not None:
        entries = index["runs"]
        index_by_variant = {entry["variant"]: entry for entry in entries}
        check("evidence index identity and exactly Y/N entries", index["schema"] == "simlox-c07-offshift-evidence-index/v1" and index["relative_raw_root"] == "runs/" and index["raw_publication"] == "local_sealed_not_committed" and len(entries) == len(index_by_variant) == 2 and set(index_by_variant) == {"draos-y", "draos-n"})
        check("evidence index manual, dictionary declaration, and native fingerprint", index["source_manual_sha256"] == digest(MANUAL) and index["source_dictionary_sha256"] == contract["source_dictionary_sha256"] and index["simlox_exe_sha256"] == digest(EXE))
        check("earlier diagnostic Y run is explicitly excluded", index["excluded_diagnostic_run"].startswith("c07-draos-y-20260930-01:") and all(entry["run_id"] != "c07-draos-y-20260930-01" for entry in entries))
    else:
        index_by_variant = {}
        check("evidence index available for byte reconciliation", False)

    for choice, run_id in RUNS.items():
        variant = "draos-" + choice.lower()
        tag = choice + ": "
        source_path = CASE / f"{variant}-input.json"
        run = CASE / "runs" / run_id
        source, unique = tables(read_json(source_path))
        sources[choice] = source
        check(tag + "unique 35-table source", unique and len(source) == 35)
        check(tag + "source/run/contract/diff byte identity", digest(source_path) == digest(run / "input.json") == contract["input_sha256"][variant] == diff["children"][choice]["sha256"])
        changed = {name for name in parent.keys() | source.keys() if parent.get(name) != source.get(name)}
        check(tag + "exact parent table change set", changed == expected_parent_delta == set(diff["children"][choice]["changed_tables"]), sorted(changed))
        check(tag + "unchanged parent tables byte-equivalent JSON", all(source.get(name) == parent.get(name) for name in parent.keys() | source.keys() if name not in changed))
        check(tag + "description and DRAOS control", values(source["ProblemDescription"]) == [[f"C07 off-shift crew availability; DRAOS={choice}"]] and record(source["Control"])["DRAOS"] == choice and record(source["Control"])["NREPS"] == 1 and record(source["Control"])["RSEED"] == "1")
        parent_control = record(parent["Control"])
        child_control = record(source["Control"])
        check(tag + "Control differs from parent only at DRAOS", source["Control"]["columns"] == parent["Control"]["columns"] and {field for field in child_control | parent_control if child_control.get(field) != parent_control.get(field)} == {"DRAOS"})
        check(tag + "exact shift/resource source rows", values(source["Shift"]) == [["DAY-OPEN", "Crew open", None]] and values(source["ShiftProfile"]) == [["CREW-DAY", "DAY-OPEN", 7.75, 10.0, 1, None, None]] and values(source["ShiftResource"]) == [["DAY-OPEN", "BASE-01", "P-CREW", 2, None, None]] and values(source["ResourceStationData"]) == [["P-CREW", "BASE-01", None, None, None, None, None, None, None, "CREW-DAY", None]])
        check(tag + "retained two crew and half-hour INSPECT", values(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]] and values(source["TaskBreakDown"]) == [["PREP-FIXED", 1, "INSPECT", 0.5, None, None]] and values(source["SubTaskResource"]) == [["PREP-FIXED", 1, "P-CREW", 1, 1, None, None, None, None]] and values(source["MissionPreparation"]) == [["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 0.5, "PREP-FIXED", None, None]])

        invocation = read_json(run / "invocation.json")
        closure = read_json(run / "closure.json")
        steps = read_json(run / "steps.json")
        check(tag + "invocation identity/path/fingerprints", invocation["case_id"] == "C07" and invocation["variant"] == variant and invocation["run_id"] == closure["run_id"] == run_id and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == digest(source_path) and invocation["parent_sha256"] == parent_hash)
        check(tag + "SSH session zero and queue mutex", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(tag + "GUI preserved through five steps", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
        paths = {"input": run / "input.json", "parent": PARENT, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
        seals = invocation["source_hashes_before"]
        check(tag + "all current source/runtime files match frozen seals", all(path.exists() and digest(path) == seals[key] for key, path in paths.items()))
        check(tag + "before/after seals and invocation hash", closure["source_hashes_before"] == closure["source_hashes_after"] == seals and closure["invocation_sha256"] == digest(run / "invocation.json") and closure["error"] is None and all(invocation[key + "_sha256"] == seals[key] for key in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == seals["python"])
        raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(tag + "complete raw inventory", raw_names == set(closure["raw"]))
        for filename, metadata in closure["raw"].items():
            path = run / filename
            check(tag + "sealed raw " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and digest(path) == metadata["sha256"])
        check(tag + "five ordered successful steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps))
        check(tag + "native command arguments preserved", all(steps[i]["arguments"] == invocation["planned_commands"][i]["arguments"] for i in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"])
        check(tag + "ordered step timestamps", all(moment(step["started_utc"]) <= moment(step["completed_utc"]) for step in steps) and all(moment(steps[i]["completed_utc"]) <= moment(steps[i + 1]["started_utc"]) for i in range(4)))

        original, original_unique = tables(read_json(run / "input.json"))
        roundtrip, roundtrip_unique = tables(read_json(run / "roundtrip-raw.json"))
        populated = {name for name, table in original.items() if values(table)}
        check(tag + "24 populated source tables and unique roundtrip", original_unique and roundtrip_unique and len(populated) == 24)
        for name in sorted(populated):
            check(tag + "exact native roundtrip " + name, original[name] == roundtrip.get(name))
        imported = (run / "import.log").read_text(errors="replace")
        exported = (run / "export.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(tag + "35-form import/export", "Number of forms inserted: 35" in imported and "Import completed!" in imported and "Export completed!" in exported)
        check(tag + "zero conversion errors and two known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted)
        check(tag + "JSON report generation", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check(tag + "one two-aircraft mission", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1 and log.count("mission allocates system:") == 2)
        check(tag + "shift starts 7.75 and ends 10", "Time: 7.75  resource shift 1 starting at <P-CREW at <BASE-01,0>>" in log and "Time: 10  resource shift 2 starting at <P-CREW at <BASE-01,0>>" in log)
        initial_free = 2 if choice == "Y" else 0
        terminal_free = initial_free
        check(tag + "off-shift and post-shift free crew", f"Time: 0  resource shift 0 starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW {initial_free}" in log and f"Time: 10  resource shift 2 starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW {terminal_free}" in log)
        work_start, work_end, launch, success = (7.5, 8, 8, 9) if choice == "Y" else (7.75, 8.25, 8.25, 9.25)
        observations[choice] = {"offshift_free_crew": initial_free, "preparation_start": work_start, "preparation_end": work_end, "mission_start": launch, "mission_success": success}
        for aircraft in (0, 1):
            subtask = f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"
            check(tag + f"aircraft {aircraft} preparation requested at 7.5", f"Time: 7.5  {subtask} started" in log and f"Time: 7.5  {subtask} requests resources" in log)
            initial_test = f"Time: 7.5  {subtask} resource availability test\n  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 {'OK' if choice == 'Y' else 'failed'}"
            check(tag + f"aircraft {aircraft} off-shift availability test", initial_test in log)
            if choice == "N":
                check(tag + f"aircraft {aircraft} waits until shift and receives resource", f"Time: 7.75  {subtask} resource received" in log and f"Time: 7.5  {subtask} starts performing" not in log)
            else:
                check(tag + f"aircraft {aircraft} rebooks at shift transition", f"Time: 7.75  {subtask} resource availability test" in log and f"Time: 7.75  {subtask} starts performing, planned to last for 0.25 hours" in log)
            check(tag + f"aircraft {aircraft} performs 30 minutes and finishes", f"Time: {work_start:g}  {subtask} starts performing, planned to last for 0.5 hours" in log and f"Time: {work_end:g}  {subtask} completed" in log and f"Time: {work_end:g}  {subtask} frees resources" in log and f"Time: {work_end:g} <TEACH-AIR-01,{aircraft}> preparation ended" in log)
        check(tag + "typed crew booking and return events", log.count("<P-CREW at <BASE-01,0>> allocated to maintenance task: 1") == (4 if choice == "Y" else 2) and log.count("<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1") == 2)
        check(tag + "successful one-hour mission at observed time", f"Time: {launch:g} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and f"Time: {success:g} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and f"Time: {success:g} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and "mission cancelled" not in log)
        check(tag + "two aircraft terminal ready", f"Time: {success:g} <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log)

        report, removed = read_report(run / "report-raw.json")
        rt, unique_report = tables(report, "report")
        report_tables[choice] = rt
        check(tag + "six report tables and structural trailing commas", unique_report and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
        system = by_start(rt["SystemResults"])
        resources = by_start(rt["ResourceResults"])
        stock = by_start(rt["StockTotalResults"])
        check(tag + "72 half-hour report bins in each ledger", all(len(ledger) == 72 and all(ledger[i / 2]["ETINT"] == (i + 1) / 2 for i in range(72)) for ledger in (system, resources, stock)))
        summary = record(rt["ResultSummary"])
        check(tag + "one successful mission summary", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1)
        total = record(rt["ResourceResultsTotal"])
        check(tag + "resource total: 2 crew, one crew-hour of work", total["NR"] == total["NRN"] == 2 and abs(total["NRUM"] * 36 - 1) < 1e-6 and total["NRMA"] == total["NRMO"] == 0 and abs(total["NRW"] * 36 - (0 if choice == "Y" else 0.5)) < 1e-6)
        expected_used = {7.5: 2} if choice == "Y" else {7.5: 1, 8.0: 1}
        expected_wait = {} if choice == "Y" else {7.5: 1}
        expected_available = ({i / 2: 2 for i in range(72)} if choice == "Y" else {7.5: 1, **{i / 2: 2 for i in range(16, 20)}})
        expected_prep = {7.5: 2} if choice == "Y" else {7.5: 2, 8.0: 1}
        expected_operation = {8.0: 2, 8.5: 2} if choice == "Y" else {8.0: 1, 8.5: 2, 9.0: 1}
        check(tag + "exact 72-bin crew use ledger", all(resources[i / 2]["NRUM"] == expected_used.get(i / 2, 0) for i in range(72)))
        check(tag + "exact 72-bin waiting ledger", all(resources[i / 2]["NRW"] == expected_wait.get(i / 2, 0) for i in range(72)))
        check(tag + "exact 72-bin crew availability ledger", all(resources[i / 2]["NRA"] == expected_available.get(i / 2, 0) for i in range(72)))
        check(tag + "two nominal crew and no mission resource booking", all(resources[i / 2]["NR"] == resources[i / 2]["NRN"] == 2 and resources[i / 2]["NRMA"] == resources[i / 2]["NRMO"] == 0 for i in range(72)))
        check(tag + "exact 72-bin system preparation ledger", all(system[i / 2]["NSYMP"] == expected_prep.get(i / 2, 0) for i in range(72)))
        check(tag + "exact 72-bin mission operation ledger", all(system[i / 2]["NSYMO"] == expected_operation.get(i / 2, 0) for i in range(72)))
        check(tag + "zero stock events across 72 bins", all(all(stock[i / 2][field] == 0 for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for i in range(72)))
        check(tag + "terminal resource and two ready aircraft", resources[35.5]["NRW"] == resources[35.5]["NRUM"] == 0 and system[35.5]["NSYRY"] == 2)
        if choice == "Y":
            ready = {i / 2: 2 for i in range(0, 15)} | {i / 2: 2 for i in range(18, 72)}
        else:
            ready = {i / 2: 2 for i in range(0, 15)} | {9.0: 1} | {i / 2: 2 for i in range(19, 72)}
        check(tag + "exact 72-bin readiness ledger", all(system[i / 2]["NSYRY"] == ready.get(i / 2, 0) for i in range(72)))

        if index is not None:
            entry = index_by_variant[variant]
            check(tag + "index run identity and raw path", entry["run_id"] == run_id and Path(entry["original_run_dir"]).resolve() == run.resolve())
            check(tag + "index byte hashes", entry["input_sha256"] == digest(run / "input.json") and entry["closure_sha256"] == digest(run / "closure.json") and entry["model_log_sha256"] == digest(run / "model.log") and entry["report_raw_sha256"] == digest(run / "report-raw.json"))
            check(tag + "index full raw inventory matches closure", entry["raw"] == closure["raw"])

    changed_pair = {name for name in sources["Y"] | sources["N"] if sources["Y"].get(name) != sources["N"].get(name)}
    check("pair differs only in Control and description", changed_pair == {"Control", "ProblemDescription"})
    y_control, n_control = record(sources["Y"]["Control"]), record(sources["N"]["Control"])
    check("pair Control delta is exactly DRAOS", {field for field in y_control | n_control if y_control.get(field) != n_control.get(field)} == {"DRAOS"})
    check("mission completion differs by exact quarter-hour", observations["Y"]["mission_success"] == 9 and observations["N"]["mission_success"] == 9.25)
    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C07.offshift_boundary", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures),
        "failures": failures, "decision": "GO_bounded_first_day_offshift_boundary" if not failures else "NO_GO",
        "observations": observations,
        "accepted_scope": "For one first-day shift and two aircraft, DRAOS=Y exposes the two nominally allocated crew before the 7.75 shift start and both 30-minute preparations finish at 8. DRAOS=N has zero free crew at 7.5, both preparations wait until 7.75 and finish at 8.25. Missions launch at 8 versus 8.25 and succeed at 9 versus 9.25, with both aircraft ready at the end.",
        "metric_interpretation": "ResourceResults.NRW is waiting demand, not booked work. The N run has 0.5 total resource-hours of waiting and both runs have one crew-hour of work. The Y log rebooks the active subtasks when the shift begins; the replay does not infer an interruption because the subtask completion time remains 8.",
        "limits": ["One fixed first-day shift, one crew type, two aircraft and one seed. No recurring day, overlap, capacity-limit, absence-row or cross-shift pause/resume result is established.", "The earlier Y -01 diagnostic run is excluded because its source omitted two null ResourceStationData schema columns and failed roundtrip validation; only frozen Y -02 and N -01 are accepted.", "The contract's source dictionary fingerprint is recorded but its original dictionary file is not part of this local package; the installed manual PDF fingerprint is independently checked.", "SSH/GUI/queue continuity is replayed from sealed metadata; this reviewer did not rerun native SIMLOX."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
