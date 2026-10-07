"""Independent, standard-library C05.var03 evidence replay.

The self-check is safe before a native run. The postrun entry point remains
disabled until the exact frozen runner/manifest and raw closure are reviewed.
No author validator or mutable accepted-case helper is imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parents[2]
CONTRACT_SHA = "cc3aa75b3c4f6cec8fff57c0de28abf9ed552f4c0bc836e581295856ca30f283"
EVENT_RE = re.compile(r"^Time: ([0-9]+(?:\.[0-9]+)?)\b(.*)$")
_REPORT_TABLES = {
    "ProblemDescription": (1, 1),
    "ResultSummary": (1, 11),
    "SystemResults": (72, 40),
    "StockTotalResults": (72, 16),
    "ResourceResults": (72, 16),
    "ResourceResultsTotal": (1, 14),
}
_REPORT_INSTANCES = {
    "ProblemDescription": "", "ResultSummary": "",
    "SystemResults": "Total over all Units;Total over all Systems;0.00;36.00",
    "StockTotalResults": "0.00;36.00;",
    "ResourceResults": "Total over all Resources;Total over all Stations;0.00;36.00",
    "ResourceResultsTotal": "Total over all Resources;Total over all Stations;0.00;36.00",
}


def sha_size(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def check_seal(path: Path, seal: dict[str, Any]) -> None:
    got_hash, got_size = sha_size(path)
    assert got_hash == seal["sha256"], (str(path), "sha", got_hash, seal["sha256"])
    assert got_size == seal["bytes"], (str(path), "size", got_size, seal["bytes"])


def drop_trailing_commas(data: bytes) -> bytes:
    """Normalize only a parser copy, retaining quoted commas and raw bytes."""
    out = bytearray()
    quoted = escaped = False
    i = 0
    while i < len(data):
        c = data[i]
        if quoted:
            out.append(c)
            if escaped:
                escaped = False
            elif c == 92:
                escaped = True
            elif c == 34:
                quoted = False
        elif c == 34:
            quoted = True
            out.append(c)
        elif c == 44:
            j = i + 1
            while j < len(data) and data[j] in b" \t\r\n":
                j += 1
            if j >= len(data) or data[j] not in b"]}":
                out.append(c)
        else:
            out.append(c)
        i += 1
    assert not quoted, "unterminated JSON string"
    return bytes(out)


def read_native_json(path: Path) -> Any:
    return json.loads(drop_trailing_commas(path.read_bytes()).decode("utf-8-sig"))


def tables(doc: dict[str, Any], kind: str) -> dict[str, dict[str, Any]]:
    obj = doc[kind]
    items = obj["tables"] if isinstance(obj, dict) else obj
    names = [t["name"] for t in items]
    assert len(names) == len(set(names)), (kind, "duplicate table")
    return {t["name"]: t for t in items}


def rows(table: dict[str, Any]) -> list[tuple[str, tuple[Any, ...]]]:
    return [
        (instance["instance_name"], tuple(row))
        for instance in table["instances"]
        for row in instance["rows"]
    ]


def report_shape(doc: dict[str, Any]) -> dict[str, int]:
    found = tables(doc, "report")
    assert set(found) == set(_REPORT_TABLES), sorted(set(found) ^ set(_REPORT_TABLES))
    total = 0
    for name, (expected_rows, expected_columns) in _REPORT_TABLES.items():
        table = found[name]
        assert len(table["instances"]) == 1, (name, "instance count")
        assert table["instances"][0]["instance_name"] == _REPORT_INSTANCES[name], (name, "instance name")
        columns = [c["name"] for c in table["columns"]]
        actual = rows(table)
        assert len(columns) == expected_columns, (name, "columns", len(columns))
        assert len(actual) == expected_rows, (name, "rows", len(actual))
        assert len(set(columns)) == len(columns), (name, "duplicate columns")
        assert all(len(row) == expected_columns for _, row in actual), (name, "row width")
        total += len(actual) * len(columns)
    assert total == 5210, total
    return {name: len(rows(table)) * len(table["columns"]) for name, table in found.items()}


def event_blocks(raw: bytes) -> list[tuple[float, str]]:
    """Attach indented native continuation lines to their timestamped event."""
    result: list[tuple[float, str]] = []
    for physical_line in raw.decode("utf-8-sig", errors="replace").splitlines():
        m = EVENT_RE.match(physical_line)
        if m:
            result.append((float(m.group(1)), m.group(2)))
        elif result:
            prior_time, prior_text = result[-1]
            result[-1] = prior_time, prior_text + "\n" + physical_line
    return result


def event_at(events: list[tuple[float, str]], phrase: str, *, hour: float | None = None) -> list[str]:
    return [
        body for time, body in events
        if phrase in body and (hour is None or math.isclose(time, hour, abs_tol=0.0001))
    ]


def compare_cell(actual: Any, expected: Any, *, basis: str) -> bool:
    """Use a declared precision policy, not one blanket numeric tolerance.

    ``event_fraction`` reflects the maximum two printed event boundaries at
    5 decimal places inside a half-hour bin. The caller must derive its
    expectation from those event boundaries. ``copy`` is for a cell whose
    exact source/control value is expected. Other numeric values are exact
    counts or scheduled half-hour endpoints.
    """
    if expected is None or isinstance(expected, (str, bool)):
        return type(actual) is type(expected) and actual == expected
    if not isinstance(actual, (int, float)) or isinstance(actual, bool):
        return False
    if basis in {"count", "endpoint"}:
        return float(actual) == float(expected)
    if basis == "copy":
        return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=1e-10)
    if basis == "event_fraction":
        # At most two 0.00005 h printed boundary errors divided by a 0.5 h bin.
        return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=0.0002)
    raise ValueError(basis)


def report_records(doc: dict[str, Any], table_name: str) -> list[dict[str, Any]]:
    table = tables(doc, "report")[table_name]
    assert len(table["instances"]) == 1, table_name
    columns = [item["name"] for item in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for _, row in rows(table)]


def _bin_integral(spans: list[tuple[float, float, float]], start: float, stop: float) -> float:
    return sum(max(0.0, min(stop, right) - max(start, left)) * value
               for left, right, value in spans) / (stop - start)


def resource_ledger(events: list[tuple[float, str]], *, capacity: int = 2) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Independently reconstruct the six-table resource control semantics.

    Reconfiguration subtasks request no personnel in the accepted A16 source.
    Only mission resource bookings contribute to NRMA before launch and NRMO
    during flight. Native ResourceResults uses RID=Total and STID=Total here.
    This same algorithm is calibrated on accepted capacity-two and capacity-one
    logs before any child log is evaluated.
    """
    points: list[tuple[float, int]] = []
    starts: list[float] = []
    ends: list[float] = []
    for hour, body in events:
        if "<MISSION-CREW at " in body and "allocated to mission assigned:" in body:
            m = re.search(r"allocated to mission assigned:\s*(\d+)", body)
            assert m, body
            points.append((hour, int(m.group(1))))
        if "<MISSION-CREW at " in body and "deallocated from  mission operation:" in body:
            m = re.search(r"deallocated from\s+mission operation:\s*(\d+)", body)
            assert m, body
            points.append((hour, -int(m.group(1))))
        if " mission starting," in body:
            starts.append(hour)
        if " mission completed:" in body or " mission cancelled" in body:
            ends.append(hour)
    assert len(starts) <= 1, starts
    if starts:
        assert len(ends) == 1 and ends[0] >= starts[0], (starts, ends)
    boundaries = sorted({0.0, 36.0, *[hour for hour, _ in points], *starts, *ends})
    spans_ma: list[tuple[float, float, float]] = []
    spans_mo: list[tuple[float, float, float]] = []
    for left, right in zip(boundaries, boundaries[1:]):
        booked = sum(delta for hour, delta in points if hour <= left)
        assert 0 <= booked <= capacity, (left, booked)
        on_mission = bool(starts and starts[0] <= left < ends[0])
        spans_ma.append((left, right, 0.0 if on_mission else float(booked)))
        spans_mo.append((left, right, float(booked) if on_mission else 0.0))
    assert sum(delta for _, delta in points) == 0, points
    expected_rows: list[dict[str, Any]] = []
    for index in range(72):
        left, right = index / 2, (index + 1) / 2
        row: dict[str, Any] = {
            "RID": "Total over all Resources", "STID": "Total over all Stations",
            "STINT": left, "ETINT": right,
            **{name: 0 for name in ("NRMO", "NRMA", "NRUM", "NRLA", "NRW", "NRF", "NRRI", "NRRT", "NRRO")},
            **{name: capacity for name in ("NR", "NRA", "NRN")},
        }
        row["NRMA"] = _bin_integral(spans_ma, left, right)
        row["NRMO"] = _bin_integral(spans_mo, left, right)
        expected_rows.append(row)
    total = {
        "RID": "Total over all Resources", "STID": "Total over all Stations",
        **{name: 0 for name in ("NRMO", "NRMA", "NRUM", "NRLA", "NRW", "NRF", "NRRI", "NRRT", "NRRO")},
        **{name: capacity for name in ("NR", "NRA", "NRN")},
    }
    total["NRMA"] = _bin_integral(spans_ma, 0.0, 36.0)
    total["NRMO"] = _bin_integral(spans_mo, 0.0, 36.0)
    return expected_rows, total


