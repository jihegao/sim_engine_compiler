"""Independent standard-library replay of the three C06 sealed CLI runs.

Reads source and raw evidence only. Never imports the author validator or runs SIMLOX.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
CONFIGS = (
    ("primary-2-artf-2", 2, 2, "P-CREW", "7.83333", "0.333333", "8", "9"),
    ("primary-0-artf-1", 0, 1, "P-ALT", "7.83333", "0.333333", "8", "9"),
    ("primary-0-artf-2", 0, 2, "P-ALT", "8.16667", "0.666667", "8.16667", "9.16667"),
)
CHECKS: list[dict] = []


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_report(path: Path):
    # Native JSON reports have structural trailing commas. Remove those only
    # outside quoted strings, preserving all report values.
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


def check(name: str, ok: bool, detail=None):
    entry = {"name": name, "passed": bool(ok)}
    if detail is not None:
        entry["detail"] = detail
    CHECKS.append(entry)


def tables(obj, root="model"):
    arr = obj[root]["tables"]
    names = [t["name"] for t in arr]
    return {t["name"]: t for t in arr}, len(names) == len(set(names))


def rows(table):
    return [row for inst in table["instances"] for row in inst["rows"]]


def names(table):
    return [column["name"] for column in table["columns"]]


def at(table, start):
    cols = names(table)
    row = next(row for row in rows(table) if row[cols.index("STINT")] == start)
    return dict(zip(cols, row))


def stamp(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def ledger(log):
    pattern = r"Time: ([\d.]+)\s+<(P-CREW|P-ALT) at <BASE-01,0>> (allocated to maintenance task|deallocated from\s+maintenance task): 1\s+available now: (\d+)"
    return [(float(t), kind, "book" if verb.startswith("allocated") else "release", int(free)) for t, kind, verb, free in re.findall(pattern, log)]


def main():
    contract = load(CASE / "contract.json")
    check("contract identity and accepted C03 staffing-2 parent", contract["case_id"] == "C06" and contract["parent_case"] == "C03.shared_crew.1.0.2" and sha(PARENT) == contract["parent_input_sha256"] == "83b454bd145621f36571a87cdf8abcbccc184f07ab8f9ad5f3111651c78881e0")
    check("manual fingerprint/pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_pages"] == [397, 398, 399, 407, 408, 409, 412, 413, 414])
    check("frozen candidate contract", contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published")
    changed = {"ProblemDescription", "MissionPreparation", "Tasks", "TaskBreakDown", "SubTaskResource", "Resource", "ResourceAllocation"}
    check("frozen seven-table change scope", set(contract["changed_tables_only"]) == changed)
    parent, parent_unique = tables(load(PARENT))
    check("unique parent tables", parent_unique and len(parent) == 31)
    sources = {}

    for variant, primary, artf, selected, prep_end, duration, launch, finish in CONFIGS:
        prefix = variant + ": "
        run_id = f"c06-{variant}-20260930-01"
        run = CASE / "runs" / run_id
        source_path = CASE / f"{variant}-input.json"
        source, unique = tables(load(source_path))
        sources[variant] = source
        check(prefix + "unique 31-table source", unique and len(source) == 31)
        check(prefix + "source SHA and copied run input", sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant])
        actual_delta = {key for key in parent.keys() | source.keys() if parent.get(key) != source.get(key)}
        check(prefix + "exact seven-table parent delta", actual_delta == changed, sorted(actual_delta))
        check(prefix + "all other parent tables identical", all(parent.get(key) == source.get(key) for key in parent.keys() | source.keys() if key not in changed))
        check(prefix + "exact source description", rows(source["ProblemDescription"]) == [[f"C06 alternative prep resource; primary {primary}; ARTF {artf}"]])
        check(prefix + "fixed 20-minute preparation", rows(source["MissionPreparation"]) == [["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 1 / 3, "PREP-FIXED", None, None]] and rows(source["Tasks"]) == [["PREP-FIXED", "Fixed 20-minute INSPECT preparation", None, None, None]] and rows(source["TaskBreakDown"]) == [["PREP-FIXED", 1, "INSPECT", 1 / 3, None, None]])
        check(prefix + "RPROB1, ARID P-ALT and ARTF", names(source["SubTaskResource"]) == ["TID", "SEQ", "RID", "QTY", "RPROB", "ARID", "ARTF", "ENRMS", "NOTE"] and rows(source["SubTaskResource"]) == [["PREP-FIXED", 1, "P-CREW", 1, 1, "P-ALT", artf, None, None]])
        check(prefix + "two resource types/capacities", rows(source["Resource"]) == [["P-CREW", "Crew A personnel", None, None, None, "SPECIAL", None, None], ["P-ALT", "Alternative preparation personnel", None, None, None, "SPECIAL", None, None]] and rows(source["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", primary, None], ["AIR_BASIC", "P-ALT", "BASE-01", 2, None]])
        check(prefix + "resource table schemas preserved", source["Resource"]["columns"] == parent["Resource"]["columns"] and source["ResourceAllocation"]["columns"] == parent["ResourceAllocation"]["columns"] and source["SubTaskResource"]["columns"] == parent["SubTaskResource"]["columns"])

        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(prefix + "invocation identity and source", invocation["case_id"] == "C06" and invocation["variant"] == variant and invocation["run_id"] == run_id and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == sha(PARENT))
        check(prefix + "session-zero SSH and queue", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(prefix + "GUI preserved", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0 and all(step["gui_preserved"] is True for step in steps))
        current = {
            "input": run / "input.json", "parent": PARENT,
            "contract": CASE / "contract.json", "builder": CASE / "build.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
            "python": Path(invocation["planned_check"]["executable"]),
            "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        }
        sealed = invocation["source_hashes_before"]
        check(prefix + "source/runtime seals before and after", all(path.exists() and sha(path) == sealed[key] for key, path in current.items()) and closure["source_hashes_before"] == sealed == closure["source_hashes_after"] and invocation["contract_sha256"] == sealed["contract"] and invocation["builder_sha256"] == sealed["builder"] and invocation["checker_sha256"] == sealed["checker"] and invocation["runner_script_sha256"] == sealed["runner_script"] and invocation["simlox_exe_sha256"] == sealed["simlox_exe"])
        check(prefix + "sealed invocation/closure", closure["invocation_sha256"] == sha(run / "invocation.json") and closure["run_id"] == run_id and closure["error"] is None)
        raw_files = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "complete raw file inventory", raw_files == set(closure["raw"]))
        for filename, meta in closure["raw"].items():
            path = run / filename
            check(prefix + "raw seal " + filename, path.exists() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"])
        check(prefix + "five successful ordered steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps))
        check(prefix + "native commands match invocation", [step["name"] for step in steps[:4]] == [step["name"] for step in invocation["planned_commands"]] and [step["arguments"] for step in steps[:4]] == [step["arguments"] for step in invocation["planned_commands"]])
        check(prefix + "step timestamps ordered", all(stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[i]["completed_utc"]) <= stamp(steps[i + 1]["started_utc"]) for i in range(4)))

        original, original_unique = tables(load(run / "input.json"))
        roundtrip, roundtrip_unique = tables(load(run / "roundtrip-raw.json"))
        populated = {key for key, table in original.items() if rows(table)}
        check(prefix + "20 row-containing input tables", original_unique and roundtrip_unique and len(populated) == 20)
        for key in sorted(populated):
            check(prefix + "exact roundtrip " + key, original[key] == roundtrip.get(key))
        imported = (run / "import.log").read_text(errors="replace")
        exported = (run / "export.log").read_text(errors="replace")
        calculated = (run / "run.log").read_text(errors="replace")
        check(prefix + "import/export complete", "Number of forms inserted: 31" in imported and "Import completed!" in imported and "Export completed!" in exported)
        check(prefix + "zero conversion errors and two known warnings", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calculated and calculated.count("warning #108") == 1 and calculated.count("warning #126") == 1 and "error #" not in calculated.lower() and "Starting simulation..." in calculated and "Saving results ..." in calculated)
        check(prefix + "report generated", "Generating Json-report" in (run / "report-export.log").read_text(errors="replace"))

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        check(prefix + "one two-aircraft mission ordered", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission activated, systems requested: 2") == 1 and log.count("mission allocates system:") == 2)
        check(prefix + "initial primary and alternative inventory", f"Free resources at: <BASE-01,0> P-CREW {primary}, P-ALT 2" in log)
        expected_ledger = [(7.5, selected, "book", 1), (7.5, selected, "book", 0), (float(prep_end), selected, "release", 1), (float(prep_end), selected, "release", 2)]
        observed_ledger = ledger(log)
        check(prefix + "exact selected resource booking/release ledger", observed_ledger == expected_ledger, observed_ledger)
        check(prefix + "only chosen resource booked", log.count(f"<{selected} at <BASE-01,0>> allocated to maintenance task: 1") == 2 and log.count(f"<{selected} at <BASE-01,0>> deallocated from  maintenance task: 1") == 2 and all(0 <= free <= 2 for _, _, _, free in observed_ledger))
        expected_primary_status = "OK" if primary else "failed"
        check(prefix + "primary availability outcome", log.count(f"<P-CREW at <BASE-01,0>> request for: 1 {expected_primary_status}") == 2)
        check(prefix + "alternative test only when needed", log.count("<P-ALT at <BASE-01,0>> request for: 1 OK") == (0 if primary else 2))
        for aircraft in (0, 1):
            subtask = f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"
            check(prefix + f"aircraft {aircraft} selection and task duration", f"Time: 7.5  {subtask} books resources\nTime: 7.5  <{selected} at <BASE-01,0>> allocated to maintenance task: 1" in log and f"Time: 7.5  {subtask} starts performing, planned to last for {duration} hours" in log)
            check(prefix + f"aircraft {aircraft} completion and release", f"Time: {prep_end}  {subtask} completed" in log and f"Time: {prep_end}  {subtask} frees resources\nTime: {prep_end}  <{selected} at <BASE-01,0>> deallocated from  maintenance task: 1" in log and f"Time: {prep_end} <TEACH-AIR-01,{aircraft}> preparation ended" in log)
        check(prefix + "mission launch, success and completion", f"Time: {launch} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log and f"Time: {finish} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and f"Time: {finish} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and "mission cancelled" not in log)
        check(prefix + "terminal two-aircraft readiness", f"Time: {finish} <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log)
        raw_report, removed = load_report(run / "report-raw.json")
        rt, rt_unique = tables(raw_report, "report")
        check(prefix + "six report tables and structural parse", rt_unique and set(rt) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"} and removed > 0)
        check(prefix + "72 complete half-hour bins", all(len(rows(rt[key])) == 72 and all(at(rt[key], i / 2)["ETINT"] == (i + 1) / 2 for i in range(72)) for key in ("SystemResults", "StockTotalResults", "ResourceResults")))
        summary = dict(zip(names(rt["ResultSummary"]), rows(rt["ResultSummary"])[0]))
        check(prefix + "one successful mission in summary", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1)
        total = dict(zip(names(rt["ResourceResultsTotal"]), rows(rt["ResourceResultsTotal"])[0]))
        expected_resource_hours = 2 * float(duration)
        check(prefix + "aggregate resource utilization reconciles duration", total["NR"] == primary + 2 and abs(total["NRUM"] * 36 - expected_resource_hours) < 1e-5 and total["NRMA"] == total["NRMO"] == 0)
        check(prefix + "terminal resource, stock and system state", at(rt["ResourceResults"], 35.5)["NR"] == primary + 2 and at(rt["ResourceResults"], 35.5)["NRUM"] == 0 and at(rt["SystemResults"], 35.5)["NSYRY"] == 2 and at(rt["StockTotalResults"], 35.5)["NBO"] == 0)
        check(prefix + "report preparation and operation bins", abs(at(rt["ResourceResults"], 7.5)["NRUM"] - (2 * min(float(duration), 0.5) / 0.5)) < 1e-5 and at(rt["SystemResults"], 7.5)["NSYMA"] == 2 and at(rt["SystemResults"], 9.5)["NSYRY"] == 2)
        if artf == 2 and primary == 0:
            check(prefix + "delay visible across 8 and 9 report bins", abs(at(rt["ResourceResults"], 8)["NRUM"] - 2 / 3) < 1e-5 and abs(at(rt["SystemResults"], 8)["NSYMO"] - 4 / 3) < 1e-5 and abs(at(rt["SystemResults"], 9)["NSYRY"] - 4 / 3) < 1e-5)
        else:
            check(prefix + "on-time mission report bins", at(rt["ResourceResults"], 8)["NRUM"] == 0 and at(rt["SystemResults"], 8)["NSYMO"] == 2 and at(rt["SystemResults"], 9)["NSYRY"] == 2)

    check("ARTF1 versus ARTF2 differs only in descriptor and factor", {k for k in sources["primary-0-artf-1"] if sources["primary-0-artf-1"][k] != sources["primary-0-artf-2"][k]} == {"ProblemDescription", "SubTaskResource"})
    check("primary2 versus primary0 at ARTF2 differs only in capacity and descriptor", {k for k in sources["primary-2-artf-2"] if sources["primary-2-artf-2"][k] != sources["primary-0-artf-2"][k]} == {"ProblemDescription", "ResourceAllocation"})
    failures = [entry for entry in CHECKS if not entry["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C06", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_alternative_resource_selection_and_timing" if not failures else "NO_GO",
        "accepted_scope": "For this fixed one-hour, two-aircraft mission, a 20-minute INSPECT preparation subtask per aircraft uses primary P-CREW when two are available despite ARTF=2. With zero primary and two P-ALT, each selects P-ALT. ARTF=1 retains 7.5-7.83333 preparation and 8-9 mission timing; ARTF=2 extends preparation to 8.16667 and shifts the mission to 8.16667-9.16667. Selected resources release at preparation completion; all variants finish with two ready aircraft.",
        "limits": ["One fixed seed, one site, one alternative type, primary capacity two/zero and ARTF one/two only; mixed shortages, multiple alternatives, and any maximum-factor rule remain unverified.", "RPROB is one, so probabilistic need is untested.", "INSPECT identity is bound by source/roundtrip; native event log labels generic subtasks.", "ResourceResults aggregates types; per-type selection is established by sealed event logs and corroborated by aggregate report totals.", "SSH/GUI/queue continuity is replayed from sealed records; this reviewer did not observe or rerun native SIMLOX live."],
        "checks": CHECKS,
    }
    out = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    out.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
