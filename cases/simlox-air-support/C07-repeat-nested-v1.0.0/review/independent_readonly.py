"""Independent standard-library, read-only replay of C07 repeat/nested runs."""

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
VARIANTS = ("explicit", "repeated", "nested")
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
    expected = {}
    for start, end, value in ranges:
        for half in range(int(start * 2), int(end * 2) + 1):
            expected[half / 2] = value
    return expected


def subtask(aircraft):
    return f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    index = load(CASE / "evidence-index.json")
    indexed_runs = {entry["variant"]: entry for entry in index["runs"]}
    parent, unique_parent = tables(load(PARENT))
    check("accepted C07 cross-day parent fingerprint", unique_parent and len(parent) == 35 and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_sha256"] == "b3780ff767af1653372e8dbd3f367f1fef9829b5fbf324cf6f354a19df558046")
    check("contract identity and unpublished candidate", contract["schema"] == "simlox-c07-repeat-nested-contract/v1" and contract["case_id"] == "C07" and contract["variant_id"] == "C07.var04" and contract["version"] == "1.0.0-candidate" and contract["parent_publication_id"] == "C07.var03.elapsed_day_boundary.1.0.0" and contract["publication_state"] == "not_published")
    check("manual fingerprint and physical pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_physical_pages"] == [418, 419, 420, 421])
    check("evidence index identity and exactly three accepted runs", index["schema"] == "simlox-c07-repeat-nested-evidence-index/v1" and index["relative_raw_root"] == "runs/" and index["raw_publication"] == "local_sealed_not_committed" and len(index["runs"]) == len(indexed_runs) == 3 and set(indexed_runs) == set(VARIANTS) and index["excluded_diagnostic_run"] is None)
    check("index manual/native hashes and dictionary declaration", index["source_manual_sha256"] == sha(MANUAL) and index["simlox_exe_sha256"] == sha(EXE) and index["source_dictionary_sha256"] == load(CASE.parent / "C07-offshift-boundary-v1.0.0" / "contract.json")["source_dictionary_sha256"])
    check("declared parent and pair change scopes", set(contract["changed_tables_from_parent_each"]) == {"ProblemDescription", "ShiftProfile"} and all(set(value) == {"ProblemDescription", "ShiftProfile"} for value in diff["pair_changed_tables"].values()))
    sources = {}
    logs = {}
    reports = {}
    expected_profile = {
        "explicit": [["CREW-DAY", "DAY-OPEN", 23, 25, 1, None, None], ["CREW-DAY", "DAY-OPEN", 26, 28, 1, None, None]],
        "repeated": [["CREW-DAY", "DAY-OPEN", 23, 25, 2, 3, None]],
        "nested": [["CREW-BLOCK", "DAY-OPEN", 1, 3, 1, None, None], ["CREW-DAY", "CREW-BLOCK", 22, None, 2, 3, None]],
    }

    for variant in VARIANTS:
        tag = variant + ": "
        source_path = CASE / f"{variant}-input.json"
        run_id = f"c07-{variant}-pair-20260930-01"
        run = CASE / "runs" / run_id
        source, unique = tables(load(source_path))
        sources[variant] = source
        check(tag + "unique 35-table source", unique and len(source) == 35)
        check(tag + "frozen source/run/contract/diff SHA", sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant] == diff["variants"][variant]["sha256"])
        changed = {name for name in parent | source if parent.get(name) != source.get(name)}
        check(tag + "exact two-table parent delta", changed == set(diff["variants"][variant]["changed_tables"]) == {"ProblemDescription", "ShiftProfile"}, sorted(changed))
        check(tag + "every unlisted parent table unchanged", all(parent.get(name) == source.get(name) for name in parent | source if name not in changed))
        check(tag + "exact description and shift source rows", rows(source["ProblemDescription"]) == [[f"C07 two equivalent crew shifts via {variant} profile; DRAOS=N"]] and rows(source["ShiftProfile"]) == expected_profile[variant])
        check(tag + "parent mission/resource inputs retained", row(source["Control"])["DRAOS"] == "N" and rows(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]] and rows(source["ShiftResource"]) == [["DAY-OPEN", "BASE-01", "P-CREW", 2, None, None]] and rows(source["TaskBreakDown"]) == [["PREP-FIXED", 1, "INSPECT", 2, None, None]] and row(source["OperationProfile"])["STIM"] == 28)

        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(tag + "invocation identity/path/source", invocation["case_id"] == "C07" and invocation["variant"] == variant and invocation["run_id"] == closure["run_id"] == run_id and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(PARENT))
        check(tag + "session-zero SSH and queue mutex", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(tag + "GUI identity preserved", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
        paths = {"input": run / "input.json", "parent": PARENT, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
        seals = invocation["source_hashes_before"]
        check(tag + "current source/runtime bytes match frozen before", all(path.exists() and sha(path) == seals[name] for name, path in paths.items()))
        check(tag + "before/after source seals and invocation hash", closure["source_hashes_before"] == closure["source_hashes_after"] == seals and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[name + "_sha256"] == seals[name] for name in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == seals["python"])
        raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(tag + "complete raw file inventory", raw_names == set(closure["raw"]))
        indexed = indexed_runs[variant]
        check(tag + "index path and core raw byte hashes", indexed["run_id"] == run_id and Path(indexed["original_run_dir"]).resolve() == run.resolve() and indexed["input_sha256"] == sha(run / "input.json") and indexed["closure_sha256"] == sha(run / "closure.json") and indexed["model_log_sha256"] == sha(run / "model.log") and indexed["report_raw_sha256"] == sha(run / "report-raw.json"))
        check(tag + "index full raw inventory matches closure", indexed["raw"] == closure["raw"])
        for filename, metadata in closure["raw"].items():
            path = run / filename
            check(tag + "raw byte seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
        check(tag + "five ordered successful steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps))
        check(tag + "planned commands and step chronology", all(steps[i]["arguments"] == invocation["planned_commands"][i]["arguments"] for i in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"] and all(stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))

        original, original_unique = tables(load(run / "input.json"))
        roundtrip, roundtrip_unique = tables(load(run / "roundtrip-raw.json"))
        populated = {name for name, table in original.items() if rows(table)}
        check(tag + "24 populated tables and unique native roundtrip", original_unique and roundtrip_unique and len(populated) == 24)
        for name in sorted(populated):
            check(tag + "exact native roundtrip " + name, original[name] == roundtrip.get(name))
        imported = (run / "import.log").read_text(errors="replace")
        exported = (run / "export.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(tag + "35-form import/export complete", "Number of forms inserted: 35" in imported and "Import completed!" in imported and "Export completed!" in exported)
        check(tag + "zero conversion errors and two known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted)
        check(tag + "JSON report export complete", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))

        log_bytes = (run / "model.log").read_bytes()
        logs[variant] = log_bytes
        log = log_bytes.decode("utf-8-sig", errors="replace").replace("\r\n", "\n")
        check(tag + "one two-aircraft formation request", len(log) > 1000 and log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1 and log.count("mission allocates system:") == 2)
        check(tag + "generated 23-25 and 26-28 shifts", all(f"Time: {hour}  resource shift {shift} starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW {capacity}" in log for hour, shift, capacity in ((0, 0, 0), (23, 1, 2), (25, 2, 0), (26, 3, 2), (28, 4, 0))))
        for aircraft in (0, 1):
            sub = subtask(aircraft)
            check(tag + f"aircraft {aircraft} positive work 23.5-25", f"Time: 23.5  {sub} started" in log and f"Time: 23.5  {sub} requests resources" in log and f"Time: 23.5  {sub} starts performing, planned to last for 2 hours" in log)
            check(tag + f"aircraft {aircraft} stop25 with .5h left", f"Time: 25  {sub} resource availability test\n  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed" in log and f"Time: 25  {sub} is stopped due to shift change, time left= 0.5" in log)
            check(tag + f"aircraft {aircraft} resume26 and finish26.5", f"Time: 26  {sub} resource received" in log and f"Time: 26  {sub} starts performing, planned to last for 0.5 hours" in log and f"Time: 26.5  {sub} completed" in log and f"Time: 26.5  {sub} frees resources" in log and f"Time: 26.5 <TEACH-AIR-01,{aircraft}> preparation ended" in log)
        check(tag + "typed crew bookings and returns", log.count("<P-CREW at <BASE-01,0>> allocated to maintenance task: 1") == 4 and log.count("<P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1") == 2)
        check(tag + "mission succeeds28-29, terminal ready2", "Time: 28 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and "mission cancelled" not in log and "Time: 29 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :" in log)

        report, removed = load_report(run / "report-raw.json")
        rt, report_unique = tables(report, "report")
        reports[variant] = rt
        check(tag + "six report tables and structural parse", report_unique and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
        summary = row(rt["ResultSummary"])
        check(tag + "one successful mission over36 hours", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1)
        total = row(rt["ResourceResultsTotal"])
        check(tag + "resource totals 4 work/2 wait hours", total["NR"] == total["NRN"] == 2 and abs(total["NRUM"] * 36 - 4) < 1e-5 and abs(total["NRW"] * 36 - 2) < 1e-5 and total["NRMA"] == total["NRMO"] == 0)
        resource = bins(rt["ResourceResults"])
        system = bins(rt["SystemResults"])
        stock = bins(rt["StockTotalResults"])
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
        check(tag + "two nominal crew and no mission booking", all(resource[i / 2]["NR"] == resource[i / 2]["NRN"] == 2 and resource[i / 2]["NRMA"] == resource[i / 2]["NRMO"] == 0 for i in range(72)))
        check(tag + "zero stock movement and terminal ready2", all(all(stock[i / 2][field] == 0 for field in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for i in range(72)) and resource[35.5]["NRUM"] == resource[35.5]["NRW"] == 0 and system[35.5]["NSYRY"] == 2)

    for left, right in (("explicit", "repeated"), ("explicit", "nested"), ("repeated", "nested")):
        changed = {name for name in sources[left] | sources[right] if sources[left].get(name) != sources[right].get(name)}
        check(f"source pair {left}/{right} exactly two-table delta", changed == set(diff["pair_changed_tables"][f"{left}-vs-{right}"]) == {"ProblemDescription", "ShiftProfile"})
    check("all three native model logs byte-identical", logs["explicit"] == logs["repeated"] == logs["nested"])
    check("all parsed reports equal except description", all(reports["explicit"].get(name) == reports[variant].get(name) for variant in ("repeated", "nested") for name in reports["explicit"] | reports[variant] if name != "ProblemDescription") and len({json.dumps(reports[variant]["ProblemDescription"], sort_keys=True) for variant in VARIANTS}) == 3)
    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1", "case_id": "C07.var04.repeat_nested", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_first_day_repeat_and_nesting" if not failures else "NO_GO",
        "accepted_scope": "For one fixed 36-hour first-to-second elapsed-day pair, explicit, IQTY/IINT repeated, and nested ShiftProfile sources generate the same 23-25 and 26-28 two-crew shifts. Both aircraft perform 23.5-25, pause with 0.5h left through 25-26, finish after resumption at 26.5, and complete a successful 28-29 mission. Native event logs are byte-identical; report tables agree except their descriptions.",
        "metric_interpretation": "ResourceResults.NRW is waiting demand, not booked work. Each run reports four crew-hours of positive work and two resource-hours of waiting; all 72 half-hour resource/system/stock bins are independently replayed.",
        "limits": ["One first-to-second elapsed-day pair does not establish weekly or automatic calendar recurrence.", "Overlapping windows, capacity-limit errors, MAXUT, GUI behavior and cross-engine equivalence are not covered.", "The index dictionary fingerprint matches a prior C07 contract declaration, but its original file is unavailable for independent hashing; the installed manual PDF is hashed.", "SSH/GUI/queue continuity is replayed from sealed metadata; the reviewer did not rerun native SIMLOX."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