def check_resource_report(doc: dict[str, Any], events: list[tuple[float, str]], *, capacity: int) -> int:
    expected_rows, expected_total = resource_ledger(events, capacity=capacity)
    actual_rows = report_records(doc, "ResourceResults")
    actual_total = report_records(doc, "ResourceResultsTotal")
    assert len(actual_rows) == 72 and len(actual_total) == 1
    count = 0
    for index, (actual, expected) in enumerate(zip(actual_rows, expected_rows)):
        assert set(actual) == set(expected)
        for name, value in expected.items():
            basis = "event_fraction" if name in {"NRMO", "NRMA"} else "count"
            assert compare_cell(actual[name], value, basis=basis), ("ResourceResults", actual["STINT"], name, actual[name], value)
            count += 1
    assert set(actual_total[0]) == set(expected_total)
    for name, value in expected_total.items():
        basis = "event_fraction" if name in {"NRMO", "NRMA"} else "count"
        assert compare_cell(actual_total[0][name], value, basis=basis), ("ResourceResultsTotal", name, actual_total[0][name], value)
        count += 1
    return count


def stock_trace(events: list[tuple[float, str]]) -> dict[str, dict[str, Any]]:
    """Track observed A/B IDs and type counts without assuming serial reuse."""
    result: dict[str, dict[str, Any]] = {}
    for item_type in ("TEACH-LRU-A", "TEACH-LRU-B"):
        prefix = f"<{item_type},0,BASE-01,0>"
        current: set[str] | None = None
        opening: set[str] | None = None
        seen: set[str] = set()
        changes: list[dict[str, Any]] = []
        demands: list[float] = []
        arrivals: list[dict[str, Any]] = []
        for hour, body in events:
            if not body.lstrip().startswith(prefix):
                continue
            ids = re.findall(rf"<{re.escape(item_type)},0,(\d+)>", body)
            if "Stock initiated" in body:
                assert current is None
                current = set(ids)
                opening = set(ids)
                seen.update(ids)
            elif "Reconfiguration item demand arrives" in body:
                demands.append(hour)
            elif "Take replacement item" in body:
                assert current is not None and len(ids) >= 1
                take_id = ids[0]
                assert take_id in current, (item_type, hour, take_id, current)
                current.remove(take_id)
                changes.append({"hour": hour, "kind": "take", "id": take_id, "level": len(current)})
            elif "Replacement item arrives" in body:
                assert len(ids) >= 1
                arrivals.append({"hour": hour, "id": ids[0]})
                seen.add(ids[0])
            elif "Put back replacement item" in body:
                assert current is not None and len(ids) >= 1
                returned_id = ids[0]
                assert returned_id not in current, (item_type, hour, returned_id)
                current.add(returned_id)
                seen.add(returned_id)
                changes.append({"hour": hour, "kind": "return", "id": returned_id, "level": len(current)})
            level = re.search(r"Stock at:.*?Level:\s*(\d+)\s+Items:(.*)", body, flags=re.S)
            if level and current is not None:
                observed_ids = set(re.findall(rf"<{re.escape(item_type)},0,(\d+)>", level.group(2)))
                assert int(level.group(1)) == len(current), (item_type, hour, level.group(1), current)
                assert observed_ids == current, (item_type, hour, observed_ids, current)
        assert current is not None, f"no opening {item_type} stock"
        for change in changes:
            if change["kind"] == "return":
                assert any(arrival["id"] == change["id"] and
                           math.isclose(arrival["hour"], change["hour"], abs_tol=0.0001)
                           for arrival in arrivals), (item_type, change, arrivals)
        result[item_type] = {"opening_ids": sorted(opening or [], key=int),
                             "observed_ids": sorted(seen, key=int), "demands": demands,
                             "arrivals": arrivals, "changes": changes,
                             "terminal_level": len(current)}
    return result


