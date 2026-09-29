"""Source-bound C02 SSH CLI validation; candidate observations are reviewed separately."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402
import build  # noqa: E402

CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
RAW_FILES = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
             "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def rows(document: dict, name: str) -> list[dict]:
    matches = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"missing or duplicate native model table: {name}")
    names = [column["name"] for column in matches[0]["columns"]]
    return [dict(zip(names, row, strict=True)) for row in matches[0]["instances"][0]["rows"]]


def check_source(variant_id: str) -> list[str]:
    errors = []
    generated = build.build()
    for name, (data, diff) in generated.items():
        if data != (HERE / "inputs" / f"{name}.json").read_bytes() or diff != (HERE / "parent-diffs" / f"{name}.json").read_bytes():
            errors.append(f"generated source or parent diff differs: {name}")
    contract_variant = CONTRACT["variants"][variant_id]
    if sha(HERE / "inputs" / f"{variant_id}.json") != contract_variant["input_sha256"]:
        errors.append("contract input hash differs")
    if sha(HERE / "parent-diffs" / f"{variant_id}.json") != contract_variant["parent_diff_sha256"]:
        errors.append("contract parent diff hash differs")
    return errors


def check_behavior(model_log: str, report: dict, variant_id: str) -> tuple[list[str], dict]:
    errors = []
    lines = model_log.splitlines()
    events = []
    for number, line in enumerate(lines, 1):
        match = re.match(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$", line)
        if match:
            events.append((number, float(match[1]), match[2].strip()))
    if not events or any(a[1] > b[1] for a, b in zip(events, events[1:])):
        errors.append("native events absent or time order differs")
    def matches(body: str) -> list[tuple[int, float, str]]:
        return [event for event in events if event[2] == body]
    def contains(marker: str) -> list[tuple[int, float, str]]:
        return [event for event in events if marker in event[2]]
    def exactly(label: str, found: list[tuple[int, float, str]], hours: list[float]) -> None:
        if len(found) != len(hours) or any(abs(e[1] - hour) > 1e-4 for e, hour in zip(found, hours)):
            errors.append(f"{label}: observed {[(e[1], e[2]) for e in found]}")
    tag = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    owner = "<TEACH-AIR-01,0>"
    first = f"subtask 0 seqno 1 within system preparation task 0 on {owner}"
    second = f"subtask 1 seqno 2 within system preparation task 0 on {owner}"
    crew = "<P-CREW at <BASE-01,0>>"
    equip = "<E-GSE at <BASE-01,0>>"
    serial = CONTRACT["variants"][variant_id]["serial"]
    success = CONTRACT["variants"][variant_id]["equipment_quantity"] == 1
    duration = 10 / 60 if serial else 0.5
    rendered = "0.166667" if serial else "0.5"
    end = 7 + duration
    exactly("notice", matches("<TEACH-UNIT> mission ordered: BASIC-MISSION"), [7])
    exactly("mission created", matches(f"{tag} mission created:"), [7])
    exactly("system allocation", matches(f"{tag} mission allocates system: {owner}"), [7])
    exactly("preparation start", matches(f"{owner} preparation started, mission: {tag}"), [7])
    exactly("task start", matches(f"system preparation task 0 on {owner} started"), [7])
    exactly("first subtask start", matches(first + " started"), [7])
    exactly("first request", matches(first + " requests resources"), [7])
    exactly("first availability", matches(first + " resource availability test"), [7])
    p_test = f"Availability test on  {crew} request for: 1 OK"
    e_test = f"Availability test on  {equip} request for: 1 {'OK' if success else 'failed'}"
    if sum(p_test in line for line in lines) != 1 or sum(e_test in line for line in lines) != 1:
        errors.append("joint P-CREW/E-GSE availability test differs")
    if any("Availability test on" in line and p_test not in line and e_test not in line for line in lines):
        errors.append("unlisted resource availability test")
    p_lines = [i for i, line in enumerate(lines, 1) if p_test in line]
    e_lines = [i for i, line in enumerate(lines, 1) if e_test in line]
    request_events = matches(first + " requests resources")
    availability_events = matches(first + " resource availability test")
    if all(len(group) == 1 for group in (request_events, availability_events, p_lines, e_lines)):
        order = [request_events[0][0], availability_events[0][0], p_lines[0], e_lines[0]]
        if any(a >= b for a, b in zip(order, order[1:])):
            errors.append(f"joint request/test order differs: {order}")
    exactly("booking", matches(first + " books resources"), [7] if success else [])
    p_lease = crew + " allocated to maintenance task: 1  available now: 0"
    e_lease = equip + " allocated to maintenance task: 1  available now: 0"
    p_release = crew + " deallocated from  maintenance task: 1  available now: 1"
    e_release = equip + " deallocated from  maintenance task: 1  available now: 1"
    exactly("P-CREW lease", matches(p_lease), [7] if success else [])
    exactly("E-GSE lease", matches(e_lease), [7] if success else [])
    exactly("P-CREW release", matches(p_release), [end] if success else [])
    exactly("E-GSE release", matches(e_release), [end] if success else [])
    exactly("first work", matches(first + f" starts performing, planned to last for {rendered} hours"), [7] if success else [])
    exactly("first completion", matches(first + " completed"), [end] if success else [])
    exactly("first frees", matches(first + " frees resources"), [end] if success else [])
    exactly("second start", matches(second + " started"), [end] if success and serial else [])
    exactly("second request", matches(second + " requests resources: no resources needed"), [end] if success and serial else [])
    exactly("second work", matches(second + " starts performing, planned to last for 0.333333 hours"), [end] if success and serial else [])
    exactly("second completion", matches(second + " completed"), [7.5] if success and serial else [])
    exactly("task completion", matches(f"system preparation task 0 on {owner} completed"), [7.5] if success else [])
    cancelled = matches(f"{tag} mission cancelled:")
    prep_end_hour = 7.5 if success else cancelled[0][1] if len(cancelled) == 1 else None
    exactly("preparation end", matches(f"{owner} preparation ended, mission: {tag}"),
            [prep_end_hour] if prep_end_hour is not None else [])
    exactly("launch", matches(f"{tag} mission starting, duration: 2 : {owner}"), [8] if success else [])
    exactly("success", matches(f"{tag} mission success:"), [10] if success else [])
    exactly("completion", matches(f"{tag} mission completed: {owner}"), [10] if success else [])
    if success:
        exactly("no cancellation", cancelled, [])
        order = [first + " requests resources", first + " resource availability test",
                 first + " books resources", p_lease, e_lease,
                 first + f" starts performing, planned to last for {rendered} hours",
                 first + " completed", first + " frees resources", p_release, e_release]
        if serial:
            order += [second + " started", second + " starts performing, planned to last for 0.333333 hours"]
        locations = [[e[0] for e in matches(body)] for body in order]
        if any(len(group) != 1 for group in locations) or any(a[0] >= b[0] for a, b in zip(locations, locations[1:])):
            errors.append(f"joint acquisition/work/release order differs: {locations}")
        if len(e_lines) == 1 and len(matches(first + " books resources")) == 1 and e_lines[0] >= matches(first + " books resources")[0][0]:
            errors.append("equipment availability was checked after booking")
    else:
        if len(cancelled) != 1 or cancelled[0][1] < 7:
            errors.append("blocked mission lacks one cancellation after notice")
        if any(" allocated to maintenance task:" in e[2] or " deallocated from  maintenance task:" in e[2]
               or " books resources" in e[2] or " starts performing," in e[2] for e in events):
            errors.append("blocked joint request had partial lease or work")
        if any(e[2].startswith(second) for e in events):
            errors.append("blocked first step incorrectly started second step")
        if len(e_lines) == 1 and len(cancelled) == 1 and e_lines[0] >= cancelled[0][0]:
            errors.append("equipment failure was logged after cancellation")
        stop = [matches(first + " ordered to stop"), matches(first + " resource waiting stopped"),
                matches(f"system preparation task 0 on {owner} stopped"),
                matches(f"{owner} preparation ended, mission: {tag}")]
        if len(cancelled) == 1 and all(len(group) == 1 for group in stop):
            positions = [cancelled[0][0]] + [group[0][0] for group in stop]
            if any(a >= b for a, b in zip(positions, positions[1:])):
                errors.append("blocked cancellation/stop order differs")
        else:
            errors.append("blocked cancellation/stop lifecycle incomplete")
    global_counts = {
        " starts performing,": 1 + int(serial) if success else 0,
        " allocated to maintenance task:": 2 if success else 0,
        " deallocated from  maintenance task:": 2 if success else 0,
        " mission starting, duration:": 1 if success else 0,
        " mission cancelled:": 0 if success else 1,
    }
    for marker, count in global_counts.items():
        if len(contains(marker)) != count:
            errors.append(f"global event count differs for {marker}")
    summary = native.table_rows(report, "ResultSummary")
    if len(summary) != 1 or any(summary[0].get(k) != v for k, v in
            {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": int(success), "MSUF": int(success)}.items()):
        errors.append("ResultSummary differs")
    system = native.table_rows(report, "SystemResults")
    resources = native.table_rows(report, "ResourceResults")
    if len(system) != 72 or len(resources) != 72:
        errors.append(f"result interval counts differ: {len(system)}, {len(resources)}")
    for index, (row, resource) in enumerate(zip(system, resources)):
        hour = index / 2
        if any(row.get(k) != v for k, v in {"STINT": hour, "ETINT": hour + 0.5, "NSYA": 1,
                "NPSTA": int(hour == 7), "NPSUC": int(success and hour == 7.5),
                "FTMO": int(success and 8 <= hour < 10), "NSYMO": int(success and 8 <= hour < 10)}.items()):
            errors.append(f"SystemResults geometry/count differs at {index}")
        expected_prep = 1 if hour == 7 else 1 / 6 if not success and hour == 7.5 else 0
        if abs(row.get("NSYMP", -1) - expected_prep) > 1e-5:
            errors.append(f"SystemResults preparation time differs at {index}")
        expected_busy = 2 if success and not serial and hour == 7 else 2 / 3 if success and serial and hour == 7 else 0
        expected_wait = 1 if not success and hour == 7 else 1 / 6 if not success and hour == 7.5 else 0
        if (resource.get("STINT") != hour or resource.get("ETINT") != hour + 0.5 or
                resource.get("NR") != (2 if success else 1) or
                abs(resource.get("NRUM", -1) - expected_busy) > 1e-5 or
                abs(resource.get("NRW", -1) - expected_wait) > 1e-5):
            errors.append(f"ResourceResults capacity/busy/wait differs at {index}")
    return errors, {"cancellation_hour": cancelled[0][1] if len(cancelled) == 1 else None,
                    "joint_resource_minutes": (60 if not serial else 20) if success else 0,
                    "system_intervals": len(system), "resource_intervals": len(resources)}


def check_run(run: Path) -> dict:
    errors = []
    for name in RAW_FILES | {"invocation.json", "closure.json"}:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing/empty raw file: {name}")
    if errors:
        return {"case_id": "C02", "version": "1.0.2", "passed": False, "differences": errors}
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    variant_id = invocation.get("variant_id")
    if variant_id not in build.VARIANTS:
        errors.append("unknown variant")
        return {"case_id": "C02", "version": "1.0.2", "passed": False, "differences": errors}
    spec = CONTRACT["variants"][variant_id]
    errors.extend(check_source(variant_id))
    paths = {"contract_sha256": HERE / "contract.json", "builder_sha256": HERE / "build.py",
             "validator_sha256": HERE / "validate.py", "runner_sha256": HERE / "run_native_ssh.ps1",
             "launcher_sha256": HERE / "invoke_loopback.ps1",
             "parent_diff_sha256": HERE / "parent-diffs" / f"{variant_id}.json"}
    for field, path in paths.items():
        if invocation.get(field) != sha(path):
            errors.append(f"invocation source fingerprint differs: {field}")
    if (invocation.get("schema") != "simlox-c02-invocation/ssh-cli-v1" or
            invocation.get("case_id") != "C02" or invocation.get("case_version") != "1.0.2" or
            invocation.get("run_id") != run.name or invocation.get("execution_mode") != "ssh_cli_v1" or
            invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", [])):
        errors.append("native invocation identity or session-0 SSH ancestry differs")
    gui = invocation.get("coexisting_gui") or {}
    if (gui.get("pid") != 13340 or gui.get("session_id") != 1 or
            gui.get("process_start_utc") != "2026-09-28T10:09:56.8261381Z" or
            gui.get("responding_at_preflight") is not True):
        errors.append("original GUI identity differs")
    if (invocation.get("parent_input_sha256") != sha(build.PARENT) or
            invocation.get("input_sha256") != spec["input_sha256"] or
            sha(run / "input.json") != spec["input_sha256"]):
        errors.append("parent or run input hash differs")
    if (closure.get("run_id") != run.name or closure.get("variant_id") != variant_id or
            closure.get("invocation_sha256") != sha(run / "invocation.json") or
            set(closure.get("raw", {})) != RAW_FILES):
        errors.append("closure identity or file list differs")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            errors.append(f"raw file closure differs: {name}")
    steps = load(run / "steps.json")
    if ([step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"] or
            any(step.get("exit_code") != 0 or not step.get("coexisting_gui_present_after") for step in steps)):
        errors.append("native step sequence/exit or GUI coexistence differs")
    source, exported = load(run / "input.json"), load(run / "roundtrip-raw.json")
    diff = load(HERE / "parent-diffs" / f"{variant_id}.json")
    for name in diff["changed_tables_only"]:
        wanted = rows(source, name)
        if wanted != rows(exported, name):
            errors.append(f"changed table roundtrip differs: {name}")
    comparison = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not comparison["all_equal"]:
        errors.append(f"native business roundtrip differs: {comparison['changed']}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", run_log))
    if conversion is None or conversion.group(1, 2) != ("0", "2") or warnings != Counter({"108": 1, "126": 1}):
        errors.append(f"conversion errors or warnings differ: {dict(warnings)}")
    report = load(run / "report-raw.json")
    intervals = native.table_rows(report, "SystemResults")
    if len(intervals) != 72 or any(row.get("STINT") != index / 2 or row.get("ETINT") != (index + 1) / 2
                                   for index, row in enumerate(intervals)):
        errors.append("system report interval geometry differs")
    behavior_errors, observed = check_behavior((run / "model.log").read_text(encoding="utf-8-sig", errors="replace"),
                                               report, variant_id)
    errors.extend(behavior_errors)
    return {"case_id": "C02", "version": "1.0.2", "variant_id": variant_id, "run_id": run.name,
            "passed": not errors, "differences": errors, "roundtrip": comparison,
            "observed": observed, "publication_state": "not_published",
            "acceptance_scope": CONTRACT["acceptance_scope"]}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate.py RUN_DIRECTORY")
    result = check_run(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
