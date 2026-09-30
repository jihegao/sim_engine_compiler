"""Independent read-only replay of the C06 both-resource-zero native candidate.

Standard library only. Never imports author scripts or executes native SIMLOX.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "C06-alternative-resource-v1.0.0" / "primary-0-artf-2-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
RUN = CASE / "runs" / "c06-both-zero-20260930-01"
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_report(path: Path):
    # Native report has structural trailing commas. Remove only those outside
    # strings; preserve every report value exactly.
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = escaped = False
    removed = 0
    for pos, ch in enumerate(raw):
        if quoted:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
            out.append(ch)
        elif ch == "," and re.match(r"\s*[}\]]", raw[pos + 1 :]):
            removed += 1
        else:
            out.append(ch)
    return json.loads("".join(out)), removed


def check(name: str, passed: bool, detail=None):
    entry = {"name": name, "passed": bool(passed)}
    if detail is not None:
        entry["detail"] = detail
    CHECKS.append(entry)


def tables(document, root="model"):
    arr = document[root]["tables"]
    names = [table["name"] for table in arr]
    return {table["name"]: table for table in arr}, len(names) == len(set(names))


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def names(table):
    return [column["name"] for column in table["columns"]]


def body(table):
    return None if table is None else {key: value for key, value in table.items() if key != "name"}


def at(table, start):
    columns = names(table)
    row = next(row for row in rows(table) if row[columns.index("STINT")] == start)
    return dict(zip(columns, row))


def stamp(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    source_path = CASE / "both-zero-input.json"
    check("contract identity and accepted C06 parent", contract["case_id"] == "C06" and contract["parent_case"] == "C06.alternative_resource_artf.1.0.0" and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_sha256"] == "42aeabcf2f7ca79efc568c515bfd5989715cdc0270f59acaad3bfe46c974bd1f")
    check("frozen child source SHA", sha(source_path) == sha(RUN / "input.json") == contract["input_sha256"] == diff["input_sha256"])
    check("manual fingerprint/pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_pages"] == [397, 398, 399, 407, 408, 409, 412, 413, 414])
    check("unpublished candidate contract", contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published")
    parent, parent_unique = tables(load(PARENT))
    source, source_unique = tables(load(source_path))
    check("unique 31-table parent/child", parent_unique and source_unique and len(parent) == len(source) == 31)
    delta = {key: {"before": body(parent.get(key)), "after": body(source.get(key))} for key in parent.keys() | source.keys() if parent.get(key) != source.get(key)}
    check("exact two-table parent diff", delta == diff["differences"] and set(delta) == set(contract["changed_tables_only"]) == {"ProblemDescription", "ResourceAllocation"})
    check("all other parent tables identical", all(parent.get(key) == source.get(key) for key in parent.keys() | source.keys() if key not in delta))
    check("source description exact", rows(source["ProblemDescription"]) == [["C06 alternative preparation resource; primary 0; alternative 0; ARTF 2"]])
    check("both primary and alternate capacities zero", rows(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 0, None], ["AIR_BASIC", "P-ALT", "BASE-01", 0, None]])
    check("required INSPECT and ARTF remain from parent", source["MissionPreparation"] == parent["MissionPreparation"] and source["Tasks"] == parent["Tasks"] and source["TaskBreakDown"] == parent["TaskBreakDown"] and source["SubTaskResource"] == parent["SubTaskResource"] and rows(source["TaskBreakDown"]) == [["PREP-FIXED", 1, "INSPECT", 1 / 3, None, None]] and rows(source["SubTaskResource"]) == [["PREP-FIXED", 1, "P-CREW", 1, 1, "P-ALT", 2, None, None]])

    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    steps = load(RUN / "steps.json")
    check("invocation identity/source", invocation["case_id"] == "C06" and invocation["variant"] == "both-zero" and invocation["run_id"] == RUN.name and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(PARENT))
    check("session-zero SSH and native queue", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    check("GUI identity preserved", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
    current_paths = {
        "input": RUN / "input.json", "parent": PARENT,
        "contract": CASE / "contract.json", "builder": CASE / "build.py",
        "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
        "python": Path(invocation["planned_check"]["executable"]),
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    }
    sealed = invocation["source_hashes_before"]
    check("current source/runtime hashes and frozen before/after", all(path.exists() and sha(path) == sealed[key] for key, path in current_paths.items()) and closure["source_hashes_before"] == sealed == closure["source_hashes_after"] and invocation["contract_sha256"] == sealed["contract"] and invocation["builder_sha256"] == sealed["builder"] and invocation["checker_sha256"] == sealed["checker"] and invocation["runner_script_sha256"] == sealed["runner_script"] and invocation["simlox_exe_sha256"] == sealed["simlox_exe"])
    check("invocation and closure seal", closure["invocation_sha256"] == sha(RUN / "invocation.json") and closure["run_id"] == RUN.name and closure["error"] is None)
    raw_files = {path.name for path in RUN.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
    check("complete raw inventory", raw_files == set(closure["raw"]))
    for filename, metadata in closure["raw"].items():
        path = RUN / filename
        check("raw seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
    check("five successful ordered steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps))
    check("native commands match invocation", [step["name"] for step in steps[:4]] == [step["name"] for step in invocation["planned_commands"]] and [step["arguments"] for step in steps[:4]] == [step["arguments"] for step in invocation["planned_commands"]])
    check("step timestamps ordered", all(stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))

    input_tables, input_unique = tables(load(RUN / "input.json"))
    exported_tables, exported_unique = tables(load(RUN / "roundtrip-raw.json"))
    populated = {key for key, table in input_tables.items() if rows(table)}
    check("20 row-containing input tables", input_unique and exported_unique and len(populated) == 20)
    for key in sorted(populated):
        check("exact native import/export roundtrip " + key, input_tables[key] == exported_tables.get(key))
    imported = (RUN / "import.log").read_text(errors="replace")
    exported = (RUN / "export.log").read_text(errors="replace")
    calculated = (RUN / "run.log").read_text(errors="replace")
    check("31-form import/export complete", "Number of forms inserted: 31" in imported and "Import completed!" in imported and "Export completed!" in exported)
    check("zero conversion errors and two known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calculated and calculated.count("warning #108") == 1 and calculated.count("warning #126") == 1 and "error #" not in calculated.lower() and "Starting simulation..." in calculated and "Saving results ..." in calculated)
    check("JSON report generated", "Generating Json-report" in (RUN / "report-export.log").read_text(errors="replace"))

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    check("initial zero inventory", "Free resources at: <BASE-01,0> P-CREW 0, P-ALT 0" in log)
    check("one two-aircraft formation ordered/assigned", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1 and log.count("mission allocates system:") == 2)
    for aircraft in (0, 1):
        subtask = f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"
        check(f"aircraft {aircraft} primary and alternative tests fail", f"Time: 7.5  {subtask} resource availability test\n  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed \n  Availability test on  <P-ALT at <BASE-01,0>> request for: 1 failed" in log)
        check(f"aircraft {aircraft} waits and stops without work", f"Time: 7.5  {subtask} requests resources" in log and f"Time: 8.66667  {subtask} ordered to stop" in log and f"Time: 8.66667  {subtask} resource waiting stopped" in log and f"Time: 8.66667  system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}> stopped" in log)
        check(f"aircraft {aircraft} terminal ready", f"Time: 8.66667 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,{aircraft}>" in log)
    check("exactly two failed tests for each resource type", log.count("<P-CREW at <BASE-01,0>> request for: 1 failed") == 2 and log.count("<P-ALT at <BASE-01,0>> request for: 1 failed") == 2)
    check("no resource booking, performance or completion", "books resources" not in log and "allocated to maintenance task" not in log and "deallocated from  maintenance task" not in log and "starts performing" not in log and "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed" not in log and "subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> completed" not in log)
    check("finite-deadline cancellation; no mission launch", log.count("Time: 8.66667 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:") == 1 and "mission starting" not in log and "mission success" not in log and "mission completed" not in log)
    check("both aircraft ready after cleanup", "Time: 8.66667 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log)

    raw_report, removed = load_report(RUN / "report-raw.json")
    result_tables, unique_report = tables(raw_report, "report")
    check("six report tables and structural parse", unique_report and set(result_tables) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
    check("72 complete half-hour bins", all(len(rows(result_tables[key])) == 72 and all(at(result_tables[key], i / 2)["ETINT"] == (i + 1) / 2 for i in range(72)) for key in ("SystemResults", "StockTotalResults", "ResourceResults")))
    summary = dict(zip(names(result_tables["ResultSummary"]), rows(result_tables["ResultSummary"])[0]))
    check("summary has no completed mission", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 0)
    total = dict(zip(names(result_tables["ResourceResultsTotal"]), rows(result_tables["ResourceResultsTotal"])[0]))
    check("zero resource stock/use with finite waiting", total["NR"] == total["NRUM"] == total["NRMO"] == total["NRMA"] == 0 and abs(total["NRW"] * 36 - 7 / 3) < 1e-5)
    check("report waiting and return to readiness", at(result_tables["ResourceResults"], 7.5)["NRW"] == 2 and at(result_tables["ResourceResults"], 8)["NRW"] == 2 and abs(at(result_tables["ResourceResults"], 8.5)["NRW"] - 2 / 3) < 1e-6 and at(result_tables["ResourceResults"], 9)["NRW"] == 0 and at(result_tables["SystemResults"], 7.5)["NSYMA"] == 2 and abs(at(result_tables["SystemResults"], 8.5)["NSYRY"] - 4 / 3) < 1e-6 and at(result_tables["SystemResults"], 9)["NSYRY"] == 2)
    waiting_bins = {7.5: 2, 8.0: 2, 8.5: 2 / 3}
    check("exact resource waiting ledger; zero elsewhere", all(abs(at(result_tables["ResourceResults"], i / 2)["NRW"] - waiting_bins.get(i / 2, 0)) < 1e-6 for i in range(72)))
    check("exact system preparation ledger; zero elsewhere", all(abs(at(result_tables["SystemResults"], i / 2)["NSYMP"] - waiting_bins.get(i / 2, 0)) < 1e-6 for i in range(72)))
    check("zero booking/operation throughout report", all(at(result_tables["ResourceResults"], i / 2)["NR"] == at(result_tables["ResourceResults"], i / 2)["NRUM"] == 0 for i in range(72)) and all(at(result_tables["SystemResults"], i / 2)["NSYMO"] == 0 for i in range(72)))
    check("no stock events in any report bin", all(all(at(result_tables["StockTotalResults"], i / 2)[key] == 0 for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for i in range(72)))
    check("terminal waiting cleared and aircraft ready", at(result_tables["ResourceResults"], 35.5)["NRW"] == 0 and at(result_tables["SystemResults"], 35.5)["NSYRY"] == 2)

    failures = [entry for entry in CHECKS if not entry["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C06.both_resource_zero", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_finite_deadline_all_zero_waiting" if not failures else "NO_GO",
        "accepted_scope": "With primary P-CREW and alternative P-ALT both at zero, both aircraft are assigned to the planned mission and start INSPECT preparation at 7.5. Both per-aircraft primary and alternative availability tests fail; neither books a resource or performs work. The retained finite deadline cancels the formation at 8.66667, both waits stop, and two aircraft return ready with no resource or stock movement.",
        "metric_interpretation": "ResourceResults.NRW and SystemResults.NSYMP represent the two waiting preparation requests from 7.5 through 8.66667, averaged into half-hour bins (2, 2, 2/3); NRW is waiting demand, not booked resource work. Resource stock NR and use NRUM/NRMA/NRMO remain zero.",
        "limits": ["This single fixed-seed all-zero boundary with a finite mission deadline does not establish indefinite waiting or horizon-unfinished behavior.", "Other capacities, alternative types, ARTF values and RPROB below one remain unverified.", "INSPECT identity is bound by exact source/roundtrip; native log uses generic subtask labels.", "SSH/GUI/queue continuity is replayed from sealed metadata; the reviewer did not observe or rerun native SIMLOX live."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
