"""Validate sealed SIMLOX preparation/resource runs against their contracts.

Raw native files are never rewritten.  SIMLOX report JSON is normalized into a
separate file, and acceptance requires both sealed provenance and observable
event behavior.  Missing resource lifecycle events remain an explicit behavior
mismatch; aggregate report values cannot substitute for them.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable

from binding import RAW_NAMES, business_rows, read_json, sha256, verify
from validate_resources import validate_resource_behavior


ROOT = Path(__file__).resolve().parent
CONTRACTS = ROOT / "contracts"
NATIVE = ROOT / "native"
CASES = ("B01", "B02", "B03", "C01", "C02", "C03")
TIME_LINE = re.compile(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$")
CONVERSION = re.compile(
    r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)"
)
WARNING = re.compile(r"\(warning #(\d+)\)\s*([^\r\n]+)")
TIME_TOLERANCE_MINUTES = 0.01

EVENT_MARKERS = {
    "preparation_start": (" preparation started,",),
    "preparation_end": (" preparation ended,",),
    "step_start": (" task starting:", " subtask starting:", " step starting:"),
    "step_end": (" task completed:", " subtask completed:", " step completed:"),
    "launch": (" mission starting,",),
    "mission_complete": (" mission completed:",),
    "resource_request": ("resource request", "requests resource", "requested resource"),
    "resource_wait": (
        "resource wait",
        "waiting for resource",
        "waits for resource",
        "availability test on",
    ),
    "resource_acquire": (
        "resource acquired",
        "resource allocated",
        "resource granted",
        "resource lease started",
        " allocated to maintenance task:",
        " resource received",
    ),
    "resource_release": (
        "resource released",
        "resource deallocated",
        "resource lease ended",
        " deallocated from  maintenance task:",
    ),
    "cancel": (" mission cancelled:", " mission aborted:"),
}


def _remove_trailing_commas(raw: bytes) -> bytes:
    text = raw.decode("utf-8-sig")
    output: list[str] = []
    quoted = False
    escaped = False
    for index, character in enumerate(text):
        if quoted:
            output.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
            continue
        if character == '"':
            quoted = True
            output.append(character)
            continue
        if character == ",":
            following = index + 1
            while following < len(text) and text[following].isspace():
                following += 1
            if following < len(text) and text[following] in "]}":
                continue
        output.append(character)
    return "".join(output).encode("utf-8")


def parse_events(text: str) -> list[dict]:
    events = []
    for line_number, line in enumerate(text.splitlines(), 1):
        match = TIME_LINE.match(line)
        if not match:
            continue
        body = match.group(2).strip()
        lowered = body.lower()
        kinds = [
            kind
            for kind, markers in EVENT_MARKERS.items()
            if any(marker in lowered for marker in markers)
        ]
        # SIMLOX 2017 emits preparation/subtask lifecycle text in this form.
        # These patterns come from the retained J35 P_ARM ENLOG probe rather
        # than invented fixture syntax.
        if re.match(r"system preparation task \d+ on <[^>]+> started$", lowered):
            kinds.append("preparation_start")
        if re.match(r"system preparation task \d+ on <[^>]+> completed$", lowered):
            kinds.append("preparation_end")
        if "subtask " in lowered and " within system preparation task " in lowered:
            if lowered.endswith(" started"):
                kinds.append("step_start")
            elif lowered.endswith(" completed"):
                kinds.append("step_end")
        if "availability test on" in lowered and " failed" not in lowered:
            kinds = [kind for kind in kinds if kind != "resource_wait"]
        kinds = list(dict.fromkeys(kinds))
        if kinds:
            events.append(
                {
                    "line": line_number,
                    "time_hours_printed": match.group(1),
                    "time_minutes": float(match.group(1)) * 60,
                    "body": body,
                    "kinds": kinds,
                    "raw": line,
                }
            )
    return events


def _events(events: Iterable[dict], kind: str) -> list[dict]:
    return [event for event in events if kind in event["kinds"]]


def _at(events: Iterable[dict], kind: str, minute: float) -> list[dict]:
    return [
        event
        for event in _events(events, kind)
        if abs(event["time_minutes"] - minute) <= TIME_TOLERANCE_MINUTES
    ]


def _contains(event: dict, *identities: str) -> bool:
    body = event["body"]
    return all(identity in body for identity in identities)


def _matches_event(
    event: dict, *, identities: Iterable[str] = (), pattern: str | None = None
) -> bool:
    if not _contains(event, *identities):
        return False
    return pattern is None or re.search(pattern, event["body"], re.IGNORECASE) is not None


def _require_timed_event(
    differences: list[dict],
    events: list[dict],
    kind: str,
    minute: float,
    assertion: str,
    *,
    identities: Iterable[str] = (),
    pattern: str | None = None,
) -> list[dict]:
    matches = [
        event
        for event in _at(events, kind, minute)
        if _matches_event(event, identities=identities, pattern=pattern)
    ]
    if len(matches) != 1:
        _difference(
            differences,
            assertion,
            kind=kind,
            expected_minutes=minute,
            identities=list(identities),
            pattern=pattern,
            actual=[event["body"] for event in _at(events, kind, minute)],
        )
    return matches


def _difference(differences: list[dict], assertion: str, **observed) -> None:
    differences.append({"assertion": assertion, "observed": observed})


def _variant(contract: dict, variant_id: str) -> dict:
    matches = [item for item in contract["variants"] if item["variant_id"] == variant_id]
    if len(matches) != 1:
        raise ValueError(f"contract does not define exactly one variant: {variant_id}")
    return matches[0]


def _launch_expectation(contract: dict, variant: dict) -> tuple[float | None, int]:
    if "expected_launch" in variant:
        return float(variant["expected_launch"]), 1
    if contract["case_id"] == "B02":
        return 480.0, 1
    if contract["case_id"] == "B03":
        return None, 3
    return None, 0


def _require_event_count(
    differences: list[dict], events: list[dict], kind: str, expected: int
) -> None:
    actual = len(_events(events, kind))
    if actual != expected:
        _difference(differences, f"{kind}_count", expected=expected, actual=actual)


def _resource_ids(contract: dict) -> list[str]:
    case_id = contract["case_id"]
    if case_id in ("C01", "C03"):
        return ["P-CREW"]
    if case_id == "C02":
        return ["P-CREW", "E-GSE"]
    return []


def _native_aircraft_identity(contract: dict, ordinal: int = 0) -> str:
    rows = contract["native_mapping"].get("expected_rows", {})
    preparation = rows.get("MissionPreparation", {})
    if isinstance(preparation, list):
        preparation = preparation[0]
    sid = preparation.get("SID", "AIR-TYPE")
    return f"<{sid},{ordinal}>"


def _native_mission_identity(contract: dict) -> str:
    rows = contract["native_mapping"].get("expected_rows", {})
    preparation = rows.get("MissionPreparation", {})
    if isinstance(preparation, list):
        preparation = preparation[0]
    return str(preparation.get("MTID", contract["business_contract"].get("mission_type", "")))


def evaluate_behavior(events: list[dict], contract: dict, variant_id: str) -> dict:
    """Evaluate only observable ENLOG behavior; it performs no file I/O."""

    variant = _variant(contract, variant_id)
    case_id = contract["case_id"]
    if case_id in ("C01", "C02", "C03"):
        raise ValueError(
            f"{case_id} resource behavior requires validate_resources; "
            "the preparation-only event parser cannot bind native owner/resource blocks"
        )
    differences: list[dict] = []
    if not events:
        _difference(differences, "timestamped_behavior_events_present", actual=0)
        return {"passed": False, "differences": differences, "event_counts": {}}
    if any(
        later["time_minutes"] + TIME_TOLERANCE_MINUTES < earlier["time_minutes"]
        for earlier, later in zip(events, events[1:])
    ):
        _difference(differences, "event_log_nondecreasing_time")

    launch_minute, launch_count = _launch_expectation(contract, variant)
    launches = _events(events, "launch")
    if len(launches) != launch_count:
        _difference(
            differences, "launch_count", expected=launch_count, actual=len(launches)
        )
    if launch_minute is not None and (
        len(launches) != 1
        or abs(launches[0]["time_minutes"] - launch_minute)
        > TIME_TOLERANCE_MINUTES
    ):
        _difference(
            differences,
            "launch_time",
            expected_minutes=launch_minute,
            actual_minutes=[event["time_minutes"] for event in launches],
        )

    blocked = "expected_state" in variant or "expected_state_at_latest_launch" in variant
    expected_preparations = 2 if case_id == "C03" else 1
    if blocked:
        if _events(events, "launch"):
            _difference(differences, "blocked_variant_has_no_launch")
        if _events(events, "preparation_end"):
            _difference(differences, "blocked_variant_has_no_preparation_completion")
    elif case_id not in ("B01", "B02", "B03"):
        _require_event_count(
            differences, events, "preparation_start", expected_preparations
        )
        _require_event_count(differences, events, "preparation_end", expected_preparations)

    if case_id == "B01" and variant_id == "fixed-30m":
        aircraft = _native_aircraft_identity(contract)
        mission = _native_mission_identity(contract)
        prep_starts = [
            event for event in _at(events, "preparation_start", 450)
            if _contains(event, aircraft, mission)
        ]
        prep_ends = [
            event for event in _at(events, "preparation_end", 480)
            if _contains(event, aircraft, mission)
        ]
        if len(prep_starts) != 1:
            _difference(differences, "fixed_preparation_start", expected_minutes=450)
        if len(prep_ends) != 1:
            _difference(differences, "fixed_preparation_end", expected_minutes=480)
        completions = _events(events, "mission_complete")
        if (
            len(launches) != 1
            or aircraft not in launches[0]["body"]
            or mission not in launches[0]["body"]
        ):
            _difference(
                differences,
                "fixed_mission_launch_identity",
                aircraft=aircraft,
                mission_type=mission,
                actual=[event["body"] for event in launches],
            )
        if (
            len(completions) != 1
            or abs(completions[0]["time_minutes"] - 540) > TIME_TOLERANCE_MINUTES
            or aircraft not in completions[0]["body"]
            or mission not in completions[0]["body"]
        ):
            _difference(
                differences,
                "fixed_mission_completion_identity_and_time",
                aircraft=aircraft,
                mission_type=mission,
                expected_minutes=540,
                actual=[event["body"] for event in completions],
            )
        if prep_starts and prep_ends and launches and completions:
            lines = [
                prep_starts[0]["line"],
                prep_ends[0]["line"],
                launches[0]["line"],
                completions[0]["line"],
            ]
            if lines != sorted(lines):
                _difference(differences, "fixed_mission_causal_order", lines=lines)
    elif case_id == "B02":
        aircraft = _native_aircraft_identity(contract)
        mission = _native_mission_identity(contract)
        expected = (
            ("preparation_start", 420, (aircraft, mission), None),
            ("step_start", 420, (aircraft,), r"subtask\s+\d+\s+seqno\s+1\b"),
            ("step_end", 430, (aircraft,), r"subtask\s+\d+\s+seqno\s+1\b"),
            ("step_start", 430, (aircraft,), r"subtask\s+\d+\s+seqno\s+2\b"),
            ("step_end", 450, (aircraft,), r"subtask\s+\d+\s+seqno\s+2\b"),
            ("preparation_end", 450, (aircraft, mission), None),
            ("launch", 480, (aircraft, mission), None),
            ("mission_complete", 540, (aircraft, mission), None),
        )
        matched = []
        for kind, minute, identities, pattern in expected:
            matched.extend(
                _require_timed_event(
                    differences,
                    events,
                    kind,
                    minute,
                    "serial_preparation_timeline",
                    identities=identities,
                    pattern=pattern,
                )
            )
        if len(matched) == len(expected) and [e["line"] for e in matched] != sorted(
            e["line"] for e in matched
        ):
            _difference(differences, "serial_preparation_causal_order")
    elif case_id == "B03":
        aircraft = _native_aircraft_identity(contract)
        recipes = (
            ("COLD-FIRST", 450, 480, 540, ((1, 450, 460), (2, 460, 480))),
            ("HOT-SORTIE", 710, 720, 780, ((1, 710, 720),)),
            ("HOT-SORTIE", 950, 960, 1020, ((1, 950, 960),)),
        )
        for mission, notice, launch, completion, steps in recipes:
            for kind, minute in (
                ("preparation_start", notice),
                ("preparation_end", launch),
                ("launch", launch),
                ("mission_complete", completion),
            ):
                matches = _require_timed_event(
                    differences,
                    events,
                    kind,
                    minute,
                    "explicit_recipe_mission_timeline",
                    identities=(aircraft, mission),
                )
            for sequence, start, end in steps:
                pattern = rf"subtask\s+\d+\s+seqno\s+{sequence}\b"
                for kind, minute in (("step_start", start), ("step_end", end)):
                    matches = _require_timed_event(
                        differences,
                        events,
                        kind,
                        minute,
                        "explicit_recipe_step_timeline",
                        identities=(aircraft,),
                        pattern=pattern,
                    )

    resource_ids = _resource_ids(contract)
    if resource_ids:
        resource_events = {
            kind: _events(events, kind)
            for kind in (
                "resource_request",
                "resource_wait",
                "resource_acquire",
                "resource_release",
            )
        }
        for resource_id in resource_ids:
            if not any(
                resource_id in event["body"]
                for event in resource_events["resource_request"]
            ):
                _difference(
                    differences,
                    "resource_request_event",
                    resource_id=resource_id,
                    actual=0,
                )
        if blocked:
            if not resource_events["resource_wait"]:
                _difference(
                    differences,
                    "blocked_variant_resource_wait_event",
                    minimum=1,
                    actual=0,
                )
            if case_id == "C03" and variant_id == "staffing-0":
                if len(resource_events["resource_wait"]) < 2:
                    _difference(
                        differences,
                        "two_aircraft_resource_wait_events",
                        minimum=2,
                        actual=len(resource_events["resource_wait"]),
                    )
            if resource_events["resource_acquire"] or resource_events["resource_release"]:
                _difference(differences, "blocked_variant_has_no_resource_lease")
        else:
            for kind in ("resource_acquire", "resource_release"):
                for resource_id in resource_ids:
                    if not any(
                        resource_id in event["body"] for event in resource_events[kind]
                    ):
                        _difference(
                            differences,
                            f"{kind}_event",
                            resource_id=resource_id,
                            actual=0,
                    )

    if case_id == "C03" and variant_id == "staffing-0" and not _events(
        events, "cancel"
    ):
        _difference(
            differences,
            "staffing_zero_native_terminal_outcome",
            expected="timestamped cancellation or abort event",
            actual=0,
        )

    if case_id == "C03" and variant_id in ("staffing-2", "staffing-1"):
        # The two aircraft are symmetric.  Native queue order may select either
        # identity first, so acceptance compares the two complete ledgers as a
        # multiset rather than assigning the first lease to AIR-01.
        aircraft = contract["business_contract"]["aircraft_roles"]
        for identity in aircraft:
            if not any(
                _contains(event, identity, "P-CREW")
                for event in _at(events, "resource_request", 450)
            ):
                _difference(
                    differences,
                    "formation_resource_request_identity",
                    aircraft=identity,
                    expected_minutes=450,
                )
        observed_ledgers = []
        for identity in aircraft:
            grants = [
                event["time_minutes"]
                for event in _events(events, "resource_acquire")
                if _contains(event, identity, "P-CREW")
            ]
            releases = [
                event["time_minutes"]
                for event in _events(events, "resource_release")
                if _contains(event, identity, "P-CREW")
            ]
            if len(grants) == 1 and len(releases) == 1:
                observed_ledgers.append((grants[0], releases[0]))
        expected_ledgers = sorted(
            (float(entry["grant"]), float(entry["release"]))
            for entry in variant["expected_ledger"]
        )
        if sorted(observed_ledgers) != expected_ledgers:
            _difference(
                differences,
                "formation_exchangeable_resource_ledgers",
                expected=expected_ledgers,
                actual=sorted(observed_ledgers),
            )
        if variant_id == "staffing-1":
            waiting_identities = {
                identity
                for identity in aircraft
                if any(
                    _contains(event, identity, "P-CREW")
                    for event in _at(events, "resource_wait", 450)
                )
            }
            if len(waiting_identities) != 1:
                _difference(
                    differences,
                    "formation_exactly_one_aircraft_waits",
                    expected=1,
                    actual=sorted(waiting_identities),
                )

    event_counts = {
        kind: len(_events(events, kind)) for kind in EVENT_MARKERS
    }
    return {
        "passed": not differences,
        "differences": differences,
        "event_counts": event_counts,
        "launch_minutes": [event["time_minutes"] for event in launches],
        "resource_evidence_basis": "direct_timestamped_ENLOG_events",
    }


def conversion_result(run_log: str, allowed_warnings: list[str]) -> dict:
    summary = CONVERSION.search(run_log)
    if not summary:
        raise ValueError("missing native input conversion summary")
    errors, warning_count, notes = map(int, summary.groups())
    warnings = WARNING.findall(run_log)
    if len(warnings) != warning_count:
        raise ValueError("native warning count/details mismatch")
    unknown = sorted({number for number, _ in warnings} - set(allowed_warnings))
    if errors != 0 or unknown:
        raise ValueError(
            f"native conversion rejected: errors={errors}, unknown_warnings={unknown}"
        )
    return {
        "errors": errors,
        "warnings": warning_count,
        "notes": notes,
        "warning_details": [
            {"number": number, "text": text} for number, text in warnings
        ],
    }


def input_table_rows(path: Path, name: str) -> list[dict]:
    document = read_json(path)
    tables = [table for table in document["model"]["tables"] if table["name"] == name]
    if len(tables) != 1:
        raise ValueError(f"native input missing or duplicate table: {name}")
    table = tables[0]
    columns = [column["name"] for column in table["columns"]]
    rows = []
    for instance in table["instances"]:
        for raw in instance["rows"]:
            if len(raw) != len(columns):
                raise ValueError(f"native input {name} column/row length mismatch")
            if any(value not in (None, "") for value in raw):
                rows.append(dict(zip(columns, raw)))
    return rows


def allowed_warnings_for_input(contract: dict, input_path: Path) -> list[str]:
    """Evaluate each warning allowlist condition against the sealed input."""

    allowed = []
    for entry in contract["acceptance_policy"].get("allowed_warnings", []):
        if not isinstance(entry, dict) or "number" not in entry or "condition" not in entry:
            raise ValueError("warning allowlist entry must include number and condition")
        number = str(entry["number"])
        condition = entry["condition"]
        if number == "108" and condition == "Control.ENLOG=Y":
            if any(row.get("ENLOG") == "Y" for row in input_table_rows(input_path, "Control")):
                allowed.append(number)
        elif number == "126" and condition == "the teaching aircraft has no Item child rows":
            if not input_table_rows(input_path, "Item"):
                allowed.append(number)
        else:
            raise ValueError(f"unsupported warning allowlist condition: #{number} {condition}")
    return allowed


def validate_input_mapping(contract: dict, input_path: Path) -> dict:
    """Bind native recipe rows to the business contract before reading ENLOG."""

    case_id = contract["case_id"]
    mapping = contract["native_mapping"]
    if case_id == "B03":
        recipes = contract["business_contract"]["recipes"]
        expected = {
            "MissionPreparation": mapping["recipe_rows"],
            "Tasks": [
                {"TID": recipe["task_id"]} for recipe in recipes.values()
            ],
            "TaskBreakDown": [
                {
                    "TID": recipe["task_id"],
                    "SEQ": step["sequence"],
                    "SUTID": step["step_id"],
                    "DURN": step["duration"] / 60,
                }
                for recipe in recipes.values()
                for step in recipe["steps"]
            ],
        }
    elif case_id in ("B01", "B02", "C01", "C02", "C03"):
        expected = mapping["expected_rows"]
    else:
        raise ValueError(
            f"input mapping acceptance is not implemented for {case_id}"
        )
    checked = {}
    for table_name, wanted_rows in expected.items():
        rows = input_table_rows(input_path, table_name)
        if isinstance(wanted_rows, dict):
            wanted_rows = [wanted_rows]
        unmatched = list(rows)
        for wanted in wanted_rows:
            matches = [
                row
                for row in unmatched
                if all(row.get(field) == value for field, value in wanted.items())
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"{case_id} {table_name} does not contain exactly one contract row: "
                    f"{wanted}"
                )
            unmatched.remove(matches[0])
        # B01--B03 contracts enumerate their complete recipe tables. C01--C03
        # list only the resource rows relevant to each claim; shared parent
        # rows remain legal and are still protected by roundtrip equality.
        complete_table_contract = case_id in ("B01", "B02", "B03")
        if complete_table_contract and (unmatched or len(rows) != len(wanted_rows)):
            raise ValueError(
                f"{case_id} {table_name} contains rows outside the contract"
            )
        checked[table_name] = wanted_rows
    return checked


def roundtrip_result(run_dir: Path) -> dict:
    original = business_rows(run_dir / "input.json")
    exported = business_rows(run_dir / "roundtrip-raw.json")
    changed = {}
    for table in sorted(original.keys() | exported.keys()):
        left = original.get(table, Counter())
        right = exported.get(table, Counter())
        if left != right:
            changed[table] = {
                "input_only": list((left - right).elements())[:3],
                "export_only": list((right - left).elements())[:3],
            }
    recorded = read_json(run_dir / "roundtrip-check.json")
    result = {
        "all_equal": not changed,
        "changed": changed,
        "input_sha256": sha256(run_dir / "input.json"),
        "roundtrip_sha256": sha256(run_dir / "roundtrip-raw.json"),
        "nonempty_business_tables": sum(bool(rows) for rows in original.values()),
    }
    for key in (
        "all_equal",
        "changed",
        "input_sha256",
        "roundtrip_sha256",
        "nonempty_business_tables",
    ):
        if recorded.get(key) != result[key]:
            raise ValueError(f"roundtrip-check.json disagrees with raw artifacts: {key}")
    if not result["all_equal"]:
        raise ValueError(f"native import/export changed business rows: {sorted(changed)}")
    return result


def table_rows(report: dict, name: str) -> list[dict]:
    tables = [table for table in report["report"]["tables"] if table["name"] == name]
    if len(tables) != 1:
        raise ValueError(f"native report missing or duplicate table: {name}")
    table = tables[0]
    columns = [column["name"] for column in table["columns"]]
    rows = []
    for instance in table["instances"]:
        for raw in instance["rows"]:
            if len(raw) != len(columns):
                raise ValueError(f"native report {name} column/row length mismatch")
            rows.append(dict(zip(columns, raw)))
    return rows


def _evaluate_recipe_report(report: dict, contract: dict) -> dict:
    """Check B02/B03 native interval results independently of ENLOG text."""

    case_id = contract["case_id"]
    if case_id == "B02":
        interval_count = 24
        preparation_profile = {14: 1.0}
        prepared_wait_intervals = {15}
        flight_intervals = {16, 17}
        successful_preparation_intervals = {15}
    elif case_id == "B03":
        interval_count = 40
        preparation_profile = {15: 1.0, 23: 1 / 3, 31: 1 / 3}
        prepared_wait_intervals = set()
        flight_intervals = {16, 17, 24, 25, 32, 33}
        successful_preparation_intervals = {16, 24, 32}
    else:
        raise ValueError(f"unsupported recipe report case: {case_id}")

    differences: list[dict] = []
    summary = table_rows(report, "ResultSummary")
    if len(summary) != 1:
        _difference(differences, "result_summary_row_count", expected=1, actual=len(summary))
    else:
        row = summary[0]
        if row.get("NREP") != 1:
            _difference(differences, "result_repetitions", expected=1, actual=row.get("NREP"))
        for metric in ("MSTF", "MSUF"):
            if metric not in row or abs(float(row[metric]) - 1.0) > 1e-9:
                _difference(
                    differences, "mission_success_summary", metric=metric, actual=row.get(metric)
                )

    system = table_rows(report, "SystemResults")
    if len(system) != interval_count:
        _difference(
            differences,
            "system_result_interval_count",
            expected=interval_count,
            actual=len(system),
        )
    preparation_count = 0
    flight_hours = 0.0
    for index, row in enumerate(system):
        required = (
            "UNID", "SID", "STINT", "ETINT", "FTMO", "NPSTA", "NPSUC",
            "NSYMA", "NSYMP", "NSYMO", "NSYRY",
        )
        missing = [field for field in required if field not in row]
        if missing:
            _difference(differences, "system_result_required_fields", index=index, missing=missing)
            continue
        start = index * 0.5
        end = start + 0.5
        if abs(float(row["STINT"]) - start) > 1e-9 or abs(float(row["ETINT"]) - end) > 1e-9:
            _difference(
                differences,
                "system_result_contiguous_half_hour_intervals",
                index=index,
                expected=[start, end],
                actual=[row["STINT"], row["ETINT"]],
            )
        if row["UNID"] != "Total over all Units" or row["SID"] != "Total over all Systems":
            _difference(
                differences,
                "system_result_total_scope",
                index=index,
                UNID=row["UNID"],
                SID=row["SID"],
            )
        expected_prep = preparation_profile.get(index, 0.0)
        expected_flight = 1.0 if index in flight_intervals else 0.0
        expected_active = expected_prep + expected_flight + (
            1.0 if index in prepared_wait_intervals else 0.0
        )
        expected_values = {
            "FTMO": expected_flight,
            "NSYMP": expected_prep,
            "NSYMO": expected_flight,
            "NSYMA": expected_active,
            "NSYRY": 1.0 - expected_active,
            "NPSTA": 1 if index in preparation_profile else 0,
            "NPSUC": 1 if index in successful_preparation_intervals else 0,
        }
        for metric, expected in expected_values.items():
            # Fractional ten-minute occupation is exported through a float32
            # report field. Keep this local tolerance separate from ENLOG time.
            tolerance = 5e-7 if metric.startswith("NSY") else 1e-9
            if abs(float(row[metric]) - expected) > tolerance:
                _difference(
                    differences,
                    "recipe_interval_profile",
                    index=index,
                    metric=metric,
                    expected=expected,
                    actual=row[metric],
                )
        preparation_count += float(row["NPSTA"])
        flight_hours += float(row["FTMO"]) * (float(row["ETINT"]) - float(row["STINT"]))

    expected_preparations = len(preparation_profile)
    if abs(preparation_count - expected_preparations) > 1e-9:
        _difference(
            differences,
            "native_preparation_count",
            expected=expected_preparations,
            actual=preparation_count,
        )
    expected_flight_hours = len(flight_intervals) * 0.5
    if abs(flight_hours - expected_flight_hours) > 1e-8:
        _difference(
            differences,
            "flight_hours_integral",
            expected=expected_flight_hours,
            actual=flight_hours,
        )
    table_names = [table["name"] for table in report["report"]["tables"]]
    required_tables = {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}
    if not required_tables.issubset(table_names):
        _difference(
            differences,
            "native_report_required_tables",
            missing=sorted(required_tables - set(table_names)),
        )
    return {
        "passed": not differences,
        "differences": differences,
        "table_names": table_names,
        "system_result_rows": len(system),
        "native_preparation_count": preparation_count,
        "flight_hours_integral": flight_hours,
    }


def evaluate_report(report: dict, contract: dict, variant_id: str) -> dict:
    """Cross-check event claims against independent native result tables."""

    if contract["case_id"] in ("B02", "B03"):
        expected_variant = {
            "B02": "serial-10m-20m",
            "B03": "explicit-cold-hot",
        }[contract["case_id"]]
        if variant_id != expected_variant:
            raise ValueError(
                f"report acceptance is not implemented for {contract['case_id']}/{variant_id}"
            )
        return _evaluate_recipe_report(report, contract)

    if contract["case_id"] != "B01" or variant_id != "fixed-30m":
        raise ValueError(
            f"report acceptance is not implemented for {contract['case_id']}/{variant_id}"
        )
    differences: list[dict] = []
    summary = table_rows(report, "ResultSummary")
    if len(summary) != 1:
        _difference(differences, "result_summary_row_count", expected=1, actual=len(summary))
    else:
        row = summary[0]
        if row.get("NREP") != 1:
            _difference(differences, "result_repetitions", expected=1, actual=row.get("NREP"))
        for metric in ("MSTF", "MSUF"):
            if metric not in row or abs(float(row[metric]) - 1.0) > 1e-9:
                _difference(
                    differences, "mission_success_summary", metric=metric, actual=row.get(metric)
                )

    system = table_rows(report, "SystemResults")
    if not system:
        _difference(differences, "system_results_nonempty", actual=0)
    preparation_count = 0.0
    flight_hours = 0.0
    for index, row in enumerate(system):
        missing = [
            field
            for field in (
                "UNID",
                "SID",
                "STINT",
                "ETINT",
                "FTMO",
                "NPSTA",
                "NSYMA",
                "NSYMP",
                "NSYMO",
                "NSYRY",
            )
            if field not in row
        ]
        if missing:
            _difference(
                differences, "system_result_required_fields", index=index, missing=missing
            )
            continue
        span = float(row["ETINT"]) - float(row["STINT"])
        if span <= 0:
            _difference(differences, "system_result_positive_interval", index=index, span=span)
            continue
        flight_hours += float(row["FTMO"]) * span
        preparation_count += float(row["NPSTA"])
        expected_start = index * 0.5
        expected_end = expected_start + 0.5
        if (
            abs(float(row["STINT"]) - expected_start) > 1e-9
            or abs(float(row["ETINT"]) - expected_end) > 1e-9
        ):
            _difference(
                differences,
                "system_result_contiguous_half_hour_intervals",
                index=index,
                expected=[expected_start, expected_end],
                actual=[row["STINT"], row["ETINT"]],
            )
        if row.get("UNID") != "Total over all Units" or row.get("SID") != "Total over all Systems":
            _difference(
                differences,
                "system_result_total_scope",
                index=index,
                UNID=row.get("UNID"),
                SID=row.get("SID"),
            )
        expected_ftmo = 1 if expected_start >= 8 and expected_end <= 9 else 0
        if abs(float(row["FTMO"]) - expected_ftmo) > 1e-9:
            _difference(
                differences,
                "flight_operation_interval_profile",
                index=index,
                expected=expected_ftmo,
                actual=row["FTMO"],
            )
        expected_state = {
            "NSYMA": 1 if expected_start >= 7.5 and expected_end <= 9 else 0,
            "NSYMP": 1 if expected_start >= 7.5 and expected_end <= 8 else 0,
            "NSYMO": 1 if expected_start >= 8 and expected_end <= 9 else 0,
            "NSYRY": 0 if expected_start >= 7.5 and expected_end <= 9 else 1,
        }
        for metric, expected_value in expected_state.items():
            if abs(float(row[metric]) - expected_value) > 1e-9:
                _difference(
                    differences,
                    "system_state_interval_profile",
                    index=index,
                    metric=metric,
                    expected=expected_value,
                    actual=row[metric],
                )
        expected_npsta = 1 if expected_start == 7.5 else 0
        if abs(float(row["NPSTA"]) - expected_npsta) > 1e-9:
            _difference(
                differences,
                "preparation_start_interval_profile",
                index=index,
                expected=expected_npsta,
                actual=row["NPSTA"],
            )
    if len(system) != 24:
        _difference(differences, "system_result_interval_count", expected=24, actual=len(system))
    if abs(preparation_count - 1.0) > 1e-9:
        _difference(
            differences,
            "native_preparation_count",
            expected=1,
            actual=preparation_count,
        )
    if abs(flight_hours - 1.0) > 1e-8:
        _difference(
            differences,
            "flight_hours_integral",
            expected=1.0,
            actual=flight_hours,
        )

    table_names = [table["name"] for table in report["report"]["tables"]]
    required_tables = {
        "ProblemDescription",
        "ResultSummary",
        "SystemResults",
        "StockTotalResults",
    }
    if not required_tables.issubset(table_names):
        _difference(
            differences,
            "native_report_required_tables",
            missing=sorted(required_tables - set(table_names)),
        )
    return {
        "passed": not differences,
        "differences": differences,
        "table_names": table_names,
        "system_result_rows": len(system),
        "native_preparation_count": preparation_count,
        "flight_hours_integral": flight_hours,
    }


def load_contract(case_id: str, variant_id: str, input_sha256: str) -> tuple[dict, dict]:
    contract = read_json(CONTRACTS / f"{case_id}.json")
    if (
        contract.get("schema") != "simlox-preparation-resource-contract/v1"
        or contract.get("case_id") != case_id
    ):
        raise ValueError("contract schema/case mismatch")
    variant = _variant(contract, variant_id)
    policy = contract.get("acceptance_policy", {})
    if policy.get("conversion_errors") != 0 or not policy.get("roundtrip_required"):
        raise ValueError("contract acceptance policy is incomplete")

    manifest_path = NATIVE / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("generated native manifest is required before execution")
    manifest = read_json(manifest_path)
    if manifest.get("schema") != "simlox-preparation-resource-native-manifest/v1":
        raise ValueError("generated native manifest schema mismatch")
    entries = manifest.get("candidates")
    if not isinstance(entries, list) or manifest.get("candidate_count") != len(entries):
        raise ValueError("generated native manifest candidate list/count mismatch")
    matches = [
        entry
        for entry in entries
        if entry.get("case_id") == case_id and entry.get("variant_id") == variant_id
    ]
    if len(matches) != 1 or matches[0].get("input_sha256") != input_sha256:
        raise ValueError("generated native manifest/input fingerprint mismatch")
    candidate_path = (ROOT / matches[0].get("path", "")).resolve()
    if (
        NATIVE.resolve() not in candidate_path.parents
        or candidate_path.suffix.lower() != ".json"
        or not candidate_path.is_file()
        or sha256(candidate_path) != input_sha256
    ):
        raise ValueError("generated native candidate path/content fingerprint mismatch")
    return contract, variant


def validate(
    run_dir: Path, case_id: str, variant_id: str, *, write: bool = True
) -> dict:
    run_dir = run_dir.resolve()
    binding = verify(run_dir, case_id, variant_id)
    contract, variant = load_contract(case_id, variant_id, binding["input_sha256"])
    supported = {
        ("B01", "fixed-30m"),
        ("B02", "serial-10m-20m"),
        ("B03", "explicit-cold-hot"),
        ("C01", "capacity-2"),
        ("C01", "capacity-1"),
        ("C01", "capacity-0"),
        ("C01", "wrong-specialty"),
        ("C02", "both-available"),
        ("C02", "equipment-zero"),
        ("C03", "staffing-2"),
        ("C03", "staffing-1"),
        ("C03", "staffing-0"),
    }
    if (case_id, variant_id) not in supported:
        raise ValueError(
            f"native behavior acceptance not implemented for {case_id}/{variant_id}; "
            "retain the sealed run as a probe without verified status"
        )
    for name in RAW_NAMES:
        path = run_dir / name
        if not path.is_file() or path.stat().st_size <= 4:
            raise ValueError(f"missing/short sealed native artifact: {name}")

    policy = contract["acceptance_policy"]
    allowed_warning_numbers = allowed_warnings_for_input(contract, run_dir / "input.json")
    conversion = conversion_result(
        (run_dir / "run.log").read_text(encoding="utf-8-sig", errors="replace"),
        allowed_warning_numbers,
    )
    roundtrip = roundtrip_result(run_dir)
    input_mapping = validate_input_mapping(contract, run_dir / "input.json")
    raw_report = run_dir / "report-raw.json"
    normalized = _remove_trailing_commas(raw_report.read_bytes())
    report = json.loads(normalized.decode("utf-8"))
    normalized_path = run_dir / "report-normalized.json"
    if write:
        if normalized_path.exists():
            raise FileExistsError(normalized_path)
        normalized_path.write_bytes(normalized)

    model_log = (run_dir / "model.log").read_text(
        encoding="utf-8-sig", errors="replace"
    )
    events = parse_events(model_log)
    if case_id in ("C01", "C02", "C03"):
        behavior = validate_resource_behavior(
            case_id, variant_id, model_log, report, contract
        )
        report_behavior = {
            "passed": behavior["passed"],
            "basis": "integrated_resource_ENLOG_and_native_report",
            "assertions": behavior["assertions"],
        }
    else:
        behavior = evaluate_behavior(events, contract, variant_id)
        report_behavior = evaluate_report(report, contract, variant_id)
    status = (
        "cli_behavior_verified"
        if behavior["passed"] and report_behavior["passed"]
        else "cli_behavior_mismatch"
    )
    artifacts = {
        name: {
            "path": str((run_dir / name).resolve()),
            "bytes": (run_dir / name).stat().st_size,
            "sha256": sha256(run_dir / name),
        }
        for name in RAW_NAMES
    }
    result = {
        "schema_version": "simlox-preparation-resource-validation/v1",
        "case_id": case_id,
        "variant_id": variant_id,
        "contract_version": contract["version"],
        "status": status,
        "gui_status": "pending",
        "cross_engine_status": "unverified",
        "binding": binding,
        "conversion": conversion,
        "roundtrip": roundtrip,
        "input_mapping": input_mapping,
        "behavior": behavior,
        "report_behavior": report_behavior,
        "event_index": events,
        "artifacts": artifacts,
        "normalized_report": {
            "path": str(normalized_path.resolve()),
            "bytes": len(normalized),
            "sha256": hashlib.sha256(normalized).hexdigest(),
            "raw_sha256": sha256(raw_report),
        },
        "variant_contract": variant,
    }
    if write:
        target = run_dir / "validation.json"
        if target.exists():
            raise FileExistsError(target)
        target.write_bytes(
            (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode(
                "utf-8"
            )
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--variant", required=True)
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    result = validate(
        args.run_dir, args.case, args.variant, write=not args.read_only
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "case_id": result["case_id"],
                "variant_id": result["variant_id"],
                "raw_report_sha256": result["normalized_report"]["raw_sha256"],
                "normalized_report_sha256": result["normalized_report"]["sha256"],
                "differences": result["behavior"].get(
                    "differences",
                    [
                        assertion
                        for assertion in result["behavior"].get("assertions", [])
                        if not assertion.get("passed")
                    ],
                ),
            },
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    if result["status"] != "cli_behavior_verified":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
