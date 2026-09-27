"""Pure-Python SIMLOX artifact validator for the A01/A02 teaching contracts.

The validator reads raw files without modifying them. SIMLOX 2017 JSON report
trailing commas are removed by a string-aware scanner into a separate file.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from native_binding import verify as verify_binding

ROOT = Path(__file__).resolve().parents[1]
CASE_DIRS = {"A01": ROOT / "A01-single-aircraft-single-mission",
             "A02": ROOT / "A02-single-aircraft-repeated-missions"}
TIME = re.compile(r"^Time: ([0-9.e+\-]+) (.*)$")
KINDS = {
    "notification": " mission ordered:",
    "created": " mission created:",
    "activated": " mission activated, systems requested:",
    "allocation": " mission allocates system:",
    "start": " mission starting, duration:",
    "task_start": " task starting:",
    "task_completion": " task completed:",
    "success": " mission success:",
    "completion": " mission completed:",
    "cancel": " mission cancelled:",
    "abort": " mission aborted:",
    "ready": " System ready <",
    "ready_decreased": " nbr ready decreased at unit:",
    "ready_increased": " nbr ready increased at unit:",
    "systems_ready": " systems ready:",
    "soon_ready": " System soon ready <",
    "fault": " critical random failure added",
    "pm": " PM task ",
    "repair": " repair task ",
    "preparation_start": " preparation started,",
    "preparation_end": " preparation ended,",
}
ZERO_SYSTEM_FIELDS = (
    "NSYMC", "NSYMP", "NSYMT", "NSYMS", "NSYUA", "NSYAL", "NSYRP", "NSYPM",
    "NSYTP", "NSYWR", "NSYWI", "NSYLA", "NSYUH", "NREPT", "NPMT", "NFAIL",
    "NDAM", "NPMS", "NROBT", "NRCFG", "STREQ", "STF", "STLOW",
    "SYDTU", "NSYDT", "NSYSW", "NPSTA", "NPSUC",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_numbers(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: normalize_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_numbers(item) for item in value]
    return value


def business_rows(path: Path) -> dict[str, Counter]:
    model = json.loads(path.read_text(encoding="utf-8-sig"))["model"]
    result = {}
    for table in model["tables"]:
        columns = [column["name"] for column in table["columns"]]
        records = []
        for instance in table["instances"]:
            for raw in instance["rows"]:
                if len(raw) != len(columns):
                    raise ValueError(f"{table['name']} column/row length mismatch")
                if any(value not in (None, "") for value in raw):
                    records.append(json.dumps(normalize_numbers(dict(zip(columns, raw))), ensure_ascii=False, sort_keys=True))
        result[table["name"]] = Counter(records)
    return result


def compare_roundtrip(original: Path, exported: Path) -> dict:
    a, b = business_rows(original), business_rows(exported)
    changed = {}
    for table in sorted(a.keys() | b.keys()):
        if a.get(table, Counter()) != b.get(table, Counter()):
            changed[table] = {"input_only": list((a.get(table, Counter()) - b.get(table, Counter())).elements())[:3],
                              "export_only": list((b.get(table, Counter()) - a.get(table, Counter())).elements())[:3]}
    return {"all_equal": not changed, "changed": changed,
            "nonempty_business_tables": sum(bool(rows) for rows in a.values())}


def remove_trailing_commas(raw: bytes) -> bytes:
    text = raw.decode("utf-8-sig")
    out = []
    quoted = False
    escaped = False
    for index, char in enumerate(text):
        if quoted:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
            out.append(char)
        elif char == ",":
            following = index + 1
            while following < len(text) and text[following].isspace():
                following += 1
            if following < len(text) and text[following] in "]}":
                continue
            out.append(char)
        else:
            out.append(char)
    return "".join(out).encode("utf-8")


def table_rows(document: dict, name: str) -> list[dict]:
    tables = [table for table in document["report"]["tables"] if table["name"] == name]
    if len(tables) != 1:
        raise ValueError(f"report missing or duplicate {name}")
    table = tables[0]
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def parse_log(path: Path) -> list[dict]:
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        match = TIME.match(line)
        if not match:
            continue
        for kind, needle in KINDS.items():
            if needle in match.group(2):
                events.append({"line": line_number, "kind": kind,
                               "time_hours_printed": match.group(1), "body": match.group(2).strip(), "text": line})
                break
    return events


def expected_behavior(events: list[dict], contract: dict, report: dict) -> dict:
    hand = contract["hand_expected"]
    by_kind = {kind: [event for event in events if event["kind"] == kind] for kind in KINDS}
    task_start = [start + contract["mission"]["duration_hours"] * .25 for start in hand["actual_start_hours"]]
    task_end = [end - contract["mission"]["duration_hours"] * .25 for end in hand["actual_end_hours"]]
    exact = {"notification": hand["notification_hours"], "created": hand["notification_hours"],
             "activated": hand["notification_hours"], "allocation": hand["notification_hours"],
             "start": hand["actual_start_hours"], "task_start": task_start,
             "task_completion": task_end, "success": hand["actual_end_hours"],
             "completion": hand["actual_end_hours"]}
    differences = []
    if not events or any(float(later["time_hours_printed"]) < float(earlier["time_hours_printed"])
                         for earlier, later in zip(events, events[1:])):
        differences.append({"field": "event_log_order_or_missing"})
    for kind, times in exact.items():
        actual = [float(event["time_hours_printed"]) for event in by_kind[kind]]
        if len(actual) != len(times) or any(abs(a - b) > 0.0001 for a, b in zip(actual, times)):
            differences.append({"field": kind, "expected_hours": times, "actual_hours_printed": actual})
    for kind in ("cancel", "abort", "fault", "pm", "repair"):
        if by_kind[kind]:
            differences.append({"field": kind, "expected_count": 0, "actual_count": len(by_kind[kind])})
    prep_starts = [float(event["time_hours_printed"]) for event in by_kind["preparation_start"]]
    prep_ends = [float(event["time_hours_printed"]) for event in by_kind["preparation_end"]]
    if (len(prep_starts) != hand["planned_waves"] or prep_starts != prep_ends
            or prep_starts != hand["notification_hours"]):
        differences.append({"field": "zero_duration_native_preparation_lifecycle",
                            "start_hours": prep_starts, "end_hours": prep_ends})
    summary_rows = table_rows(report, "ResultSummary")
    if len(summary_rows) != 1:
        raise ValueError("expected one ResultSummary row")
    summary = summary_rows[0]
    if (summary["NREP"] != 1 or summary["RTILW"] != 0
            or abs(summary["RTIUP"] - contract["observation"]["end_hours"]) > 1e-9):
        differences.append({"field": "result_window", "actual": {key: summary[key] for key in ("NREP", "RTILW", "RTIUP")}})
    started = len(by_kind["start"])
    completed = len(by_kind["completion"])
    sid = contract["aircraft"][0]["native_sid"]
    mission_id = contract["mission"]["business_id"]
    unit = contract["aircraft"][0].get("unit", "TEACH-UNIT")
    base = contract["aircraft"][0]["base"]
    aircraft = f"<{sid},0>"
    for index in range(hand["planned_waves"]):
        tag = f"<{mission_id},{unit},0,0,{index}>"
        expected_body = {
            "notification": f"<{unit}> mission ordered: {mission_id}",
            "created": f"{tag} mission created:",
            "activated": f"{tag} mission activated, systems requested: 1",
            "allocation": f"{tag} mission allocates system: {aircraft}",
            "task_start": f"{tag} task starting: {aircraft}",
            "task_completion": f"{tag} task completed: {aircraft}",
            "success": f"{tag} mission success:",
            "completion": f"{tag} mission completed: {aircraft}",
        }
        for kind, body in expected_body.items():
            if len(by_kind[kind]) <= index or by_kind[kind][index]["body"] != body:
                differences.append({"field": f"{kind}_identity", "wave": index,
                                    "expected": body, "actual": by_kind[kind][index]["body"] if len(by_kind[kind]) > index else None})
        if len(by_kind["start"]) <= index or not re.fullmatch(
                rf"{re.escape(tag)} mission starting, duration: {contract['mission']['duration_hours']}(?:\.0)? : {re.escape(aircraft)}",
                by_kind["start"][index]["body"]):
            differences.append({"field": "start_identity", "wave": index,
                                "actual": by_kind["start"][index]["body"] if len(by_kind["start"]) > index else None})
        ordered = ("notification", "created", "activated", "allocation", "start", "success", "completion")
        if all(len(by_kind[kind]) > index for kind in ordered):
            lines = [by_kind[kind][index]["line"] for kind in ordered]
            if lines != sorted(lines):
                differences.append({"field": "mission_lifecycle_order", "wave": index, "lines": lines})
    decreased = [float(event["time_hours_printed"]) for event in by_kind["ready_decreased"]]
    increased = [float(event["time_hours_printed"]) for event in by_kind["ready_increased"]]
    for kind in ("ready_decreased", "ready_increased"):
        body = f"{aircraft} nbr ready {'decreased' if kind == 'ready_decreased' else 'increased'} at unit: <{unit} at <{base},0>>"
        if any(event["body"] != body for event in by_kind[kind]):
            differences.append({"field": "aircraft_ready_identity", "kind": kind, "expected": body})
    expected_systems_ready = f"<{unit} at <{base},0>> systems ready: 1 :{aircraft}"
    if (len(by_kind["systems_ready"]) != 1 + hand["planned_waves"] or
            any(event["body"] != expected_systems_ready for event in by_kind["systems_ready"])):
        differences.append({"field": "systems_ready_identity", "expected": expected_systems_ready})
    expected_ready = f"<{sid},{base},0> System ready {aircraft}"
    if (len(by_kind["ready"]) != 2 * hand["planned_waves"] or
            any(event["body"] != expected_ready for event in by_kind["ready"])):
        differences.append({"field": "system_ready_identity", "expected": expected_ready})
    expected_soon_ready = f"<{sid},{base},0> System soon ready {aircraft}, estimated remaining time: 0"
    if any(event["body"] != expected_soon_ready for event in by_kind["soon_ready"]):
        differences.append({"field": "system_soon_ready_identity", "expected": expected_soon_ready})
    for kind in ("preparation_start", "preparation_end"):
        expected_prep = [f"{aircraft} preparation {'started' if kind == 'preparation_start' else 'ended'}, mission: <{mission_id},{unit},0,0,{i}>"
                         for i in range(hand["planned_waves"])]
        if [event["body"] for event in by_kind[kind]] != expected_prep:
            differences.append({"field": f"{kind}_identity", "expected": expected_prep})
    if decreased != hand["notification_hours"] or increased != [0] + hand["ready_after_hours"]:
        differences.append({"field": "aircraft_ready_state", "decreased_hours": decreased, "increased_hours": increased})
    flight_hours_from_mission_intervals = sum(float(end["time_hours_printed"]) - float(start["time_hours_printed"])
                                              for start, end in zip(by_kind["start"], by_kind["completion"]))
    if abs(flight_hours_from_mission_intervals - hand["flight_hours_integral"]) > 0.0001:
        differences.append({"field": "flight_hours_from_mission_intervals", "actual": flight_hours_from_mission_intervals})
    system = table_rows(report, "SystemResults")
    interval = contract["observation"]["interval_minutes"] / 60
    horizon = contract["observation"]["end_hours"]
    if len(system) != round(horizon / interval):
        differences.append({"field": "system_result_intervals", "actual_count": len(system)})
    integrals = {field: 0.0 for field in ("FTMO", "NSYMO", "NSYMA", "NSYMR", "NSYRY")}
    for index, row in enumerate(system):
        start, end = float(row["STINT"]), float(row["ETINT"])
        if abs(start - index * interval) > 1e-8 or abs(end - (index + 1) * interval) > 1e-8:
            differences.append({"field": "system_interval", "index": index, "start": start, "end": end})
            break
        if row.get("UNID") != "Total over all Units" or row.get("SID") != "Total over all Systems":
            differences.append({"field": "system_report_scope", "index": index})
        span = end - start
        def fraction(windows):
            return sum(max(0.0, min(end, right) - max(start, left)) for left, right in windows) / span
        mission_windows = list(zip(hand["actual_start_hours"], hand["actual_end_hours"]))
        allocated_windows = list(zip(hand["notification_hours"], hand["actual_end_hours"]))
        reserved_windows = list(zip(hand["notification_hours"], hand["actual_start_hours"]))
        allocated, flying, reserved = fraction(allocated_windows), fraction(mission_windows), fraction(reserved_windows)
        expected_profile = {"FTMO": flying, "NSYMO": flying, "NSYMA": allocated,
                            "NSYMR": reserved, "NSYRY": 1 - allocated}
        for field, expected_value in expected_profile.items():
            if field not in row or abs(float(row[field]) - expected_value) > 1e-8:
                differences.append({"field": "system_interval_profile", "index": index,
                                    "metric": field, "expected": expected_value, "actual": row.get(field)})
            if field in row:
                integrals[field] += float(row[field]) * span
        if row.get("NSYA") != 1:
            differences.append({"field": "system_count_interval", "index": index, "metric": "NSYA", "actual": row.get("NSYA")})
        for field in ZERO_SYSTEM_FIELDS:
            if field not in row or row[field] != 0:
                differences.append({"field": "unintended_mechanism_interval", "index": index,
                                    "metric": field, "expected": 0, "actual": row.get(field)})
        if row.get("SYDT", "missing") is not None:
            differences.append({"field": "system_interval_not_applicable", "index": index,
                                "metric": "SYDT", "expected": None, "actual": row.get("SYDT", "missing")})
    flight_hours_from_system_results = integrals["FTMO"]
    ready_hours_from_system_results = integrals["NSYRY"]
    expected_integrals = {"FTMO": hand["flight_hours_integral"], "NSYMO": hand["flight_hours_integral"],
                          "NSYMA": hand["planned_waves"] * 3, "NSYMR": hand["planned_waves"],
                          "NSYRY": hand["ready_hours_integral"]}
    for field, expected_value in expected_integrals.items():
        if abs(integrals[field] - expected_value) > 1e-8:
            differences.append({"field": "system_integral", "metric": field,
                                "expected": expected_value, "actual": integrals[field]})
    native_preparations_started = sum(int(row["NPSTA"]) for row in system)
    if native_preparations_started != 0:
        differences.append({"field": "unintended_native_preparation_count", "expected": 0,
                            "actual": native_preparations_started})
    for field in ("MSTF", "MSUF"):
        if abs(float(summary[field]) - 1) > 1e-8:
            differences.append({"field": field, "expected": 1, "actual": summary[field]})
    return {"passed": not differences, "differences": differences,
            "planned_waves": hand["planned_waves"], "launched_waves": started,
            "sorties": started, "completed_waves": completed,
            "cancelled_waves": len(by_kind["cancel"]),
            "unfinished_at_horizon": started - completed - len(by_kind["abort"]),
            "flight_hours_from_mission_intervals": flight_hours_from_mission_intervals,
            "flight_hours_from_system_results": flight_hours_from_system_results,
            "ready_hours_from_system_results": ready_hours_from_system_results,
            "system_interval_integrals_aircraft_hours": integrals,
            "native_zero_duration_preparation_count": native_preparations_started,
            "result_summary": {key: summary[key] for key in ("NREP", "RTILW", "RTIUP", "MSTF", "MSUF") if key in summary}}


def validate(run_dir: Path, case_id: str, *, write: bool = True, require_binding: bool = True) -> dict:
    if not require_binding and write:
        raise ValueError("legacy unsealed analysis is read-only and cannot be accepted")
    binding = verify_binding(run_dir, case_id) if require_binding else None
    case_dir = CASE_DIRS[case_id]
    contract = json.loads((case_dir / "contract.json").read_text(encoding="utf-8"))
    required = {name: run_dir / name for name in ("input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "report-raw.json", "run.log", "model.log", "steps.json")}
    for name, path in required.items():
        if not path.is_file() or path.stat().st_size <= 4:
            raise ValueError(f"missing/invalid native artifact: {name}")
    checked_input = case_dir / "native-input.json"
    if sha256(required["input.json"]) != sha256(checked_input):
        raise ValueError("native run input differs from checked case input")
    if not write and (run_dir / "validation.json").is_file() and require_binding:
        frozen = json.loads((run_dir / "validation.json").read_text(encoding="utf-8-sig"))
        for name, record in frozen.get("artifacts", {}).items():
            if name in required and sha256(required[name]) != record["sha256"]:
                raise ValueError(f"native run artifact changed since acceptance: {name}")
    steps = json.loads(required["steps.json"].read_text(encoding="utf-8-sig"))
    if [step["name"] for step in steps] != ["import", "export", "calc", "jsonreport"] or any(step["exit_code"] != 0 for step in steps):
        raise ValueError("incomplete/failed native command sequence")
    roundtrip = compare_roundtrip(required["input.json"], required["roundtrip-raw.json"])
    run_log = required["run.log"].read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    if not conversion:
        raise ValueError("missing conversion summary")
    errors, warning_count, notes = map(int, conversion.groups())
    warnings = re.findall(r"\(warning #(\d+)\) ([^\r\n]+)", run_log)
    if len(warnings) != warning_count:
        raise ValueError("warning count/details mismatch")
    explained = {
        "108": "ENLOG=Y intentionally records the first native repetition; measurement runs must disable it",
        "126": "the teaching system intentionally contains no items; absence of fault-bearing child rows is the case contract",
    }
    unknown_warnings = sorted({number for number, _ in warnings} - explained.keys())
    if errors or unknown_warnings or not roundtrip["all_equal"]:
        raise ValueError(f"native conversion/roundtrip invalid: errors={errors}, unknown_warnings={unknown_warnings}, changed={list(roundtrip['changed'])}")
    normalized = remove_trailing_commas(required["report-raw.json"].read_bytes())
    report = json.loads(normalized.decode("utf-8"))
    normalized_path = run_dir / "report-normalized.json"
    if write:
        if normalized_path.exists():
            raise FileExistsError(normalized_path)
        normalized_path.write_bytes(normalized)
    events = parse_log(required["model.log"])
    behavior = expected_behavior(events, contract, report)
    result = {
        "case_id": case_id, "behavior": behavior, "roundtrip": roundtrip,
        "conversion": {"errors": errors, "warnings": warning_count, "notes": notes,
                       "warning_details": [{"number": number, "text": message, "explanation": explained[number]} for number, message in warnings]},
        "artifacts": {name: {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)} for name, path in required.items()},
        "normalized_report": {"path": str(normalized_path), "bytes": len(normalized),
                              "sha256": hashlib.sha256(normalized).hexdigest()},
        "event_index": events,
        "binding": binding,
        "status": ("cli_behavior_verified" if behavior["passed"] else "cli_behavior_mismatch") if require_binding
                  else "legacy_unsealed_reanalysis",
        "gui_status": "pending",
    }
    if write:
        target = run_dir / "validation.json"
        if target.exists():
            raise FileExistsError(target)
        target.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--case", choices=sorted(CASE_DIRS), required=True)
    parser.add_argument("--read-only", action="store_true", help="recheck an immutable prior run without writing artifacts")
    parser.add_argument("--legacy-read-only", action="store_true", help="analyze old unsealed runs without acceptance attribution")
    args = parser.parse_args()
    result = validate(args.run_dir, args.case, write=not (args.read_only or args.legacy_read_only),
                      require_binding=not args.legacy_read_only)
    print(json.dumps({"status": result["status"], "behavior": result["behavior"],
                      "raw_report_sha256": result["artifacts"]["report-raw.json"]["sha256"],
                      "normalized_report_sha256": result["normalized_report"]["sha256"]}))
    if result["status"] != "cli_behavior_verified" and not args.legacy_read_only:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