def stock_report_expected(events: list[tuple[float, str]]) -> list[dict[str, Any]]:
    """Accepted A16 demand-bin rule; only valid when no backorders are observed."""
    assert not event_at(events, "backorder"), "backorder requires a separate stock rule"
    demand_hours = [hour for hour, body in events if "Reconfiguration item demand arrives" in body]
    result: list[dict[str, Any]] = []
    for index in range(72):
        start, stop = index / 2, (index + 1) / 2
        count = sum(start <= hour < stop for hour in demand_hours)
        row: dict[str, Any] = {
            "STINT": start, "ETINT": stop, "NBO": 0, "NBOU": None,
            "ROS": 0 if count else None, "ROST": 0 if count else None,
            "WT": 0 if count else None, "WTT": 0 if count else None,
            "WTS": None, "PNB": 1,
            "NDF": 0, "NDD": 0, "NDR": count, "NDP": 0, "NLD": 0,
            "NWT": count,
        }
        result.append(row)
    return result


def check_stock_report(doc: dict[str, Any], events: list[tuple[float, str]]) -> int:
    actual_rows = report_records(doc, "StockTotalResults")
    expected_rows = stock_report_expected(events)
    assert len(actual_rows) == len(expected_rows) == 72
    checks = 0
    for actual, expected in zip(actual_rows, expected_rows):
        assert set(actual) == set(expected)
        for key, value in expected.items():
            basis = "endpoint" if key in {"STINT", "ETINT"} else "count"
            assert compare_cell(actual[key], value, basis=basis), ("StockTotalResults", actual["STINT"], key, actual[key], value)
            checks += 1
    return checks


def system_state_ledger(events: list[tuple[float, str]], *, fleet: int) -> list[dict[str, Any]]:
    """Reconstruct observed ready/assignment/reconfiguration/mission states.

    This covers event-derived fields only; semantic metrics such as STREQ are
    deliberately not guessed from the report itself.
    """
    ready: set[int] = set()
    allocated: set[int] = set()
    reconfig: set[int] = set()
    in_mission: set[int] = set()
    changes: list[tuple[float, dict[str, float]]] = [(0.0, {})]
    reconfig_starts: list[float] = []
    physical = re.compile(r"<TEACH-(?:AIR-01|CONF-A|CONF-B),(\d+)>")

    def one_id(body: str) -> int:
        found = physical.findall(body)
        assert found, body
        return int(found[0])

    for hour, body in events:
        if "nbr ready increased at unit:" in body:
            ready.add(one_id(body))
            allocated.discard(one_id(body))
        elif "nbr ready decreased at unit:" in body:
            ready.discard(one_id(body))
        elif "mission allocates system:" in body:
            item = int(physical.findall(body)[-1])
            allocated.add(item)
            ready.discard(item)
        elif " reconfig started, mission:" in body:
            reconfig.add(one_id(body))
            reconfig_starts.append(hour)
        elif " reconfig ended, mission:" in body:
            reconfig.remove(one_id(body))
        elif " mission starting," in body:
            matches = [int(value) for value in physical.findall(body)]
            assert matches, body
            in_mission.update(matches)
        elif " mission completed:" in body:
            in_mission.clear()
        if len(ready) > fleet or len(allocated) > fleet or reconfig - allocated or in_mission - allocated:
            raise AssertionError((hour, body, ready, allocated, reconfig, in_mission))
        changes.append((hour, {"NSYRY": float(len(ready)), "NSYMA": float(len(allocated)),
                               "NSYMO": float(len(in_mission)), "NSYMC": float(len(reconfig)),
                               "NSYMR": float(len(allocated - reconfig - in_mission)),
                               "NSYA": float(fleet), "FTMO": float(bool(in_mission)),
                               "STACC": float(len(in_mission))}))
    assert len(ready) == fleet and not allocated and not reconfig and not in_mission
    # Collapse same-time events to the state after the last event at that time.
    time_state: dict[float, dict[str, float]] = {}
    for time, state in changes:
        if state:
            time_state[time] = state
    timestamps = sorted({0.0, 36.0, *time_state})
    spans = [(left, right, time_state[left]) for left, right in zip(timestamps, timestamps[1:])]
    result: list[dict[str, Any]] = []
    for index in range(72):
        left, right = index / 2, (index + 1) / 2
        expected = {name: sum(max(0.0, min(stop, right) - max(start, left)) * state[name]
                              for start, stop, state in spans) / 0.5
                    for name in ("NSYRY", "NSYMA", "NSYMO", "NSYMC", "NSYMR", "NSYA", "FTMO", "STACC")}
        expected["NRCFG"] = sum(left <= time < right for time in reconfig_starts)
        result.append(expected)
    return result


