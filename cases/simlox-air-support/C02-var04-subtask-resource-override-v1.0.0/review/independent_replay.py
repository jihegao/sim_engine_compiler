"""Independent, read-only C02.var04 evidence replay. Never launches SIMLOX.

The self-check validates the frozen design and accepted controls before native runs
exist. A complete replay writes no files; its JSON is printed to stdout.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parents[2]
CONTRACT_SHA = "5458f7b0615ecd8e25d1cba9fd25b14151297112c4446f29eb8bac3371ad31a3"
REPORT_SHAPE = {
    "ProblemDescription": (1, 1),
    "ResultSummary": (1, 11),
    "SystemResults": (72, 40),
    "StockTotalResults": (72, 16),
    "ResourceResults": (72, 16),
    "ResourceResultsTotal": (1, 14),
}
RAW_FILES = {
    "input.json", "model.sxi", "import.log", "roundtrip-raw.json", "export.log",
    "steps.json", "roundtrip-validation.json", "model.sxo", "model.log",
    "run.log", "report-raw.json", "report-export.log", "author-validation.json",
}
STAGES = ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
GUI = {"pid": 13340, "session_id": 1, "start_unix_ms": 1790590196826, "responding": True}


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def check(self, condition: bool, label: str) -> None:
        self.checks += 1
        if not condition:
            self.failures.append(label)

    def same(self, actual: object, expected: object, label: str) -> None:
        if isinstance(actual, (int, float)) and not isinstance(actual, bool) and isinstance(expected, (int, float)) and not isinstance(expected, bool):
            self.check(math.isclose(actual, expected, rel_tol=0, abs_tol=1e-6), label)
        else:
            self.check(actual == expected, label)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_copy(raw: bytes) -> dict:
    """Remove native trailing commas outside strings, only in a parser copy."""
    text = raw.decode("utf-8-sig")
    out: list[str] = []
    quoted = escaped = False
    for i, char in enumerate(text):
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
        elif char == ",":
            j = i + 1
            while j < len(text) and text[j].isspace():
                j += 1
            if j >= len(text) or text[j] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def tables(doc: dict, key: str) -> dict[str, dict]:
    return {t["name"]: t for t in doc[key]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def cells(doc: dict, key: str) -> dict[tuple[str, int, int, str], object]:
    result = {}
    for name, t in tables(doc, key).items():
        columns = [c["name"] for c in t["columns"]]
        for instance_id, instance in enumerate(t["instances"]):
            for row_id, row in enumerate(instance["rows"]):
                for column_id, value in enumerate(row):
                    result[name, instance_id, row_id, columns[column_id]] = value
    return result


def seal(a: Audit, path: Path, pin: dict, label: str) -> None:
    a.check(path.is_file(), label + " exists")
    if path.is_file():
        raw = path.read_bytes()
        a.same(len(raw), pin["bytes"], label + " size")
        a.same(sha(raw), pin["sha256"], label + " SHA")


def git_bytes(relative_path: str) -> bytes:
    return subprocess.check_output(["git", "show", "HEAD:" + relative_path], cwd=ROOT)


def accepted(a: Audit, contract: dict) -> tuple[dict, dict, bytes]:
    manual = contract["manual"]
    seal(a, Path(manual["installed_pdf"]), manual["pin"], "manual")
    seal(a, ROOT / contract["catalog"]["path"], contract["catalog"]["pin"], "catalog")
    plan = ROOT / "cases/simlox-air-support/execution-plan-v2.md"
    seal(a, plan, contract["catalog"]["execution_plan_pin"], "execution plan")
    for family in ("C02", "C01"):
        package = contract["accepted_evidence"][family]
        for relative_name, source in package["published_source"].items():
            path = f"cases/simlox-air-support/{package['package']}/{relative_name}"
            raw_local = (ROOT / path).read_bytes()
            a.same(len(raw_local), source["local_bytes"], family + " local size " + relative_name)
            a.same(sha(raw_local), source["local_sha256"], family + " local SHA " + relative_name)
            raw_git = git_bytes(path)
            a.same(len(raw_git), source["published_git_bytes"], family + " published size " + relative_name)
            a.same(sha(raw_git), source["published_git_sha256"], family + " published SHA " + relative_name)
        for run_name in ("single_equipment_zero", "single_both_context", "capacity_two_context"):
            if run_name not in package:
                continue
            run = package[run_name]
            directory = Path(run["path"])
            seal(a, directory / "invocation.json", run["invocation"], family + " " + run_name + " invocation")
            seal(a, directory / "closure.json", run["closure"], family + " " + run_name + " closure")
            for filename, pin in run["raw"].items():
                seal(a, directory / filename, pin, family + " " + run_name + " " + filename)
    c02 = contract["accepted_evidence"]["C02"]
    negative = c02["single_equipment_zero"]
    positive = c02["single_both_context"]
    negative_report = json_copy((Path(negative["path"]) / "report-raw.json").read_bytes())
    positive_report = json_copy((Path(positive["path"]) / "report-raw.json").read_bytes())
    negative_log = (Path(negative["path"]) / "model.log").read_bytes()
    for label, report in (("negative", negative_report), ("positive", positive_report)):
        shape = {name: (len(rows(table)), len(table["columns"])) for name, table in tables(report, "report").items()}
        a.same(shape, REPORT_SHAPE, label + " report shape")
        a.same(len(cells(report, "report")), 5210, label + " report cell count")
    return negative_report, positive_report, negative_log


def expected_input(parent: dict, contract: dict, arm: str) -> dict:
    result = copy.deepcopy(parent)
    t = tables(result, "model")
    t["TaskResource"]["instances"][0]["rows"] = copy.deepcopy(contract["source_design"]["shared_addition"]["rows"])
    t["SubTaskResource"]["instances"][0]["rows"] = copy.deepcopy(contract["source_design"][arm + "_arm"]["subtaskresource_rows"])
    t["ProblemDescription"]["instances"][0]["rows"][0][0] = contract["source_design"][arm + "_arm"]["description"]
    return result


def input_checks(a: Audit, contract: dict, input_path: Path, arm: str) -> dict:
    parent_path = ROOT / "cases/simlox-air-support/C02-joint-resources-v1.0.2/inputs/single-equipment-zero.json"
    seal(a, parent_path, contract["source_design"]["parent_input_pin"], "parent input")
    parent = json_copy(parent_path.read_bytes())
    doc = json_copy(input_path.read_bytes())
    wanted = expected_input(parent, contract, arm)
    a.same(doc, wanted, arm + " exact source document")
    a.same(len(tables(doc, "model")), 31, arm + " table count")
    a.same(sum(bool(rows(t)) for t in tables(doc, "model").values()), 21, arm + " row-containing table count")
    a.same(sum(any(any(v is not None for v in row) for row in rows(t)) for t in tables(doc, "model").values()), 18, arm + " substantive table count")
    a.same(len(rows(tables(doc, "model")["TaskResource"])), 2, arm + " explicit main task resources")
    a.same(len(rows(tables(doc, "model")["SubTaskResource"])), 2 if arm == "joint" else 1, arm + " explicit subtask resources")
    return doc


def roundtrip(a: Audit, input_doc: dict, exported: dict, arm: str) -> None:
    authored = tables(input_doc, "model")
    actual = tables(exported, "model")
    a.same(set(actual), set(authored), arm + " exported 31-table set")
    for name, source in authored.items():
        if name not in actual:
            continue
        candidate = actual[name]
        a.same(candidate["columns"], source["columns"], arm + " " + name + " schema")
        a.same([x["instance_name"] for x in candidate["instances"]],
               [x["instance_name"] for x in source["instances"]], arm + " " + name + " instances")
        for observed, authored_instance in zip(candidate["instances"], source["instances"]):
            authored_rows = authored_instance["rows"]
            native_rows = observed["rows"]
            if authored_rows:
                a.same(native_rows, authored_rows, arm + " " + name + " authored rows")
            else:
                a.check(len(native_rows) <= 1 and all(all(value is None for value in row) for row in native_rows),
                        arm + " " + name + " empty-table native null placeholder")


def compare_report(a: Audit, actual: dict, expected: dict, label: str) -> None:
    actual_tables, expected_tables = tables(actual, "report"), tables(expected, "report")
    a.same(set(actual_tables), set(expected_tables), label + " table topology")
    for name, reference in expected_tables.items():
        if name not in actual_tables:
            continue
        observed = actual_tables[name]
        a.same(observed["columns"], reference["columns"], label + " " + name + " columns")
        a.same([x.get("instance_name") for x in observed["instances"]],
               [x.get("instance_name") for x in reference["instances"]],
               label + " " + name + " instances")
    x, y = cells(actual, "report"), cells(expected, "report")
    a.same(set(x), set(y), label + " cell keys")
    for key, want in y.items():
        if key in x:
            value = x[key]
            if isinstance(value, (int, float)) and not isinstance(value, bool) and isinstance(want, (int, float)) and not isinstance(want, bool):
                a.check(math.isfinite(value) and math.isfinite(want) and math.isclose(value, want, rel_tol=0, abs_tol=1e-9),
                        label + " " + repr(key))
            else:
                a.same(value, want, label + " " + repr(key))


def expected_child_report(positive: dict, description: str) -> dict:
    result = copy.deepcopy(positive)
    t = tables(result, "report")
    rows(t["ProblemDescription"])[0][0] = description
    rr = t["ResourceResults"]
    names = [x["name"] for x in rr["columns"]]
    for row in rows(rr):
        row[names.index("NR")] = 1
        row[names.index("NRA")] = 1
        row[names.index("NRN")] = 1
        row[names.index("NRUM")] = 1 if row[names.index("STINT")] == 7 else 0
    total = t["ResourceResultsTotal"]
    names = [x["name"] for x in total["columns"]]
    row = rows(total)[0]
    for field in ("NR", "NRA", "NRN"):
        row[names.index(field)] = 1
    row[names.index("NRUM")] = 0.5 / 36
    return result


def event_checks(a: Audit, log_raw: bytes, arm: str, accepted_negative_log: bytes) -> None:
    log = log_raw.decode("utf-8-sig")
    if arm == "joint":
        a.same(log_raw, accepted_negative_log, "joint control event-log byte identity")
        a.check("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK" in log, "joint crew availability")
        a.check("Availability test on  <E-GSE at <BASE-01,0>> request for: 1 failed" in log, "joint equipment failure")
        a.check("mission cancelled" in log and "mission starting" not in log, "joint blocked mission")
        return
    sequence = [
        "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION",
        "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>",
        "Time: 7  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> requests resources",
        "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
        "Time: 7  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1",
        "Time: 7  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours",
        "Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed",
        "Time: 7.5  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1",
        "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,0>",
        "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success:",
        "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed: <TEACH-AIR-01,0>",
        "Time: 10 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>",
        "Time: 10 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>",
    ]
    position = -1
    for fragment in sequence:
        found = log.find(fragment, position + 1)
        a.check(found > position, "crew-only ordered event " + fragment)
        if found > position:
            position = found
    for fragment in ("Availability test on  <E-GSE", "<E-GSE at <BASE-01,0>> allocated to maintenance task", "<E-GSE at <BASE-01,0>> deallocated from  maintenance task", "mission cancelled", "mission failed", "item demand", "backorder"):
        a.check(fragment not in log, "crew-only excluded event " + fragment)
    a.same(log.count("<P-CREW at <BASE-01,0>> allocated to maintenance task"), 1, "crew-only one lease")
    a.same(log.count("<P-CREW at <BASE-01,0>> deallocated from  maintenance task"), 1, "crew-only one release")
    a.same(log.count("mission starting, duration: 2"), 1, "crew-only one launch")
    a.same(log.count("mission success:"), 1, "crew-only one mission success")


def replay_run(a: Audit, contract: dict, arm: str, negative: dict, positive: dict, negative_log: bytes) -> dict:
    run_id = contract["ownership"]["planned_run_ids"][0 if arm == "joint" else 1]
    run = CASE / "runs" / run_id
    closure_raw = (run / "closure.json").read_bytes()
    closure = json_copy(closure_raw)
    invocation_raw = (run / "invocation.json").read_bytes()
    invocation = json_copy(invocation_raw)
    manifest_raw = (CASE / "prelaunch-manifest.json").read_bytes()
    manifest = json_copy(manifest_raw)
    approval_raw = (CASE / "review/independent-prelaunch-go.json").read_bytes()
    approval = json_copy(approval_raw)
    preflight_path = CASE / approval["preflight_relative_path"]
    preflight_raw = preflight_path.read_bytes()
    preflight = json_copy(preflight_raw)
    source_pins = {item["key"]: item["sha256"] for item in manifest["source_files"]}
    a.same(closure["run_id"], run_id, arm + " closure ID")
    a.same(invocation["run_id"], run_id, arm + " invocation ID")
    a.same(closure["invocation_sha256"], sha(invocation_raw), arm + " invocation link")
    a.same(closure["source_hashes_before"], closure["source_hashes_after"], arm + " source stable")
    a.same(closure["source_hashes_before"], invocation["source_hashes_before"], arm + " invocation source link")
    a.same(closure["source_hashes_before"], source_pins, arm + " 70 frozen source pins")
    a.same(closure.get("manifest_sha256"), sha(manifest_raw), arm + " manifest closure pin")
    a.same(invocation.get("manifest_sha256"), sha(manifest_raw), arm + " manifest invocation pin")
    a.same(closure.get("approval_sha256"), sha(approval_raw), arm + " approval closure pin")
    a.same(invocation.get("approval_sha256"), sha(approval_raw), arm + " approval invocation pin")
    a.same(approval.get("decision"), "GO_PRELAUNCH", arm + " independent prelaunch decision")
    a.same(approval.get("manifest_sha256"), sha(manifest_raw), arm + " approval manifest pin")
    a.same(approval.get("preflight_sha256"), sha(preflight_raw), arm + " approved SSH preflight pin")
    a.same(closure.get("approved_preflight_sha256"), sha(preflight_raw), arm + " preflight closure pin")
    a.same(invocation.get("approved_preflight_sha256"), sha(preflight_raw), arm + " preflight invocation pin")
    a.same(preflight.get("ssh_session"), 0, arm + " preflight SSH session")
    a.same(preflight.get("mutex_free"), True, arm + " preflight mutex")
    a.same(preflight.get("gui"), GUI, arm + " preflight protected GUI")
    a.same(preflight.get("native_process_started"), False, arm + " preflight no native child")
    a.same(invocation["session_id"], 0, arm + " SSH session")
    a.check(invocation.get("ssh_ancestors"), arm + " SSH ancestry")
    a.same(invocation.get("queue_mutex"), "Global\\SimloxIssue18NativeQueue", arm + " queue identity")
    a.same(invocation.get("gui"), GUI, arm + " GUI identity")
    a.same([x.get("name") for x in invocation.get("planned_commands", [])],
           ["import", "export", "calc", "jsonreport"], arm + " four native commands")
    a.check(closure.get("error") in (None, ""), arm + " closure success")
    a.same(set(closure["raw"]), RAW_FILES, arm + " complete raw inventory")
    for filename, pin in closure["raw"].items():
        seal(a, run / filename, pin, arm + " raw " + filename)
    steps = json_copy((run / "steps.json").read_bytes())
    a.same([x.get("name") for x in steps], STAGES, arm + " six ordered stages")
    for index, step in enumerate(steps):
        a.same(step.get("status"), "completed", arm + f" stage {index} completed")
        a.same(step.get("exit_code"), 0, arm + f" stage {index} exit")
        a.same(step.get("gui_preserved"), True, arm + f" stage {index} protected GUI")
        if step.get("name") in ("import", "export", "calc", "jsonreport"):
            a.same(step.get("child_session_id"), 0, arm + f" stage {index} child session")
            a.check(isinstance(step.get("child_pid"), int) and step["child_pid"] != GUI["pid"],
                    arm + f" stage {index} native child PID")
    doc = input_checks(a, contract, run / "input.json", arm)
    authored = CASE / f"{arm}-input.json"
    a.same((run / "input.json").read_bytes(), authored.read_bytes(), arm + " frozen authored input copy")
    a.same(invocation.get("input_sha256"), sha((run / "input.json").read_bytes()), arm + " invocation input")
    roundtrip(a, doc, json_copy((run / "roundtrip-raw.json").read_bytes()), arm)
    log = (run / "model.log").read_bytes()
    event_checks(a, log, arm, negative_log)
    text = (run / "run.log").read_text(encoding="utf-8-sig")
    a.check("Errors: 0, Warnings: 2, Notes: 0" in text, arm + " converter summary")
    a.same(sorted(re.findall(r"warning\s*#(\d+)", text, flags=re.I)), ["108", "126"],
           arm + " converter warning IDs only")
    report = json_copy((run / "report-raw.json").read_bytes())
    shape = {name: (len(rows(table)), len(table["columns"])) for name, table in tables(report, "report").items()}
    a.same(shape, REPORT_SHAPE, arm + " six report shapes")
    a.same(len(cells(report, "report")), 5210, arm + " report cell count")
    if arm == "joint":
        expected = copy.deepcopy(negative)
        rows(tables(expected, "report")["ProblemDescription"])[0][0] = contract["source_design"]["joint_arm"]["description"]
    else:
        expected = expected_child_report(positive, contract["source_design"]["crewonly_arm"]["description"])
    compare_report(a, report, expected, arm + " report")
    actual_tables = tables(report, "report")
    def field_rows(name: str, field: str) -> list:
        table = actual_tables[name]
        column = [x["name"] for x in table["columns"]].index(field)
        return [row[column] for row in rows(table)]
    use_hours = sum(value * .5 for value in field_rows("ResourceResults", "NRUM"))
    wait_hours = sum(value * .5 for value in field_rows("ResourceResults", "NRW"))
    ready_hours = sum(value * .5 for value in field_rows("SystemResults", "NSYRY"))
    flight_hours = sum(value * .5 for value in field_rows("SystemResults", "NSYMO"))
    a.same(use_hours, 0 if arm == "joint" else .5, arm + " resource use hours")
    a.same(wait_hours, 7/12 if arm == "joint" else 0, arm + " resource wait hours")
    a.same(ready_hours, 36-7/12 if arm == "joint" else 33, arm + " aircraft ready hours")
    a.same(flight_hours, 0 if arm == "joint" else 2, arm + " aircraft flight hours")
    a.same(field_rows("SystemResults", "NSYRY")[-1], 1, arm + " terminal ready aircraft")
    a.same(field_rows("SystemResults", "NSYA")[-1], 1, arm + " terminal available aircraft")
    a.same(field_rows("ResourceResults", "NR")[-1], 1, arm + " terminal one crew resource")
    a.same(field_rows("ResourceResults", "NRUM")[-1], 0, arm + " terminal no crew occupation")
    return {"run_id": run_id, "closure_sha256": sha(closure_raw), "invocation_sha256": sha(invocation_raw), "raw_count": len(closure["raw"])}


def tamper_probes(a: Audit, contract: dict, positive: dict, negative_log: bytes) -> None:
    a.same(json_copy(b'{"literal": ",}", "array": [1,]}'), {"literal": ",}", "array": [1]}, "string-aware parser probe")
    candidate = expected_child_report(positive, contract["source_design"]["crewonly_arm"]["description"])
    changed = copy.deepcopy(candidate)
    t = tables(changed, "report")["SystemResults"]
    rows(t)[14][4] = "tampered"
    probe = Audit()
    compare_report(probe, changed, candidate, "mutated System cell")
    a.check(bool(probe.failures), "tampered report cell is rejected")
    changed = copy.deepcopy(candidate)
    resource = tables(changed, "report")["ResourceResults"]
    column = [x["name"] for x in resource["columns"]].index("NRUM")
    rows(resource)[14][column] = 2
    probe = Audit()
    compare_report(probe, changed, candidate, "mutated resource use")
    a.check(bool(probe.failures), "tampered resource ledger cell is rejected")
    authored = json_copy((CASE / "crewonly-input.json").read_bytes())
    changed_input = copy.deepcopy(authored)
    rows(tables(changed_input, "model")["TaskResource"])[0][2] = 2
    probe = Audit()
    roundtrip(probe, authored, changed_input, "tampered source")
    a.check(bool(probe.failures), "tampered populated source row is rejected")
    positive_run = Path(contract["accepted_evidence"]["C02"]["single_both_context"]["path"])
    source_lines = (positive_run / "model.log").read_bytes().splitlines()
    valid_log = b"\n".join(line for line in source_lines if b"Availability test on  <E-GSE" not in line
                          and b"<E-GSE at <BASE-01,0>> allocated to maintenance task" not in line
                          and b"<E-GSE at <BASE-01,0>> deallocated from  maintenance task" not in line)
    probe = Audit()
    event_checks(probe, valid_log, "crewonly", negative_log)
    a.check(not probe.failures, "synthetic accepted-format crew-only event gate")
    probe = Audit()
    event_checks(probe, (positive_run / "model.log").read_bytes(), "crewonly", negative_log)
    a.check(any("E-GSE" in error for error in probe.failures), "typed equipment booking probe is rejected")


def run() -> dict:
    a = Audit()
    contract_raw = (CASE / "contract.json").read_bytes()
    a.same(sha(contract_raw), CONTRACT_SHA, "frozen contract SHA")
    contract = json_copy(contract_raw)
    manifest = json_copy((CASE / "prelaunch-manifest.json").read_bytes())
    a.same(manifest.get("contract_sha256"), CONTRACT_SHA, "manifest contract link")
    a.same(len(manifest["source_files"]), 70, "70 frozen source records")
    for pin in manifest["source_files"]:
        seal(a, Path(pin["path"]), pin, "manifest " + pin["key"])
    negative, positive, negative_log = accepted(a, contract)
    tamper_probes(a, contract, positive, negative_log)
    authored_inputs = {}
    for arm in ("joint", "crewonly"):
        path = CASE / f"{arm}-input.json"
        if path.is_file():
            input_checks(a, contract, path, arm)
            authored_inputs[arm] = sha(path.read_bytes())
    base = {"schema": "c02-var04-independent-replay/v1", "contract_sha256": CONTRACT_SHA}
    run_paths = [CASE / "runs" / x for x in contract["ownership"]["planned_run_ids"]]
    if "--self-check" in sys.argv or not all((x / "closure.json").is_file() for x in run_paths):
        return {**base, "decision": "PENDING_NATIVE" if not a.failures else "NO_GO", "checks": a.checks, "failures": a.failures, "authored_inputs": authored_inputs, "native_run_present": [x.is_dir() for x in run_paths]}
    runs = [replay_run(a, contract, arm, negative, positive, negative_log) for arm in ("joint", "crewonly")]
    return {**base, "decision": "GO_BOUNDED" if not a.failures else "NO_GO", "checks": a.checks, "failures": a.failures, "runs": runs,
            "limits": ["One fixed one-aircraft INSPECT subtask and zero E-GSE capacity only.", "No general inheritance law, other task types, GUI visual result, or cross-engine parity."]}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True, indent=2))
