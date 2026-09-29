"""Independent, read-only audit of all four C01 1.0.2 native runs.

No production builder, validator, or shared validation helper is imported.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json"
VARIANTS = {"capacity-2": (2, 0), "capacity-1": (1, 0),
            "capacity-0": (0, 0), "wrong-specialty": (0, 2)}
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    # The 2017 native report exporter writes trailing commas.
    value = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",(?=\s*[}\]])", "", value))


def tables(document: dict, envelope: str) -> dict[str, list[dict]]:
    result = {}
    for item in document[envelope]["tables"]:
        name = item["name"]
        if name in result or len(item["instances"]) != 1:
            raise ValueError(f"duplicate table or unexpected instance count: {name}")
        columns = [column["name"] for column in item["columns"]]
        result[name] = [dict(zip(columns, row, strict=True)) for row in item["instances"][0]["rows"]]
    return result


def source_audit() -> list[str]:
    errors = []
    contract = read(HERE / "contract.json")
    if contract.get("parent_case") != "B02@1.0.2" or sha(PARENT) != contract.get("parent_input_sha256"):
        errors.append("B02 1.0.2 parent identity or hash differs")
    parent = read(PARENT)
    baseline = tables(parent, "model")
    if baseline["Resource"] or baseline["ResourceAllocation"] or baseline["SubTaskResource"]:
        errors.append("B02 parent already has resource rows")
    for variant, (crew, other) in VARIANTS.items():
        path = HERE / "inputs" / f"{variant}.json"
        diff_path = HERE / "parent-diffs" / f"{variant}.json"
        spec = contract["variants"][variant]
        if sha(path) != spec["input_sha256"] or sha(diff_path) != spec["parent_diff_sha256"]:
            errors.append(f"{variant}: source or exact diff hash differs")
        child = read(path)
        before, after = tables(parent, "model"), tables(child, "model")
        if list(before) != list(after):
            errors.append(f"{variant}: table order differs from B02")
        changed = [name for name in before if before[name] != after.get(name)]
        if changed != ["Resource", "ResourceAllocation", "SubTaskResource"]:
            errors.append(f"{variant}: changed tables differ: {changed}")
        resource = [
            {"RID": rid, "DESCR": description, "PRICE": None, "SUSTC": None, "TLLEN": None,
             "TYPE": "SPECIAL", "MUTILF": None, "NOTE": None}
            for rid, description in (("P-CREW", "Crew A personnel"), ("P-OTHER", "Other specialty personnel"))
        ]
        allocation = [
            {"POINT": "AIR_BASIC", "RID": rid, "STID": "BASE-01", "RQTY": quantity, "NOTE": None}
            for rid, quantity in (("P-CREW", crew), ("P-OTHER", other))
        ]
        demand = [{"TID": "PREP-FIXED", "SEQ": 1, "RID": "P-CREW", "QTY": 2,
                   "RPROB": 1, "ARID": None, "ARTF": None, "ENRMS": None, "NOTE": None}]
        expected = {"Resource": resource, "ResourceAllocation": allocation, "SubTaskResource": demand}
        if any(after[name] != wanted for name, wanted in expected.items()):
            errors.append(f"{variant}: personnel source delta differs")
        if after["TaskBreakDown"] != before["TaskBreakDown"] or after["MissionPreparation"] != before["MissionPreparation"]:
            errors.append(f"{variant}: B02 serial task changed")
        declared = read(diff_path)
        wanted_diff = {name: {"parent_rows": before[name], "child_rows": after[name]} for name in changed}
        if (declared.get("parent_case") != "B02@1.0.2" or declared.get("variant_id") != variant
                or declared.get("parent_input_sha256") != sha(PARENT)
                or declared.get("child_input_sha256") != sha(path)
                or declared.get("changed_tables_only") != changed or declared.get("tables") != wanted_diff
                or declared.get("added_rows") != 5 or declared.get("removed_rows") != 0
                or declared.get("field_changes") != 0):
            errors.append(f"{variant}: declared diff differs from computed delta")
    return errors


def timeline(log: str) -> list[tuple[int, float, str]]:
    return [(number, float(match[1]), match[2].strip())
            for number, line in enumerate(log.splitlines(), 1)
            if (match := re.match(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$", line))]


def audit_events(log: str, variant: str) -> tuple[list[str], dict]:
    errors = []
    events = timeline(log)
    if not events or any(a[1] > b[1] for a, b in zip(events, events[1:])):
        errors.append("native time events absent or unordered")
    def pick(marker: str) -> list[tuple[int, float, str]]:
        return [event for event in events if marker in event[2]]
    def expect(label: str, marker: str, hours: list[float]) -> None:
        found = pick(marker)
        if len(found) != len(hours) or any(abs(event[1] - hour) > 1e-4 for event, hour in zip(found, hours)):
            errors.append(f"{label}: {[(e[1], e[2]) for e in found]}")
    expect("notice", " mission ordered:", [7])
    expect("mission creation", " mission created:", [7])
    expect("aircraft allocation", " mission allocates system:", [7])
    expect("preparation start", " preparation started,", [7])
    request_line = "Availability test on  <P-CREW at <BASE-01,0>> request for: 2 "
    if log.count(request_line) != 1 or "Availability test on  <P-OTHER" in log:
        errors.append("personnel request was not exactly P-CREW x2")
    success = variant == "capacity-2"
    expect("request", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> requests resources", [7])
    expect("availability test", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> resource availability test", [7])
    expect("acquisition", " allocated to maintenance task:", [7] if success else [])
    expect("release", " deallocated from  maintenance task:", [7 + 10 / 60] if success else [])
    expect("INSPECT work", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing,", [7] if success else [])
    expect("SERVICE work", "subtask 1 seqno 2 within system preparation task 0 on <TEACH-AIR-01,0> starts performing,", [7 + 10 / 60] if success else [])
    expect("launch", " mission starting, duration:", [8] if success else [])
    expect("mission success", " mission success:", [10] if success else [])
    expect("mission completion", " mission completed:", [10] if success else [])
    cancel = pick(" mission cancelled:")
    if success:
        if request_line + "OK" not in log or cancel:
            errors.append("capacity-two booking or cancellation differs")
        expect("INSPECT completion", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed", [7 + 10 / 60])
        expect("SERVICE completion", "subtask 1 seqno 2 within system preparation task 0 on <TEACH-AIR-01,0> completed", [7.5])
        prep_done = [e for e in events if e[2] == "system preparation task 0 on <TEACH-AIR-01,0> completed"]
        if len(prep_done) != 1 or abs(prep_done[0][1] - 7.5) > 1e-4:
            errors.append(f"preparation completion: {prep_done}")
        expect("preparation end", " preparation ended,", [7.5])
        if "allocated to maintenance task: 2  available now: 0" not in log or "deallocated from  maintenance task: 2  available now: 2" not in log:
            errors.append("two-unit lease ledger differs")
        first = "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0>"
        second = "subtask 1 seqno 2 within system preparation task 0 on <TEACH-AIR-01,0>"
        crew = "<P-CREW at <BASE-01,0>>"
        order = [
            first + " books resources",
            crew + " allocated to maintenance task: 2  available now: 0",
            first + " starts performing, planned to last for 0.166667 hours",
            first + " completed",
            first + " frees resources",
            crew + " deallocated from  maintenance task: 2  available now: 2",
            second + " starts performing, planned to last for 0.333333 hours",
        ]
        positions = [[event[0] for event in events if event[2] == label] for label in order]
        if any(len(group) != 1 for group in positions) or any(
                left[0] >= right[0] for left, right in zip(positions, positions[1:])):
            errors.append(f"crew acquisition/work/release order differs: {positions}")
        return errors, {"cancellation_hour": None, "lease_person_minutes": 20}
    if request_line + "failed" not in log or any(" books resources" in e[2] for e in events):
        errors.append("blocked request or booking differs")
    if len(cancel) != 1 or cancel[0][1] < 7:
        errors.append("blocked mission lacks one cancellation after notice")
    ordered = pick("subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> ordered to stop")
    waiting = pick("subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> resource waiting stopped")
    stopped = [e for e in events if e[2] == "system preparation task 0 on <TEACH-AIR-01,0> stopped"]
    end = pick(" preparation ended,")
    if any(len(group) != 1 for group in (cancel, ordered, waiting, stopped, end)):
        errors.append("blocked stop lifecycle incomplete")
    elif not (cancel[0][0] < ordered[0][0] < waiting[0][0] < stopped[0][0] < end[0][0]):
        errors.append("blocked stop event order differs")
    return errors, {"cancellation_hour": cancel[0][1] if len(cancel) == 1 else None, "lease_person_minutes": 0}


def audit_report(report: dict, variant: str) -> tuple[list[str], dict]:
    errors = []
    data = tables(report, "report")
    success = variant == "capacity-2"
    summary = data.get("ResultSummary", [])
    expected_summary = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": int(success), "MSUF": int(success)}
    if len(summary) != 1 or any(summary[0].get(k) != v for k, v in expected_summary.items()):
        errors.append("ResultSummary differs")
    system, resources = data.get("SystemResults", []), data.get("ResourceResults", [])
    if len(system) != 72 or len(resources) != 72:
        errors.append(f"report interval counts differ: {len(system)}, {len(resources)}")
    capacity = sum(VARIANTS[variant])
    wait = {"capacity-2": 0, "capacity-1": 1, "capacity-0": 2, "wrong-specialty": 2}[variant]
    totals = Counter()
    for index, (sysrow, resrow) in enumerate(zip(system, resources)):
        hour = index / 2
        if any(sysrow.get(k) != v for k, v in {"STINT": hour, "ETINT": hour + .5, "NSYA": 1}.items()):
            errors.append(f"SystemResults geometry {index}")
        wanted = {"NPSTA": int(hour == 7), "NPSUC": int(success and hour == 7.5),
                  "FTMO": int(success and 8 <= hour < 10), "NSYMO": int(success and 8 <= hour < 10)}
        for field, value in wanted.items():
            if sysrow.get(field) != value:
                errors.append(f"SystemResults {field} {index}")
            totals[field] += sysrow.get(field, 0) * (1 if field.startswith("NP") else .5)
        expected_busy = 2 / 3 if success and hour == 7 else 0
        expected_wait = wait * (1 if hour == 7 else 1 / 6 if hour == 7.5 else 0)
        if (resrow.get("STINT") != hour or resrow.get("ETINT") != hour + .5
                or resrow.get("NR") != capacity or abs(resrow.get("NRUM", -1) - expected_busy) > 1e-5
                or abs(resrow.get("NRW", -1) - expected_wait) > 1e-5):
            errors.append(f"ResourceResults capacity/busy/wait {index}")
    if any(abs(totals[k] - v) > 1e-8 for k, v in
           {"NPSTA": 1, "NPSUC": int(success), "FTMO": 2 if success else 0,
            "NSYMO": 2 if success else 0}.items()):
        errors.append(f"SystemResults totals differ: {dict(totals)}")
    return errors, {"system_intervals": len(system), "resource_intervals": len(resources),
                    "metric_totals": dict(totals)}


def run_audit(run: Path, variant: str) -> tuple[list[str], dict]:
    errors = []
    contract = read(HERE / "contract.json")
    spec = contract["variants"][variant]
    for name in RAW | {"invocation.json", "closure.json", "run-manifest.json", "validation.json"}:
        if not (run / name).is_file() or (run / name).stat().st_size < 5:
            return [f"missing or empty run file: {name}"], {}
    invocation, closure, manifest, validation = [read(run / name) for name in
        ("invocation.json", "closure.json", "run-manifest.json", "validation.json")]
    if invocation.get("variant_id") != variant or invocation.get("run_id") != run.name:
        errors.append("invocation variant or run ID mismatch")
    source_paths = {"contract_sha256": HERE / "contract.json", "builder_sha256": HERE / "build.py",
                    "validator_sha256": HERE / "validate.py", "runner_sha256": HERE / "run_native_ssh.ps1",
                    "launcher_sha256": HERE / "invoke_loopback.ps1",
                    "parent_diff_sha256": HERE / "parent-diffs" / f"{variant}.json"}
    for field, path in source_paths.items():
        if invocation.get(field) != sha(path):
            errors.append(f"invocation {field} mismatch")
    if (invocation.get("parent_input_sha256") != sha(PARENT)
            or invocation.get("input_sha256") != spec["input_sha256"]
            or sha(run / "input.json") != spec["input_sha256"]):
        errors.append("run input or parent hash mismatch")
    if (invocation.get("execution_mode") != "ssh_cli_v1" or invocation.get("session_id") != 0
            or "sshd.exe" not in invocation.get("ssh_ancestor_names", [])
            or invocation.get("simlox_exe_sha256") != "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"):
        errors.append("native executable or SSH session provenance mismatch")
    gui = invocation.get("coexisting_gui") or {}
    if (gui.get("pid") != 13340 or gui.get("session_id") != 1
            or gui.get("process_start_utc") != "2026-09-28T10:09:56.8261381Z"
            or gui.get("responding_at_preflight") is not True):
        errors.append("original GUI provenance mismatch")
    if (closure.get("variant_id") != variant or closure.get("invocation_sha256") != sha(run / "invocation.json")
            or set(closure.get("raw", {})) != RAW):
        errors.append("raw closure identity or file set mismatch")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            errors.append(f"raw closure mismatch: {name}")
    if (manifest.get("invocation_sha256") != sha(run / "invocation.json")
            or manifest.get("closure_sha256") != sha(run / "closure.json")
            or manifest.get("validation_sha256") != sha(run / "validation.json")):
        errors.append("manifest chain mismatch")
    if not validation.get("passed") or validation.get("differences") or validation.get("variant_id") != variant:
        errors.append("source-bound validation mismatch")
    steps = read(run / "steps.json")
    if ([s.get("name") for s in steps] != ["import", "export", "calc", "jsonreport"]
            or any(s.get("exit_code") != 0 or not s.get("coexisting_gui_present_after") for s in steps)):
        errors.append("native step or GUI coexistence failure")
    original, roundtrip = tables(read(run / "input.json"), "model"), tables(read(run / "roundtrip-raw.json"), "model")
    for name, source in original.items():
        if source and source != roundtrip.get(name):
            errors.append(f"native roundtrip changed business table {name}")
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", conversion)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", conversion))
    if not match or match.group(1, 2) != ("0", "2") or warnings != Counter({"108": 1, "126": 1}):
        errors.append("conversion errors or warning allowlist differs")
    event_errors, observed = audit_events((run / "model.log").read_text(encoding="utf-8-sig", errors="replace"), variant)
    report_errors, metrics = audit_report(read(run / "report-raw.json"), variant)
    errors.extend(event_errors + report_errors)
    hashes = {name: sha(run / name) for name in ("invocation.json", "closure.json", "run-manifest.json",
               "validation.json", "model.sxi", "model.sxo", "model.log", "report-raw.json")}
    nonempty = sum(any(any(value not in (None, "") for value in row.values()) for row in table)
                   for table in original.values())
    return errors, {"run_id": run.name, "roundtrip_business_tables": nonempty,
                    "raw_closure_count": len(closure.get("raw", {})), "observed": observed,
                    **metrics, "hashes": hashes}


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("usage: review_readonly.py CAPACITY2_RUN CAPACITY1_RUN CAPACITY0_RUN WRONG_RUN")
    errors = source_audit()
    runs = {}
    for variant, name in zip(VARIANTS, sys.argv[1:], strict=True):
        differences, details = run_audit(Path(name), variant)
        errors.extend(f"{variant}: {message}" for message in differences)
        runs[variant] = details
    result = {"schema": "simlox-c01-independent-readonly-review/v1", "case_id": "C01",
              "version": "1.0.2", "passed": not errors, "differences": errors,
              "reviewer_sha256": sha(HERE / "review_readonly.py"), "runs": runs}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