def check_system_full_report(doc: dict[str, Any], events: list[tuple[float, str]], *, fleet: int,
                             configured_types: int) -> int:
    actual_rows = report_records(doc, "SystemResults")
    expected_rows = system_state_ledger(events, fleet=fleet)
    assert len(actual_rows) == len(expected_rows) == 72
    count = 0
    columns = set(actual_rows[0])
    assert len(columns) == 40
    for index, (actual, expected) in enumerate(zip(actual_rows, expected_rows)):
        full_expected: dict[str, Any] = {name: 0 for name in columns}
        full_expected.update({"UNID": "Total over all Units", "SID": "Total over all Systems",
                              "STINT": index / 2, "ETINT": (index + 1) / 2, "SYDT": None})
        full_expected.update(expected)
        full_expected["STREQ"] = expected["FTMO"] * configured_types / 2
        assert set(full_expected) == columns
        for key, value in full_expected.items():
            basis = "event_fraction" if key in {"NSYRY", "NSYMA", "NSYMO", "NSYMC", "NSYMR", "FTMO", "STACC", "STREQ"} else "count"
            assert compare_cell(actual[key], value, basis=basis), ("SystemResults", actual["STINT"], key, actual[key], value)
            count += 1
    return count


def check_summary_report(doc: dict[str, Any], events: list[tuple[float, str]]) -> int:
    rows = report_records(doc, "ResultSummary")
    assert len(rows) == 1 and len(rows[0]) == 11
    starts = event_at(events, " mission starting,")
    successes = event_at(events, " mission success:")
    completions = event_at(events, " mission completed:")
    cancels = event_at(events, " mission cancelled")
    assert (len(starts) == len(successes) == len(completions)) if starts else (not successes and not completions)
    assert not (successes and cancels)
    completed = int(bool(starts) and len(starts) == len(successes) == len(completions))
    expected = {"NREP": 1, "RTILW": 0, "RTIUP": 36,
                "MTMF": completed, "RSMTMF": 0, "MSTF": completed,
                "RSMSTF": 0, "MSUF": completed, "RSMSUF": 0,
                "STMF": completed, "RSSTMF": 0}
    assert set(rows[0]) == set(expected)
    for key, value in expected.items():
        assert compare_cell(rows[0][key], value, basis="count"), ("ResultSummary", key, rows[0][key], value)
    return 11


def check_problem_description(doc: dict[str, Any], source: dict[str, Any]) -> int:
    actual = report_records(doc, "ProblemDescription")
    table = tables(source, "model")["ProblemDescription"]
    expected = rows(table)
    assert len(actual) == len(expected) == 1
    assert list(actual[0]) == ["PDESC"]
    assert compare_cell(actual[0]["PDESC"], expected[0][1][0], basis="copy")
    return 1


def child_event_gate(events: list[tuple[float, str]], *, arm: str) -> dict[str, Any]:
    assert arm in {"crew", "radio"}
    ordered = [(t, body) for t, body in events if "mission ordered: SHARED-CONFIG-MISSION" in body]
    created = [(t, body) for t, body in events if "mission created:" in body]
    activated = [(t, body) for t, body in events if "mission activated, systems requested: 2" in body]
    assert len(ordered) == len(created) == len(activated) == 1
    assert all(math.isclose(items[0][0], 7, abs_tol=0.0001) for items in (ordered, created, activated))
    starts = [(t, body) for t, body in events if " mission starting," in body]
    successes = [(t, body) for t, body in events if " mission success:" in body]
    completes = [(t, body) for t, body in events if " mission completed:" in body]
    cancels = [(t, body) for t, body in events if " mission cancelled" in body]
    failed_radio = [(t, body) for t, body in events
                    if "Availability test on" in body and "MISSION-RADIO" in body
                    and "request for: 1" in body and "failed" in body]
    radio_grant = [(t, body) for t, body in events if "MISSION-RADIO" in body and
                   ("allocated to mission" in body or "deallocated from" in body)]
    assert not radio_grant, radio_grant
    crew_bookings = [(t, body) for t, body in events if "MISSION-CREW" in body and
                     "allocated to mission assigned: 1" in body]
    crew_releases = [(t, body) for t, body in events if "MISSION-CREW" in body and
                    "deallocated from" in body and "mission operation: 1" in body]
    if arm == "crew":
        assert len(starts) == len(successes) == len(completes) == 1 and not cancels
        assert math.isclose(starts[0][0], 8, abs_tol=0.0001)
        assert math.isclose(successes[0][0], 10, abs_tol=0.0001)
        assert math.isclose(completes[0][0], 10, abs_tol=0.0001)
        participants = re.findall(r"<TEACH-CONF-([AB]),(\d+)>", starts[0][1])
        assert len(participants) == 2 and {kind for kind, _ in participants} == {"A", "B"}
        # Configured-SID numeric suffixes are local to each SID. Two distinct
        # opening TEACH-AIR-01 IDs, not these suffixes, establish distinct aircraft.
        allocations = [re.findall(r"mission allocates system: <TEACH-AIR-01,(\d+)>", body)
                       for _, body in events if "mission allocates system:" in body]
        assert len(allocations) == 2 and all(allocations)
        assert {match[0] for match in allocations} == {"0", "1"}
        assert len(crew_bookings) == len(crew_releases) == 2
        assert all(math.isclose(t, 7, abs_tol=0.0001) for t, _ in crew_bookings)
        assert all(math.isclose(t, 10, abs_tol=0.0001) for t, _ in crew_releases)
        assert not failed_radio
    else:
        # The source requires NOS=MNOS=2 and one of EACH configured type.
        # A one-aircraft launch cannot satisfy that source and is rejected.
        assert not starts and not successes and not completes
        assert len(cancels) == 1 and 7 <= cancels[0][0] < 10
        assert failed_radio, "missing one-unit radio shortage witness"
        assert len(crew_bookings) == len(crew_releases) <= 1
        assert all(math.isclose(t, cancels[0][0], abs_tol=0.0001) for t, _ in crew_releases)
    return {"starts": len(starts), "successes": len(successes), "cancels": len(cancels),
            "failed_radio_tests": len(failed_radio), "crew_bookings": len(crew_bookings),
            "crew_releases": len(crew_releases)}


