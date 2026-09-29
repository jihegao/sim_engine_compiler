"""Independent read-only audit of B01 1.0.1 raw evidence.

This deliberately does not import the production builder or validator.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_native_json(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    # SIMLOX 2017 writes trailing commas in its report export.
    return json.loads(re.sub(r",(?=\s*[}\]])", "", raw))


def rows(document: dict, envelope: str) -> dict[str, list[dict]]:
    result = {}
    for table in document[envelope]["tables"]:
        names = [column["name"] for column in table["columns"]]
        if table["name"] in result:
            raise ValueError(f"duplicate table: {table['name']}")
        result[table["name"]] = [dict(zip(names, row, strict=True)) for instance in table["instances"]
                                  for row in instance["rows"]]
    return result


def check_source() -> list[str]:
    errors = []
    parent = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
    contract = read_native_json(HERE / "contract.json")
    if digest(parent) != contract["parent_input_sha256"]:
        errors.append("A01 parent hash mismatch")
    if digest(HERE / "native-input.json") != contract["input_sha256"]:
        errors.append("B01 candidate hash mismatch")
    if digest(HERE / "parent-diff.json") != contract["parent_diff_sha256"]:
        errors.append("exact parent diff hash mismatch")
    parent_doc, child_doc = read_native_json(parent), read_native_json(HERE / "native-input.json")
    parent_tables, child_tables = rows(parent_doc, "model"), rows(child_doc, "model")
    if parent_tables.keys() != child_tables.keys():
        errors.append("native table set or order changed")
    changed = [name for name in parent_tables if parent_tables[name] != child_tables.get(name)]
    if changed != ["MissionPreparation", "Tasks"]:
        errors.append(f"actual changed tables differ: {changed}")
    expected_prep = {"MTID": "BASIC-MISSION", "SID": "TEACH-AIR-01", "STID": "BASE-01",
                     "DURN": 0.5, "TID": "PREP-FIXED", "DURND": None, "NOTE": None}
    expected_task = {"TID": "PREP-FIXED", "DESCR": "Fixed 30-minute BASIC-MISSION preparation",
                     "TCID": None, "TLID": None, "NOTE": None}
    if parent_tables.get("MissionPreparation") != [] or child_tables.get("MissionPreparation") != [expected_prep]:
        errors.append("preparation is not one exact A01-derived row")
    if parent_tables.get("Tasks") != [] or child_tables.get("Tasks") != [expected_task]:
        errors.append("task is not one exact A01-derived row")
    if len(child_tables.get("MissionType", [])) != 1 or child_tables["MissionType"][0].get("NOPER") != 1.0:
        errors.append("A01 one-hour notice parameter was not retained")
    declared = read_native_json(HERE / "parent-diff.json")
    if declared.get("changed_tables_only") != changed or declared.get("added_rows") != 2 or declared.get("removed_rows") != 0 or declared.get("field_changes") != 0:
        errors.append("declared exact parent diff does not match observed two-row delta")
    return errors


def check_evidence(run: Path) -> tuple[list[str], dict]:
    errors = []
    invocation = read_native_json(run / "invocation.json")
    closure = read_native_json(run / "closure.json")
    manifest = read_native_json(run / "run-manifest.json")
    validation = read_native_json(run / "validation.json")
    contract = read_native_json(HERE / "contract.json")
    if set(closure.get("raw", {})) != RAW:
        errors.append("raw closure file set differs")
    for name, item in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != item.get("bytes") or digest(path) != item.get("sha256"):
            errors.append(f"raw file closure mismatch: {name}")
    if digest(run / "input.json") != contract["input_sha256"]:
        errors.append("run input differs from checked candidate")
    for field, path in {"contract_sha256": HERE / "contract.json", "builder_sha256": HERE / "build.py",
                        "parent_diff_sha256": HERE / "parent-diff.json", "validator_sha256": HERE / "validate.py",
                        "runner_sha256": HERE / "run_native_ssh.ps1"}.items():
        if invocation.get(field) != digest(path):
            errors.append(f"invocation source hash mismatch: {field}")
    if invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []):
        errors.append("session-0 SSH provenance missing")
    gui = invocation.get("coexisting_gui") or {}
    if gui.get("pid") != 13340 or gui.get("session_id") != 1 or gui.get("process_start_utc") != "2026-09-28T10:09:56.8261381Z":
        errors.append("preserved GUI process identity mismatch")
    steps = read_native_json(run / "steps.json")
    if [step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"] or any(
            step.get("exit_code") != 0 or not step.get("coexisting_gui_present_after") for step in steps):
        errors.append("native step sequence, exit code or GUI coexistence mismatch")
    if manifest.get("closure_sha256") != digest(run / "closure.json") or manifest.get("validation_sha256") != digest(run / "validation.json"):
        errors.append("run manifest closure or validation hash mismatch")
    if not validation.get("passed") or validation.get("differences"):
        errors.append("source-bound validator did not pass")
    source_rows = rows(read_native_json(run / "input.json"), "model")
    export_rows = rows(read_native_json(run / "roundtrip-raw.json"), "model")
    for name, source in source_rows.items():
        if source and source != export_rows.get(name):
            errors.append(f"business rows changed in native roundtrip: {name}")
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    found = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", conversion)
    if not found or found.group(1, 2) != ("0", "2") or Counter(re.findall(r"\(warning #(\d+)\)", conversion)) != Counter({"108": 1, "126": 1}):
        errors.append("conversion errors or warning allowlist mismatch")

    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    timed = [(float(hour), body.strip()) for hour, body in re.findall(r"^Time:\s*([\d.eE+\-]+)\s+([^\r\n]+)", log, re.M)]
    owner, tag = "<TEACH-AIR-01,0>", "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    events = {
        "notice": (" mission ordered:", [(7, "<TEACH-UNIT> mission ordered: BASIC-MISSION")]),
        "created": (" mission created:", [(7, f"{tag} mission created:")]),
        "allocation": (" mission allocates system:", [(7, f"{tag} mission allocates system: {owner}")]),
        "preparation_start": (" preparation started,", [(7, f"{owner} preparation started, mission: {tag}")]),
        "work": (" starts performing,", [(7, f"subtask 0 seqno 0 within system preparation task 0 on {owner} starts performing, planned to last for 0.5 hours")]),
        "preparation_end": (" preparation ended,", [(7.5, f"{owner} preparation ended, mission: {tag}")]),
        "launch": (" mission starting, duration:", [(8, f"{tag} mission starting, duration: 2 : {owner}")]),
        "success": (" mission success:", [(10, f"{tag} mission success:")]),
        "completion": (" mission completed:", [(10, f"{tag} mission completed: {owner}")]),
        "cancel": (" mission cancelled:", []),
        "abort": (" mission aborted:", []),
    }
    for label, (marker, expected) in events.items():
        observed = [(hour, body) for hour, body in timed if marker in body]
        if observed != expected:
            errors.append(f"global {label} events differ: {observed!r}")
    expected_task = [(7, f"system preparation task 0 on {owner} started"),
                     (7.5, f"system preparation task 0 on {owner} completed")]
    observed_task = [(hour, body) for hour, body in timed if body.startswith("system preparation task ")]
    if observed_task != expected_task:
        errors.append(f"global preparation task lifecycle differs: {observed_task!r}")
    expected_subtask = [
        (7, f"subtask 0 seqno 0 within system preparation task 0 on {owner} started"),
        (7, f"subtask 0 seqno 0 within system preparation task 0 on {owner} requests resources: no resources needed"),
        (7, f"subtask 0 seqno 0 within system preparation task 0 on {owner} resource availability test"),
        (7, f"subtask 0 seqno 0 within system preparation task 0 on {owner} starts performing, planned to last for 0.5 hours"),
        (7.5, f"subtask 0 seqno 0 within system preparation task 0 on {owner} completed"),
    ]
    observed_subtask = [(hour, body) for hour, body in timed if body.startswith("subtask ")]
    if observed_subtask != expected_subtask:
        errors.append(f"global preparation subtask lifecycle differs: {observed_subtask!r}")
    if len(timed) == 0 or any(a[0] > b[0] for a, b in zip(timed, timed[1:])):
        errors.append("native event times missing or unordered")

    report = read_native_json(run / "report-raw.json")
    report_rows = rows(report, "report")
    summary = report_rows.get("ResultSummary", [])
    if len(summary) != 1 or any(summary[0].get(key) != value for key, value in
                                {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}.items()):
        errors.append("native ResultSummary mismatch")
    intervals = report_rows.get("SystemResults", [])
    if len(intervals) != 72:
        errors.append(f"native SystemResults interval count is {len(intervals)}")
    totals = Counter()
    for index, row in enumerate(intervals):
        start = index / 2
        expected = {"NPSTA": int(start == 7), "NPSUC": int(start == 7.5), "NSYMP": int(start == 7),
                    "FTMO": int(8 <= start < 10), "NSYMO": int(8 <= start < 10)}
        if row.get("STINT") != start or row.get("ETINT") != start + 0.5 or row.get("NSYA") != 1:
            errors.append(f"SystemResults interval geometry or aircraft count mismatch at {index}")
        for field, value in expected.items():
            if row.get(field) != value:
                errors.append(f"SystemResults {field} mismatch at interval {index}")
            else:
                totals[field] += value if field.startswith("NP") else value * 0.5
    if any(abs(totals[key] - value) > 1e-8 for key, value in
           {"NPSTA": 1, "NPSUC": 1, "NSYMP": 0.5, "FTMO": 2, "NSYMO": 2}.items()):
        errors.append(f"system result totals mismatch: {dict(totals)}")
    hashes = {name: digest(run / name) for name in ("invocation.json", "closure.json", "run-manifest.json",
                                                       "validation.json", "model.sxi", "model.sxo", "model.log", "report-raw.json")}
    business_table_count = sum(any(any(value not in (None, "") for value in row.values()) for row in table)
                               for table in source_rows.values())
    return errors, {"run_id": invocation.get("run_id"), "raw_closure_count": len(closure.get("raw", {})),
                    "roundtrip_business_tables": business_table_count,
                    "system_result_intervals": len(intervals), "metric_totals": dict(totals), "hashes": hashes}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: review_readonly.py RUN_DIRECTORY")
    run = Path(sys.argv[1])
    errors = check_source()
    observed_errors, details = check_evidence(run)
    errors.extend(observed_errors)
    result = {"schema": "simlox-b01-independent-readonly-review/v1", "case_id": "B01", "version": "1.0.1",
              "passed": not errors, "differences": errors, "reviewer_sha256": digest(HERE / "review_readonly.py"), **details}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
