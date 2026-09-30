"""Independent standard-library read-only replay of sealed C08 exact-limit run."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "C08-shift-maxut-v1.0.0" / "maxut-one-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
RUN_ID = "c08-exact-limit-20260930-02"
CHECKS: list[dict] = []


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_native_report(path):
    raw = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = escaped = False
    repairs = 0
    for index, char in enumerate(raw):
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
        elif char == "," and raw[index + 1 :].lstrip().startswith(("}", "]")):
            repairs += 1
        else:
            output.append(char)
    return json.loads("".join(output)), repairs


def check(name, condition, detail=None):
    result = {"name": name, "passed": bool(condition)}
    if detail is not None:
        result["detail"] = detail
    CHECKS.append(result)


def tables(document, key="model"):
    sequence = document[key]["tables"]
    names = [table["name"] for table in sequence]
    return {table["name"]: table for table in sequence}, len(names) == len(set(names))


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def columns(table):
    return [column["name"] for column in table["columns"]]


def row(table):
    return dict(zip(columns(table), rows(table)[0]))


def bins(table):
    return {item["STINT"]: item for item in (dict(zip(columns(table), values)) for values in rows(table))}


def grid(*intervals):
    values = {}
    for start, end, value in intervals:
        for half in range(int(start * 2), int(end * 2) + 1):
            values[half / 2] = value
    return values


def subtask(aircraft):
    return f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"


def check_ledger(name, ledger, expected):
    fields = set(ledger[0]) - {"RID", "STID", "UNID", "SID", "STINT", "ETINT"}
    check(name + " 72 intervals", len(ledger) == 72 and all(ledger[index / 2]["ETINT"] == (index + 1) / 2 for index in range(72)))
    check(name + " expected fields present", set(expected) <= fields)
    for field in sorted(fields):
        wanted = expected.get(field, {})
        if wanted is None:
            condition = all(ledger[index / 2][field] is None for index in range(72))
        else:
            condition = all(isinstance(ledger[index / 2][field], (int, float)) and abs(ledger[index / 2][field] - wanted.get(index / 2, 0)) < 1e-6 for index in range(72))
        check(name + " full " + field, condition)


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    source_path = CASE / "exact-limit-input.json"
    run = CASE / "runs" / RUN_ID
    excluded = CASE / "runs" / "c08-exact-limit-20260930-01"
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    parent, parent_unique = tables(read(PARENT))
    source, source_unique = tables(read(source_path))
    parent_sha = "00e660275ace4d71d41cdafa725da2b552baeea9604756d94ad6b07de846e9d5"
    source_sha = "dc75e99a8007fe74c7a830633657c32957877b9eb0a162588f7dedc6bc1f428b"
    check("accepted C08.var02 parent SHA", parent_unique and len(parent) == 35 and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_input_sha256"] == parent_sha)
    check("contract and diff identities", contract["schema"] == "simlox-c08-exact-limit-contract/v1" and contract["case_id"] == "C08" and contract["variant_id"] == "C08.var04" and contract["version"] == "1.0.0-candidate" and contract["parent_publication_id"] == "C08.var02.shift_maxut_one.1.0.0" and contract["publication_state"] == "not_published" and diff["schema"] == "simlox-c08-exact-limit-diff/v1")
    check("manual fingerprint and page references", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_physical_pages"] == [296, 402, 403, 404, 422, 423])
    check("unique 35-table source and child SHA", source_unique and len(source) == 35 and sha(source_path) == sha(run / "input.json") == contract["input_sha256"] == diff["child_input_sha256"] == source_sha)
    changed = {name for name in parent | source if parent.get(name) != source.get(name)}
    check("exact parent table delta", changed == {"ProblemDescription", "TaskBreakDown"} and all(parent[name] == source[name] for name in parent if name not in changed), sorted(changed))
    old, new = row(parent["TaskBreakDown"]), row(source["TaskBreakDown"])
    check("one-hour DURN alone changes business source", {field for field in old | new if old.get(field) != new.get(field)} == {"DURN"} and old["DURN"] == 2 and new["DURN"] == 1 and new["TID"] == "PREP-FIXED" and new["SEQ"] == 1 and new["SUTID"] == "INSPECT" and rows(source["ProblemDescription"]) == [["C08 exact MAXUT limit at preparation completion; DRAOS=N"]])
    check("scalar, one-hour MAXUT, two windows retained", row(source["MissionPreparation"])["DURN"] == 2 and row(source["MissionPreparation"])["TID"] == "PREP-FIXED" and row(source["ShiftResource"])["MAXUT"] == 1 and row(source["ShiftResource"])["QTY"] == 2 and rows(source["ShiftProfile"]) == [["CREW-DAY", "DAY-OPEN", 23, 25, 1, None, None], ["CREW-DAY", "DAY-OPEN", 26, 28, 1, None, None]] and row(source["Control"])["DRAOS"] == "N")

    invocation = read(run / "invocation.json")
    closure = read(run / "closure.json")
    steps = read(run / "steps.json")
    excluded_invocation = read(excluded / "invocation.json")
    check("diagnostic -01 excluded for contract fingerprint", excluded_invocation["run_id"] == "c08-exact-limit-20260930-01" and excluded_invocation["input_sha256"] == source_sha and excluded_invocation["contract_sha256"] != sha(CASE / "contract.json") and invocation["contract_sha256"] == sha(CASE / "contract.json") and stamp(excluded_invocation["created_utc"]) < stamp(invocation["created_utc"]))
    check("final run identity and input/parent linkage", invocation["case_id"] == "C08" and invocation["variant"] == "exact-limit" and invocation["run_id"] == closure["run_id"] == RUN_ID and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == source_sha and invocation["parent_sha256"] == parent_sha)
    check("SSH session zero, mutex, GUI preservation", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and all(step["gui_preserved"] is True for step in steps))
    sealed_paths = {"input": run / "input.json", "parent": PARENT, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
    seals = invocation["source_hashes_before"]
    check("all frozen source/runtime hashes match current bytes", all(path.exists() and sha(path) == seals[name] for name, path in sealed_paths.items()))
    check("before/after source seals and invocation seal", closure["source_hashes_before"] == closure["source_hashes_after"] == seals and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[key + "_sha256"] == seals[key] for key in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == seals["python"])
    raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
    check("complete raw inventory", raw_names == set(closure["raw"]))
    for filename, metadata in closure["raw"].items():
        path = run / filename
        check("raw byte seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
    check("five successful ordered steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None and stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[index]["completed_utc"]) <= stamp(steps[index + 1]["started_utc"]) for index in range(4)))
    check("planned command arguments executed", all(steps[index]["arguments"] == invocation["planned_commands"][index]["arguments"] for index in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"])

    original, original_unique = tables(read(run / "input.json"))
    exported, exported_unique = tables(read(run / "roundtrip-raw.json"))
    populated = {name for name in original if rows(original[name])}
    null_only = {name for name in populated if all(all(value is None for value in record) for record in rows(original[name]))}
    check("24 row-containing tables and 3 all-null placeholders", original_unique and exported_unique and len(populated) == 24 and null_only == {"ControlParameters", "GlobalParameters", "OperationParameter"})
    for name in sorted(populated):
        check("exact native roundtrip " + name, original[name] == exported.get(name))
    converted = (run / "run.log").read_text(errors="replace")
    check("import/export and conversion accepted", "Number of forms inserted: 35" in (run / "import.log").read_text(errors="replace") and "Import completed!" in (run / "import.log").read_text(errors="replace") and "Export completed!" in (run / "export.log").read_text(errors="replace") and "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted and "Generating Json-report" in (run / "report-export.log").read_text(errors="replace") and (run / "model.sxo").stat().st_size > 4)

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    check("fixed mission and shift events", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission allocates system:") == 2 and all(f"Time: {hour}  resource shift {shift} starting at <P-CREW at <BASE-01,0>>" in log for hour, shift in ((23, 1), (25, 2), (26, 3), (28, 4))))
    check("no resource timeout or waiting", "out of utilisation time" not in log and "resource time-out" not in log and "resource waiting" not in log and "mission cancelled" not in log)
    event_lines = log.splitlines()
    for aircraft in (0, 1):
        sub = subtask(aircraft)
        check(f"aircraft {aircraft} one-hour effective work", f"Time: 23.5  {sub} starts performing, planned to last for 1 hours" in log and f"Time: 24.5  {sub} completed" in log and f"Time: 24.5  {sub} frees resources" in log and f"Time: 24.5 <TEACH-AIR-01,{aircraft}> preparation ended" in log)
    order = [
        f"Time: 24.5  {subtask(0)} completed",
        "Time: 24.5  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
        "Time: 24.5  <P-CREW at <BASE-01,0>> set time to max utilisation: 0",
        "Time: 24.5 <TEACH-AIR-01,0> preparation ended",
        f"Time: 24.5  {subtask(1)} completed",
        "Time: 24.5  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 2",
        "Time: 24.5 <TEACH-AIR-01,1> preparation ended",
    ]
    positions = [next((index for index, line in enumerate(event_lines) if line.startswith(fragment)), -1) for fragment in order]
    check("24.5 completion-before-limit event ordering", all(position >= 0 for position in positions) and positions == sorted(positions), positions)
    check("two crew bookings/releases, no second-window work", log.count("allocated to maintenance task: 1") == 2 and log.count("deallocated from  maintenance task: 1") == 2 and "Time: 26  " + subtask(0) + " starts performing" not in log and "Time: 26  " + subtask(1) + " starts performing" not in log)
    check("28-29 success and terminal ready two", "Time: 28 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and "Time: 29 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log)

    native, repairs = read_native_report(run / "report-raw.json")
    report, report_unique = tables(native, "report")
    check("six parsed native report tables", report_unique and repairs > 0 and set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"})
    summary, total = row(report["ResultSummary"]), row(report["ResourceResultsTotal"])
    check("one successful mission and two crew hours", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1 and total["NR"] == total["NRN"] == 2 and abs(total["NRUM"] * 36 - 2) < 1e-5 and total["NRW"] == total["NRMA"] == total["NRMO"] == 0)
    resource = bins(report["ResourceResults"])
    system = bins(report["SystemResults"])
    stock = bins(report["StockTotalResults"])
    check_ledger("ResourceResults", resource, {"NR": grid((0, 35.5, 2)), "NRN": grid((0, 35.5, 2)), "NRUM": grid((23.5, 24, 2)), "NRA": grid((23, 24.5, 2), (26, 27.5, 2))})
    check_ledger("SystemResults", system, {"NSYRY": grid((0, 23, 2), (29, 35.5, 2)), "NSYMA": grid((23.5, 28.5, 2)), "NSYMP": grid((23.5, 24, 2)), "NSYMR": grid((24.5, 27.5, 2)), "NSYMO": grid((28, 28.5, 2)), "NSYA": grid((0, 35.5, 2)), "FTMO": grid((28, 28.5, 1)), "STACC": grid((28, 28.5, 2)), "SYDT": None, "NPSTA": grid((23.5, 23.5, 2)), "NPSUC": grid((24.5, 24.5, 2))})
    check_ledger("StockTotalResults", stock, {"PNB": grid((0, 35.5, 1)), "NBOU": None, "ROS": None, "ROST": None, "WT": None, "WTT": None, "WTS": None})
    check("terminal report ready two, no usage/wait", system[35.5]["NSYRY"] == 2 and resource[35.5]["NRUM"] == resource[35.5]["NRW"] == 0)

    if (CASE / "evidence-index.json").exists():
        evidence = read(CASE / "evidence-index.json")
        check("evidence index frozen identity and diagnostic exclusion", sha(CASE / "evidence-index.json") == "e55e136949073a783377608c8226a62fab4a13e250c9f0e9c5f0099296a7d5da" and evidence["schema"] == "simlox-c08-exact-limit-evidence-index/v1" and evidence["relative_raw_root"] == "runs/" and evidence["raw_publication"] == "local_sealed_not_committed" and len(evidence["runs"]) == 1 and evidence["source_manual_sha256"] == sha(MANUAL) and evidence["simlox_exe_sha256"] == sha(EXE) and evidence["excluded_diagnostic_run"].startswith("c08-exact-limit-20260930-01:"))
        entries = [entry for entry in evidence["runs"] if entry["run_id"] == RUN_ID]
        check("evidence index identifies final run", len(entries) == 1 and Path(entries[0]["original_run_dir"]).resolve() == run.resolve())
        if entries:
            entry = entries[0]
            check("evidence index top-level hashes", entry["input_sha256"] == sha(run / "input.json") and entry["closure_sha256"] == sha(run / "closure.json") and entry["run_log_sha256"] == sha(run / "run.log") and entry["model_log_sha256"] == sha(run / "model.log") and entry["report_raw_sha256"] == sha(run / "report-raw.json"))
            check("evidence index raw inventory", entry["raw"] == closure["raw"] == {name: {"bytes": (run / name).stat().st_size, "sha256": sha(run / name)} for name in raw_names})

    failures = [result for result in CHECKS if not result["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C08.var04.exact_limit",
        "review_date": "2026-09-30",
        "passed": not failures,
        "check_count": len(CHECKS),
        "passed_count": len(CHECKS) - len(failures),
        "failures": failures,
        "decision": "GO_bounded_exact_limit_completion" if not failures else "NO_GO",
        "accepted_scope": "For this fixed-seed two-aircraft model with one-hour TaskBreakDown and one-hour ShiftResource.MAXUT, both tasks complete at 24.5 as pool time reaches zero. No time-out occurs; preparation ends at 24.5; the formation succeeds 28-29 and both aircraft are ready at the terminal horizon.",
        "metric_interpretation": "The report has two crew-hours of positive work, zero resource waiting and 72 checked half-hour bins in every resource, system and stock field. Unlisted numeric fields must be zero; native null-only fields are checked as null.",
        "limits": ["One exact-limit event ordering on this installed executable. It does not establish general equal-time priority, partial pool demand, station overrides, GUI behavior or cross-engine equivalence.", "The -01 run is excluded because it predates the final contract metadata. SSH/GUI/mutex status is replayed from sealed metadata; no native rerun was performed."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