def child_stock_edges(events: list[tuple[float, str]], *, arm: str,
                      trace: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Bind observed opening item IDs to each typed demand and base-aircraft edge."""
    assert arm in {"crew", "radio"}
    linked: dict[str, Any] = {}
    base_owners: set[str] = set()
    for suffix in ("A", "B"):
        item_type = f"TEACH-LRU-{suffix}"
        demand_re = re.compile(
            rf"<{item_type},0,BASE-01,0> Reconfiguration item demand arrives "
            r"from pos <TEACH-AIR-01,BASE-01,(\d+)>")
        take_re = re.compile(
            rf"<{item_type},0,BASE-01,0> Take replacement item <{item_type},0,(\d+)> from stock")
        demand = [(hour, match.group(1)) for hour, body in events
                  if (match := demand_re.search(body))]
        takes = [(hour, match.group(1)) for hour, body in events
                 if (match := take_re.search(body))]
        assert len(demand) <= 1 and len(takes) <= 1, (item_type, demand, takes)
        assert len(takes) <= len(demand), (item_type, "orphan take")
        if takes:
            assert takes[0][1] in trace[item_type]["opening_ids"], (item_type, "take not opening ID")
            assert math.isclose(takes[0][0], demand[0][0], abs_tol=0.0001)
        if arm == "crew":
            assert len(demand) == len(takes) == 1, (item_type, "positive demand/take")
        if not demand:
            linked[item_type] = {"demand": 0, "take": 0}
            continue
        demand_hour, base_id = demand[0]
        starts = [hour for hour, body in events
                  if f"<TEACH-AIR-01,{base_id}> reconfig started, mission: <SHARED-CONFIG-MISSION," in body]
        ends = [hour for hour, body in events
                if f"<TEACH-AIR-01,{base_id}> reconfig ended, mission: <SHARED-CONFIG-MISSION," in body]
        assert len(starts) <= 1 and len(ends) <= 1
        if arm == "crew":
            assert len(starts) == len(ends) == 1
            assert demand_hour - 0.0001 <= starts[0] <= ends[0] <= 8.0001
            fit_start = [(hour, match.group(1)) for hour, body in events
                         if (match := re.search(
                             rf"system reconfig fit task (\d+) on <TEACH-AIR-01,{base_id}> started", body))]
            fit_end = [(hour, match.group(1)) for hour, body in events
                       if (match := re.search(
                           rf"system reconfig fit task (\d+) on <TEACH-AIR-01,{base_id}> completed", body))]
            assert len(fit_start) == len(fit_end) == 1
            assert fit_start[0][1] == fit_end[0][1]
            assert starts[0] - 0.0001 <= fit_start[0][0] <= fit_end[0][0] <= ends[0] + 0.0001
            prepared = [(hour, match.group(1)) for hour, body in events
                        if (match := re.search(
                            rf"<TEACH-CONF-{suffix},(\d+)> preparation started, mission: <SHARED-CONFIG-MISSION,", body))]
            assert len(prepared) == 1 and ends[0] <= prepared[0][0] <= 8.0001
            launched = [(hour, body) for hour, body in events if " mission starting," in body]
            assert len(launched) == 1 and f"<TEACH-CONF-{suffix},{prepared[0][1]}>" in launched[0][1]
            base_owners.add(base_id)
        linked[item_type] = {"demand": len(demand), "take": len(takes),
                             "base_id": base_id, "taken_id": takes[0][1] if takes else None,
                             "reconfig_started": len(starts), "reconfig_ended": len(ends)}
    if arm == "crew":
        assert base_owners == {"0", "1"}, base_owners
    for item_type, data in trace.items():
        for arrival in data["arrivals"]:
            assert any(change["kind"] == "return" and change["id"] == arrival["id"]
                       and math.isclose(change["hour"], arrival["hour"], abs_tol=0.0001)
                       for change in data["changes"]), (item_type, "orphan arrival", arrival)
        assert len(data["opening_ids"]) == 1, (item_type, "opening stock count")
        assert 0 <= data["terminal_level"] <= 1, (item_type, "terminal stock level")
    return linked


def child_roundtrip(source: dict[str, Any], exported: dict[str, Any]) -> int:
    assert source["model"]["database_version"] == exported["model"]["database_version"]
    before = tables(source, "model")
    after = tables(exported, "model")
    assert len(before) == len(after) == 33 and set(before) == set(after)
    populated = 0
    for name, original in before.items():
        native = after[name]
        assert original["columns"] == native["columns"], ("roundtrip columns", name)
        original_instances = {item["instance_name"]: item["rows"] for item in original["instances"]}
        native_instances = {item["instance_name"]: item["rows"] for item in native["instances"]}
        assert len(original_instances) == len(original["instances"]), ("duplicate source instance", name)
        assert len(native_instances) == len(native["instances"]), ("duplicate export instance", name)
        assert set(original_instances) == set(native_instances), ("roundtrip instances", name)
        row_count = sum(len(rows_) for rows_ in original_instances.values())
        if row_count:
            populated += 1
            assert original_instances == native_instances, ("roundtrip populated rows", name)
        else:
            assert all(all(value is None for value in row)
                       for rows_ in native_instances.values() for row in rows_), ("non-null placeholder", name)
    assert populated == 24
    return populated


def child_converter(log: str) -> int:
    assert re.search(r"Input conversion completed\. Errors: 0, Warnings: 4, Notes: 0\b", log)
    diagnostics = [(form, int(record), int(code), message.strip())
                   for form, block in re.findall(r"Form:\s*(\w+)(.*?)(?=Form:|Input conversion completed)",
                                                  log, flags=re.S)
                   for record, code, message in re.findall(r"rec\s+(\d+):\s*\(warning\s+#(\d+)\)\s*([^\r\n]*)", block, flags=re.I)]
    assert diagnostics == [
        ("Control", 1, 108, "Enabling simulation log may generate extensive data in log file"),
        ("Item", 1, 2053, "FRT is zero for: TEACH-LRU-01"),
        ("Item", 2, 2053, "FRT is zero for: TEACH-LRU-A"),
        ("Item", 3, 2053, "FRT is zero for: TEACH-LRU-B"),
    ], diagnostics
    assert len(re.findall(r"\((?:warning|error|note)\s*#\d+\)", log, flags=re.I)) == 4
    return 4


def child_report(run: Path, *, arm: str) -> dict[str, Any]:
    source = read_native_json(CASE / f"{arm}-input.json")
    exported = read_native_json(run / "roundtrip-raw.json")
    roundtrip_tables = child_roundtrip(source, exported)
    diagnostics = child_converter((run / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
    events = event_blocks((run / "model.log").read_bytes())
    event_summary = child_event_gate(events, arm=arm)
    physical_stock = stock_trace(events)
    stock_edges = child_stock_edges(events, arm=arm, trace=physical_stock)
    report = read_native_json(run / "report-raw.json")
    shape = report_shape(report)
    control_run = CASE.parent / "C05-mission-resource-v1.0.0" / "runs" / "c05-capacity-2-20260930-01"
    control = read_native_json(control_run / "report-raw.json")
    for name, table in tables(report, "report").items():
        assert table["columns"] == tables(control, "report")[name]["columns"], ("report column metadata", name)
    checks = {
        "description": check_problem_description(report, source),
        "summary": check_summary_report(report, events),
        "system": check_system_full_report(report, events, fleet=2, configured_types=2),
        "stock": check_stock_report(report, events),
        "resource_and_total": check_resource_report(report, events, capacity=2),
    }
    assert sum(checks.values()) == sum(shape.values()) == 5210, checks
    return {"roundtrip_tables": roundtrip_tables, "diagnostics": diagnostics,
            "events": event_summary, "physical_stock": physical_stock,
            "stock_edges": stock_edges,
            "report_cells": checks}


def accepted_controls(contract: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for label, seal in contract["accepted_native_runs"].items():
        run = Path(seal["path"])
        check_seal(run / "closure.json", seal["closure"])
        check_seal(run / "invocation.json", seal["invocation"])
        for name, raw_seal in seal["raw"].items():
            check_seal(run / name, raw_seal)
        events = event_blocks((run / "model.log").read_bytes())
        summary[label] = {"raw_seals": len(seal["raw"]), "events": len(events)}
        if label == "A16":
            summary[label]["diagnostics"] = child_converter((run / "run.log").read_text(encoding="utf-8-sig", errors="replace"))
            summary[label]["stock_trace"] = stock_trace(events)
            report = read_native_json(run / "report-raw.json")
            summary[label]["stock_ledger_cells"] = check_stock_report(report, events)
            summary[label]["system_cells"] = check_system_full_report(report, events, fleet=1, configured_types=1)
            summary[label]["summary_cells"] = check_summary_report(report, events)
        if label in {"C05", "C05_var02_radio0"}:
            report = read_native_json(run / "report-raw.json")
            shape = report_shape(report)
            assert sum(shape.values()) == 5210
            summary[label]["report_cells"] = sum(shape.values())
            summary[label]["stock_ledger_cells"] = check_stock_report(report, events)
            summary[label]["system_cells"] = check_system_full_report(report, events, fleet=2, configured_types=0)
            summary[label]["summary_cells"] = check_summary_report(report, events)
            source = read_native_json(run / "input.json")
            summary[label]["description_cells"] = check_problem_description(report, source)
            summary[label]["resource_ledger_cells"] = check_resource_report(report, events, capacity=2)
            assert sum(summary[label][key] for key in
                       ("description_cells", "summary_cells", "system_cells",
                        "stock_ledger_cells", "resource_ledger_cells")) == 5210
    return summary


def accepted_source_bytes(contract: dict[str, Any]) -> int:
    count = 0
    for group in contract["accepted_source_pins"].values():
        package = group["package"]
        for relative, identities in group["files"].items():
            path = ROOT / "cases" / "simlox-air-support" / package / relative
            check_seal(path, identities["local"])
            git_path = path.relative_to(ROOT).as_posix()
            blob = subprocess.run(
                ["git", "show", f"HEAD:{git_path}"], cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
            ).stdout
            assert hashlib.sha256(blob).hexdigest() == identities["published_git"]["sha256"], git_path
            assert len(blob) == identities["published_git"]["bytes"], git_path
            count += 1
    assert count == 23, count
    return count


def source_design(contract: dict[str, Any]) -> dict[str, Any]:
    crew = json.loads((CASE / "crew-input.json").read_text(encoding="utf-8-sig"))
    radio = json.loads((CASE / "radio-input.json").read_text(encoding="utf-8-sig"))
    ctab = tables(crew, "model")
    rtab = tables(radio, "model")
    assert set(ctab) == set(rtab) and len(ctab) == 33
    different = [name for name in ctab if ctab[name] != rtab[name]]
    assert set(different) == {"ProblemDescription", "MissionResource"}, different
    assert len([t for t in ctab.values() if rows(t)]) == 24
    mission_type = rows(ctab["MissionType"])
    assert len(mission_type) == 1
    assert mission_type[0][1][0] == "SHARED-CONFIG-MISSION"
    assert mission_type[0][1][2:4] == (2, 2), ("mandatory formation", mission_type)
    mission_system = {row[1]: row for _, row in rows(ctab["MissionSystem"])}
    assert set(mission_system) == {"TEACH-CONF-A", "TEACH-CONF-B"}
    assert mission_system["TEACH-CONF-A"][2:5] == (1, 1, 1)
    assert mission_system["TEACH-CONF-B"][2:5] == (2, 1, 1), ("contract B PRI2", mission_system["TEACH-CONF-B"])
    parent_path = ROOT / "cases" / "simlox-air-support" / "A16-two-config-reconfiguration-v1.0.0" / "native-input.json"
    parent = json.loads(parent_path.read_text(encoding="utf-8-sig"))
    ptab = tables(parent, "model")
    assert len(ptab) == 32
    expected_common_changes = {
        "ProblemDescription", "SystemDeployment", "MissionType", "OperationProfile",
        "MissionSystem", "Resource", "ResourceAllocation",
    }
    changed_common = {name for name in ptab if ptab[name] != ctab[name]}
    assert changed_common == expected_common_changes, sorted(changed_common ^ expected_common_changes)
    assert set(ctab) - set(ptab) == {"MissionResource"}
    assert not (set(ptab) - set(ctab))
    assert parent["model"]["database_version"] == crew["model"]["database_version"] == radio["model"]["database_version"]
    prior_deployment = rows(ptab["SystemDeployment"])
    child_deployment = rows(ctab["SystemDeployment"])
    assert len(prior_deployment) == len(child_deployment) == 1
    assert prior_deployment[0][1][2] == 1 and child_deployment[0][1][2] == 2
    assert prior_deployment[0][1][:2] == child_deployment[0][1][:2]
    assert prior_deployment[0][1][3:] == child_deployment[0][1][3:]
    prior_a_type = next(row for _, row in rows(ptab["MissionType"]) if row[0] == "CONF-A-MISSION")
    assert mission_type[0][1][4:] == prior_a_type[4:], "MissionType timing/reliability drift"
    prior_h8 = next(row for _, row in rows(ptab["OperationProfile"]) if row[2] == 8)
    child_h8 = rows(ctab["OperationProfile"])
    assert len(child_h8) == 1 and child_h8[0][1][1] == "SHARED-CONFIG-MISSION"
    assert child_h8[0][1][:1] + child_h8[0][1][2:] == prior_h8[:1] + prior_h8[2:]
    prior_system = {row[1]: row for _, row in rows(ptab["MissionSystem"])}
    for sid in ("TEACH-CONF-A", "TEACH-CONF-B"):
        assert mission_system[sid][1] == prior_system[sid][1]
        assert mission_system[sid][3:] == prior_system[sid][3:], ("MissionSystem non-priority drift", sid)
    radio_control = json.loads((ROOT / "cases" / "simlox-air-support" /
                                "C05-var02-two-resource-types-v1.0.0" / "radio-0-input.json").read_text(encoding="utf-8-sig"))
    control_tables = tables(radio_control, "model")
    assert ctab["Resource"] == control_tables["Resource"]
    assert ctab["ResourceAllocation"] == control_tables["ResourceAllocation"]
    assert ctab["MissionResource"]["columns"] == control_tables["MissionResource"]["columns"]
    cr = rows(ctab["MissionResource"])
    rr = rows(rtab["MissionResource"])
    assert len(cr) == len(rr) == 2
    assert any(tuple(row)[:4] == ("SHARED-CONFIG-MISSION", "TEACH-CONF-A", "MISSION-CREW", 1) for _, row in cr)
    assert any(tuple(row)[:4] == ("SHARED-CONFIG-MISSION", "TEACH-CONF-B", "MISSION-CREW", 1) for _, row in cr)
    assert any(tuple(row)[:4] == ("SHARED-CONFIG-MISSION", "TEACH-CONF-B", "MISSION-RADIO", 1) for _, row in rr)
    # The B key moves; the common A row is byte-value identical.
    assert set(cr) ^ set(rr) == {
        ("", ("SHARED-CONFIG-MISSION", "TEACH-CONF-B", "MISSION-CREW", 1, None)),
        ("", ("SHARED-CONFIG-MISSION", "TEACH-CONF-B", "MISSION-RADIO", 1, None)),
    }
    alloc = rows(ctab["ResourceAllocation"])
    assert any(row[1] == "MISSION-CREW" and row[3] == 2 for _, row in alloc)
    assert any(row[1] == "MISSION-RADIO" and row[3] == 0 for _, row in alloc)
    return {"tables": len(ctab), "row_containing": 24,
            "common_changed_tables": sorted(changed_common | {"MissionResource"}),
            "pair_changed_tables": different}


def self_test() -> None:
    fixture = b'{"a":"literal,] and \\\"quoted\\\"","b":[1,2,],}'
    assert json.loads(drop_trailing_commas(fixture)) == {"a": 'literal,] and "quoted"', "b": [1, 2]}
    assert event_blocks(b"Time: 7 first\n  second\nTime: 8 third\n") == [(7.0, " first\n  second"), (8.0, " third")]
    assert compare_cell(1.00001, 1.0, basis="event_fraction")
    assert not compare_cell(1.0003, 1.0, basis="event_fraction")
    assert not compare_cell(1.00001, 1.0, basis="count")
    assert not compare_cell(None, 0, basis="count")
    assert not compare_cell("TEACH-CONF-A", "TEACH-CONF-B", basis="copy")
    assert not compare_cell("1", 1, basis="count")
    synthetic_negative = [
        (7.0, " mission ordered: SHARED-CONFIG-MISSION"),
        (7.0, "<SHARED-CONFIG-MISSION,TEACH-UNIT,0,0,0> mission created:"),
        (7.0, "<SHARED-CONFIG-MISSION,TEACH-UNIT,0,0,0> mission activated, systems requested: 2"),
        (7.0, "<TEACH-AIR-01,1> system resource availability test\n  Availability test on <MISSION-RADIO at <BASE-01,0>> request for: 1 failed"),
        (8.33333, "<SHARED-CONFIG-MISSION,TEACH-UNIT,0,0,0> mission cancelled:"),
    ]
    assert child_event_gate(synthetic_negative, arm="radio")["starts"] == 0
    one_system_launch = synthetic_negative + [(8.0, "<SHARED-CONFIG-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-CONF-A,0>")]
    try:
        child_event_gate(one_system_launch, arm="radio")
    except AssertionError:
        pass
    else:
        raise AssertionError("one-system negative launch escaped")


def tamper_control_report(contract: dict[str, Any]) -> int:
    """Prove representative cells cannot be copied through unchecked."""
    run = Path(contract["accepted_native_runs"]["C05"]["path"])
    pristine = read_native_json(run / "report-raw.json")
    events = event_blocks((run / "model.log").read_bytes())
    source = read_native_json(run / "input.json")
    probes = (
        ("SystemResults", 16, "NSYRY", 1, lambda report: check_system_full_report(report, events, fleet=2, configured_types=0)),
        ("SystemResults", 16, "SYDT", 0, lambda report: check_system_full_report(report, events, fleet=2, configured_types=0)),
        ("StockTotalResults", 14, "NDR", 9, lambda report: check_stock_report(report, events)),
        ("ResourceResults", 14, "NRMA", 1.01, lambda report: check_resource_report(report, events, capacity=2)),
        ("ResourceResultsTotal", 0, "RID", "wrong type", lambda report: check_resource_report(report, events, capacity=2)),
        ("ResultSummary", 0, "MSTF", 0, lambda report: check_summary_report(report, events)),
        ("ProblemDescription", 0, "PDESC", "wrong description", lambda report: check_problem_description(report, source)),
    )
    for name, row_index, column, replacement, checker in probes:
        changed = json.loads(json.dumps(pristine))
        table = tables(changed, "report")[name]
        index = [cell["name"] for cell in table["columns"]].index(column)
        table["instances"][0]["rows"][row_index][index] = replacement
        try:
            checker(changed)
        except AssertionError:
            continue
        raise AssertionError(("tamper escaped", name, row_index, column))
    return len(probes)


def tamper_stock_edges() -> int:
    """Reject wrong opening IDs, demand owners, fit edges and configured launches."""
    fixture = [
        (0.0, "<TEACH-LRU-A,0,BASE-01,0> Stock initiated\n  Stock at: <TEACH-LRU-A,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-A,0,0>,"),
        (0.0, "<TEACH-LRU-B,0,BASE-01,0> Stock initiated\n  Stock at: <TEACH-LRU-B,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-B,0,2>,"),
    ]
    for suffix, base, item_id in (("A", "0", "0"), ("B", "1", "2")):
        fixture += [
            (7.0, f"<TEACH-LRU-{suffix},0,BASE-01,0> Reconfiguration item demand arrives from pos <TEACH-AIR-01,BASE-01,{base}>"),
            (7.0, f"<TEACH-LRU-{suffix},0,BASE-01,0> Take replacement item <TEACH-LRU-{suffix},0,{item_id}> from stock"),
            (7.0, f"<TEACH-AIR-01,{base}> reconfig started, mission: <SHARED-CONFIG-MISSION,TEACH-UNIT,0,0,0>"),
            (7.0, f" system reconfig fit task {base} on <TEACH-AIR-01,{base}> started"),
            (7.33333, f" system reconfig fit task {base} on <TEACH-AIR-01,{base}> completed"),
            (7.33333, f"<TEACH-AIR-01,{base}> reconfig ended, mission: <SHARED-CONFIG-MISSION,TEACH-UNIT,0,0,0>"),
            (7.33333, f"<TEACH-CONF-{suffix},0> preparation started, mission: <SHARED-CONFIG-MISSION,TEACH-UNIT,0,0,0>"),
        ]
    fixture.append((8.0, "<SHARED-CONFIG-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-CONF-A,0>,<TEACH-CONF-B,0>"))
    child_stock_edges(fixture, arm="crew", trace=stock_trace(fixture))
    substitutions = (
        ("Take replacement item <TEACH-LRU-A,0,0>", "Take replacement item <TEACH-LRU-A,0,9>"),
        ("from pos <TEACH-AIR-01,BASE-01,1>", "from pos <TEACH-AIR-01,BASE-01,0>"),
        ("system reconfig fit task 0 on <TEACH-AIR-01,0> completed", "system reconfig fit task 0 on <TEACH-AIR-01,1> completed"),
        ("<TEACH-CONF-A,0> preparation started", "<TEACH-CONF-A,9> preparation started"),
    )
    for old, new in substitutions:
        changed = [(hour, body.replace(old, new)) for hour, body in fixture]
        assert changed != fixture, old
        try:
            child_stock_edges(changed, arm="crew", trace=stock_trace(changed))
        except AssertionError:
            continue
        raise AssertionError(("stock-edge tamper escaped", old))
    return len(substitutions)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true", help="check parsers, frozen contract, controls and draft source without native")
    args = parser.parse_args()
    if not args.self_check:
        raise SystemExit("postrun replay awaits exact frozen manifest and immutable child raw closures")
    self_test()
    assert sha_size(CASE / "contract.json")[0] == CONTRACT_SHA
    contract = json.loads((CASE / "contract.json").read_text(encoding="utf-8-sig"))
    source_pins = accepted_source_bytes(contract)
    controls = accepted_controls(contract)
    design = source_design(contract)
    tamper_probes = tamper_control_report(contract) + tamper_stock_edges()
    print(json.dumps({"status": "PREP_ONLY", "contract_sha256": CONTRACT_SHA,
                      "accepted_source_pins": source_pins, "controls": controls,
                      "design": design, "tamper_probes_rejected": tamper_probes},
                     sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
