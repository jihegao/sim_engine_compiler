"""Pure ENLOG/report validation for the C01--C03 resource probes."""
from __future__ import annotations

import math
import re

TIME = re.compile(r"^Time:\s+(\S+)\s*(.*)$")
TASK = re.compile(r"subtask\s+\d+\s+seqno\s+(?P<seq>\d+)\s+within system preparation task\s+(?P<task>\d+)\s+on\s+(?P<owner><AIR-TYPE,\d+>)", re.I)
AIRCRAFT = re.compile(r"<AIR-TYPE,\d+>")
SUPPORTED = {(case, variant) for case, variants in {
    "C01": ("capacity-2", "capacity-1", "capacity-0", "wrong-specialty"),
    "C02": ("both-available", "equipment-zero"),
    "C03": ("staffing-2", "staffing-1", "staffing-0"),
}.items() for variant in variants}


def parse_resource_events(raw_text: str) -> list[dict]:
    """Group timestamped ENLOG records with untimestamped detail lines."""
    blocks, current = [], None
    for line_number, line in enumerate(raw_text.splitlines(), 1):
        match = TIME.match(line)
        if match:
            if current:
                blocks.append(current)
            current = {"line": line_number, "time_minutes": float(match.group(1)) * 60,
                       "body": match.group(2).strip(), "continuation": []}
        elif current is not None:
            current["continuation"].append(line.strip())
    if current:
        blocks.append(current)
    for block in blocks:
        block["text"] = "\n".join([block["body"], *block["continuation"]])
        match = TASK.search(block["body"])
        block["task_key"] = match.groupdict() if match else None
    return blocks


def _rows(report: dict, name: str) -> list[dict]:
    tables = [table for table in report.get("report", {}).get("tables", []) if table.get("name") == name]
    if len(tables) != 1:
        return []
    table = tables[0]
    columns = [column["name"] for column in table.get("columns", [])]
    return [dict(zip(columns, row, strict=True)) for instance in table.get("instances", []) for row in instance.get("rows", [])]


def _interval(report: dict, start: float, end: float) -> dict | None:
    return next((row for row in _rows(report, "ResourceResults")
                 if row.get("RID") == "Total over all Resources" and row.get("STID") == "Total over all Stations"
                 and math.isclose(float(row["STINT"]), start, abs_tol=1e-9)
                 and math.isclose(float(row["ETINT"]), end, abs_tol=1e-9)), None)


def _num(row: dict | None, field: str, expected: float) -> bool:
    return row is not None and math.isclose(float(row[field]), expected, abs_tol=1e-6)


def _at(blocks: list[dict], minute: float, phrase: str) -> list[dict]:
    return [block for block in blocks if math.isclose(block["time_minutes"], minute, abs_tol=1e-3)
            and phrase.lower() in block["text"].lower()]


def _task(blocks: list[dict], owner: str, seq: str, phrase: str, minute: float | None = None) -> list[dict]:
    return [block for block in blocks if block["task_key"] and block["task_key"]["owner"] == owner
            and block["task_key"]["seq"] == seq and phrase.lower() in block["body"].lower()
            and (minute is None or math.isclose(block["time_minutes"], minute, abs_tol=1e-3))]


def _availability(blocks: list[dict], owner: str, seq: str, minute: float, rid: str, outcome: str,
                  quantity: int = 1) -> bool:
    pattern = re.compile(rf"<{re.escape(rid)} at <BASE-01,0>> request for:\s+{quantity}\s+{outcome}\b", re.I)
    return any(pattern.search(block["text"]) for block in _task(blocks, owner, seq, "resource availability test", minute))


def _availability_set(blocks: list[dict], owner: str, seq: str, minute: float,
                      expected: list[tuple[str, int, str]], event_count: int = 1) -> bool:
    events = _task(blocks, owner, seq, "resource availability test", minute)
    if len(events) != event_count:
        return False
    expected_lines = sorted(f"<{rid} at <BASE-01,0>> request for: {quantity} {outcome}".lower()
                            for rid, quantity, outcome in expected)
    for event in events:
        details = sorted(line.strip().removeprefix("Availability test on").strip().lower()
                         for line in event["continuation"] if "Availability test on" in line)
        if details != expected_lines:
            return False
    return True


def _owners(blocks: list[dict]) -> set[str]:
    return {match.group(0) for block in blocks for match in AIRCRAFT.finditer(block["body"])}


