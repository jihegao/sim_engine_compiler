"""Independent standard-library read-only replay of C07 invalid-shift evidence."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PREVIOUS = CASE.parent / "C07-repeat-nested-v1.0.0"
PARENTS = {"explicit": PREVIOUS / "explicit-input.json", "repeated": PREVIOUS / "repeated-input.json"}
EXPLICIT_RUN = PREVIOUS / "runs" / "c07-explicit-pair-20260930-01"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
VARIANTS = ("overlap", "repeated-overlap", "over-capacity")
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


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    check("contract identity and unpublished candidate", contract["schema"] == "simlox-c07-invalid-shifts-contract/v1" and contract["case_id"] == "C07" and contract["variant_id"] == "C07.var05" and contract["version"] == "1.0.0-candidate" and contract["parent_publication_id"] == "C07.var04.repeat_nested_two_window.1.0.0" and contract["publication_state"] == "not_published")
    check("installed manual fingerprint and pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_physical_pages"] == [419, 420, 421, 799, 843])
    parent_tables = {}
    for name, path in PARENTS.items():
        parent, unique = tables(load(path))
        parent_tables[name] = parent
        check(name + " accepted parent fingerprint", unique and len(parent) == 35 and sha(path) == contract["parent_input_sha256"][name] == diff["parent_sha256"][name])
    check("accepted explicit raw control available", EXPLICIT_RUN.exists() and sha(EXPLICIT_RUN / "input.json") == sha(PARENTS["explicit"]))
    report_candidate = None

    for variant in VARIANTS:
        tag = variant + ": "
        parent_name = contract["variants"][variant]["parent"]
        parent = parent_tables[parent_name]
        parent_path = PARENTS[parent_name]
        source_path = CASE / f"{variant}-input.json"
        run_id = f"c07-{variant}-20260930-01"
        run = CASE / "runs" / run_id
        source, unique = tables(load(source_path))
        check(tag + "unique 35-table source", unique and len(source) == 35)
        check(tag + "source/run/contract/diff SHA", sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant] == diff["variants"][variant]["sha256"])
        check(tag + "correct accepted parent selected", parent_name == diff["variants"][variant]["parent"] and sha(parent_path) == contract["parent_input_sha256"][parent_name])
        changed = {name for name in parent | source if parent.get(name) != source.get(name)}
        expected_tables = {"ProblemDescription", "ShiftResource"} if variant == "over-capacity" else {"ProblemDescription", "ShiftProfile"}
        check(tag + "exact two-table parent delta", changed == expected_tables == set(diff["variants"][variant]["changed_tables"]), sorted(changed))
        check(tag + "all other parent tables identical", all(parent.get(name) == source.get(name) for name in parent | source if name not in changed))
        check(tag + "only label plus one business field changes", rows(source["ProblemDescription"]) == [[f"C07 invalid {variant} crew shift diagnostic; DRAOS=N"]] and (rows(source["ShiftProfile"]) == rows(parent["ShiftProfile"]) if variant == "over-capacity" else rows(source["ShiftResource"]) == rows(parent["ShiftResource"])))
        if variant == "overlap":
            before = rows(parent["ShiftProfile"])
            after = rows(source["ShiftProfile"])
            check(tag + "second explicit STIM alone 26 to 24.5", after[0] == before[0] and len(after) == len(before) == 2 and {name for name, old, new in zip(columns(parent["ShiftProfile"]), before[1], after[1]) if old != new} == {"STIM"} and before[1][2] == 26 and after[1][2] == 24.5)
        elif variant == "repeated-overlap":
            before = row(parent["ShiftProfile"])
            after = row(source["ShiftProfile"])
            check(tag + "IINT alone 3 to 1.5", {name for name in before | after if before.get(name) != after.get(name)} == {"IINT"} and before["IINT"] == 3 and after["IINT"] == 1.5 and after["STIM"] == 23 and after["ETIM"] == 25)
        else:
            before = row(parent["ShiftResource"])
            after = row(source["ShiftResource"])
            check(tag + "QTY alone 2 to 3; nominal deployment remains 2", {name for name in before | after if before.get(name) != after.get(name)} == {"QTY"} and before["QTY"] == 2 and after["QTY"] == 3 and rows(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]])

        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(tag + "invocation identity, path and source", invocation["case_id"] == "C07" and invocation["variant"] == variant and invocation["run_id"] == closure["run_id"] == run_id and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(parent_path))
        check(tag + "session-zero SSH/queue mutex", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(tag + "GUI preserved in recorded steps", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
        runner = CASE / ("run_capacity_ssh.ps1" if variant == "over-capacity" else "run_rejection_ssh.ps1")
        paths = {"input": run / "input.json", "parent": parent_path, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": runner, "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
        seals = invocation["source_hashes_before"]
        check(tag + "current source/runtime match frozen before seals", all(path.exists() and sha(path) == seals[name] for name, path in paths.items()))
        check(tag + "before/after source seals and invocation hash", closure["source_hashes_before"] == closure["source_hashes_after"] == seals and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[name + "_sha256"] == seals[name] for name in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == seals["python"])
        raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(tag + "complete raw file inventory", raw_names == set(closure["raw"]))
        for filename, metadata in closure["raw"].items():
            path = run / filename
            check(tag + "raw byte seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
        expected_names = ["import", "export", "calc", "jsonreport", "check_import_export"] if variant == "over-capacity" else ["import", "export", "calc", "check_import_export"]
        check(tag + "exact step sequence, exit code and statuses", [step["name"] for step in steps] == expected_names and all(step["exit_code"] == 0 and step["error"] is None and step["status"] == ("expected_rejection" if step["name"] == "calc" and variant != "over-capacity" else "completed") for step in steps))
        check(tag + "planned commands and step chronology", all(steps[i]["arguments"] == invocation["planned_commands"][i]["arguments"] for i in range(len(invocation["planned_commands"]))) and steps[-1]["arguments"] == invocation["planned_check"]["arguments"] and all(stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(len(steps) - 1)))

        original, original_unique = tables(load(run / "input.json"))
        roundtrip, roundtrip_unique = tables(load(run / "roundtrip-raw.json"))
        populated = {name for name, table in original.items() if rows(table)}
        check(tag + "24 populated business tables and unique roundtrip", original_unique and roundtrip_unique and len(populated) == 24)
        for name in sorted(populated):
            check(tag + "exact native roundtrip " + name, original[name] == roundtrip.get(name))
        imported = (run / "import.log").read_text(errors="replace")
        exported = (run / "export.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(tag + "35-form import/export complete", "Number of forms inserted: 35" in imported and "Import completed!" in imported and "Export completed!" in exported)
        if variant != "over-capacity":
            errors = [line for line in converted.splitlines() if "(error #" in line]
            expected_errors = ["rec 1: (error #250) Shifts overlap: DAY-OPEN and DAY-OPEN"] if variant == "overlap" else ["rec 1: (error #249) IINT less than shift duration (ETIM-STIM) causes overlapping shifts.", "rec 1: (error #250) Shifts overlap: DAY-OPEN and DAY-OPEN"]
            check(tag + "exact converter rejection diagnostics", errors == expected_errors and f"Input conversion completed. Errors: {len(expected_errors)}, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1)
            check(tag + "calc exits zero but simulation not started", steps[2]["exit_code"] == 0 and "Starting simulation..." not in converted and "Saving results ..." not in converted)
            check(tag + "4-byte unusable result; no log/report/export step", (run / "model.sxo").stat().st_size == 4 and "model.log" not in raw_names and "report-raw.json" not in raw_names and "report-export.log" not in raw_names and "jsonreport" not in expected_names and len(invocation["planned_commands"]) == 3)
        else:
            warnings = [line for line in converted.splitlines() if "(warning #" in line]
            check(tag + "warning #60 plus #108/#126; zero errors", len(warnings) == 3 and any("(warning #60) The quantity in the shift is greater than the deployed quantity:  P-CREW/BASE-01" in line for line in warnings) and converted.count("warning #108") == converted.count("warning #126") == 1 and "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in converted and "error #" not in converted.lower())
            check(tag + "simulation and JSON report completed", "Starting simulation..." in converted and "Saving results ..." in converted and "Generating Json-report" in (run / "report-export.log").read_text(errors="replace") and (run / "model.sxo").stat().st_size > 4)
            check(tag + "QTY3 survives exact native import/export", row(roundtrip["ShiftResource"])["QTY"] == 3 and row(original["ShiftResource"])["QTY"] == 3)
            log_bytes = (run / "model.log").read_bytes()
            parent_log_bytes = (EXPLICIT_RUN / "model.log").read_bytes()
            check(tag + "native event log byte-identical to accepted explicit control", log_bytes == parent_log_bytes)
            log = log_bytes.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
            check(tag + "effective free capacity two, never three", all(f"Time: {hour}  resource shift {shift} starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW 2" in log for hour, shift in ((23, 1), (26, 3))) and "Free resources at: <BASE-01,0> P-CREW 3" not in log)
            check(tag + "mission 28-29 success, terminal ready2", "Time: 28 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "mission cancelled" not in log and "Time: 29 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :" in log)
            report, removed = load_report(run / "report-raw.json")
            rt, report_unique = tables(report, "report")
            parent_report, parent_removed = load_report(EXPLICIT_RUN / "report-raw.json")
            parent_rt, parent_unique = tables(parent_report, "report")
            report_candidate = rt
            check(tag + "six report tables and structural parse", report_unique and parent_unique and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0 and parent_removed > 0)
            check(tag + "report tables equal control except description", all(rt.get(name) == parent_rt.get(name) for name in rt | parent_rt if name != "ProblemDescription") and rt["ProblemDescription"] != parent_rt["ProblemDescription"])
            summary = row(rt["ResultSummary"])
            check(tag + "one successful mission summary", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1)
            total = row(rt["ResourceResultsTotal"])
            check(tag + "resource totals two nominal/effective, work4 wait2", total["NR"] == total["NRN"] == 2 and abs(total["NRUM"] * 36 - 4) < 1e-5 and abs(total["NRW"] * 36 - 2) < 1e-5 and total["NRMA"] == total["NRMO"] == 0)
            resource, system, stock = (bins(rt[name]) for name in ("ResourceResults", "SystemResults", "StockTotalResults"))
            check(tag + "72 complete half-hour bins", all(len(ledger) == 72 and all(ledger[i / 2]["ETINT"] == (i + 1) / 2 for i in range(72)) for ledger in (resource, system, stock)))
            expected = {
                "NRUM": (resource, series([(23.5, 24.5, 2), (26, 26, 2)])),
                "NRW": (resource, series([(25, 25.5, 2)])),
                "NRA": (resource, series([(23, 24.5, 2), (26, 27.5, 2)])),
                "NSYRY": (system, series([(0, 23, 2), (29, 35.5, 2)])),
                "NSYMA": (system, series([(23.5, 28.5, 2)])),
                "NSYMP": (system, series([(23.5, 26, 2)])),
                "NSYMO": (system, series([(28, 28.5, 2)])),
            }
            for field, (ledger, wanted) in expected.items():
                check(tag + "exact 72-bin " + field + " ledger", all(abs(ledger[i / 2][field] - wanted.get(i / 2, 0)) < 1e-6 for i in range(72)))
            check(tag + "resource count two and zero mission booking", all(resource[i / 2]["NR"] == resource[i / 2]["NRN"] == 2 and resource[i / 2]["NRMA"] == resource[i / 2]["NRMO"] == 0 for i in range(72)))
            check(tag + "zero stock movement and terminal ready2", all(all(stock[i / 2][field] == 0 for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for i in range(72)) and resource[35.5]["NRUM"] == resource[35.5]["NRW"] == 0 and system[35.5]["NSYRY"] == 2)

    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1", "case_id": "C07.var05.invalid_shifts", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_rejection_and_clamp" if not failures else "NO_GO",
        "accepted_scope": "Explicit half-hour shift overlap yields converter error #250; repeated interval shorter than shift duration yields both #249 and #250. Both calc commands exit zero but stop before simulation with four-byte unusable .sxo files and no report. A QTY3 active shift against nominal deployment2 produces warning #60, zero errors, effective capacity2, and a valid native outcome byte-identical to the accepted explicit control log, with report tables equal except description.",
        "metric_interpretation": "For overcapacity, ResourceResults.NRW is waiting demand rather than booked work. Exact 72-bin ledgers show four crew-hours positive work, two resource-hours waiting, resource capacity two, mission success and terminal two ready aircraft.",
        "limits": ["Negative overlap runners exercised import, export, calc and roundtrip check, not jsonreport. Their calc exit code zero is not acceptance; converter error text and unusable output are decisive.", "These are one explicit overlap, one repeated-interval overlap and one resource/station overcapacity input on this installed executable. No generic invalid-shift resolution or multi-resource clamping claim follows.", "Calendar recurrence, MAXUT, GUI visual behavior and cross-engine equivalence remain unverified. SSH/GUI/queue continuity is replayed from sealed metadata; the reviewer did not rerun native SIMLOX."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
