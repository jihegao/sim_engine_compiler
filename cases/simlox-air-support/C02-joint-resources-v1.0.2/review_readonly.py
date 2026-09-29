"""Independent read-only review of C02 sources and four sealed native runs.

Uses only standard-library readers; never imports the builder or validator.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C01-personnel-capacity-v1.0.2" / "inputs" / "capacity-2.json"
VARIANTS = {"single-both": (False, 1), "single-equipment-zero": (False, 0),
            "serial-both": (True, 1), "serial-equipment-zero": (True, 0)}
RAW = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log",
       "export.log", "run.log", "model.log", "report-raw.json", "report-export.log", "steps.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(document: dict, envelope: str) -> dict[str, list[dict]]:
    result = {}
    for item in document[envelope]["tables"]:
        name = item["name"]
        if name in result or len(item["instances"]) != 1:
            raise ValueError(f"duplicate table or instance: {name}")
        columns = [column["name"] for column in item["columns"]]
        result[name] = [dict(zip(columns, row, strict=True)) for row in item["instances"][0]["rows"]]
    return result


def source_audit() -> list[str]:
    errors = []
    contract = read(HERE / "contract.json")
    if sha(PARENT) != contract["parent_input_sha256"] or contract["parent_case"] != "C01@1.0.2/capacity-2":
        errors.append("published C01 parent identity/hash differs")
    parent = read(PARENT)
    baseline = tables(parent, "model")
    if [(r["RID"], r["RQTY"]) for r in baseline["ResourceAllocation"]] != [("P-CREW", 2), ("P-OTHER", 0)]:
        errors.append("C01 parent allocation is not published capacity-two source")
    for variant, (serial, equipment) in VARIANTS.items():
        path = HERE / "inputs" / f"{variant}.json"
        diff_path = HERE / "parent-diffs" / f"{variant}.json"
        spec = contract["variants"][variant]
        if sha(path) != spec["input_sha256"] or sha(diff_path) != spec["parent_diff_sha256"]:
            errors.append(f"{variant}: contract source hashes differ")
        child = read(path)
        after = tables(child, "model")
        if list(baseline) != list(after):
            errors.append(f"{variant}: model table order differs")
        changed = [name for name in baseline if baseline[name] != after.get(name)]
        expected_changed = ["Resource", "ResourceAllocation", "TaskBreakDown", "SubTaskResource"] if not serial else [
            "Resource", "ResourceAllocation", "SubTaskResource"]
        if changed != expected_changed:
            errors.append(f"{variant}: changed table set/order differs: {changed}")
        expected_resource = baseline["Resource"] + [
            {"RID": "E-GSE", "DESCR": "Ground support equipment", "PRICE": None, "SUSTC": None,
             "TLLEN": None, "TYPE": "SPECIAL", "MUTILF": None, "NOTE": None}]
        expected_allocation = [dict(baseline["ResourceAllocation"][0], RQTY=1),
                               baseline["ResourceAllocation"][1],
                               {"POINT": "AIR_BASIC", "RID": "E-GSE", "STID": "BASE-01",
                                "RQTY": equipment, "NOTE": None}]
        expected_demand = [dict(baseline["SubTaskResource"][0], QTY=1),
                           {"TID": "PREP-FIXED", "SEQ": 1, "RID": "E-GSE", "QTY": 1,
                            "RPROB": 1, "ARID": None, "ARTF": None, "ENRMS": None, "NOTE": None}]
        expected_breakdown = baseline["TaskBreakDown"] if serial else [
            dict(baseline["TaskBreakDown"][0], DURN=0.5)]
        expected = {"Resource": expected_resource, "ResourceAllocation": expected_allocation,
                    "SubTaskResource": expected_demand, "TaskBreakDown": expected_breakdown}
        for name, wanted in expected.items():
            if after[name] != wanted:
                errors.append(f"{variant}: {name} source rows differ")
        if after["MissionPreparation"] != baseline["MissionPreparation"] or after["MissionType"] != baseline["MissionType"]:
            errors.append(f"{variant}: C01 mission and preparation identity changed")
        declared = read(diff_path)
        wanted_diff = {name: {"parent_rows": baseline[name], "child_rows": after[name]} for name in changed}
        if (declared.get("parent_case") != "C01@1.0.2/capacity-2"
                or declared.get("parent_input_sha256") != sha(PARENT)
                or declared.get("child_input_sha256") != sha(path)
                or declared.get("variant_id") != variant
                or declared.get("changed_tables_only") != changed
                or declared.get("added_rows") != 3
                or declared.get("removed_rows") != (0 if serial else 1)
                or declared.get("tables") != wanted_diff):
            errors.append(f"{variant}: exact parent diff differs from computed delta")
    return errors


def behavior_audit(log: str, report: dict, variant: str) -> tuple[list[str], dict]:
    errors = []
    serial, equipment = VARIANTS[variant]
    success = equipment == 1
    owner, tag = "<TEACH-AIR-01,0>", "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    first = f"subtask 0 seqno 1 within system preparation task 0 on {owner}"
    second = f"subtask 1 seqno 2 within system preparation task 0 on {owner}"
    crew, device = "<P-CREW at <BASE-01,0>>", "<E-GSE at <BASE-01,0>>"
    lines = log.splitlines()
    events = [(number, float(match[1]), match[2].strip())
              for number, line in enumerate(lines, 1)
              if (match := re.match(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$", line))]
    if not events or any(a[1] > b[1] for a, b in zip(events, events[1:])):
        errors.append("native event time order differs")
    def event(body: str) -> list[tuple[int, float, str]]:
        return [record for record in events if record[2] == body]
    def exact(label: str, body: str, times: list[float]) -> None:
        found = event(body)
        if len(found) != len(times) or any(abs(row[1] - hour) > 1e-4 for row, hour in zip(found, times)):
            errors.append(f"{label}: {[(r[1], r[2]) for r in found]}")
    exact("notice", "<TEACH-UNIT> mission ordered: BASIC-MISSION", [7])
    exact("created", f"{tag} mission created:", [7])
    exact("aircraft allocation", f"{tag} mission allocates system: {owner}", [7])
    exact("preparation start", f"{owner} preparation started, mission: {tag}", [7])
    exact("task start", f"system preparation task 0 on {owner} started", [7])
    exact("INSPECT request", first + " requests resources", [7])
    exact("INSPECT availability", first + " resource availability test", [7])
    p_test = f"Availability test on  {crew} request for: 1 OK"
    e_test = f"Availability test on  {device} request for: 1 {'OK' if success else 'failed'}"
    p_line = [i for i, line in enumerate(lines, 1) if p_test in line]
    e_line = [i for i, line in enumerate(lines, 1) if e_test in line]
    if len(p_line) != 1 or len(e_line) != 1 or sum("Availability test on" in line for line in lines) != 2:
        errors.append("joint resource test lines differ")
    if len(event(first + " requests resources")) == 1 and len(event(first + " resource availability test")) == 1 and len(p_line) == 1 and len(e_line) == 1:
        test_order = [event(first + " requests resources")[0][0],
                      event(first + " resource availability test")[0][0], p_line[0], e_line[0]]
        if any(a >= b for a, b in zip(test_order, test_order[1:])):
            errors.append(f"joint request/test order differs: {test_order}")
    duration = "0.166667" if serial else "0.5"
    end = 7 + 10 / 60 if serial else 7.5
    p_lease = crew + " allocated to maintenance task: 1  available now: 0"
    e_lease = device + " allocated to maintenance task: 1  available now: 0"
    p_release = crew + " deallocated from  maintenance task: 1  available now: 1"
    e_release = device + " deallocated from  maintenance task: 1  available now: 1"
    exact("booking", first + " books resources", [7] if success else [])
    for label, body, hour in (("crew acquisition", p_lease, 7), ("equipment acquisition", e_lease, 7),
                              ("crew release", p_release, end), ("equipment release", e_release, end)):
        exact(label, body, [hour] if success else [])
    exact("INSPECT work", first + f" starts performing, planned to last for {duration} hours", [7] if success else [])
    exact("INSPECT completion", first + " completed", [end] if success else [])
    exact("SERVICE start", second + " started", [end] if success and serial else [])
    exact("SERVICE unresourced", second + " requests resources: no resources needed",
          [end] if success and serial else [])
    exact("SERVICE work", second + " starts performing, planned to last for 0.333333 hours",
          [end] if success and serial else [])
    exact("SERVICE completion", second + " completed", [7.5] if success and serial else [])
    exact("preparation completion", f"system preparation task 0 on {owner} completed", [7.5] if success else [])
    exact("launch", f"{tag} mission starting, duration: 2 : {owner}", [8] if success else [])
    exact("mission success", f"{tag} mission success:", [10] if success else [])
    exact("mission completion", f"{tag} mission completed: {owner}", [10] if success else [])
    cancel = event(f"{tag} mission cancelled:")
    if success:
        if cancel:
            errors.append("successful variant cancelled")
        order = [first + " requests resources", first + " resource availability test",
                 first + " books resources", p_lease, e_lease,
                 first + f" starts performing, planned to last for {duration} hours",
                 first + " completed", first + " frees resources", p_release, e_release]
        if serial:
            order += [second + " started", second + " starts performing, planned to last for 0.333333 hours"]
        positions = [[row[0] for row in event(body)] for body in order]
        if (any(len(group) != 1 for group in positions)
                or any(left[0] >= right[0] for left, right in zip(positions, positions[1:]))):
            errors.append(f"joint lease/work/release order differs: {positions}")
        if len(e_line) == 1 and len(event(first + " books resources")) == 1 and e_line[0] >= event(first + " books resources")[0][0]:
            errors.append("equipment test followed booking")
        exact("preparation end", f"{owner} preparation ended, mission: {tag}", [7.5])
    else:
        if len(cancel) != 1 or cancel[0][1] < 7:
            errors.append("blocked mission cancellation differs")
        if (any(" allocated to maintenance task:" in row[2] or " deallocated from  maintenance task:" in row[2]
                or " books resources" in row[2] or " starts performing," in row[2] for row in events)
                or any(row[2].startswith(second) for row in events)):
            errors.append("blocked joint request had partial lease, work or SERVICE")
        stop = [event(first + " ordered to stop"), event(first + " resource waiting stopped"),
                event(f"system preparation task 0 on {owner} stopped"),
                event(f"{owner} preparation ended, mission: {tag}")]
        if len(cancel) == 1 and all(len(group) == 1 for group in stop):
            positions = [cancel[0][0]] + [group[0][0] for group in stop]
            if any(a >= b for a, b in zip(positions, positions[1:])):
                errors.append("blocked cancellation/stop order differs")
        else:
            errors.append("blocked stop lifecycle incomplete")
    for marker, count in {
        " starts performing,": (1 + int(serial)) if success else 0,
        " allocated to maintenance task:": 2 if success else 0,
        " deallocated from  maintenance task:": 2 if success else 0,
        " mission starting, duration:": 1 if success else 0,
        " mission cancelled:": 0 if success else 1,
    }.items():
        if sum(marker in row[2] for row in events) != count:
            errors.append(f"global event count differs for {marker}")
    data = tables(report, "report")
    summary = data.get("ResultSummary", [])
    if len(summary) != 1 or any(summary[0].get(k) != v for k, v in
            {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": int(success), "MSUF": int(success)}.items()):
        errors.append("native summary differs")
    system, resources = data.get("SystemResults", []), data.get("ResourceResults", [])
    if len(system) != 72 or len(resources) != 72:
        errors.append(f"result interval counts differ: {len(system)}, {len(resources)}")
    totals = Counter()
    for index, (row, res) in enumerate(zip(system, resources)):
        hour = index / 2
        expected = {"STINT": hour, "ETINT": hour + .5, "NSYA": 1,
                    "NPSTA": int(hour == 7), "NPSUC": int(success and hour == 7.5),
                    "FTMO": int(success and 8 <= hour < 10), "NSYMO": int(success and 8 <= hour < 10)}
        if any(row.get(k) != v for k, v in expected.items()):
            errors.append(f"SystemResults interval {index} differs")
        prep = 1 if hour == 7 else 1 / 6 if not success and hour == 7.5 else 0
        if abs(row.get("NSYMP", -1) - prep) > 1e-5:
            errors.append(f"SystemResults preparation interval {index} differs")
        busy = (2 if not serial else 2 / 3) if success and hour == 7 else 0
        wait = 1 if not success and hour == 7 else 1 / 6 if not success and hour == 7.5 else 0
        if (res.get("STINT") != hour or res.get("ETINT") != hour + .5
                or res.get("NR") != 1 + equipment
                or abs(res.get("NRUM", -1) - busy) > 1e-5 or abs(res.get("NRW", -1) - wait) > 1e-5):
            errors.append(f"ResourceResults interval {index} differs")
        totals["preparation_starts"] += row.get("NPSTA", 0)
        totals["preparation_successes"] += row.get("NPSUC", 0)
        totals["flight_hours"] += row.get("FTMO", 0) * .5
    return errors, {"cancellation_hour": cancel[0][1] if len(cancel) == 1 else None,
                    "joint_resource_minutes": (20 if serial else 60) if success else 0,
                    "system_intervals": len(system), "resource_intervals": len(resources),
                    "metric_totals": dict(totals)}


def run_audit(run: Path, variant: str) -> tuple[list[str], dict]:
    errors = []
    spec = read(HERE / "contract.json")["variants"][variant]
    for name in RAW | {"invocation.json", "closure.json", "run-manifest.json", "validation.json"}:
        if not (run / name).is_file() or (run / name).stat().st_size <= 4:
            return [f"missing/empty run file: {name}"], {}
    invocation, closure, manifest, validation = [read(run / name) for name in
        ("invocation.json", "closure.json", "run-manifest.json", "validation.json")]
    if (invocation.get("case_id") != "C02" or invocation.get("variant_id") != variant
            or invocation.get("run_id") != run.name or invocation.get("case_version") != "1.0.2"):
        errors.append("invocation case/variant identity differs")
    source_paths = {"contract_sha256": HERE / "contract.json", "builder_sha256": HERE / "build.py",
                    "validator_sha256": HERE / "validate.py", "runner_sha256": HERE / "run_native_ssh.ps1",
                    "launcher_sha256": HERE / "invoke_loopback.ps1",
                    "parent_diff_sha256": HERE / "parent-diffs" / f"{variant}.json"}
    for field, path in source_paths.items():
        if invocation.get(field) != sha(path):
            errors.append(f"invocation source fingerprint differs: {field}")
    if (invocation.get("parent_input_sha256") != sha(PARENT)
            or invocation.get("input_sha256") != spec["input_sha256"]
            or sha(run / "input.json") != spec["input_sha256"]):
        errors.append("parent or run input hash differs")
    if (invocation.get("execution_mode") != "ssh_cli_v1" or invocation.get("session_id") != 0
            or "sshd.exe" not in invocation.get("ssh_ancestor_names", [])
            or invocation.get("simlox_exe_sha256") != "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"):
        errors.append("native executable or SSH provenance differs")
    gui = invocation.get("coexisting_gui") or {}
    if (gui.get("pid") != 13340 or gui.get("session_id") != 1
            or gui.get("process_start_utc") != "2026-09-28T10:09:56.8261381Z"
            or gui.get("responding_at_preflight") is not True):
        errors.append("original GUI identity differs")
    if (closure.get("variant_id") != variant or closure.get("run_id") != run.name
            or closure.get("invocation_sha256") != sha(run / "invocation.json")
            or set(closure.get("raw", {})) != RAW):
        errors.append("raw closure identity/file set differs")
    for name, record in closure.get("raw", {}).items():
        path = run / name
        if not path.is_file() or path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
            errors.append(f"raw closure mismatch: {name}")
    if (manifest.get("invocation_sha256") != sha(run / "invocation.json")
            or manifest.get("closure_sha256") != sha(run / "closure.json")
            or manifest.get("validation_sha256") != sha(run / "validation.json")):
        errors.append("manifest chain differs")
    if not validation.get("passed") or validation.get("differences"):
        errors.append("source-bound validator did not pass")
    steps = read(run / "steps.json")
    if ([step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"]
            or any(step.get("exit_code") != 0 or not step.get("coexisting_gui_present_after") for step in steps)):
        errors.append("native step sequence, exit or GUI coexistence differs")
    before, after = tables(read(run / "input.json"), "model"), tables(read(run / "roundtrip-raw.json"), "model")
    for name, source in before.items():
        if source and source != after.get(name):
            errors.append(f"native roundtrip changed business rows: {name}")
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", conversion)
    if not match or match.group(1, 2) != ("0", "2") or Counter(re.findall(
            r"\(warning #(\d+)\)", conversion)) != Counter({"108": 1, "126": 1}):
        errors.append("conversion errors or warning allowlist differs")
    behavior_errors, observed = behavior_audit(
        (run / "model.log").read_text(encoding="utf-8-sig", errors="replace"),
        read(run / "report-raw.json"), variant)
    errors.extend(behavior_errors)
    hashes = {name: sha(run / name) for name in ("invocation.json", "closure.json", "run-manifest.json",
               "validation.json", "model.sxi", "model.sxo", "model.log", "report-raw.json")}
    nonempty = sum(any(any(value not in (None, "") for value in row.values()) for row in table)
                   for table in before.values())
    return errors, {"run_id": run.name, "roundtrip_business_tables": nonempty,
                    "raw_closure_count": len(closure.get("raw", {})), "observed": observed, "hashes": hashes}


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("usage: review_readonly.py SINGLE_BOTH SINGLE_ZERO SERIAL_BOTH SERIAL_ZERO")
    errors = source_audit()
    runs = {}
    for variant, path in zip(VARIANTS, sys.argv[1:], strict=True):
        differences, details = run_audit(Path(path), variant)
        errors.extend(f"{variant}: {message}" for message in differences)
        runs[variant] = details
    result = {"schema": "simlox-c02-independent-readonly-review/v1", "case_id": "C02",
              "version": "1.0.2", "passed": not errors, "differences": errors,
              "reviewer_sha256": sha(HERE / "review_readonly.py"), "runs": runs}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