def _check(items: list[dict], name: str, ok: bool, expected, observed=None) -> None:
    items.append({"id": name, "passed": bool(ok), "expected": expected, "observed": observed})


def _allocation(blocks: list[dict], minute: float, rid: str, quantity: int, action: str,
                available_now: int) -> int:
    phrase = "allocated to maintenance task" if action == "grant" else "deallocated from  maintenance task"
    pattern = re.compile(rf"<{re.escape(rid)} at <BASE-01,0>> {re.escape(phrase)}:\s*{quantity}\s+available now:\s*{available_now}\b", re.I)
    return sum(bool(pattern.search(block["body"])) for block in blocks if math.isclose(block["time_minutes"], minute, abs_tol=1e-3))


def _allocation_blocks(blocks: list[dict], minute: float, rid: str, quantity: int, action: str,
                       available_now: int) -> list[dict]:
    phrase = "allocated to maintenance task" if action == "grant" else "deallocated from  maintenance task"
    pattern = re.compile(rf"<{re.escape(rid)} at <BASE-01,0>> {re.escape(phrase)}:\s*{quantity}\s+available now:\s*{available_now}\b", re.I)
    return [block for block in blocks if math.isclose(block["time_minutes"], minute, abs_tol=1e-3)
            and pattern.search(block["body"])]


def _mission(blocks: list[dict], minute: float, phrase: str, mission: str, owners: set[str]) -> bool:
    matches = _at(blocks, minute, phrase)
    return len(matches) == 1 and mission in matches[0]["body"] and _owners(matches) == owners


def _preparation_ended(blocks: list[dict], owner: str, minute: float) -> bool:
    return len([block for block in _at(blocks, minute, "preparation ended") if owner in block["body"]]) == 1


def _blocked_termination(blocks: list[dict], owner: str, seq: str, minute: float, mission: str) -> bool:
    cancel = _at(blocks, minute, "mission cancelled")
    ordered = _task(blocks, owner, seq, "ordered to stop", minute)
    stopped = _task(blocks, owner, seq, "resource waiting stopped", minute)
    ended = [block for block in _at(blocks, minute, "preparation ended") if owner in block["body"]]
    return (len(cancel) == len(ordered) == len(stopped) == len(ended) == 1
            and mission in cancel[0]["body"] and mission in ended[0]["body"]
            and _event_count(blocks, "mission cancelled") == 1
            and _task_count(blocks, owner, seq, "ordered to stop") == 1
            and _task_count(blocks, owner, seq, "resource waiting stopped") == 1
            and cancel[0]["line"] < ordered[0]["line"] < stopped[0]["line"] < ended[0]["line"])


def _event_count(blocks: list[dict], phrase: str) -> int:
    return sum(phrase.lower() in block["body"].lower() for block in blocks)


def _task_count(blocks: list[dict], owner: str, seq: str, phrase: str) -> int:
    return len(_task(blocks, owner, seq, phrase))


def _mission_after_preparation(blocks: list[dict], launch: float, completion: float,
                               launch_phrase: str, mission: str, owners: set[str]) -> bool:
    launches = _at(blocks, launch, launch_phrase)
    completions = _at(blocks, completion, "mission completed")
    prep_ends = [block for block in blocks if "preparation ended" in block["body"].lower()
                 and any(owner in block["body"] for owner in owners)]
    return (_mission(blocks, launch, launch_phrase, mission, owners)
            and _mission(blocks, completion, "mission completed", mission, owners)
            and len(prep_ends) == len(owners)
            and all(sum(owner in block["body"] for block in prep_ends) == 1 for owner in owners)
            and all(block["time_minutes"] <= launch for block in prep_ends)
            and all(block["line"] < launches[0]["line"] for block in prep_ends)
            and launches[0]["line"] < completions[0]["line"]
            and _event_count(blocks, launch_phrase) == 1
            and _event_count(blocks, "mission completed") == 1)


def _blocked_task_is_quiescent(blocks: list[dict], owner: str, seq: str,
                               after_line: int = -1) -> bool:
    forbidden_task_events = (
        "resource received", "books resources", "starts performing", "completed", "frees resources",
    )
    if any(_task_count(blocks, owner, seq, phrase) for phrase in forbidden_task_events):
        return False
    forbidden_resource_events = ("allocated to maintenance task", "deallocated from  maintenance task")
    return not any(block["line"] > after_line and any(phrase in block["body"].lower()
                   for phrase in forbidden_resource_events) for block in blocks)


