"""Read-only, source-bound native CLI acceptance for A09 nested v1.0.1."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
import validate_native as native  # noqa: E402

CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
OLD_CASE = HERE.parent / "A09-hierarchical-operation-profile"
PREDICTION = CONTRACT["v101_prediction_if_candidate_rule_holds"]
HAND = {"notification_hours": PREDICTION["notification_hours"],
        "start_hours": PREDICTION["launch_hours"],
        "end_hours": PREDICTION["completion_hours"]}
RAW_NAMES = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo",
             "import.log", "export.log", "run.log", "model.log",
             "report-raw.json", "report-export.log", "steps.json"}
AIRCRAFT = "<TEACH-AIR-01,0>"
UNIT = "TEACH-UNIT"
MISSION = "BASIC-MISSION"
TAG = re.compile(r"^(<BASIC-MISSION,TEACH-UNIT,[^>]+>) ")
CONVERSION = re.compile(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)")
WARNINGS = Counter({"108": 1, "126": 1})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite_number(value: object) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result if result.tzinfo and result.utcoffset() == timedelta(0) else None


def expected_arguments(run: PureWindowsPath) -> dict[str, str]:
    return {
        "import": f'-silent -jimport "{run / "input.json"}" -save "{run / "model.sxi"}" -log "{run / "import.log"}" -close',
        "export": f'"{run / "model.sxi"}" -silent -jexport "{run / "roundtrip-raw.json"}" -log "{run / "export.log"}" -close',
        "calc": f'"{run / "model.sxi"}" -silent -threads 1 -calc -log "{run / "run.log"}" -close',
        "jsonreport": f'"{run / "model.sxo"}" -silent -jsonreport "{run / "report-raw.json"}" -log "{run / "report-export.log"}" -close',
    }


def check_provenance(run_dir: Path, invocation: dict, closure: dict, steps: list[dict]) -> list[str]:
    errors: list[str] = []
    expected_sha = CONTRACT["candidate_input_sha256"]
    if (invocation.get("schema") != "simlox-a09-v101-invocation/ssh-cli-v1"
            or invocation.get("case_id") != "A09"
            or invocation.get("case_version") != CONTRACT["version"]
            or invocation.get("variant") != "nested-v101"
            or invocation.get("execution_mode") != "ssh_cli_v1"
            or invocation.get("input_sha256") != expected_sha
            or invocation.get("previous_input_sha256") != CONTRACT["previous_input_sha256"]
            or invocation.get("flat_control_sha256") != CONTRACT["flat_control_sha256"]):
        errors.append("invocation case/version/variant/source differs")
    source_files = {
        "contract_sha256": "contract.json", "native_validator_sha256": "validate_native_cli.py",
        "builder_sha256": "build.py", "runner_sha256": "run_native_ssh.ps1",
    }
    for key, name in source_files.items():
        if invocation.get(key) != sha256(HERE / name):
            errors.append(f"invocation {key} differs from current source")
    parser = HERE.parent / "tools" / "validate_native.py"
    if invocation.get("shared_parser_sha256") != sha256(parser):
        errors.append("invocation shared parser hash differs")
    binding = HERE.parent / "tools" / "native_binding.py"
    if invocation.get("shared_binding_sha256") != sha256(binding):
        errors.append("invocation shared binding import hash differs")
    if (invocation.get("parent_input_sha256") != CONTRACT["parent_input_sha256"]
            or sha256(HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json") != CONTRACT["parent_input_sha256"]):
        errors.append("frozen A02 parent source differs")
    if (sha256(OLD_CASE / "native-nested.json") != CONTRACT["previous_input_sha256"]
            or sha256(OLD_CASE / "native-flat.json") != CONTRACT["flat_control_sha256"]):
        errors.append("v1.0.0 nested/flat source differs")
    exe_sha = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
    if invocation.get("simlox_exe_sha256") != exe_sha:
        errors.append("native executable identity differs")
    python_sha = "2204195cec25879507d958a8b6949add67091244b8b4da9cf3672f993548fa49"
    if invocation.get("python_exe_sha256") != python_sha:
        errors.append("Python validator executable identity differs")
    if (invocation.get("python_path") != r"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe"
            or invocation.get("working_directory") != r"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace"):
        errors.append("known native working/Python path differs")
    if (invocation.get("session_id") != 0 or invocation.get("session_name") not in (None, "")
            or invocation.get("ssh_connection_present") is not True
            or "sshd.exe" not in [str(name).lower() for name in invocation.get("ssh_ancestor_names", [])]
            or utc(invocation.get("created_utc")) is None
            or not isinstance(invocation.get("host_name"), str)
            or not re.fullmatch(r"[A-Za-z0-9._-]+", invocation["host_name"])):
        errors.append("SSH session provenance differs")
    if invocation.get("queue_mutex") != r"Global\SimloxIssue18NativeQueue":
        errors.append("host-wide native queue mutex differs")
    gui = invocation.get("coexisting_gui")
    allow = invocation.get("allow_existing_gui")
    if type(allow) is not bool or allow != (gui is not None):
        errors.append("GUI coexistence flag differs")
    if gui is not None:
        if (not isinstance(gui, dict) or type(gui.get("pid")) is not int or gui["pid"] <= 0
                or type(gui.get("session_id")) is not int or gui["session_id"] <= 0
                or utc(gui.get("process_start_utc")) is None
                or not isinstance(gui.get("session_query_line"), str)
                or not re.match(rf"^\s*>?\s*(Console|RDP-Tcp#\d+)\s+\S+\s+{gui['session_id']}\s+(?:Active|运行中)(?:\s|$)", gui["session_query_line"], re.I)):
            errors.append("active existing GUI PID/session evidence differs")
    original = invocation.get("original_run_dir")
    if not isinstance(original, str):
        errors.append("original Windows path absent")
        return errors
    win_path = PureWindowsPath(original)
    if (not win_path.is_absolute() or win_path.name != run_dir.name
            or invocation.get("run_id") != run_dir.name
            or re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", run_dir.name) is None):
        errors.append("original Windows run path differs")
        return errors
    planned = expected_arguments(win_path)
    if not isinstance(steps, list) or [step.get("name") for step in steps] != list(planned):
        errors.append("native step order differs")
    else:
        prior = utc(invocation.get("created_utc"))
        for step in steps:
            start, end = utc(step.get("started_utc")), utc(step.get("completed_utc"))
            seconds = step.get("wall_seconds")
            if (step.get("arguments") != planned[step["name"]] or type(step.get("exit_code")) is not int
                    or step["exit_code"] != 0 or step.get("launch_error") is not None
                    or step.get("gui_state_check_passed") is not True
                    or step.get("gui_state_check_error") is not None
                    or not finite_number(seconds) or seconds < 0
                    or start is None or end is None or start > end or (prior is not None and start < prior)):
                errors.append(f"native {step['name']} arguments/exit/timing differ")
            if gui is not None and step.get("coexisting_gui_present_after") is not True:
                errors.append(f"native {step['name']} did not preserve GUI")
            prior = end
    if (closure.get("schema") != "simlox-a09-v101-closure/v1" or closure.get("case_id") != "A09"
            or closure.get("case_version") != CONTRACT["version"] or closure.get("variant") != "nested-v101"
            or closure.get("run_id") != run_dir.name or closure.get("input_sha256") != expected_sha
            or closure.get("invocation_sha256") != sha256(run_dir / "invocation.json")
            or set(closure.get("raw", {})) != RAW_NAMES):
        errors.append("raw closure identity/file set differs")
    for name, record in closure.get("raw", {}).items():
        path = run_dir / name
        if not path.is_file() or path.stat().st_size <= 4 or path.stat().st_size != record.get("bytes") or sha256(path) != record.get("sha256"):
            errors.append(f"raw closure mismatch: {name}")
    return errors


def check_events(events: list[dict]) -> tuple[list[str], list[str]]:
    hand = HAND
    times = {"notification": hand["notification_hours"], "created": hand["notification_hours"],
             "activated": hand["notification_hours"], "allocation": hand["notification_hours"],
             "preparation_start": hand["notification_hours"], "preparation_end": hand["notification_hours"],
             "start": hand["start_hours"], "task_start": [x + .5 for x in hand["start_hours"]],
             "task_completion": [x - .5 for x in hand["end_hours"]],
             "success": hand["end_hours"], "completion": hand["end_hours"]}
    by_kind = {kind: [e for e in events if e["kind"] == kind] for kind in native.KINDS}
    errors: list[str] = []
    for event in events:
        try:
            time = float(event["time_hours_printed"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return [f"event line {event.get('line')} has invalid time"], []
        if not math.isfinite(time):
            return [f"event line {event.get('line')} has non-finite time"], []
    if not events or any(float(b["time_hours_printed"]) < float(a["time_hours_printed"])
                         for a, b in zip(events, events[1:])):
        errors.append("event log absent or out of time order")
    for kind, wanted in times.items():
        actual = [float(e["time_hours_printed"]) for e in by_kind[kind]]
        if len(actual) != len(wanted) or any(abs(a - b) > 1e-4 for a, b in zip(actual, wanted)):
            errors.append(f"{kind} wave times/count differ: {actual}")
    if [e["body"] for e in by_kind["notification"]] != [f"<{UNIT}> mission ordered: {MISSION}"] * 4:
        errors.append("mission notification identity differs")
    tags = []
    for index, event in enumerate(by_kind["created"][:4]):
        match = TAG.match(event["body"])
        if not match or event["body"] != f"{match[1]} mission created:":
            errors.append(f"created mission identity differs at wave {index}")
        else:
            tags.append(match[1])
    if len(tags) != 4 or len(set(tags)) != 4:
        errors.append("four distinct native mission instance tags required")
    for index, tag in enumerate(tags):
        exact = {
            "activated": f"{tag} mission activated, systems requested: 1",
            "allocation": f"{tag} mission allocates system: {AIRCRAFT}",
            "task_start": f"{tag} task starting: {AIRCRAFT}",
            "task_completion": f"{tag} task completed: {AIRCRAFT}",
            "success": f"{tag} mission success:",
            "completion": f"{tag} mission completed: {AIRCRAFT}",
            "preparation_start": f"{AIRCRAFT} preparation started, mission: {tag}",
            "preparation_end": f"{AIRCRAFT} preparation ended, mission: {tag}",
        }
        for kind, expected in exact.items():
            if len(by_kind[kind]) <= index or by_kind[kind][index]["body"] != expected:
                errors.append(f"{kind} identity differs at wave {index}")
        if len(by_kind["start"]) <= index or not re.fullmatch(
                rf"{re.escape(tag)} mission starting, duration: 2(?:\.0)? : {re.escape(AIRCRAFT)}",
                by_kind["start"][index]["body"]):
            errors.append(f"start identity/duration differs at wave {index}")
        order = ("notification", "created", "activated", "allocation", "start", "success", "completion")
        if all(len(by_kind[kind]) > index for kind in order):
            lines = [by_kind[kind][index]["line"] for kind in order]
            if lines != sorted(lines):
                errors.append(f"mission lifecycle order differs at wave {index}")
    for kind in ("cancel", "abort", "fault", "pm", "repair"):
        if by_kind[kind]:
            errors.append(f"unexpected {kind} event count {len(by_kind[kind])}")
    ready_body = f"{AIRCRAFT} nbr ready {{}} at unit: <{UNIT} at <BASE-01,0>>"
    for kind, wanted in (("ready_decreased", hand["notification_hours"]),
                         ("ready_increased", [0, *hand["end_hours"]])):
        actual = [float(e["time_hours_printed"]) for e in by_kind[kind]]
        if actual != wanted or any(e["body"] != ready_body.format("decreased" if kind == "ready_decreased" else "increased") for e in by_kind[kind]):
            errors.append(f"aircraft {kind} time/identity differs")
    # The accepted flat control emits two System ready lines and one soon-ready
    # line at each completion, plus a unit-level ready line at time zero and
    # after every completion. Check the complete trace, not just mission lines.
    base_system = "<TEACH-AIR-01,BASE-01,0>"
    readiness = {
        "ready": ([hour for hour in hand["end_hours"] for _ in range(2)],
                  f"{base_system} System ready {AIRCRAFT}"),
        "systems_ready": ([0, *hand["end_hours"]],
                          f"<{UNIT} at <BASE-01,0>> systems ready: 1 :{AIRCRAFT}"),
        "soon_ready": (hand["end_hours"],
                       f"{base_system} System soon ready {AIRCRAFT}, estimated remaining time: 0"),
    }
    for kind, (wanted, body) in readiness.items():
        actual = [float(e["time_hours_printed"]) for e in by_kind[kind]]
        if (len(actual) != len(wanted)
                or any(abs(a - b) > 1e-4 for a, b in zip(actual, wanted))
                or any(e["body"] != body for e in by_kind[kind])):
            errors.append(f"{kind} time/count/identity differs: {actual}")
    return errors, tags


def check_report(report: dict) -> list[str]:
    hand = HAND
    errors: list[str] = []
    summary = native.table_rows(report, "ResultSummary")
    if len(summary) != 1:
        return ["ResultSummary must have one row"]
    row = summary[0]
    # All ResultSummary columns below are pinned to the passed native flat
    # control report, not inferred from an undocumented SIMLOX rule.
    for field, value in {"NREP": 1, "RTILW": 0, "RTIUP": 48,
                         "MTMF": 1, "RSMTMF": 0, "MSTF": 1, "RSMSTF": 0,
                         "MSUF": 1, "RSMSUF": 0, "STMF": 1, "RSSTMF": 0}.items():
        if not finite_number(row.get(field)) or abs(row[field] - value) > 1e-8:
            errors.append(f"ResultSummary.{field} differs")
    system = native.table_rows(report, "SystemResults")
    if len(system) != 96:
        errors.append(f"SystemResults expected 96 intervals, observed {len(system)}")
    integrals = {field: 0.0 for field in ("FTMO", "NSYMO", "STACC", "NSYMA", "NSYMR", "NSYRY")}
    flights = list(zip(hand["start_hours"], hand["end_hours"]))
    allocations = list(zip(hand["notification_hours"], hand["end_hours"]))
    reservations = list(zip(hand["notification_hours"], hand["start_hours"]))
    for index, row in enumerate(system):
        try:
            start, end = float(row["STINT"]), float(row["ETINT"])
        except (KeyError, TypeError, ValueError, OverflowError):
            errors.append(f"SystemResults interval {index} lacks valid bounds")
            continue
        if not math.isfinite(start) or not math.isfinite(end):
            errors.append(f"SystemResults interval {index} non-finite bounds")
            continue
        if abs(start - index * .5) > 1e-8 or abs(end - (index + 1) * .5) > 1e-8:
            errors.append(f"SystemResults interval {index} grid differs")
            continue
        def fraction(windows: list[tuple[float, float]]) -> float:
            return sum(max(0.0, min(end, right) - max(start, left)) for left, right in windows) / (end - start)
        flying, allocated, reserved = fraction(flights), fraction(allocations), fraction(reservations)
        profile = {"FTMO": flying, "NSYMO": flying, "STACC": flying, "NSYMA": allocated,
                   "NSYMR": reserved, "NSYRY": 1 - allocated}
        system_count = row.get("NSYA")
        if (row.get("UNID") != "Total over all Units" or row.get("SID") != "Total over all Systems"
                or not finite_number(system_count) or system_count != 1):
            errors.append(f"SystemResults interval {index} scope/system count differs")
        for field, expected in profile.items():
            value = row.get(field)
            if not finite_number(value) or abs(value - expected) > 1e-8:
                errors.append(f"SystemResults interval {index} {field} differs")
            else:
                integrals[field] += value * .5
        for field in native.ZERO_SYSTEM_FIELDS:
            value = row.get(field)
            if not finite_number(value) or value != 0:
                errors.append(f"SystemResults interval {index} unexpected {field}")
        if row.get("SYDT", "missing") is not None:
            errors.append(f"SystemResults interval {index} SYDT differs")
    for field, expected in {"FTMO": 8, "NSYMO": 8, "STACC": 8,
                            "NSYMA": 12, "NSYMR": 4, "NSYRY": 36}.items():
        if abs(integrals[field] - expected) > 1e-8:
            errors.append(f"SystemResults {field} integral differs")
    return errors


def check_description(*documents: dict) -> list[str]:
    expected = [["A09 two-day, two-wave schedule comparison; no J35/F35 equivalence"]]
    errors = []
    for label, document, envelope in zip(("source", "roundtrip", "report"), documents, ("model", "model", "report")):
        try:
            tables = [t for t in document[envelope]["tables"] if t["name"] == "ProblemDescription"]
            if len(tables) != 1 or [c["name"] for c in tables[0]["columns"]] != ["PDESC"] or len(tables[0]["instances"]) != 1 or tables[0]["instances"][0]["rows"] != expected:
                errors.append(f"{label} ProblemDescription.PDESC differs")
        except (KeyError, TypeError):
            errors.append(f"{label} ProblemDescription.PDESC malformed")
    return errors


def validate(run_dir: Path) -> dict:
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", run_dir.name) is None:
        raise ValueError("run directory identity differs")
    expected_sha = CONTRACT["candidate_input_sha256"]
    for name in RAW_NAMES | {"invocation.json", "closure.json"}:
        path = run_dir / name
        if not path.is_file() or path.stat().st_size <= 4:
            raise ValueError(f"missing or empty native artifact: {name}")
    if sha256(HERE / "native-nested.json") != expected_sha or sha256(run_dir / "input.json") != expected_sha:
        raise ValueError("native run input differs from checked A09 candidate")
    invocation = json.loads((run_dir / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run_dir / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run_dir / "steps.json").read_text(encoding="utf-8-sig"))
    errors = check_provenance(run_dir, invocation, closure, steps)
    roundtrip = native.compare_roundtrip(run_dir / "input.json", run_dir / "roundtrip-raw.json")
    if not roundtrip["all_equal"]:
        errors.append(f"native roundtrip changed business rows: {list(roundtrip['changed'])}")
    log = (run_dir / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = CONVERSION.search(log)
    warnings = Counter(re.findall(r"\(warning #(\d+)\)", log))
    if conversion is None or int(conversion[1]) != 0 or int(conversion[2]) != 2 or int(conversion[3]) != 0 or warnings != WARNINGS:
        errors.append(f"native conversion errors/warnings differ: {conversion.groups() if conversion else None}, {dict(warnings)}")
    source = json.loads(native.remove_trailing_commas((run_dir / "input.json").read_bytes()))
    exported = json.loads(native.remove_trailing_commas((run_dir / "roundtrip-raw.json").read_bytes()))
    report = json.loads(native.remove_trailing_commas((run_dir / "report-raw.json").read_bytes()))
    errors.extend(check_description(source, exported, report))
    events = native.parse_log(run_dir / "model.log")
    event_errors, tags = check_events(events)
    errors.extend(event_errors)
    errors.extend(check_report(report))
    return {"schema": "simlox-a09-v101-native-cli-validation/v1", "case_id": "A09",
            "case_version": CONTRACT["version"], "variant": "nested-v101",
            "passed": not errors, "differences": errors,
            "input_sha256": expected_sha, "native_mission_tags_by_wave": tags,
            "roundtrip": roundtrip, "scope": "isolated_contract_cli_candidate",
            "gui_status": "not_run", "publication_state": "not_published"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    result = validate(args.run_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
