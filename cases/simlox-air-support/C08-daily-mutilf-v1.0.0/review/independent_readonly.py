"""Independent, standard-library-only replay of four sealed C08 daily MUTILF runs.

Reads sources and native artifacts. Never imports the candidate builder/checker or
executes SIMLOX. Writes only the deterministic JSON review next to this script.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
ACCEPTED = CASE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
VARIANTS = ("no-shift-control", "zero-budget", "finite-budget", "station-override")
CHECKS: list[dict] = []


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    output = []
    quoted = escaped = False
    repairs = 0
    for position, char in enumerate(raw):
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
        elif char == "," and raw[position + 1 :].lstrip().startswith(("}", "]")):
            repairs += 1
        else:
            output.append(char)
    return json.loads("".join(output)), repairs


def check(name, passed, detail=None):
    finding = {"name": name, "passed": bool(passed)}
    if detail is not None:
        finding["detail"] = detail
    CHECKS.append(finding)


def table_map(document, root="model"):
    source = document[root]["tables"]
    names = [table["name"] for table in source]
    return {table["name"]: table for table in source}, len(names) == len(set(names))


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def columns(table):
    return [column["name"] for column in table["columns"]]


def single(table):
    return dict(zip(columns(table), rows(table)[0]))


def bins(table):
    return {record["STINT"]: record for record in (dict(zip(columns(table), row)) for row in rows(table))}


def grid(*intervals):
    expected = {}
    for beginning, ending, value in intervals:
        for index in range(int(beginning * 2), int(ending * 2) + 1):
            expected[index / 2] = value
    return expected


def time_stamp(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def subtask(aircraft):
    return f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"


def exact_ledger(label, ledger, expected_fields):
    """Every cell in each numeric report field is checked, including zero cells."""
    metadata = {"STINT", "ETINT", "RID", "STID", "UNID", "SID"}
    fields = set(ledger[0]) - metadata
    check(label + " field inventory", set(expected_fields) <= fields)
    for field in sorted(fields):
        wanted = expected_fields.get(field, {})
        if wanted is None:
            check(label + " 72-bin " + field, all(ledger[index / 2][field] is None for index in range(72)))
        else:
            check(label + " 72-bin " + field, all(isinstance(ledger[index / 2][field], (int, float)) and abs(ledger[index / 2][field] - wanted.get(index / 2, 0)) < 1e-6 for index in range(72)))


def main():
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    accepted, accepted_unique = table_map(load(ACCEPTED))
    accepted_hash = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"
    check("accepted parent identity", accepted_unique and len(accepted) == 35 and digest(ACCEPTED) == contract["parent_input_sha256"] == diff["accepted_parent_sha256"] == accepted_hash)
    check("contract and diff identities", contract["schema"] == "simlox-c08-daily-mutilf-contract/v1" and contract["case_id"] == "C08" and contract["variant_id"] == "C08.var01" and contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published" and diff["schema"] == "simlox-c08-daily-mutilf-exact-diff/v1" and set(diff["variants"]) == set(VARIANTS))
    check("manual bytes and pages", MANUAL.exists() and digest(MANUAL) == contract["source_manual_sha256"] == "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3" and contract["source_manual_physical_pages"] == [414, 416, 417, 419, 423])
    evidence = load(CASE / "evidence-index.json")
    indexed_runs = {entry["variant"]: entry for entry in evidence["runs"]}
    check("evidence index frozen identity and four-run inventory", digest(CASE / "evidence-index.json") == "06c107d8a45f1b5587e8e4ca3c84fcfbef6849beff65d9a5a25e4e0f543affb7" and evidence["schema"] == "simlox-c08-daily-mutilf-evidence-index/v1" and evidence["relative_raw_root"] == "runs/" and evidence["raw_publication"] == "local_sealed_not_committed" and len(evidence["runs"]) == 4 and set(indexed_runs) == set(VARIANTS) and evidence["source_manual_sha256"] == digest(MANUAL) and evidence["simlox_exe_sha256"] == digest(EXE))

    sources = {variant: CASE / (variant + "-input.json") for variant in VARIANTS}
    source_tables = {variant: table_map(load(path)) for variant, path in sources.items()}
    report_tables = {}
    logs = {}
    runs = {}
    for variant in VARIANTS:
        prefix = variant + ": "
        source_path = sources[variant]
        child, unique_child = source_tables[variant]
        spec = diff["variants"][variant]
        parent_path = ACCEPTED if variant == "no-shift-control" else sources[spec["parent"]]
        parent, unique_parent = table_map(load(parent_path))
        run_id = f"c08-{variant}-20260930-01"
        run = CASE / "runs" / run_id
        runs[variant] = run
        check(prefix + "source/lineage fingerprints", unique_child and unique_parent and len(child) == len(parent) == 35 and digest(source_path) == contract["input_sha256"][variant] == spec["input_sha256"] == digest(run / "input.json") and digest(parent_path) == spec["parent_sha256"])
        changed = {name for name in child | parent if child.get(name) != parent.get(name)}
        check(prefix + "exact two-table delta and unchanged 33", changed == set(spec["changed_tables"]) and len(changed) == 2 and "ProblemDescription" in changed and spec["unchanged_table_count"] == 33 and all(child[name] == parent[name] for name in child if name not in changed), sorted(changed))
        expected_table, expected_field, old, new = {
            "no-shift-control": ("ResourceStationData", "SHPID", "CREW-DAY", None),
            "zero-budget": ("Resource", "MUTILF", None, 0),
            "finite-budget": ("Resource", "MUTILF", None, 0.03125),
            "station-override": ("ResourceStationData", "MUTILF", None, 1),
        }[variant]
        previous_row, changed_row = single(parent[expected_table]), single(child[expected_table])
        check(prefix + "single business field delta", changed == {"ProblemDescription", expected_table} and {field for field in previous_row | changed_row if previous_row.get(field) != changed_row.get(field)} == {expected_field} and previous_row[expected_field] == old and changed_row[expected_field] == new)
        check(prefix + "fixed no-shift model", single(child["ResourceStationData"])["SHPID"] is None and single(child["ShiftResource"])["QTY"] == 2 and single(child["ShiftResource"])["MAXUT"] is None and rows(child["ShiftProfile"]) == [["CREW-DAY", "DAY-OPEN", 23, 25, 1, None, None], ["CREW-DAY", "DAY-OPEN", 26, 28, 1, None, None]] and single(child["Control"])["DRAOS"] == "N" and single(child["Control"])["SIMPE"] == 36 and single(child["Control"])["RSEED"] == "1")

        invocation = load(run / "invocation.json")
        closure = load(run / "closure.json")
        steps = load(run / "steps.json")
        check(prefix + "run identity and source linkage", invocation["case_id"] == "C08" and invocation["variant"] == variant and invocation["run_id"] == closure["run_id"] == run_id and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == digest(source_path) and invocation["parent_sha256"] == digest(parent_path) and invocation["accepted_parent_sha256"] == accepted_hash)
        check(prefix + "session-zero SSH/mutex/GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and all(step["gui_preserved"] is True for step in steps))
        sealed_paths = {"input": run / "input.json", "parent": parent_path, "accepted_parent": ACCEPTED, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
        seals = invocation["source_hashes_before"]
        check(prefix + "current source/runtime hashes match frozen seals", all(path.exists() and digest(path) == seals[key] for key, path in sealed_paths.items()))
        check(prefix + "before/after seals and closure", closure["source_hashes_before"] == closure["source_hashes_after"] == seals and closure["invocation_sha256"] == digest(run / "invocation.json") and closure["error"] is None and all(invocation[key + "_sha256"] == seals[key] for key in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == seals["python"])
        raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "complete raw inventory", raw_names == set(closure["raw"]))
        for name, metadata in closure["raw"].items():
            path = run / name
            check(prefix + "raw seal " + name, path.exists() and path.stat().st_size == metadata["bytes"] and digest(path) == metadata["sha256"])
        index_entry = indexed_runs[variant]
        check(prefix + "evidence index path/top-level hashes", index_entry["run_id"] == run_id and Path(index_entry["original_run_dir"]).resolve() == run.resolve() and index_entry["input_sha256"] == digest(run / "input.json") and index_entry["closure_sha256"] == digest(run / "closure.json") and index_entry["run_log_sha256"] == digest(run / "run.log") and index_entry["model_log_sha256"] == digest(run / "model.log") and index_entry["report_raw_sha256"] == digest(run / "report-raw.json"))
        check(prefix + "evidence index complete raw reconciliation", index_entry["raw"] == closure["raw"] == {name: {"bytes": (run / name).stat().st_size, "sha256": digest(run / name)} for name in raw_names})
        check(prefix + "five guarded steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None for step in steps) and all(time_stamp(step["started_utc"]) <= time_stamp(step["completed_utc"]) for step in steps) and all(time_stamp(steps[i]["completed_utc"]) <= time_stamp(steps[i + 1]["started_utc"]) for i in range(4)))
        check(prefix + "planned commands executed", all(steps[index]["arguments"] == invocation["planned_commands"][index]["arguments"] for index in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"])

        original, unique_original = table_map(load(run / "input.json"))
        roundtrip, unique_roundtrip = table_map(load(run / "roundtrip-raw.json"))
        populated = {name for name in original if rows(original[name])}
        null_only = {name for name in populated if all(all(value is None for value in record) for record in rows(original[name]))}
        check(prefix + "24 populated tables and 3 all-null placeholders", unique_original and unique_roundtrip and len(populated) == 24 and null_only == {"ControlParameters", "GlobalParameters", "OperationParameter"})
        for name in sorted(populated):
            check(prefix + "exact native roundtrip " + name, original[name] == roundtrip.get(name))
        imported = (run / "import.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(prefix + "conversion and report generation", "Number of forms inserted: 35" in imported and "Import completed!" in imported and "Export completed!" in (run / "export.log").read_text(errors="replace") and "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == 1 and converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted and "Generating Json-report" in (run / "report-export.log").read_text(errors="replace") and (run / "model.sxo").stat().st_size > 4)

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        logs[variant] = log
        check(prefix + "no active shift in native events", "Time: 0  resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period" in log and "Time: 36  resource shift 0 ended at <P-CREW at <BASE-01,0>> time gap to next = 0" in log and "resource shift 1 starting" not in log)
        check(prefix + "two-aircraft mission ordered and terminal ready", log.count("mission ordered: BASIC-MISSION") == 1 and log.count("mission allocates system:") == 2 and "<TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log)
        report, repairs = native_report(run / "report-raw.json")
        parsed, unique_report = table_map(report, "report")
        report_tables[variant] = parsed
        check(prefix + "six parseable native report tables", repairs > 0 and unique_report and set(parsed) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"})
        for ledger_name in ("ResourceResults", "SystemResults", "StockTotalResults"):
            ledger = bins(parsed[ledger_name])
            check(prefix + ledger_name + " 72 contiguous bins", len(ledger) == 72 and all(ledger[index / 2]["ETINT"] == (index + 1) / 2 for index in range(72)))

    control = runs["no-shift-control"]
    override = runs["station-override"]
    check("control/override byte-identical native event logs", digest(control / "model.log") == digest(override / "model.log"))
    left, right = report_tables["no-shift-control"], report_tables["station-override"]
    check("control/override report equality except description", {name for name in left | right if left.get(name) != right.get(name)} == {"ProblemDescription"})

    for variant in VARIANTS:
        log = logs[variant]
        prefix = variant + ": "
        for aircraft in (0, 1):
            sub = subtask(aircraft)
            check(prefix + f"aircraft {aircraft} preparation start", f"Time: 23.5  {sub} started" in log)
            if variant in ("no-shift-control", "station-override"):
                check(prefix + f"aircraft {aircraft} work and finish", f"Time: 23.5  {sub} starts performing, planned to last for 2 hours" in log and f"Time: 25.5  {sub} completed" in log and f"Time: 25.5 <TEACH-AIR-01,{aircraft}> preparation ended" in log)
            elif variant == "zero-budget":
                check(prefix + f"aircraft {aircraft} never starts positive work", f"Time: 23.5  {sub} resource availability test" in log and f"{sub} starts performing" not in log and f"{sub} books resources" not in log and f"Time: 27  {sub} resource waiting stopped" in log)
            else:
                check(prefix + f"aircraft {aircraft} works then stops with 0.75h left", f"Time: 23.5  {sub} starts performing, planned to last for 2 hours" in log and f"Time: 24.75  {sub} is stopped due to resource time-out, time left= 0.75" in log and f"Time: 29  {sub} resource waiting stopped" in log and f"{sub} completed" not in log)
        if variant in ("no-shift-control", "station-override"):
            check(prefix + "28-29 successful mission", "Time: 28 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and "mission cancelled" not in log and "Time: 29 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log)
        elif variant == "zero-budget":
            check(prefix + "zero work and cancellation27", "starts performing" not in log and "allocated to maintenance task" not in log and "Time: 27 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:" in log and "mission success:" not in log and "Time: 27 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log)
        else:
            check(prefix + "day reset, 24.75 limit and cancellation29", "Time: 24  Start of day no 1" in log and "Time: 24  <P-CREW at <BASE-01,0>> set time to max utilisation: 0.75" in log and "Time: 24.75  <P-CREW at <BASE-01,0>> out of utilisation time" in log and "Time: 29 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled:" in log and "mission starting" not in log and "Time: 29 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log)

        parsed = report_tables[variant]
        summary = single(parsed["ResultSummary"])
        total = single(parsed["ResourceResultsTotal"])
        expected_success = int(variant in ("no-shift-control", "station-override"))
        check(prefix + "mission summary and resource totals", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == expected_success and total["NR"] == total["NRN"] == 2 and total["NRMA"] == total["NRMO"] == 0)
        work_hours, wait_hours = {"no-shift-control": (4, 0), "zero-budget": (0, 7), "finite-budget": (2.5, 8.5), "station-override": (4, 0)}[variant]
        check(prefix + "work/wait integral totals", abs(total["NRUM"] * 36 - work_hours) < 1e-5 and abs(total["NRW"] * 36 - wait_hours) < 1e-5)
        resource = bins(parsed["ResourceResults"])
        system = bins(parsed["SystemResults"])
        stock = bins(parsed["StockTotalResults"])
        common_resource = {"NR": grid((0, 35.5, 2)), "NRN": grid((0, 35.5, 2))}
        common_system = {"NSYA": grid((0, 35.5, 2)), "NPSTA": grid((23.5, 23.5, 2))}
        if variant in ("no-shift-control", "station-override"):
            resource_expected = common_resource | {"NRUM": grid((23.5, 25, 2)), "NRA": grid((0, 35.5, 2))}
            system_expected = common_system | {"NSYRY": grid((0, 23, 2), (29, 35.5, 2)), "NSYMA": grid((23.5, 28.5, 2)), "NSYMP": grid((23.5, 25, 2)), "NSYMR": grid((25.5, 27.5, 2)), "NSYMO": grid((28, 28.5, 2)), "FTMO": grid((28, 28.5, 1)), "STACC": grid((28, 28.5, 2)), "NPSUC": grid((25.5, 25.5, 2))}
        elif variant == "zero-budget":
            resource_expected = common_resource | {"NRA": grid((0, 35.5, 2)), "NRW": grid((23.5, 26.5, 2))}
            system_expected = common_system | {"NSYRY": grid((0, 23, 2), (27, 35.5, 2)), "NSYMA": grid((23.5, 26.5, 2)), "NSYMP": grid((23.5, 26.5, 2))}
        else:
            resource_expected = common_resource | {"NRUM": grid((23.5, 24, 2), (24.5, 24.5, 1)), "NRW": grid((24.5, 24.5, 1), (25, 28.5, 2)), "NRA": grid((0, 24, 2), (24.5, 24.5, 1))}
            system_expected = common_system | {"NSYRY": grid((0, 23, 2), (29, 35.5, 2)), "NSYMA": grid((23.5, 28.5, 2)), "NSYMP": grid((23.5, 28.5, 2))}
        exact_ledger(prefix + "ResourceResults", resource, resource_expected)
        exact_ledger(prefix + "SystemResults", system, system_expected | {"SYDT": None})
        exact_ledger(prefix + "StockTotalResults", stock, {"PNB": grid((0, 35.5, 1)), "NBOU": None, "ROS": None, "ROST": None, "WT": None, "WTT": None, "WTS": None})
        check(prefix + "ready two, no active work/wait at horizon", system[35.5]["NSYRY"] == 2 and resource[35.5]["NRUM"] == resource[35.5]["NRW"] == 0)

    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "C08.var01.daily_mutilf",
        "review_date": "2026-09-30",
        "passed": not failures,
        "check_count": len(CHECKS),
        "passed_count": len(CHECKS) - len(failures),
        "failures": failures,
        "decision": "GO_bounded_four_variant_daily_mutilf" if not failures else "NO_GO",
        "accepted_scope": "On this fixed-seed two-aircraft, no-active-shift, one-station model, MUTILF=0 blocks work and cancels at 27; MUTILF=0.03125 gives 2.5 pool crew-hours of work across the day boundary, then time-out at 24.75 with 0.75h per aircraft left and cancellation at 29. Station MUTILF=1 overrides resource MUTILF=0.03125 and exactly reproduces the no-shift control event log and report values except description; both finish preparation at 25.5 and succeed at 29.",
        "metric_interpretation": "ResourceResults.NRUM is positive booked work; NRW is waiting, including partial 24.5-25 bin in finite-budget. All numeric cells in all 72 resource, system and stock bins are checked against the observed timeline, with zero expected for unlisted fields.",
        "limits": ["Four fixed-seed cases only. General daily reset, other MUTILF values, sequential jobs, multiple resource/station models, shift interactions and cross-engine behavior remain unverified.", "SSH/GUI/mutex evidence is replayed from sealed invocation/closure metadata; this review did not rerun native SIMLOX."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