def _ordered_transaction(blocks: list[dict], owner: str, seq: str, start: float, end: float,
                         resources: list[tuple[str, int, int | None, int | None]],
                         require_preparation_end: bool = False,
                         request_minute: float | None = None,
                         availability_count: int = 1) -> bool:
    """Bind owner task rows to intervening resource rows in native line order."""
    stages = [
        _task(blocks, owner, seq, "requests resources", start if request_minute is None else request_minute),
        _task(blocks, owner, seq, "resource availability test", start),
        _task(blocks, owner, seq, "books resources", start),
        _task(blocks, owner, seq, "starts performing", start),
        _task(blocks, owner, seq, "completed", end),
        _task(blocks, owner, seq, "frees resources", end),
    ]
    if any(len(stage) != 1 for stage in stages):
        return False
    if (_task_count(blocks, owner, seq, "requests resources") != 1
            or _task_count(blocks, owner, seq, "resource availability test") != availability_count
            or _task_count(blocks, owner, seq, "books resources") != 1
            or _task_count(blocks, owner, seq, "starts performing") != 1
            or _task_count(blocks, owner, seq, "completed") != 1
            or _task_count(blocks, owner, seq, "frees resources") != 1):
        return False
    request, availability, books, performing, completed, frees = (stage[0] for stage in stages)
    if not (request["line"] < availability["line"] < books["line"] < performing["line"]
            < completed["line"] < frees["line"]):
        return False
    prep_ends = [block for block in _at(blocks, end, "preparation ended") if owner in block["body"]]
    release_upper = prep_ends[0]["line"] if len(prep_ends) == 1 else float("inf")
    for rid, quantity, free_after_grant, free_after_release in resources:
        grant_free = rf"{free_after_grant}" if free_after_grant is not None else r"\d+"
        release_free = rf"{free_after_release}" if free_after_release is not None else r"\d+"
        grants = [block for block in blocks if books["line"] < block["line"] < performing["line"]
                  and re.search(rf"<{re.escape(rid)} at <BASE-01,0>> allocated to maintenance task:\s*{quantity}\s+available now:\s*{grant_free}\b", block["body"], re.I)]
        releases = [block for block in blocks if frees["line"] < block["line"] < release_upper
                    and math.isclose(block["time_minutes"], end, abs_tol=1e-3)
                    and re.search(rf"<{re.escape(rid)} at <BASE-01,0>> deallocated from  maintenance task:\s*{quantity}\s+available now:\s*{release_free}\b", block["body"], re.I)]
        if len(grants) != 1 or len(releases) != 1:
            return False
    return not require_preparation_end or len(prep_ends) == 1


