"""Independent read-only standard-library replay of C06 RPROB endpoints."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "C06-both-resource-zero-v1.0.0" / "both-zero-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path):
    # SIMLOX's report has trailing structural commas. Remove only those outside
    # strings; all names and numerical values remain unchanged.
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
        elif char == "," and re.match(r"\s*[}\]]", raw[pos + 1 :]):
            removed += 1
        else:
            out.append(char)
    return json.loads("".join(out)), removed


def check(name: str, passed: bool, detail=None):
    item = {"name": name, "passed": bool(passed)}
    if detail is not None:
        item["detail"] = detail
    CHECKS.append(item)


def tables(obj, root="model"):
    arr = obj[root]["tables"]
    keys = [t["name"] for t in arr]
    return {t["name"]: t for t in arr}, len(keys) == len(set(keys))


def rows(table):
    return [row for inst in table["instances"] for row in inst["rows"]]


def names(table):
    return [col["name"] for col in table["columns"]]


def body(table):
    return None if table is None else {key: value for key, value in table.items() if key != "name"}


def at(table, start):
    cols = names(table)
    row = next(row for row in rows(table) if row[cols.index("STINT")] == start)
    return dict(zip(cols, row))


def stamp(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    check("contract identity and accepted both-zero parent", contract["case_id"] == "C06" and contract["variant_id"] == "C06.var04" and contract["parent_case"] == "C06.both_resource_zero.1.0.0" and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_sha256"] == "05c6da90b5c8e509ea57132026d781822e1399d7693f469ec08c307bff9342cc")
    check("manual fingerprint/pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_pages"] == [397, 398, 399, 407, 408, 409, 412, 413, 414])
    check("frozen unpublished candidate", contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published")
    check("frozen two-table change set", set(contract["changed_tables_only"]) == {"ProblemDescription", "SubTaskResource"})
    parent, unique_parent = tables(load(PARENT))
    check("unique 31-table parent", unique_parent and len(parent) == 31)
    sources = {}

    for endpoint in (0, 1):
        variant = f"rprob-{endpoint}"
        prefix = variant + ": "
        run_id = f"c06-{variant}-20260930-01"
        run = CASE / "runs" / run_id
        source_path = CASE / f"{variant}-input.json"
        source, unique = tables(load(source_path))
        sources[endpoint] = source
        check(prefix + "unique 31-table source", unique and len(source) == 31)
        check(prefix + "source hash and copied run input", sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant] == diff["input_sha256"][variant])
        actual_diff = {key: {"before": body(parent.get(key)), "after": body(source.get(key))} for key in parent.keys() | source.keys() if parent.get(key) != source.get(key)}
        check(prefix + "exact frozen parent delta", actual_diff == diff["parent_differences"][variant], sorted(actual_diff))
        expected_delta = {"ProblemDescription", "SubTaskResource"} if endpoint == 0 else {"ProblemDescription"}
        check(prefix + "only intended tables differ", set(actual_diff) == expected_delta)
        check(prefix + "all other parent tables identical", all(parent.get(key) == source.get(key) for key in parent.keys() | source.keys() if key not in actual_diff))
        check(prefix + "endpoint description", rows(source["ProblemDescription"]) == [[f"C06 zero-resource probability endpoint; RPROB {endpoint}"]])
        check(prefix + "only RPROB endpoint changes resource demand", source["SubTaskResource"]["columns"] == parent["SubTaskResource"]["columns"] and rows(source["SubTaskResource"]) == [["PREP-FIXED", 1, "P-CREW", 1, endpoint, "P-ALT", 2, None, None]])
        check(prefix + "both resource stocks stay zero", source["ResourceAllocation"] == parent["ResourceAllocation"] and rows(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 0, None], ["AIR_BASIC", "P-ALT", "BASE-01", 0, None]])
        check(prefix + "fixed INSPECT source and schedule retained", source["MissionPreparation"] == parent["MissionPreparation"] and source["TaskBreakDown"] == parent["TaskBreakDown"] and rows(source["TaskBreakDown"]) == [["PREP-FIXED", 1, "INSPECT", 1 / 3, None, None]])

        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(prefix + "invocation identity/source", invocation["case_id"] == "C06" and invocation["variant"] == variant and invocation["run_id"] == run_id and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(PARENT))
        check(prefix + "session-zero SSH and queue", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(prefix + "GUI identity preserved", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
        current = {
            "input": run / "input.json", "parent": PARENT,
            "contract": CASE / "contract.json", "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "python": Path(invocation["planned_check"]["executable"]),
            "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        }
        sealed = invocation["source_hashes_before"]
        check(prefix + "source/runtime seals before/after", all(path.exists() and sha(path) == sealed[key] for key, path in current.items()) and closure["source_hashes_before"] == sealed == closure["source_hashes_after"] and invocation["contract_sha256"] == sealed["contract"] and invocation["builder_sha256"] == sealed["builder"] and invocation["checker_sha256"] == sealed["checker"] and invocation["runner_script_sha256"] == sealed["runner_script"] and invocation["simlox_exe_sha256"] == sealed["simlox_exe"])
        check(prefix + "invocation and closure seal", closure["invocation_sha256"] == sha(run / "invocation.json") and closure["run_id"] == run_id and closure["error"] is None)
        raw_files = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "complete raw inventory", raw_files == set(closure["raw"]))
        for filename, metadata in closure["raw"].items():
            path = run / filename
            check(prefix + "raw seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
        check(prefix + "five successful ordered steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps))
        check(prefix + "native commands match invocation", [step["name"] for step in steps[:4]] == [planned["name"] for planned in invocation["planned_commands"]] and [step["arguments"] for step in steps[:4]] == [planned["arguments"] for planned in invocation["planned_commands"]])
        check(prefix + "step timestamps ordered", all(stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))

        input_tables, unique_input = tables(load(run / "input.json"))
        roundtrip, unique_roundtrip = tables(load(run / "roundtrip-raw.json"))
        populated = {key for key, table in input_tables.items() if rows(table)}
        check(prefix + "20 row-containing input tables", unique_input and unique_roundtrip and len(populated) == 20)
        for key in sorted(populated):
            check(prefix + "exact native roundtrip " + key, input_tables[key] == roundtrip.get(key))
        imported = (run / "import.log").read_text(errors="replace")
        exported = (run / "export.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(prefix + "31-form import/export complete", "Number of forms inserted: 31" in imported and "Import completed!" in imported and "Export completed!" in exported)
        check(prefix + "zero conversion errors/two known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted)
        check(prefix + "report generation complete", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check(prefix + "initial zero resource inventory", "Free resources at: <BASE-01,0> P-CREW 0, P-ALT 0" in log)
        check(prefix + "one two-aircraft mission assigned", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1 and log.count("mission allocates system:") == 2)
        check(prefix + "no typed resource booking/release", "<P-CREW at <BASE-01,0>> allocated" not in log and "<P-ALT at <BASE-01,0>> allocated" not in log and "<P-CREW at <BASE-01,0>> deallocated" not in log and "<P-ALT at <BASE-01,0>> deallocated" not in log)
        for aircraft in (0, 1):
            subtask = f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"
            check(prefix + f"aircraft {aircraft} source-bound task starts", f"Time: 7.5  {subtask} started" in log and f"Time: 7.5  {subtask} requests resources" in log)
            if endpoint == 0:
                check(prefix + f"aircraft {aircraft} no sampled demand", f"Time: 7.5  {subtask} resource availability test\nTime: 7.5  {subtask} books resources" in log and f"Time: 7.5  {subtask} starts performing, planned to last for 0.333333 hours" in log)
                check(prefix + f"aircraft {aircraft} fixed task completes without typed release", f"Time: 7.83333  {subtask} completed" in log and f"Time: 7.83333  {subtask} frees resources\nTime: 7.83333 <BASE-01,0> trig missions" in log and f"Time: 7.83333 <TEACH-AIR-01,{aircraft}> preparation ended" in log)
            else:
                check(prefix + f"aircraft {aircraft} both availability tests fail", f"Time: 7.5  {subtask} resource availability test\n  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed \n  Availability test on  <P-ALT at <BASE-01,0>> request for: 1 failed" in log)
                check(prefix + f"aircraft {aircraft} waiting stopped at cancellation", f"Time: 8.66667  {subtask} ordered to stop" in log and f"Time: 8.66667  {subtask} resource waiting stopped" in log and f"Time: 8.66667  system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}> stopped" in log)
        if endpoint == 0:
            check(prefix + "generic book/free text is not typed allocation", log.count("books resources") == 2 and log.count("frees resources") == 2 and "<P-CREW at <BASE-01,0>> request for: 1" not in log and "<P-ALT at <BASE-01,0>> request for: 1" not in log)
            check(prefix + "one successful 8-9 mission", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log and log.count("Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:") == 1 and log.count("Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:") == 1 and "mission cancelled" not in log)
            check(prefix + "terminal two aircraft ready at 9", "Time: 9 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log)
        else:
            check(prefix + "exactly two failed tests per resource", log.count("<P-CREW at <BASE-01,0>> request for: 1 failed") == 2 and log.count("<P-ALT at <BASE-01,0>> request for: 1 failed") == 2)
            check(prefix + "finite-deadline cancellation, no work/launch", log.count("Time: 8.66667 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:") == 1 and "books resources" not in log and "starts performing" not in log and "mission starting" not in log and "mission success" not in log)
            check(prefix + "terminal two aircraft ready at 8.66667", "Time: 8.66667 <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log)

        parsed_report, removed = native_report(run / "report-raw.json")
        rt, unique_report = tables(parsed_report, "report")
        check(prefix + "six report tables and structural parse", unique_report and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
        check(prefix + "72 complete half-hour bins", all(len(rows(rt[key])) == 72 and all(at(rt[key], i / 2)["ETINT"] == (i + 1) / 2 for i in range(72)) for key in ("SystemResults", "StockTotalResults", "ResourceResults")))
        summary = dict(zip(names(rt["ResultSummary"]), rows(rt["ResultSummary"])[0]))
        success = 1 if endpoint == 0 else 0
        check(prefix + "mission summary endpoint", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == success)
        total = dict(zip(names(rt["ResourceResultsTotal"]), rows(rt["ResourceResultsTotal"])[0]))
        check(prefix + "zero resource stock/use and expected waiting total", total["NR"] == total["NRUM"] == total["NRMA"] == total["NRMO"] == 0 and abs(total["NRW"] * 36 - (0 if endpoint == 0 else 7 / 3)) < 1e-5)
        waiting = {} if endpoint == 0 else {7.5: 2, 8.0: 2, 8.5: 2 / 3}
        check(prefix + "exact NRW waiting bins; zero elsewhere", all(abs(at(rt["ResourceResults"], i / 2)["NRW"] - waiting.get(i / 2, 0)) < 1e-6 for i in range(72)))
        check(prefix + "zero typed resource stock/use in every bin", all(all(at(rt["ResourceResults"], i / 2)[key] == 0 for key in ("NR", "NRUM", "NRMA", "NRMO")) for i in range(72)))
        expected_prep = {7.5: 4 / 3} if endpoint == 0 else waiting
        check(prefix + "system preparation bins and terminal readiness", all(abs(at(rt["SystemResults"], i / 2)["NSYMP"] - expected_prep.get(i / 2, 0)) < 1e-6 for i in range(72)) and at(rt["SystemResults"], 35.5)["NSYRY"] == 2)
        check(prefix + "system operation endpoint", (at(rt["SystemResults"], 8)["NSYMO"] == at(rt["SystemResults"], 8.5)["NSYMO"] == 2 and at(rt["SystemResults"], 9)["NSYRY"] == 2) if endpoint == 0 else all(at(rt["SystemResults"], i / 2)["NSYMO"] == 0 for i in range(72)))
        check(prefix + "no stock events in any bin", all(all(at(rt["StockTotalResults"], i / 2)[key] == 0 for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for i in range(72)))
        check(prefix + "terminal inventory and waiting clear", at(rt["ResourceResults"], 35.5)["NR"] == at(rt["ResourceResults"], 35.5)["NRW"] == 0 and at(rt["StockTotalResults"], 35.5)["NBO"] == 0)

    pair = {key: {"before": body(sources[0].get(key)), "after": body(sources[1].get(key))} for key in sources[0].keys() | sources[1].keys() if sources[0].get(key) != sources[1].get(key)}
    check("exact pairwise endpoint delta", pair == diff["pairwise_differences"] and set(pair) == {"ProblemDescription", "SubTaskResource"})
    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C06.var04", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_rprob_zero_one_endpoints" if not failures else "NO_GO",
        "accepted_scope": "With both resource capacities zero, RPROB 0 yields no typed resource demand for either aircraft: both INSPECT preparation subtasks perform from 7.5 to 7.83333 without a typed allocation, and the 8-9 mission succeeds. At RPROB 1 both aircraft test and fail primary/alternative availability, wait without booking or work, then cancel at 8.66667 and return ready. Resource stock/use and stock events stay zero in both sealed runs.",
        "metric_interpretation": "At RPROB 0 the generic subtask 'books resources' and 'frees resources' lines do not name an allocated P-CREW or P-ALT and do not establish a resource booking. Typed event lines and ResourceResults.NR/NRUM/NRMA/NRMO are zero. At RPROB 1, ResourceResults.NRW and SystemResults.NSYMP show waiting demand in bins 7.5-8=2, 8-8.5=2, 8.5-9=2/3; NRW is not booked work time.",
        "limits": ["Only deterministic RPROB zero/one endpoints under one fixed seed and zero capacity of both types; no inference about intermediate Bernoulli frequency, per-aircraft independence, or nonzero resource capacity.", "INSPECT identity is source/roundtrip bound; the native log labels generic subtasks.", "SSH/GUI/queue continuity is replayed from sealed metadata; this reviewer did not observe or rerun native SIMLOX live."],
        "checks": CHECKS,
    }
    out = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    out.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
