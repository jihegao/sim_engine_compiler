"""Independent standard-library read-only replay of C10 crew-failure pair."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
BASE = CASE.parent
PARENT = BASE / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"
SCHEMA_SOURCE = BASE / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
VARIANTS = ("oper-no-spare", "oper-one-spare")
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
    return [row for instance in table["instances"] for row in instance["rows"]]


def columns(table):
    return [column["name"] for column in table["columns"]]


def row(table):
    return dict(zip(columns(table), rows(table)[0]))


def bins(table):
    return {record["STINT"]: record for record in (dict(zip(columns(table), values)) for values in rows(table))}


def grid(*ranges):
    expected = {}
    for start, end, value in ranges:
        for half in range(int(start * 2), int(end * 2) + 1):
            expected[half / 2] = value
    return expected


def ledger(label, actual, expected):
    check(label + " contiguous 72 half-hour bins", len(actual) == 72 and all(actual[index / 2]["ETINT"] == (index + 1) / 2 for index in range(72)))
    fields = set(actual[0]) - {"RID", "STID", "UNID", "SID", "STINT", "ETINT"}
    check(label + " expected fields present", set(expected) <= fields)
    for field in sorted(fields):
        wanted = expected.get(field, {})
        if wanted is None:
            valid = all(actual[index / 2][field] is None for index in range(72))
        else:
            valid = all(isinstance(actual[index / 2][field], (int, float)) and abs(actual[index / 2][field] - wanted.get(index / 2, 0)) < 1e-6 for index in range(72))
        check(label + " exact 72-bin " + field, valid)


def subtask(aircraft):
    return f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on <TEACH-AIR-01,{aircraft}>"


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    parent, unique_parent = tables(read(PARENT))
    schema, unique_schema = tables(read(SCHEMA_SOURCE))
    parent_sha = "83b454bd145621f36571a87cdf8abcbccc184f07ab8f9ad5f3111651c78881e0"
    schema_sha = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"
    child_shas = {"oper-no-spare": "c334c1d6c0efa89f9ff70151a45180cac53b9ae05bf1a783219b566f41dbd62b", "oper-one-spare": "e34ce47cc2d26fa74fb9a90766cfd426caae0ff7b4a7fc75038867762d7b4278"}
    check("accepted C03 parent and C07 schema source", unique_parent and len(parent) == 31 and sha(PARENT) == contract["parent_input_sha256"] == diff["parent_input_sha256"] == parent_sha and unique_schema and sha(SCHEMA_SOURCE) == contract["schema_source_input_sha256"] == diff["schema_source_input_sha256"] == schema_sha)
    check("contract/diff identity", contract["schema"] == "simlox-c10-resource-failure-contract/v1" and contract["case_id"] == "C10" and contract["variant_id"] == "C10.var02" and contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published" and diff["schema"] == "simlox-c10-resource-failure-diff/v1")
    check("manual fingerprint/pages", MANUAL.exists() and sha(MANUAL) == contract["source_manual_sha256"] and contract["source_manual_physical_pages"] == [221, 412, 416, 417, 754])
    dictionary_lines = DICTIONARY.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    check("dictionary fingerprint and resource-failure schema", sha(DICTIONARY) == contract["source_dictionary_sha256"] == "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0" and contract["source_dictionary_lines"] == [673, 679] and dictionary_lines[675].startswith("ResourceStationData;4;RMTBF;") and dictionary_lines[676].startswith("ResourceStationData;5;RFTT;") and "OPERATION or CALENDAR" in dictionary_lines[676] and dictionary_lines[677].startswith("ResourceStationData;6;RMDT;"))
    sources = {}
    reports = {}
    logs = {}
    for variant in VARIANTS:
        tag = variant + ": "
        source_path = CASE / (variant + "-input.json")
        run_id = f"c10-{variant}-20260930-01"
        run = CASE / "runs" / run_id
        child, unique_child = tables(read(source_path))
        sources[variant] = child
        check(tag + "32-table source and frozen hash", unique_child and len(child) == 32 and sha(source_path) == sha(run / "input.json") == contract["input_sha256"][variant] == diff["child_input_sha256"][variant] == child_shas[variant])
        if variant == "oper-no-spare":
            changed = {name for name in parent | child if parent.get(name) != child.get(name)}
            check(tag + "exact parent delta", changed == {"ProblemDescription", "ResourceStationData"} and all(parent[name] == child[name] for name in parent if name not in changed), sorted(changed))
            station = row(child["ResourceStationData"])
            check(tag + "operation-time failure row and schema", columns(child["ResourceStationData"]) == columns(schema["ResourceStationData"]) and station == {"RID": "P-CREW", "STID": "BASE-01", "PRICE": None, "SUSTC": None, "MUTILF": None, "RMTBF": 0.5, "RFTT": "OPERATION", "RMDT": 0.25, "RMDTD": None, "SHPID": None, "NOTE": None} and row(child["ResourceAllocation"])["RQTY"] == 2)
        else:
            prior = sources["oper-no-spare"]
            changed = {name for name in prior | child if prior.get(name) != child.get(name)}
            before, after = row(prior["ResourceAllocation"]), row(child["ResourceAllocation"])
            check(tag + "exact pair delta", changed == {"ProblemDescription", "ResourceAllocation"} and all(prior[name] == child[name] for name in prior if name not in changed) and {field for field in before | after if before.get(field) != after.get(field)} == {"RQTY"} and before["RQTY"] == 2 and after["RQTY"] == 3, sorted(changed))
        check(tag + "fixed mission and horizon", row(child["MissionPreparation"])["DURN"] == 0.5 and row(child["MissionType"])["NOS"] == row(child["MissionType"])["MNOS"] == 2 and row(child["MissionType"])["DURN"] == 1 and row(child["Control"])["SIMPE"] == 36 and row(child["Control"])["RSEED"] == "1" and row(child["ResourceStationData"])["SHPID"] is None)

        invocation = read(run / "invocation.json")
        closure = read(run / "closure.json")
        steps = read(run / "steps.json")
        check(tag + "run identity/source linkage", invocation["case_id"] == "C10" and invocation["variant"] == variant and invocation["run_id"] == closure["run_id"] == run_id and Path(invocation["original_run_dir"]).resolve() == run.resolve() and invocation["input_sha256"] == sha(source_path) and invocation["parent_sha256"] == parent_sha)
        check(tag + "SSH session0/mutex/GUI", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] is True and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1 and all(step["gui_preserved"] is True for step in steps))
        sealed = {"input": run / "input.json", "parent": PARENT, "contract": CASE / "contract.json", "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(invocation["planned_check"]["executable"]), "simlox_exe": EXE}
        before = invocation["source_hashes_before"]
        check(tag + "frozen source/runtime bytes", all(path.exists() and sha(path) == before[name] for name, path in sealed.items()))
        check(tag + "closure/invocation seals", closure["source_hashes_before"] == closure["source_hashes_after"] == before and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None and all(invocation[key + "_sha256"] == before[key] for key in ("contract", "builder", "checker", "runner_script", "simlox_exe")) and invocation["python_sha256"] == before["python"])
        raw_names = {path.name for path in run.iterdir() if path.is_file()} - {"invocation.json", "closure.json"}
        check(tag + "complete raw inventory", raw_names == set(closure["raw"]))
        for filename, metadata in closure["raw"].items():
            path = run / filename
            check(tag + "raw seal " + filename, path.exists() and path.stat().st_size == metadata["bytes"] and sha(path) == metadata["sha256"])
        check(tag + "five ordered successful steps", len(steps) == 5 and [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None and timestamp(step["started_utc"]) <= timestamp(step["completed_utc"]) for step in steps) and all(timestamp(steps[index]["completed_utc"]) <= timestamp(steps[index + 1]["started_utc"]) for index in range(4)))
        check(tag + "planned commands executed", all(steps[index]["arguments"] == invocation["planned_commands"][index]["arguments"] for index in range(4)) and steps[4]["arguments"] == invocation["planned_check"]["arguments"])

        original, original_unique = tables(read(run / "input.json"))
        exported, exported_unique = tables(read(run / "roundtrip-raw.json"))
        populated = {name for name in original if rows(original[name])}
        null_only = {name for name in populated if all(all(value is None for value in record) for record in rows(original[name]))}
        check(tag + "21 populated roundtrip tables including null placeholders", original_unique and exported_unique and len(populated) == 21 and null_only == {"ControlParameters", "GlobalParameters", "OperationParameter"})
        for name in sorted(populated):
            check(tag + "exact native roundtrip " + name, original[name] == exported.get(name))
        imported = (run / "import.log").read_text(errors="replace")
        converted = (run / "run.log").read_text(errors="replace")
        check(tag + "converter/report success", "Number of forms inserted: 32" in imported and "Import completed!" in imported and "Export completed!" in (run / "export.log").read_text(errors="replace") and "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converted and converted.count("warning #108") == converted.count("warning #126") == 1 and "error #" not in converted.lower() and "Starting simulation..." in converted and "Saving results ..." in converted and "Generating Json-report" in (run / "report-export.log").read_text(errors="replace") and (run / "model.sxo").stat().st_size > 4)

        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        logs[variant] = log
        check(tag + "operational failure and quarter-hour repair", log.count("Time: 7.73494 <P-CREW at <BASE-01,0>> Failed") == 1 and log.count("Time: 7.98494 <P-CREW at <BASE-01,0>> Repaired") == 1 and "Time: 0  resource shift 0 starting at <P-CREW at <BASE-01,0>> no shift period" in log and "Time: 36  resource shift 0 ended" in log and "Time: 7.5 <P-CREW at <BASE-01,0>> Next Random Failure 7.73494" in log)
        check(tag + "both tasks start 7.5", all(f"Time: 7.5  {subtask(aircraft)} starts performing, planned to last for 0.5 hours" in log for aircraft in (0, 1)))
        if variant == "oper-no-spare":
            check(tag + "failed owner stops and waits", f"Time: 7.73494  {subtask(0)} is stopped due to a resource failure, time left= 0.265061" in log and f"Time: 7.73494  {subtask(0)} requests resources" in log and f"Time: 7.98494  {subtask(0)} resource received" in log and f"Time: 7.98494  {subtask(0)} starts performing, planned to last for 0.265061 hours" in log)
            check(tag + "second task continuous and delayed launch", f"Time: 8  {subtask(1)} completed" in log and f"Time: 8.25  {subtask(0)} completed" in log and "Time: 8.25 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 9.25 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "Time: 9.25 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log)
        else:
            check(tag + "spare pool keeps both tasks continuous", "is stopped due to a resource failure" not in log and "resource waiting" not in log and all(f"Time: 8  {subtask(aircraft)} completed" in log for aircraft in (0, 1)) and "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 1" in log and "Time: 9 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:" in log and "Time: 9 <TEACH-UNIT at <BASE-01,0>> systems ready: 2" in log)

        report_doc, repairs = native_report(run / "report-raw.json")
        report, report_unique = tables(report_doc, "report")
        reports[variant] = report
        check(tag + "six parsed report tables", repairs > 0 and report_unique and set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"})
        summary, total = row(report["ResultSummary"]), row(report["ResourceResultsTotal"])
        quantity = 2 if variant == "oper-no-spare" else 3
        wait = 0.25 if variant == "oper-no-spare" else 0
        check(tag + "success/work/failure/wait integrals", summary["NREP"] == 1 and summary["RTIUP"] == 36 and summary["MTMF"] == summary["MSTF"] == summary["MSUF"] == 1 and total["NR"] == total["NRN"] == quantity and abs(total["NRUM"] * 36 - 1) < 1e-5 and abs(total["NRF"] * 36 - 0.25) < 1e-5 and abs(total["NRW"] * 36 - wait) < 1e-5 and total["NRMA"] == total["NRMO"] == 0)
        resource = bins(report["ResourceResults"])
        system = bins(report["SystemResults"])
        stock = bins(report["StockTotalResults"])
        resource_expected = {"NR": grid((0, 35.5, quantity)), "NRN": grid((0, 35.5, quantity)), "NRF": grid((7.5, 7.5, 0.5)), "NRA": grid((0, 35.5, quantity), (7.5, 7.5, quantity - 0.5))}
        system_expected = {"NSYRY": grid((0, 7, 2), (9.5 if variant == "oper-no-spare" else 9, 35.5, 2)), "NSYMA": grid((7.5, 8.5 if variant == "oper-one-spare" else 8.5, 2)), "NSYA": grid((0, 35.5, 2)), "SYDT": None, "NPSTA": grid((7.5, 7.5, 2)), "NPSUC": grid((8, 8, 2))}
        if variant == "oper-no-spare":
            resource_expected |= {"NRUM": grid((7.5, 7.5, 1.5), (8, 8, 0.5)), "NRW": grid((7.5, 7.5, 0.5))}
            system_expected |= {"NSYRY": grid((0, 7, 2), (9, 9, 1), (9.5, 35.5, 2)), "NSYMA": grid((7.5, 8.5, 2), (9, 9, 1)), "NSYMP": grid((7.5, 7.5, 2), (8, 8, 0.5)), "NSYMR": grid((8, 8, 0.5)), "NSYMO": grid((8, 8, 1), (8.5, 8.5, 2), (9, 9, 1)), "FTMO": grid((8, 8, 0.5), (8.5, 8.5, 1), (9, 9, 0.5)), "STACC": grid((8, 8, 1), (8.5, 8.5, 2), (9, 9, 1))}
        else:
            resource_expected |= {"NRUM": grid((7.5, 7.5, 2))}
            system_expected |= {"NSYMP": grid((7.5, 7.5, 2)), "NSYMO": grid((8, 8.5, 2)), "FTMO": grid((8, 8.5, 1)), "STACC": grid((8, 8.5, 2))}
        ledger(tag + "ResourceResults", resource, resource_expected)
        ledger(tag + "SystemResults", system, system_expected)
        ledger(tag + "StockTotalResults", stock, {"PNB": grid((0, 35.5, 1)), "NBOU": None, "ROS": None, "ROST": None, "WT": None, "WTT": None, "WTS": None})
        check(tag + "terminal ready two and crew available", system[35.5]["NSYRY"] == 2 and resource[35.5]["NR"] == resource[35.5]["NRN"] == resource[35.5]["NRA"] == quantity and resource[35.5]["NRUM"] == resource[35.5]["NRW"] == resource[35.5]["NRF"] == 0)

    check("pair changes only crew pool and description", {name for name in sources["oper-no-spare"] | sources["oper-one-spare"] if sources["oper-no-spare"].get(name) != sources["oper-one-spare"].get(name)} == {"ProblemDescription", "ResourceAllocation"})
    check("spare prevents stop and quarter-hour mission delay", "resource failure, time left=" in logs["oper-no-spare"] and "resource failure, time left=" not in logs["oper-one-spare"] and "Time: 8.25 <BASIC-MISSION" in logs["oper-no-spare"] and "Time: 8 <BASIC-MISSION" in logs["oper-one-spare"])
    check("pair report stock and mission summary equal", reports["oper-no-spare"]["StockTotalResults"] == reports["oper-one-spare"]["StockTotalResults"] and reports["oper-no-spare"]["ResultSummary"] == reports["oper-one-spare"]["ResultSummary"])

    if (CASE / "evidence-index.json").exists():
        evidence = read(CASE / "evidence-index.json")
        indexed = {entry["variant"]: entry for entry in evidence["runs"]}
        check("evidence index pair inventory", sha(CASE / "evidence-index.json") == "a88318e208ba60419287de08f490865de9bc82f72ed22d4518a8f4a01087df88" and evidence["schema"] == "simlox-c10-resource-failure-evidence-index/v1" and evidence["relative_raw_root"] == "runs/" and evidence["raw_publication"] == "local_sealed_not_committed" and len(evidence["runs"]) == 2 and set(indexed) == set(VARIANTS) and evidence["source_manual_sha256"] == sha(MANUAL) and evidence["source_dictionary_sha256"] == sha(DICTIONARY) and evidence["simlox_exe_sha256"] == sha(EXE))
        for variant in VARIANTS:
            run = CASE / "runs" / f"c10-{variant}-20260930-01"
            entry = indexed[variant]
            closure = read(run / "closure.json")
            check(variant + ": evidence index path/top-level hashes", Path(entry["original_run_dir"]).resolve() == run.resolve() and entry["run_id"] == run.name and entry["input_sha256"] == sha(run / "input.json") and entry["closure_sha256"] == sha(run / "closure.json") and entry["run_log_sha256"] == sha(run / "run.log") and entry["model_log_sha256"] == sha(run / "model.log") and entry["report_raw_sha256"] == sha(run / "report-raw.json"))
            check(variant + ": evidence index full raw bytes", entry["raw"] == closure["raw"] == {name: {"bytes": (run / name).stat().st_size, "sha256": sha(run / name)} for name in closure["raw"]})

    failures = [item for item in CHECKS if not item["passed"]]
    result = {
        "schema": "simlox-independent-readonly-review/v1", "case_id": "C10.var02.resource_operation_failure", "review_date": "2026-09-30",
        "passed": not failures, "check_count": len(CHECKS), "passed_count": len(CHECKS) - len(failures), "failures": failures,
        "decision": "GO_bounded_operational_crew_failure_pair" if not failures else "NO_GO",
        "accepted_scope": "For this fixed-seed P-CREW operational-failure pair, a crew fails at 7.73494 and is repaired at 7.98494. With only two crew, subtask 0 stops with 0.265061h left, waits for repair, then finishes 8.25 and delays mission to 8.25-9.25. With three crew, both subtasks continue to 8 and the mission runs 8-9. Both finish successfully with two aircraft ready.",
        "metric_interpretation": "Both reports record one crew-hour of positive work and 0.25 resource-hours failed. No-spare additionally records 0.25 resource-hours waiting; spare records zero. All numeric/null values in the 72 half-hour resource/system/stock bins are checked.",
        "limits": ["The native log identifies a failing P-CREW pool resource, but not individual crew identities; uninterrupted tasks with a spare support pool-level substitution, not an individual replacement trace.", "One seed and one RMTBF/RMDT value on this installed executable. Calendar failure time, off-shift spares, other seeds, GUI visual behavior and cross-engine equivalence remain unverified.", "SSH/GUI/mutex status is replayed from sealed metadata; native SIMLOX was not rerun."],
        "checks": CHECKS,
    }
    output = Path(__file__).with_name("independent-readonly-2026-09-30.json")
    output.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({key: result[key] for key in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