def validate_resource_behavior(case_id: str, variant_id: str, raw_text: str, report_doc: dict, contract: dict) -> dict:
    if contract.get("case_id") != case_id:
        raise ValueError("contract case_id does not match requested case")
    if (case_id, variant_id) not in SUPPORTED:
        return {"passed": False, "status": "unsupported_pending_native_evidence", "assertions": [],
                "observability_limits": ["no sealed native resource contract for this variant"]}
    blocks, checks = parse_resource_events(raw_text), []
    _check(checks, "nondecreasing_native_timestamps",
           all(left["time_minutes"] <= right["time_minutes"] for left, right in zip(blocks, blocks[1:])), True)
    a0, a1 = "<AIR-TYPE,0>", "<AIR-TYPE,1>"

    if case_id == "C01":
        positive = variant_id == "capacity-2"
        _check(checks, "qualified_request_identity_and_quantity",
               len(_task(blocks, a0, "1", "requests resources", 450)) == 1
               and _availability_set(blocks, a0, "1", 450,
                                     [("P-CREW", 2, "OK" if positive else "failed")]),
               {"owner": a0, "RID": "P-CREW", "QTY": 2, "available": positive})
        if positive:
            _check(checks, "two_person_lease", _allocation(blocks, 450, "P-CREW", 2, "grant", 0) == 1
                   and _allocation(blocks, 480, "P-CREW", 2, "release", 2) == 1
                   and _event_count(blocks, "allocated to maintenance task") == 1
                   and _event_count(blocks, "deallocated from  maintenance task") == 1
                   and _ordered_transaction(blocks, a0, "1", 450, 480, [("P-CREW", 2, 0, 2)], True), "450-480")
            _check(checks, "mission_launch_and_completion",
                   _mission_after_preparation(blocks, 480, 540, "mission starting",
                                              "<MISSION-BASIC,RESOURCE-UNIT,0,0,0>", {a0}),
                   "480 launch, 540 completion")
            row = _interval(report_doc, 7.5, 8)
            _check(checks, "resource_report", _num(row, "NR", 2) and _num(row, "NRUM", 2) and _num(row, "NRW", 0),
                   {"NR": 2, "NRUM": 2, "NRW": 0}, row)
        else:
            _check(checks, "no_partial_lease_or_launch", _task_count(blocks, a0, "1", "requests resources") == 1
                   and _task_count(blocks, a0, "1", "resource availability test") == 1
                   and _blocked_task_is_quiescent(blocks, a0, "1")
                   and not any("mission starting" in b["body"] or "mission completed" in b["body"]
                               for b in blocks), True)
            _check(checks, "observed_native_cancellation", len(_at(blocks, 510, "mission cancelled")) == 1, 510)
            _check(checks, "blocked_wait_stops_after_cancellation",
                   _blocked_termination(blocks, a0, "1", 510, "<MISSION-BASIC,RESOURCE-UNIT,0,0,0>"),
                   "cancel -> ordered stop -> wait stopped -> preparation ended")
            first, second = _interval(report_doc, 7.5, 8), _interval(report_doc, 8, 8.5)
            wait = 1 if variant_id == "capacity-1" else 2
            _check(checks, "blocked_resource_report", _num(first, "NRUM", 0) and _num(first, "NRW", wait)
                   and _num(second, "NRUM", 0) and _num(second, "NRW", wait), {"NRUM": 0, "NRW": wait}, {"first": first, "second": second})

    elif case_id == "C02":
        available = variant_id == "both-available"
        _check(checks, "inspect_personnel_transaction", _availability_set(blocks, a0, "1", 450, [("P-CREW", 1, "OK")])
               and _allocation(blocks, 450, "P-CREW", 1, "grant", 0) == 1
               and _allocation(blocks, 460.0002, "P-CREW", 1, "release", 1) == 1
               and _ordered_transaction(blocks, a0, "1", 450, 460.0002, [("P-CREW", 1, 0, 1)]), "P-CREW 450-460")
        _check(checks, "service_joint_availability",
               _availability_set(blocks, a0, "2", 460.0002,
                                 [("P-CREW", 1, "OK"), ("E-GSE", 1, "OK" if available else "failed")],
                                 1 if available else 2),
               {"P-CREW": "OK", "E-GSE": "OK" if available else "failed"})
        inspect_release = _allocation_blocks(blocks, 460.0002, "P-CREW", 1, "release", 1)
        service_request_all = _task(blocks, a0, "2", "requests resources")
        _check(checks, "inspect_release_precedes_service_request",
               len(inspect_release) == len(service_request_all) == 1
               and inspect_release[0]["line"] < service_request_all[0]["line"], True)
        if available:
            _check(checks, "joint_grant_and_release", all(_allocation(blocks, 460.0002, rid, 1, "grant", 0) == 1 for rid in ("P-CREW", "E-GSE"))
                   and all(_allocation(blocks, 480, rid, 1, "release", 1) == 1 for rid in ("P-CREW", "E-GSE"))
                   and _event_count(blocks, "allocated to maintenance task") == 3
                   and _event_count(blocks, "deallocated from  maintenance task") == 3
                   and _ordered_transaction(blocks, a0, "2", 460.0002, 480,
                                            [("P-CREW", 1, 0, 1), ("E-GSE", 1, 0, 1)], True), "both resources 460-480")
            _check(checks, "mission_launch_and_completion",
                   _mission_after_preparation(blocks, 480, 540, "mission starting",
                                              "<MISSION-BASIC,RESOURCE-UNIT,0,0,0>", {a0}),
                   "480 launch, 540 completion")
        else:
            service_request = _task(blocks, a0, "2", "requests resources", 460.0002)
            service_line = service_request[0]["line"] if len(service_request) == 1 else -1
            _check(checks, "no_partial_service_lease", _task_count(blocks, a0, "2", "requests resources") == 1
                   and _task_count(blocks, a0, "2", "resource availability test") == 2
                   and _blocked_task_is_quiescent(blocks, a0, "2", service_line)
                   and _allocation(blocks, 460.0002, "P-CREW", 1, "grant", 0) == 0
                   and not any("mission starting" in b["body"] or "mission completed" in b["body"]
                               for b in blocks), True)
            _check(checks, "observed_native_cancellation", len(_at(blocks, 540, "mission cancelled")) == 1, 540)
            _check(checks, "blocked_wait_stops_after_cancellation",
                   _blocked_termination(blocks, a0, "2", 540, "<MISSION-BASIC,RESOURCE-UNIT,0,0,0>"),
                   "cancel -> ordered stop -> wait stopped -> preparation ended")
        row = _interval(report_doc, 7.5, 8)
        use, wait = ((5 / 3, 0) if available else (1 / 3, 2 / 3))
        _check(checks, "resource_report", _num(row, "NRUM", use) and _num(row, "NRW", wait), {"NRUM": use, "NRW": wait}, row)

    else:
        staffing = int(next(item["P-CREW"] for item in contract["variants"] if item["variant_id"] == variant_id))
        _check(checks, "two_distinct_owner_requests", all(len(_task(blocks, owner, "1", "requests resources", 450)) == 1
                                                           for owner in (a0, a1)), [a0, a1])
        if staffing == 2:
            for owner, task in ((a0, "0"), (a1, "1")):
                _check(checks, f"parallel_ledger_{task}", _availability_set(blocks, owner, "1", 450, [("P-CREW", 1, "OK")])
                       and len(_task(blocks, owner, "1", "books resources", 450)) == 1
                       and len(_task(blocks, owner, "1", "starts performing", 450)) == 1
                       and len(_task(blocks, owner, "1", "completed", 480)) == 1
                       and len(_task(blocks, owner, "1", "frees resources", 480)) == 1
                       and _preparation_ended(blocks, owner, 480)
                       and _ordered_transaction(blocks, owner, "1", 450, 480,
                                                [("P-CREW", 1, None, None)], True),
                       {"owner": owner, "grant": 450, "release": 480})
            _check(checks, "parallel_capacity_ledger",
                   all(_allocation(blocks, 450, "P-CREW", 1, "grant", free) == 1 for free in (1, 0))
                   and all(_allocation(blocks, 480, "P-CREW", 1, "release", free) == 1 for free in (1, 2))
                   and _event_count(blocks, "allocated to maintenance task") == 2
                   and _event_count(blocks, "deallocated from  maintenance task") == 2,
                   {"grants": 2, "releases": 2})
            launch, completion = 480, 540
        elif staffing == 1:
            first = [owner for owner in (a0, a1) if _availability(blocks, owner, "1", 450, "P-CREW", "OK")]
            second = [owner for owner in (a0, a1) if _availability(blocks, owner, "1", 450, "P-CREW", "failed")]
            first_owner = first[0] if len(first) == 1 else ""
            second_owner = second[0] if len(second) == 1 else ""
            _check(checks, "first_owner_ledger", bool(first_owner) and first_owner != second_owner
                   and _availability_set(blocks, first_owner, "1", 450, [("P-CREW", 1, "OK")])
                   and len(_task(blocks, first_owner, "1", "books resources", 450)) == 1
                   and len(_task(blocks, first_owner, "1", "starts performing", 450)) == 1
                   and len(_task(blocks, first_owner, "1", "completed", 480)) == 1
                   and len(_task(blocks, first_owner, "1", "frees resources", 480)) == 1
                   and _preparation_ended(blocks, first_owner, 480)
                   and _ordered_transaction(blocks, first_owner, "1", 450, 480, [("P-CREW", 1, 0, 1)], True), {"grant": 450, "release": 480})
            retry = _task(blocks, second_owner, "1", "resource availability test", 480) if second_owner else []
            received = _task(blocks, second_owner, "1", "resource received", 480) if second_owner else []
            books = _task(blocks, second_owner, "1", "books resources", 480) if second_owner else []
            performing = _task(blocks, second_owner, "1", "starts performing", 480) if second_owner else []
            received_ordered = (len(retry) == len(received) == len(books) == len(performing) == 1
                                and retry[0]["line"] < received[0]["line"] < books[0]["line"] < performing[0]["line"])
            first_release = _allocation_blocks(blocks, 480, "P-CREW", 1, "release", 1)
            _check(checks, "second_owner_wait_regrant_ledger", bool(second_owner) and first_owner != second_owner
                   and _availability_set(blocks, second_owner, "1", 450, [("P-CREW", 1, "failed")])
                   and _availability_set(blocks, second_owner, "1", 480, [("P-CREW", 1, "OK")])
                   and len(_task(blocks, second_owner, "1", "resource received", 480)) == 1
                   and len(_task(blocks, second_owner, "1", "books resources", 480)) == 1
                   and len(_task(blocks, second_owner, "1", "completed", 510)) == 1
                   and len(_task(blocks, second_owner, "1", "frees resources", 510)) == 1
                   and _preparation_ended(blocks, second_owner, 510)
                   and received_ordered
                   and len(first_release) == 1 and first_release[0]["line"] < retry[0]["line"]
                   and _ordered_transaction(blocks, second_owner, "1", 480, 510,
                                            [("P-CREW", 1, 0, 1)], True, 450, 2),
                   {"wait": 450, "grant": 480, "release": 510})
            _check(checks, "serial_capacity_ledger",
                   _allocation(blocks, 450, "P-CREW", 1, "grant", 0) == 1
                   and _allocation(blocks, 480, "P-CREW", 1, "release", 1) == 1
                   and _allocation(blocks, 480, "P-CREW", 1, "grant", 0) == 1
                   and _allocation(blocks, 510, "P-CREW", 1, "release", 1) == 1
                   and _event_count(blocks, "allocated to maintenance task") == 2
                   and _event_count(blocks, "deallocated from  maintenance task") == 2,
                   "one lease at a time")
            launch, completion = 510, 570
        else:
            _check(checks, "both_owners_blocked_without_grant",
                   all(_availability_set(blocks, owner, "1", 450, [("P-CREW", 1, "failed")])
                       and _task_count(blocks, owner, "1", "requests resources") == 1
                       and _task_count(blocks, owner, "1", "resource availability test") == 1
                       and _blocked_task_is_quiescent(blocks, owner, "1") for owner in (a0, a1))
                   and not any("mission starting" in b["body"] or "mission completed" in b["body"]
                               for b in blocks), True)
            _check(checks, "observed_early_native_cancellation", len(_at(blocks, 510, "mission cancelled")) == 1, 510)
            _check(checks, "both_waits_stop_without_work",
                   all(_blocked_termination(blocks, owner, "1", 510,
                                            "<FORMATION-TWO,FORMATION-UNIT,0,0,0>")
                       for owner in (a0, a1)),
                   [a0, a1])
            launch = completion = None
        if launch is not None:
            _check(checks, "formation_launch_and_completion",
                   _mission_after_preparation(blocks, launch, completion, "mission starting",
                                              "<FORMATION-TWO,FORMATION-UNIT,0,0,0>", {a0, a1}),
                   {"launch": launch, "completion": completion, "owners": [a0, a1]})
        first, second = _interval(report_doc, 7.5, 8), _interval(report_doc, 8, 8.5)
        expected = {2: (2, 0, 0, 0), 1: (1, 1, 1, 0), 0: (0, 2, 0, 2)}[staffing]
        _check(checks, "capacity_interval_report", _num(first, "NRUM", expected[0]) and _num(first, "NRW", expected[1])
               and _num(second, "NRUM", expected[2]) and _num(second, "NRW", expected[3]),
               {"first": expected[:2], "second": expected[2:]}, {"first": first, "second": second})

    summary = _rows(report_doc, "ResultSummary")
    succeeds = variant_id in {"capacity-2", "both-available", "staffing-2", "staffing-1"}
    _check(checks, "mission_summary_correlates_with_enlog", len(summary) == 1
           and _num(summary[0], "MSTF", int(succeeds)) and _num(summary[0], "MSUF", int(succeeds)),
           {"MSTF": int(succeeds), "MSUF": int(succeeds)}, summary[0] if summary else None)
    passed = all(item["passed"] for item in checks)
    limits = ["ResourceResults is accepted only with owner task blocks from ENLOG",
              "resource lines are bound to the adjacent owner subtask transaction block",
              "GUI review and cross-engine equivalence remain outside this validator"]
    if (case_id, variant_id) == ("C03", "staffing-0"):
        limits.append("native cancellation occurred at 510 before the 540 latest-launch bound; C04 cancellation semantics remain unresolved")
    return {"passed": passed, "status": "bounded_native_resource_behavior_verified" if passed else "resource_behavior_mismatch",
            "assertions": checks, "observability_limits": limits}
