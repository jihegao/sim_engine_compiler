"""Independent stdlib read-only replay of C10 off-shift standby pair."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
BASE = CASE.parent
PARENT_CASE = BASE / "C10-resource-failure-v1.0.0"
PARENT = PARENT_CASE / "oper-one-spare-input.json"
PARENT_RUN = PARENT_CASE / "runs" / "c10-oper-one-spare-20260930-01"
NO_SPARE_RUN = PARENT_CASE / "runs" / "c10-oper-no-spare-20260930-01"
SCHEMA = BASE / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
VARIANTS = ("onshift-three", "onshift-two-offshift-one")
CHECKS: list[dict] = []


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path):
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
    item = {"name": name, "passed": bool(condition)}
    if detail is not None:
        item["detail"] = detail
    CHECKS.append(item)


def tables(document, key="model"):
    source = document[key]["tables"]
    names = [table["name"] for table in source]
    return {table["name"]: table for table in source}, len(names) == len(set(names))


def rows(table):
    return [entry for instance in table["instances"] for entry in instance["rows"]]


def columns(table):
    return [column["name"] for column in table["columns"]]


def row(table):
    return dict(zip(columns(table), rows(table)[0]))


def bins(table):
    return {entry["STINT"]: entry for entry in (dict(zip(columns(table), values)) for values in rows(table))}


def grid(*intervals):
    result = {}
    for start, end, value in intervals:
        for index in range(int(start * 2), int(end * 2) + 1):
            result[index / 2] = value
    return result


def ledger(label, actual, expected):
    check(label + " 72 contiguous bins", len(actual) == 72 and all(actual[index / 2]["ETINT"] == (index + 1) / 2 for index in range(72)))
    fields = set(actual[0]) - {"RID", "STID", "UNID", "SID", "STINT", "ETINT"}
    check(label + " expected fields present", set(expected) <= fields)
    for field in sorted(fields):
        wanted = expected.get(field, {})
        if wanted is None:
            valid = all(actual[index / 2][field] is None for index in range(72))
        else:
            valid = all(isinstance(actual[index / 2][field], (int, float)) and abs(actual[index / 2][field] - wanted.get(index / 2, 0)) < 1e-6 for index in range(72))
        check(label + " full " + field, valid)


def subtask(aircraft):
    return f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    parent, parent_unique = tables(read(PARENT))
    schema, schema_unique = tables(read(SCHEMA))
    parent_sha = "e34ce47cc2d26fa74fb9a90766cfd426caae0ff7b4a7fc75038867762d7b4278"
    schema_sha = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"
    child_shas = {"onshift-three": "4e8ffe8bad98d5313279c189aeb8947db64f2f04d61789c0a6c5db134d011d92", "onshift-two-offshift-one": "7d11ed709942d00fdbdab558bfabb82471f38b3f3a3098df33171df96c38922d"}
    check("accepted parent and shift schema fingerprints", parent_unique and schema_unique and len(parent) == 32 and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_input_sha256"] == parent_sha and sha(SCHEMA) == contract["schema_source_input_sha256"] == diff["schema_source_input_sha256"] == schema_sha)
    check("contract/diff scope and accepted parent signoff", contract["schema"] == "simlox-c10-offshift-spare-contract/v1" and contract["case_id"] == "C10" and contract["variant_id"] == "C10.var03" and contract["version"] == "1.0.0-candidate" and contract["parent_variant"] == "oper-one-spare" and contract["publication_state"] == "not_published" and diff["schema"] == "simlox-c10-offshift-spare-diff/v1" and "accepted_bounded_cli_scope" in (PARENT_CASE / "cli-scope-signoff-2026-09-30.md").read_text(encoding="utf-8"))
    check("manual/dictionary fingerprints and pages", sha(MANUAL) == contract["source_manual_sha256"] and sha(DICTIONARY) == contract["source_dictionary_sha256"] and contract["source_manual_physical_pages"] == [221, 418, 419, 421, 422])
    parent_closure = read(PARENT_RUN / "closure.json")
    check("accepted three-crew parent raw seal", parent_closure["run_id"] == PARENT_RUN.name and parent_closure["invocation_sha256"] == sha(PARENT_RUN / "invocation.json") and set(parent_closure["raw"]) == {path.name for path in PARENT_RUN.iterdir() if path.is_file()} - {"invocation.json", "closure.json"} and all((PARENT_RUN / name).stat().st_size == metadata["bytes"] and sha(PARENT_RUN / name) == metadata["sha256"] for name, metadata in parent_closure["raw"].items()))
    check("corroborating accepted two-crew no-spare run sealed", sha(NO_SPARE_RUN / "model.log") == read(NO_SPARE_RUN / "closure.json")["raw"]["model.log"]["sha256"] and "Time: 7.73494  " + subtask(0) + " is stopped due to a resource failure" in (NO_SPARE_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace"))

    sources = {}
    reports = {}
    logs = {}
    for variant in VARIANTS:
        prefix = variant + ": "
        source_path = CASE / (variant + "-input.json")
        run_id = f"c10-{variant}-20260930-01"
        run = CASE / "runs" / run_id
        child, child_unique = tables(read(source_path))
        sources[variant] = child
        check(prefix + "35-table child source and SHA", child_unique and len(child) == 35 and sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant] == diff["child_input_sha256"][variant] == child_shas[variant])
        changed = {name for name in parent | child if parent.get(name) != child.get(name)}
        check(prefix + "exact six-table parent delta", changed == {"ProblemDescription", "Control", "ResourceStationData", "Shift", "ShiftProfile", "ShiftResource"} and all(parent[name] == child[name] for name in parent if name not in changed), sorted(changed))
        old_control, new_control = row(parent["Control"]), row(child["Control"])
        old_station, new_station = row(parent["ResourceStationData"]), row(child["ResourceStationData"])
        check(prefix + "single-field control/station edits", {field for field in old_control | new_control if old_control.get(field) != new_control.get(field)} == {"DRAOS"} and old_control["DRAOS"] is None and new_control["DRAOS"] == "N" and {field for field in old_station | new_station if old_station.get(field) != new_station.get(field)} == {"SHPID"} and old_station["SHPID"] is None and new_station["SHPID"] == "CREW-DAY" and new_station["RMTBF"] == 0.5 and new_station["RFTT"] == "OPERATION" and new_station["RMDT"] == 0.25)
        qty = 3 if variant == "onshift-three" else 2
        check(prefix + "7–10 shift and three allocated crew", columns(child["Shift"]) == columns(schema["Shift"]) and columns(child["ShiftProfile"]) == columns(schema["ShiftProfile"]) and columns(child["ShiftResource"]) == columns(schema["ShiftResource"]) and rows(child["Shift"]) == [["DAY-OPEN", "Crew scheduled 7 to 10", None]] and rows(child["ShiftProfile"]) == [["CREW-DAY", "DAY-OPEN", 7, 10, 1, None, None]] and rows(child["ShiftResource"]) == [["DAY-OPEN", "BASE-01", "P-CREW", qty, None, None]] and row(child["ResourceAllocation"])["RQTY"] == 3)

        invocation = read(run / "invocation.json")
        closure = read(run / "closure.json")
        steps = read(run / "steps.json")
        check(prefix + "run identity/source", invocation["case_id"] == "C10" and invocation["variant"] == variant and invocation["run_id"] == closure["run_id"] == run_id and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == parent_sha)
        check(prefix + "session0 SSH/mutex/GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and all(step["gui_preserved"] is True for step in steps))
        sealed = {"input": run / "input.json", "parent": PARENT, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
        before = invocation["source_hashes_before"]
        check(prefix + "frozen source/runtime bytes", all(path.exists() and sha(path) == before[name] for name, path in sealed.items()))
        check(prefix + "closure/invocation seals", closure["source_hashes_before"] == closure["source_hashes_after"] == before and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[key + "_sha256"] == before[key] for key in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == before["python"])
        raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(prefix + "complete raw inventory", raw_names == set(closure["raw"]))
        for filename, metadata in closure["raw"].items():
            path = run / filename
            check(prefix + "raw byte seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
        check(prefix + "five ordered successful steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None and stamp(step["started_utc"]) <= stamp(step["completed_utc"]) for step in steps) and all(stamp(steps[index]["completed_utc"]) <= stamp(steps[index + 1]["started_utc"]) for index in range(4)))
        check(prefix + "planned command arguments executed", all(steps[index]["arguments"] == invocation["planned_commands"][index]["arguments"] for index in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"])
        original, original_unique = tables(read(run / "input.json"))
        roundtrip, roundtrip_unique = tables(read(run / "roundtrip-raw.json"))
        populated = {name for name in original if rows(original[name])}
        null_only = {name for name in populated if all(all(value is None for value in entry) for entry in rows(original[name]))}
        check(prefix + "24 populated tables and null placeholders", original_unique and roundtrip_unique and len(populated) == 24 and null_only == {"ControlParameters", "GlobalParameters", "OperationParameter"})
        for name in sorted(populated):
            check(prefix + "exact native roundtrip " + name, original[name] == roundtrip.get(name))
        converted = (run / "run.log").read_text(errors="replace")
        check(prefix + "converter/report accepted", "Number of forms inserted: 35" in (run / "import.log").read_text(errors="replace") and "Import completed!" in (run / "import.log").read_text(errors="replace") and "Export completed!" in (run / "export.log").read_text(errors="replace") and "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted and "Generating Json-report" in (run / "report-export.log").read_text(errors="replace") and (run / "model.sxo").stat().st_size > 4)

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        logs[variant] = log
        check(prefix + "shift starts7 and ends10 with 0 offshift", "Time: 0  resource shift 0 starting at <P-CREW at <BASE-01,0>>" in log and "Time: 7  resource shift 1 starting at <P-CREW at <BASE-01,0>>" in log and f"Time: 7  resource shift 1 starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW {qty}" in log and "Time: 10  resource shift 1 ended at <P-CREW at <BASE-01,0>>" in log and "Time: 10  resource shift 2 starting at <P-CREW at <BASE-01,0>>, overlap time from previous = 0\n  Free resources at: <BASE-01,0> P-CREW 0" in log)
        check(prefix + "two active tasks, failure and repair, no stop", all(f"Time: 7.5  {subtask(aircraft)} starts performing, planned to last for 0.5 hours" in log and f"Time: 8  {subtask(aircraft)} completed" in log for aircraft in (0, 1)) and log.count("Time: 7.73494 <P-CREW at <BASE-01,0>> Failed") == 1 and log.count("Time: 7.98494 <P-CREW at <BASE-01,0>> Repaired") == 1 and "is stopped due to a resource failure" not in log and "resource waiting" not in log)
        check(prefix + "mission8–9 success and ready2", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed:" in log and "Time: 9 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log and "mission cancelled" not in log)

        native, repairs = native_report(run / "report-raw.json")
        report, report_unique = tables(native, "report")
        reports[variant] = report
        check(prefix + "six parsed report tables", repairs > 0 and report_unique and set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"})
        summary, total = row(report["ResultSummary"]), row(report["ResourceResultsTotal"])
        check(prefix + "summary and work/failure/wait integrals", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1 and total["NR"] == total["NRN"] == 3 and abs(total["NRUM"] * 36 - 1) < 1e-5 and abs(total["NRF"] * 36 - 0.25) < 1e-5 and total["NRW"] == total["NRMA"] == total["NRMO"] == 0)
        resource = bins(report["ResourceResults"])
        system = bins(report["SystemResults"])
        stock = bins(report["StockTotalResults"])
        expected_resource = {"NR": grid((0, 35.5, 3)), "NRN": grid((0, 35.5, 3)), "NRUM": grid((7.5, 7.5, 2)), "NRF": grid((7.5, 7.5, 0.5)), "NRA": grid((7, 7, qty), (7.5, 7.5, 2.5 if qty == 3 else 2), (8, 9.5, qty))}
        expected_system = {"NSYRY": grid((0, 7, 2), (9, 35.5, 2)), "NSYMA": grid((7.5, 8.5, 2)), "NSYMP": grid((7.5, 7.5, 2)), "NSYMO": grid((8, 8.5, 2)), "NSYA": grid((0, 35.5, 2)), "FTMO": grid((8, 8.5, 1)), "STACC": grid((8, 8.5, 2)), "SYDT": None, "NPSTA": grid((7.5, 7.5, 2)), "NPSUC": grid((8, 8, 2))}
        ledger(prefix + "ResourceResults", resource, expected_resource)
        ledger(prefix + "SystemResults", system, expected_system)
        ledger(prefix + "StockTotalResults", stock, {"PNB": grid((0, 35.5, 1)), "NBOU": None, "ROS": None, "ROST": None, "WT": None, "WTT": None, "WTS": None})
        check(prefix + "terminal aircraft ready2 and offshift crew availability0", system[35.5]["NSYRY"] == 2 and resource[35.5]["NR"] == resource[35.5]["NRN"] == 3 and resource[35.5]["NRA"] == resource[35.5]["NRUM"] == resource[35.5]["NRW"] == resource[35.5]["NRF"] == 0)

    three, two = sources["onshift-three"], sources["onshift-two-offshift-one"]
    old, new = row(three["ShiftResource"]), row(two["ShiftResource"])
    check("pair differs only on-shift QTY and description", {name for name in three | two if three.get(name) != two.get(name)} == {"ProblemDescription", "ShiftResource"} and {field for field in old | new if old.get(field) != new.get(field)} == {"QTY"} and old["QTY"] == 3 and new["QTY"] == 2)
    check("pair reports identical system/stock/mission outcome", all(reports["onshift-three"][name] == reports["onshift-two-offshift-one"][name] for name in ("ResultSummary", "SystemResults", "StockTotalResults")))
    check("two-onshift available count stays two during failure", bins(reports["onshift-two-offshift-one"]["ResourceResults"])[7.5]["NRA"] == 2 and bins(reports["onshift-two-offshift-one"]["ResourceResults"])[7.5]["NRF"] == 0.5 and bins(reports["onshift-three"]["ResourceResults"])[7.5]["NRA"] == 2.5)

    if (CASE / "evidence-index.json").exists():
        index = read(CASE / "evidence-index.json")
        entries = {entry["variant"]: entry for entry in index["runs"]}
        check("evidence index pair inventory", len(index["runs"]) == 2 and set(entries) == set(VARIANTS) and index["source_manual_sha256"] == sha(MANUAL) and index["source_dictionary_sha256"] == sha(DICTIONARY) and index["simlox_exe_sha256"] == sha(EXE))
        for variant in VARIANTS:
            run = CASE / "runs" / f"c10-{variant}-20260930-01"
            entry = entries[variant]
            closure = read(run / "closure.json")
            check(variant + ": index path/source/raw", Path(entry["original_run_dir"]).resolve() == run.resolve() and entry["input_sha256"] == sha(run / "input.json") and entry["closure_sha256"] == sha(run / "closure.json") and entry["run_log_sha256"] == sha(run / "run.log") and entry["model_log_sha256"] == sha(run / "model.log") and entry["report_raw_sha256"] == sha(run / "report-raw.json") and entry["raw"] == closure["raw"])

    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1", "case_id": "C10.var03.offshift_standby", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_offshift_standby_pair" if not failures else "NO_GO",
        "accepted_scope": "With three allocated P-CREW, the paired children schedule three versus two on shift from 7-10. Both record a pool failure at 7.73494 and repair at 7.98494 while two preparations run; neither task stops, both finish at 8, and the formation succeeds 8-9. The two-on-shift report keeps NRA=2 through the failure bin while NRF averages 0.5 there; all crew availability is zero after shift end at 10.",
        "metric_interpretation": "Both reports show one crew-hour positive work, 0.25 resource-hours failed, zero waiting, two ready aircraft at the terminal horizon, and zero stock movement. All 72 half-hour resource/system/stock numeric and null fields are checked.",
        "limits": ["The log identifies the P-CREW pool, not individual worker identity; uninterrupted tasks with two scheduled crew and one allocated off-shift crew support a pool-level standby interpretation only.", "One fixed seed, one 7-10 shift, one MTBF/MDT pair on this executable. Other shift patterns, off-shift policy outside the window, GUI visuals and cross-engine equivalence remain unverified.", "SSH/GUI/mutex continuity is replayed from sealed metadata; native SIMLOX was not rerun."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
