"""Source-bound C03 native behavior validator."""
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


def check_behavior(model_log: str, report: dict, variant: str) -> tuple[list[str], dict]:
    errors = []
    lines = model_log.splitlines()
    events = []
    for number, line in enumerate(lines, 1):
        match = re.match(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$", line)
        if match:
            events.append((number, float(match[1]), match[2].strip()))
    if not events or any(a[1] > b[1] for a, b in zip(events, events[1:])):
        errors.append("native event chronology absent or unordered")

    def find(marker: str) -> list[tuple[int, float, str]]:
        return [event for event in events if marker in event[2]]

    def exact(body: str) -> list[tuple[int, float, str]]:
        return [event for event in events if event[2] == body]

    def times(label: str, found: list[tuple[int, float, str]], wanted: list[float]) -> None:
        if len(found) != len(wanted) or any(abs(row[1]-hour) > 1e-4 for row, hour in zip(found, wanted)):
            errors.append(f"{label}: {[e[1:] for e in found]}")

    tag = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    owners = ["<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>"]
    cap = build.CAPACITIES[variant]
    launch = {2: 8, 1: 8.5, 0: None}[cap]
    completion = None if launch is None else launch + 1
    times("notice", exact("<TEACH-UNIT> mission ordered: BASIC-MISSION"), [7.5])
    times("mission created", exact(tag + " mission created:"), [7.5])
    times("formation request", exact(tag + " mission activated, systems requested: 2"), [7.5])
    times("allocation", find(tag + " mission allocates system:"), [7.5, 7.5])
    for owner in owners:
        times(f"{owner} allocation", exact(tag + " mission allocates system: " + owner), [7.5])
        times(f"{owner} preparation start", exact(owner + " preparation started, mission: " + tag), [7.5])
        times(f"{owner} preparation end", exact(owner + " preparation ended, mission: " + tag),
              [{2: 8, 1: 8 if owner == owners[0] else 8.5, 0: 8.5}[cap]])
    requests = find(" requests resources")
    availability = find(" resource availability test")
    times("two distinct preparation requests", requests, [7.5, 7.5])
    if len(requests) == 2 and {owner for event in requests for owner in owners if owner in event[2]} != set(owners):
        errors.append("request owners differ")
    expected_availability = [7.5, 7.5] + ([8] if cap == 1 else [])
    times("availability lifecycle", availability, expected_availability)
    raw_tests = [(number, line) for number, line in enumerate(lines, 1)
                 if "Availability test on" in line]
    expected_ok = {2: 2, 1: 2, 0: 0}[cap]
    expected_failed = {2: 0, 1: 1, 0: 2}[cap]
    if (len(raw_tests) != expected_ok + expected_failed
            or sum("<P-CREW at <BASE-01,0>> request for: 1 OK" in line for _, line in raw_tests) != expected_ok
            or sum("<P-CREW at <BASE-01,0>> request for: 1 failed" in line for _, line in raw_tests) != expected_failed):
        errors.append("personnel availability tests differ")
    books, work, finished, frees = (find(marker) for marker in
                                     (" books resources", " starts performing,", " completed", " frees resources"))
    # A completed marker above also matches unrelated completion events; select subtask rows.
    finished = [event for event in finished if "subtask" in event[2]]
    lease = find(" allocated to maintenance task:")
    release = find(" deallocated from  maintenance task:")
    if cap == 0:
        for label, group in (("booking", books), ("work", work), ("subtask completion", finished),
                             ("lease", lease), ("release", release)):
            times(label, group, [])
        times("mission cancellation", exact(tag + " mission cancelled:"), [8.5])
        for owner in owners:
            task = next((row[2] for row in requests if owner in row[2]), None)
            if task is None:
                continue
            stem = task.removesuffix(" requests resources")
            stop = [exact(stem + suffix) for suffix in
                    (" ordered to stop", " resource waiting stopped")]
            for suffix, group in zip((" ordered to stop", " resource waiting stopped"), stop):
                times(f"{owner}{suffix}", group, [8.5])
            cancel = exact(tag + " mission cancelled:")
            prep_end = exact(owner + " preparation ended, mission: " + tag)
            if (len(cancel) == 1 and all(len(group) == 1 for group in stop)
                    and len(prep_end) == 1 and not
                    cancel[0][0] < stop[0][0][0] < stop[1][0][0] < prep_end[0][0]):
                errors.append(f"{owner} cancellation and wait-stop order differs")
        times("no launch", find(" mission starting, duration:"), [])
    else:
        wanted_work = [7.5, 7.5] if cap == 2 else [7.5, 8]
        wanted_done = [8, 8] if cap == 2 else [8, 8.5]
        for label, group, wanted in (("booking", books, wanted_work),
                                      ("work", work, wanted_work),
                                      ("subtask completion", finished, wanted_done),
                                      ("resource freeing", frees, wanted_done),
                                      ("crew lease", lease, wanted_work),
                                      ("crew release", release, wanted_done)):
            times(label, group, wanted)
        if len(work) == 2 and {owner for event in work for owner in owners if owner in event[2]} != set(owners):
            errors.append("two distinct aircraft did not perform work")
        for owner in owners:
            own = [event for event in work if owner in event[2]]
            if len(own) != 1 or "planned to last for 0.5 hours" not in own[0][2]:
                errors.append(f"{owner} work duration differs")
        for index, grant in enumerate(lease):
            if index >= len(work) or index >= len(books):
                break
            owner = next((owner for owner in owners if owner in work[index][2]), None)
            if (owner is None or owner not in books[index][2]
                    or not books[index][0] < grant[0] < work[index][0]
                    or not any(owner in line for line in lines[grant[0]:work[index][0]-1])):
                errors.append("crew lease was not bound to owner before work")
        for index, freed in enumerate(frees):
            if index >= len(release) or freed[0] >= release[index][0]:
                errors.append("crew released before owner finished")
        if cap == 1 and len(release) == 2 and len(lease) == 2 and release[0][0] >= lease[1][0]:
            errors.append("second crew lease preceded first release")
        if cap == 1 and len(work) == 2:
            waiting_owner = next((owner for owner in owners if owner in work[1][2]), None)
            received = find(" resource received")
            if (waiting_owner is None or len(received) != 1
                    or waiting_owner not in received[0][2] or abs(received[0][1] - 8) > 1e-4
                    or len(release) != 2 or len(books) != 2
                    or not release[0][0] < received[0][0] < books[1][0]):
                errors.append("waiting aircraft did not receive released crew before booking")
        elif find(" resource received"):
            errors.append("unexpected resource wait exit")
        times("launch", exact(tag + " mission starting, duration: 1 : " + ",".join(owners)), [launch])
        times("success", exact(tag + " mission success:"), [completion])
        times("completion", exact(tag + " mission completed: " + ",".join(owners)), [completion])
        times("no cancellation", find(" mission cancelled:"), [])
    if cap == 0:
        times("no success", find(" mission success:"), [])
        times("no completion", find(" mission completed:"), [])

    summary = native.table_rows(report, "ResultSummary")
    if len(summary) != 1 or any(summary[0].get(k) != v for k, v in
            {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": int(cap > 0), "MSUF": int(cap > 0)}.items()):
        errors.append("native ResultSummary differs")
    system = native.table_rows(report, "SystemResults")
    resources = native.table_rows(report, "ResourceResults")
    if len(system) != 72 or len(resources) != 72:
        errors.append(f"result interval counts differ: {len(system)}, {len(resources)}")
    for index, (row, resource) in enumerate(zip(system, resources)):
        hour = index / 2
        preparing = (2 if hour == 7.5 else 1 if cap == 1 and hour == 8 else
                     2 if cap == 0 and hour == 8 else 0)
        succeeded = (2 if cap == 2 and hour == 8 else
                     1 if cap == 1 and hour in (8, 8.5) else 0)
        mission = int(launch is not None and launch <= hour < completion)
        wanted = {"STINT": hour, "ETINT": hour + .5, "NSYA": 2,
                  "NSYMP": preparing, "NPSTA": 2 if hour == 7.5 else 0,
                  "NPSUC": succeeded, "FTMO": mission, "NSYMO": 2 * mission}
        if any(row.get(key) != value for key, value in wanted.items()):
            errors.append(f"SystemResults interval differs at {index}")
        busy = 2 if cap == 2 and hour == 7.5 else 1 if cap == 1 and hour in (7.5, 8) else 0
        waiting = 1 if cap == 1 and hour == 7.5 else 2 if cap == 0 and hour in (7.5, 8) else 0
        wanted_resource = {"STINT": hour, "ETINT": hour + .5, "NR": cap,
                           "NRUM": busy, "NRW": waiting}
        if any(abs(resource.get(key, -100) - value) > 1e-5 for key, value in wanted_resource.items()):
            errors.append(f"ResourceResults interval differs at {index}")
    return errors, {"cancellation_hour": 8.5 if cap == 0 else None,
                    "launch_hour": launch, "crew_person_minutes": 60 if cap > 0 else 0,
                    "system_intervals": len(system), "resource_intervals": len(resources)}


def validate(run: Path) -> dict:
    errors = []
    for name in RAW_FILES | {"invocation.json", "closure.json"}:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing or empty native artifact: {name}")
    if errors:
        return {"case_id": "C03", "passed": False, "differences": errors}
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    variant = invocation.get("variant_id")
    if variant not in build.CAPACITIES:
        errors.append("unknown variant")
        return {"case_id": "C03", "passed": False, "differences": errors}
    spec = CONTRACT["variants"][variant]
    if (sha(build.PARENT) != CONTRACT["parent_input_sha256"]
            or sha(HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json") != CONTRACT["formation_parent_input_sha256"]):
        errors.append("accepted parent source hash differs")
    parent = json.loads(build.PARENT.read_bytes())
    for name in build.CAPACITIES:
        source, diff = build.build_variant(parent, name)
        if (source != (HERE / "inputs" / f"{name}.json").read_bytes()
                or diff != (HERE / "parent-diffs" / f"{name}.json").read_bytes()):
            errors.append(f"generated model or parent delta differs: {name}")
    paths = {"contract_sha256": HERE / "contract.json", "builder_sha256": HERE / "build.py",
             "validator_sha256": HERE / "validate.py", "runner_sha256": HERE / "run_native_ssh.ps1",
             "launcher_sha256": HERE / "invoke_loopback.ps1",
             "parent_diff_sha256": HERE / "parent-diffs" / f"{variant}.json"}
    for field, path in paths.items():
        if invocation.get(field) != sha(path):
            errors.append(f"invocation source fingerprint differs: {field}")
    if (invocation.get("case_id") != "C03" or invocation.get("case_version") != "1.0.2"
            or invocation.get("run_id") != run.name or invocation.get("variant_id") != variant
            or invocation.get("input_sha256") != spec["input_sha256"]
            or invocation.get("parent_input_sha256") != sha(build.PARENT)
            or invocation.get("formation_parent_input_sha256") != CONTRACT["formation_parent_input_sha256"]
            or invocation.get("execution_mode") != "ssh_cli_v1" or invocation.get("session_id") != 0
            or "sshd.exe" not in invocation.get("ssh_ancestor_names", [])):
        errors.append("native SSH invocation identity differs")
    gui = invocation.get("coexisting_gui") or {}
    if (gui.get("pid") != 13340 or gui.get("session_id") != 1
            or gui.get("process_start_utc") != "2026-09-28T10:09:56.8261381Z"
            or gui.get("responding_at_preflight") is not True):
        errors.append("preserved GUI identity differs")
    if sha(run / "input.json") != spec["input_sha256"]:
        errors.append("native run input hash differs")
    if (closure.get("run_id") != run.name or closure.get("variant_id") != variant
            or closure.get("invocation_sha256") != sha(run / "invocation.json")
            or set(closure.get("raw", {})) != RAW_FILES):
        errors.append("closure identity or inventory differs")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            errors.append(f"raw closure mismatch: {name}")
    steps = load(run / "steps.json")
    if ([step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"]
            or any(step.get("exit_code") != 0 or not step.get("coexisting_gui_present_after") for step in steps)):
        errors.append("native step exit or GUI coexistence differs")
    comparison = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not comparison["all_equal"]:
        errors.append(f"native business roundtrip differs: {comparison['changed']}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", run_log))
    if conversion is None or conversion.group(1, 2) != ("0", "2") or warnings != Counter({"108": 1, "126": 1}):
        errors.append(f"native conversion errors or warnings differ: {dict(warnings)}")
    report = load(run / "report-raw.json")
    system = native.table_rows(report, "SystemResults")
    resources = native.table_rows(report, "ResourceResults")
    if len(system) != 72 or len(resources) != 72:
        errors.append(f"result interval counts differ: {len(system)}, {len(resources)}")
    behavior_errors, observed = check_behavior(
        (run / "model.log").read_text(encoding="utf-8-sig", errors="replace"), report, variant)
    errors.extend(behavior_errors)
    return {"case_id": "C03", "version": "1.0.2", "variant_id": variant, "run_id": run.name,
            "passed": not errors, "differences": errors, "roundtrip": comparison,
            "observed": observed, "validation_scope": "source_bound_native_behavior",
            "publication_state": "not_published"}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate.py RUN_DIRECTORY")
    result = validate(Path(sys.argv[1]))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)
