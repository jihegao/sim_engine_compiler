"""Independent standard-library replay of twelve sealed C06 RPROB=0.5 runs.

Reads frozen source and raw artifacts only. Does not import author code or run SIMLOX.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "C06-rprob-endpoints-v1.0.0" / "rprob-1-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXPECTED_PATTERNS = {
    1: "ND", 2: "DN", 3: "ND", 4: "DN", 5: "NN", 6: "DD",
    7: "NN", 8: "ND", 9: "DN", 10: "NN", 11: "DD", 12: "NN",
}
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_report(path: Path):
    # SIMLOX report has trailing structural commas. Remove these only outside
    # JSON strings without changing any report value.
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


def check(name: str, ok: bool, detail=None):
    item = {"name": name, "passed": bool(ok)}
    if detail is not None:
        item["detail"] = detail
    CHECKS.append(item)


def tables(doc, root="model"):
    arr = doc[root]["tables"]
    keys = [table["name"] for table in arr]
    return {table["name"]: table for table in arr}, len(keys) == len(set(keys))


def rows(table):
    return [row for inst in table["instances"] for row in inst["rows"]]


def columns(table):
    return [col["name"] for col in table["columns"]]


def body(table):
    return None if table is None else {key: value for key, value in table.items() if key != "name"}


def at(table, start):
    names = columns(table)
    row = next(row for row in rows(table) if row[names.index("STINT")] == start)
    return dict(zip(names, row))


def stamp(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def classify(log: str, aircraft: int):
    subtask = f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"
    lead = f"Time: 7.5  {subtask} resource availability test\n"
    demanded = lead + "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed \n  Availability test on  <P-ALT at <BASE-01,0>> request for: 1 failed"
    no_demand = lead + f"Time: 7.5  {subtask} books resources"
    if demanded in log and no_demand not in log:
        return "D"
    if no_demand in log and demanded not in log:
        return "N"
    return "?"


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    index = load(CASE / "evidence-index.json")
    indexed_runs = {item["variant"]: item for item in index["runs"]}
    check("evidence index identity and twelve unique entries", index["schema"] == "simlox-c06-rprob-half-matrix-evidence-index/v1" and len(index["runs"]) == len(indexed_runs) == 12 and set(indexed_runs) == {f"seed-{i:02d}" for i in range(1, 13)})
    check("evidence index manual and native fingerprints", index["source_manual_sha256"] == sha(MANUAL) and index["simlox_exe_sha256"] == sha(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")))
    check("contract identity and accepted RPROB-one parent", contract["case_id"] == "C06" and contract["variant_id"] == "C06.var04" and contract["parent_case"] == "C06.rprob_endpoints.1.0.0" and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_sha256"] == "0e548e167a48aed7e76dfeec5b0fbdfbb817f41bc3c88e0b1e246396ab218fa4")
    check("manual fingerprint/pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_pages"] == [397, 398, 399, 407, 408, 409, 412, 413, 414])
    check("frozen unpublished candidate", contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published")
    check("frozen source change scope", set(contract["changed_tables_only"]) == {"ProblemDescription", "SubTaskResource", "Control"})
    parent, unique_parent = tables(load(PARENT))
    check("unique 31-table parent", unique_parent and len(parent) == 31)
    observations = {}

    for seed in range(1, 13):
        variant = f"seed-{seed:02d}"
        prefix = variant + ": "
        source_path = CASE / f"{variant}-input.json"
        run_id = f"c06-rprob-half-{variant}-20260930-01"
        run = CASE / "runs" / run_id
        source, unique = tables(load(source_path))
        check(prefix + "unique 31-table source", unique and len(source) == 31)
        check(prefix + "frozen input and run copy SHA", sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant] == diff["input_sha256"][variant])
        actual_diff = {key: {"before": body(parent.get(key)), "after": body(source.get(key))} for key in parent.keys() | source.keys() if parent.get(key) != source.get(key)}
        check(prefix + "exact parent delta", actual_diff == diff["parent_differences"][variant], sorted(actual_diff))
        expected_delta = {"ProblemDescription", "SubTaskResource"} if seed == 1 else {"ProblemDescription", "SubTaskResource", "Control"}
        check(prefix + "only expected tables differ", set(actual_diff) == expected_delta)
        check(prefix + "all other parent tables exact", all(parent.get(key) == source.get(key) for key in parent.keys() | source.keys() if key not in actual_diff))
        check(prefix + "description seed tag", rows(source["ProblemDescription"]) == [[f"C06 intermediate probability resource demand; RPROB 0.5; seed {seed}"]])
        check(prefix + "RPROB half with zero resource capacities", rows(source["SubTaskResource"]) == [["PREP-FIXED", 1, "P-CREW", 1, 0.5, "P-ALT", 2, None, None]] and source["ResourceAllocation"] == parent["ResourceAllocation"] and rows(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 0, None], ["AIR_BASIC", "P-ALT", "BASE-01", 0, None]])
        control = dict(zip(columns(source["Control"]), rows(source["Control"])[0]))
        check(prefix + "explicit frozen seed and one replication", control["RSEED"] == str(seed) and control["NREPS"] == 1 and source["Control"]["columns"] == parent["Control"]["columns"])
        check(prefix + "fixed INSPECT and schedule retained", source["MissionPreparation"] == parent["MissionPreparation"] and source["TaskBreakDown"] == parent["TaskBreakDown"] and rows(source["TaskBreakDown"]) == [["PREP-FIXED", 1, "INSPECT", 1 / 3, None, None]])

        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(prefix + "invocation identity/source", invocation["case_id"] == "C06" and invocation["variant"] == variant and invocation["run_id"] == run_id and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(PARENT))
        check(prefix + "session-zero SSH and mutex", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(prefix + "GUI identity preserved", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
        current = {
            "input": run / "input.json", "parent": PARENT,
            "contract": CASE / "contract.json", "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "python": Path(invocation["planned_check"]["executable"]),
            "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        }
        recorded = invocation["source_hashes_before"]
        check(prefix + "source/runtime seals before/after", all(path.exists() and sha(path) == recorded[key] for key, path in current.items()) and closure["source_hashes_before"] == recorded == closure["source_hashes_after"] and invocation["contract_sha256"] == recorded["contract"] and invocation["builder_sha256"] == recorded["builder"] and invocation["checker_sha256"] == recorded["checker"] and invocation["runner_script_sha256"] == recorded["runner_script"] and invocation["simlox_exe_sha256"] == recorded["simlox_exe"])
        check(prefix + "invocation/closure seal", closure["invocation_sha256"] == sha(run / "invocation.json") and closure["run_id"] == run_id and closure["error"] is None)
        raw_files = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "complete raw inventory", raw_files == set(closure["raw"]))
        for filename, metadata in closure["raw"].items():
            path = run / filename
            check(prefix + "raw seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
        check(prefix + "five successful ordered steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps))
        check(prefix + "native commands match invocation", [step["name"] for step in steps[:4]] == [p["name"] for p in invocation["planned_commands"]] and [step["arguments"] for step in steps[:4]] == [p["arguments"] for p in invocation["planned_commands"]])
        check(prefix + "ordered step timestamps", all(stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))

        original, unique_original = tables(load(run / "input.json"))
        roundtrip, unique_roundtrip = tables(load(run / "roundtrip-raw.json"))
        populated = {key for key, table in original.items() if rows(table)}
        check(prefix + "20 row-containing source tables", unique_original and unique_roundtrip and len(populated) == 20)
        for key in sorted(populated):
            check(prefix + "exact native roundtrip " + key, original[key] == roundtrip.get(key))
        imported = (run / "import.log").read_text(errors="replace")
        exported = (run / "export.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(prefix + "31-form import/export complete", "Number of forms inserted: 31" in imported and "Import completed!" in imported and "Export completed!" in exported)
        check(prefix + "zero conversion errors and two known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted)
        check(prefix + "report generation complete", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        pattern = "".join(classify(log, aircraft) for aircraft in (0, 1))
        observations[variant] = pattern
        check(prefix + "observed per-aircraft pattern", pattern == EXPECTED_PATTERNS[seed], pattern)
        indexed = indexed_runs[variant]
        check(prefix + "index identity and original local path", indexed["run_id"] == run_id and Path(indexed["original_run_dir"]).resolve() == run.resolve())
        check(prefix + "index raw byte fingerprints", indexed["input_sha256"] == sha(run / "input.json") and indexed["closure_sha256"] == sha(run / "closure.json") and indexed["model_log_sha256"] == sha(run / "model.log") and indexed["report_raw_sha256"] == sha(run / "report-raw.json"))
        check(prefix + "index outcome inferred from log", indexed["observed_pattern"] == pattern and indexed["mission_outcome"] == ("success" if pattern == "NN" else "cancelled") and indexed["cancellation_hour"] == (None if pattern == "NN" else (8.66667 if pattern == "DD" else 9)))
        check(prefix + "one two-aircraft mission assigned", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1 and log.count("mission allocates system:") == 2)
        check(prefix + "zero initial and typed resource allocation", "Free resources at: <BASE-01,0> P-CREW 0, P-ALT 0" in log and "<P-CREW at <BASE-01,0>> allocated" not in log and "<P-ALT at <BASE-01,0>> allocated" not in log and "<P-CREW at <BASE-01,0>> deallocated" not in log and "<P-ALT at <BASE-01,0>> deallocated" not in log)
        demand_count = pattern.count("D")
        no_demand_count = pattern.count("N")
        cancel_at = "8.66667" if pattern == "DD" else ("9" if demand_count else None)
        check(prefix + "generic books count tracks no-demand tasks", log.count("books resources") == no_demand_count and log.count("frees resources") == no_demand_count)
        for aircraft, state in enumerate(pattern):
            subtask = f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"
            check(prefix + f"aircraft {aircraft} preparation start", f"Time: 7.5  {subtask} started" in log and f"Time: 7.5  {subtask} requests resources" in log)
            if state == "N":
                check(prefix + f"aircraft {aircraft} no typed demand and fixed work", f"Time: 7.5  {subtask} resource availability test\nTime: 7.5  {subtask} books resources" in log and f"Time: 7.5  {subtask} starts performing, planned to last for 0.333333 hours" in log)
                check(prefix + f"aircraft {aircraft} completes at 7.83333", f"Time: 7.83333  {subtask} completed" in log and f"Time: 7.83333  {subtask} frees resources" in log and f"Time: 7.83333 <TEACH-AIR-01,{aircraft}> preparation ended" in log)
            elif state == "D":
                check(prefix + f"aircraft {aircraft} failed primary and alternative tests", f"Time: 7.5  {subtask} resource availability test\n  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed \n  Availability test on  <P-ALT at <BASE-01,0>> request for: 1 failed" in log)
                check(prefix + f"aircraft {aircraft} waiting stopped at cancellation", f"Time: {cancel_at}  {subtask} ordered to stop" in log and f"Time: {cancel_at}  {subtask} resource waiting stopped" in log and f"Time: {cancel_at}  system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}> stopped" in log and f"Time: 7.5  {subtask} starts performing" not in log)
        if pattern == "NN":
            check(prefix + "successful 8-9 mission", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log and log.count("Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:") == 1 and log.count("Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:") == 1 and "mission cancelled" not in log)
        else:
            check(prefix + "finite-deadline cancellation and no launch", log.count(f"Time: {cancel_at} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:") == 1 and "mission starting" not in log and "mission success" not in log and "mission completed" not in log)
        check(prefix + "terminal two ready aircraft", f"Time: {('9' if pattern != 'DD' else '8.66667')} <TEACH-UNIT at <BASE-01,0>> systems ready: 2 :" in log and "<TEACH-AIR-01,0>" in log and "<TEACH-AIR-01,1>" in log)

        report, removed = load_report(run / "report-raw.json")
        rt, unique_report = tables(report, "report")
        check(prefix + "six report tables and structural parse", unique_report and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
        check(prefix + "72 complete half-hour bins", all(len(rows(rt[key])) == 72 and all(at(rt[key], i / 2)["ETINT"] == (i + 1) / 2 for i in range(72)) for key in ("SystemResults", "StockTotalResults", "ResourceResults")))
        summary = dict(zip(columns(rt["ResultSummary"]), rows(rt["ResultSummary"])[0]))
        success = 1 if pattern == "NN" else 0
        check(prefix + "mission summary matches pattern", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == success)
        expected_wait_hours = 0 if pattern == "NN" else (7 / 3 if pattern == "DD" else 1.5)
        total = dict(zip(columns(rt["ResourceResultsTotal"]), rows(rt["ResourceResultsTotal"])[0]))
        check(prefix + "resource total zero stock/use, expected waiting", total["NR"] == total["NRUM"] == total["NRMA"] == total["NRMO"] == 0 and abs(total["NRW"] * 36 - expected_wait_hours) < 1e-5)
        wait_bins = {} if pattern == "NN" else ({7.5: 2, 8.0: 2, 8.5: 2 / 3} if pattern == "DD" else {7.5: 1, 8.0: 1, 8.5: 1})
        prep_bins = {7.5: 2 / 3 * no_demand_count + demand_count}
        if pattern == "DD":
            prep_bins.update({8.0: 2, 8.5: 2 / 3})
        elif demand_count == 1:
            prep_bins.update({8.0: 1, 8.5: 1})
        operation_bins = {8.0: 2, 8.5: 2} if pattern == "NN" else {}
        check(prefix + "exact NRW waiting ledger over all 72 bins", all(abs(at(rt["ResourceResults"], i / 2)["NRW"] - wait_bins.get(i / 2, 0)) < 1e-6 for i in range(72)))
        check(prefix + "exact NSYMP preparation ledger over all bins", all(abs(at(rt["SystemResults"], i / 2)["NSYMP"] - prep_bins.get(i / 2, 0)) < 1e-6 for i in range(72)))
        check(prefix + "exact NSYMO mission operation ledger", all(abs(at(rt["SystemResults"], i / 2)["NSYMO"] - operation_bins.get(i / 2, 0)) < 1e-6 for i in range(72)))
        check(prefix + "zero typed resource stock/use every bin", all(all(at(rt["ResourceResults"], i / 2)[key] == 0 for key in ("NR", "NRUM", "NRMA", "NRMO")) for i in range(72)))
        check(prefix + "zero stock events every bin", all(all(at(rt["StockTotalResults"], i / 2)[key] == 0 for key in ("NBO", "NDF", "NDD", "NDR", "NDP", "NLD", "NWT")) for i in range(72)))
        check(prefix + "terminal inventory, waiting and readiness", at(rt["ResourceResults"], 35.5)["NR"] == at(rt["ResourceResults"], 35.5)["NRW"] == 0 and at(rt["SystemResults"], 35.5)["NSYRY"] == 2 and at(rt["StockTotalResults"], 35.5)["NBO"] == 0)
        check(prefix + "assignment/return report boundary", at(rt["SystemResults"], 7.5)["NSYMA"] == 2 and at(rt["SystemResults"], 9)["NSYRY"] == 2)

    check("all four observed patterns represented", set(observations.values()) == {"NN", "ND", "DN", "DD"})
    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C06.var04.rprob_half_matrix", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_twelve_seed_observed_patterns" if not failures else "NO_GO",
        "observed_patterns": observations,
        "accepted_scope": "In twelve fixed RPROB=0.5 native runs with both resource capacities zero, each aircraft's observed typed-demand/work trace is classified N (no typed resource need, 20-minute preparation completes) or D (both resource tests fail and preparation waits). All four NN/ND/DN/DD patterns appear. NN launches at 8 and succeeds at 9; mixed patterns cancel at 9 after one preparation completes; DD cancels at 8.66667. All runs end with two ready aircraft, zero typed resource allocation/use, and zero stock events.",
        "metric_interpretation": "Generic 'books resources' text on an N subtask does not establish P-CREW or P-ALT allocation. Typed resource event lines and NR/NRUM/NRMA/NRMO are zero. ResourceResults.NRW reports waiting demand, not booked work; the exact 72-bin waiting and SystemResults.NSYMP/NSYMO ledgers are checked for each seed.",
        "limits": ["Twelve fixed seeds show observed pattern coverage only; they do not establish a 0.5 Bernoulli law, independent per-aircraft sampling, or random-stream stability.", "Both resource capacities are zero, so interactions with available resources remain untested.", "INSPECT identity is source/roundtrip bound; the native event log uses generic subtask labels.", "SSH/GUI/queue continuity is replayed from sealed metadata; this reviewer did not rerun or observe native SIMLOX live."],
        "checks": CHECKS,
    }
    out = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    out.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
