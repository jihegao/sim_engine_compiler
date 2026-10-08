"""Bounded, read-only classifier of the accepted I04.var01 return/transfer trace."""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

from source_gate import CASE, PARENT, RECOVERY, exact, load, verify

RUN = "i04-var01-system-between-v100-ssh-20261005-01"
LOG = (8158, "e9c2bbc20a9496c1ce72f3e4c2806c94d1a52ab8ee409a37ea790bc98eca1c8f")
REPORT = (103974, "f1cd6496d7fbdeda3f6deb7d57ee16f762db27984e0aa27e13b16bc9715375b3")
INPUT = (44614, "50cc69df36afa0cecbbf8e6e7d699012f8987bb06bee11a1e347235d397da0ea")
SIGNATURE = (15315, "0f70dffabfe3f8c82f2495674b298eed2f174cdbe672b9e6ceac37ad05b995db")
MID = {0: "BASIC-MISSION,TEACH-GROUP,0,0,0", 1: "BASIC-MISSION,TEACH-GROUP,0,0,1"}
UNIT = {0: "TEACH-UNIT", 1: "TEACH-UNIT-2"}
BASE = {0: "BASE-01", 1: "BASE-02"}
SYS = "TEACH-AIR-01"
COUNT = {
    # Every timed record must be recognized, including diagnostics.
    "failure_clock": 19, "ready_inc": 7, "ready_dec": 5,
    "ready_list": 6, "start_day": 2, "mission_ordered": 2,
    "mission_created": 2, "mission_activated": 2, "allocates": 4,
    "release_excess": 4, "preparation_started": 4, "preparation_ended": 4,
    "mission_starting": 2, "task_start": 2, "task_completed": 2,
    "mission_success": 2, "mission_completed": 2, "soon_ready": 4,
    "turnround_started": 4, "turnround_ended": 4, "system_arrives": 4,
    "system_ready": 10, "transfer_out": 1, "transfer_in": 1,
    "repair_priority": 4,
}


def aircraft(value: str) -> int:
    m = re.fullmatch(r"<TEACH-AIR-01,([01])>", value)
    assert m, f"invalid physical aircraft: {value}"
    return int(m.group(1))


def mission(value: str) -> int:
    assert value.startswith("<") and value.endswith(">")
    inner = value[1:-1]
    assert inner in MID.values(), f"wrong mission identity: {inner}"
    return 0 if inner == MID[0] else 1


def unit_descriptor(value: str) -> int:
    m = re.fullmatch(r"<(TEACH-UNIT(?:-2)?) at <(BASE-0[12]),0>>", value)
    assert m, f"wrong unit descriptor: {value}"
    index = 0 if m.group(1) == UNIT[0] else 1
    assert m.group(2) == BASE[index]
    return index


def station_descriptor(value: str) -> int:
    m = re.fullmatch(r"<TEACH-AIR-01,(BASE-0[12]),0>", value)
    assert m, f"wrong outer station descriptor: {value}"
    return 0 if m.group(1) == BASE[0] else 1


def classify_message(message: str) -> tuple[str, dict]:
    """Consume one complete native timed line; unknown grammar is an error."""
    s = message.strip()
    m = re.fullmatch(r"(<TEACH-AIR-01,[01]>) Next random failure will occur 1e\+010", s)
    if m: return "failure_clock", {"id": aircraft(m.group(1))}
    m = re.fullmatch(r"(<TEACH-AIR-01,[01]>) nbr ready (increased|decreased) at unit: (<TEACH-UNIT(?:-2)? at <BASE-0[12],0>>)", s)
    if m: return ("ready_inc" if m.group(2) == "increased" else "ready_dec"), {"id": aircraft(m.group(1)), "unit": unit_descriptor(m.group(3))}
    m = re.fullmatch(r"(<TEACH-UNIT(?:-2)? at <BASE-0[12],0>>) systems ready: ([12]) :(.+)", s)
    if m:
        ids = tuple(aircraft(v) for v in re.findall(r"<TEACH-AIR-01,[01]>", m.group(3)))
        assert ",".join(f"<{SYS},{i}>" for i in ids) == m.group(3)
        assert len(ids) == int(m.group(2)) and len(set(ids)) == len(ids)
        return "ready_list", {"unit": unit_descriptor(m.group(1)), "ids": ids}
    m = re.fullmatch(r"Start of day no ([01])", s)
    if m: return "start_day", {"day": int(m.group(1))}
    m = re.fullmatch(r"<TEACH-GROUP> mission ordered: BASIC-MISSION", s)
    if m: return "mission_ordered", {}
    m = re.fullmatch(r"(<BASIC-MISSION,TEACH-GROUP,0,0,[01]>) mission created:", s)
    if m: return "mission_created", {"mission": mission(m.group(1))}
    m = re.fullmatch(r"(<BASIC-MISSION,TEACH-GROUP,0,0,[01]>) mission activated, systems requested: 2", s)
    if m: return "mission_activated", {"mission": mission(m.group(1))}
    m = re.fullmatch(r"(<BASIC-MISSION,TEACH-GROUP,0,0,[01]>) mission allocates system: (<TEACH-AIR-01,[01]>)", s)
    if m: return "allocates", {"mission": mission(m.group(1)), "id": aircraft(m.group(2))}
    m = re.fullmatch(r"(<TEACH-AIR-01,[01]>) releases excess resources \(if any\)", s)
    if m: return "release_excess", {"id": aircraft(m.group(1))}
    m = re.fullmatch(r"(<TEACH-AIR-01,[01]>) preparation (started|ended), mission: (<BASIC-MISSION,TEACH-GROUP,0,0,[01]>)", s)
    if m: return ("preparation_started" if m.group(2) == "started" else "preparation_ended"), {"id": aircraft(m.group(1)), "mission": mission(m.group(3))}
    m = re.fullmatch(r"(<BASIC-MISSION,TEACH-GROUP,0,0,[01]>) mission starting, duration: 2 : (<TEACH-AIR-01,[01]>),(<TEACH-AIR-01,[01]>)", s)
    if m: return "mission_starting", {"mission": mission(m.group(1)), "ids": (aircraft(m.group(2)), aircraft(m.group(3)))}
    m = re.fullmatch(r"(<BASIC-MISSION,TEACH-GROUP,0,0,[01]>) task (starting|completed): (<TEACH-AIR-01,[01]>),(<TEACH-AIR-01,[01]>)", s)
    if m: return ("task_start" if m.group(2) == "starting" else "task_completed"), {"mission": mission(m.group(1)), "ids": (aircraft(m.group(3)), aircraft(m.group(4)))}
    m = re.fullmatch(r"(<BASIC-MISSION,TEACH-GROUP,0,0,[01]>) mission success:", s)
    if m: return "mission_success", {"mission": mission(m.group(1))}
    m = re.fullmatch(r"(<BASIC-MISSION,TEACH-GROUP,0,0,[01]>) mission completed: (<TEACH-AIR-01,[01]>),(<TEACH-AIR-01,[01]>)", s)
    if m: return "mission_completed", {"mission": mission(m.group(1)), "ids": (aircraft(m.group(2)), aircraft(m.group(3)))}
    m = re.fullmatch(r"(<TEACH-AIR-01,BASE-0[12],0>) System soon ready (<TEACH-AIR-01,[01]>), estimated remaining time: 0", s)
    if m: return "soon_ready", {"base": station_descriptor(m.group(1)), "id": aircraft(m.group(2))}
    m = re.fullmatch(r"(<TEACH-AIR-01,[01]>) turnround (started|ended), mission: (<BASIC-MISSION,TEACH-GROUP,0,0,[01]>)(?: reduction factor: 1)?", s)
    if m: return ("turnround_started" if m.group(2) == "started" else "turnround_ended"), {"id": aircraft(m.group(1)), "mission": mission(m.group(3))}
    m = re.fullmatch(r"(<TEACH-AIR-01,BASE-0[12],0>) System arrives (<TEACH-AIR-01,[01]>), mission success,", s)
    if m: return "system_arrives", {"base": station_descriptor(m.group(1)), "id": aircraft(m.group(2))}
    m = re.fullmatch(r"(<TEACH-AIR-01,BASE-0[12],0>) System ready (<TEACH-AIR-01,[01]>)", s)
    if m: return "system_ready", {"base": station_descriptor(m.group(1)), "id": aircraft(m.group(2))}
    m = re.fullmatch(r"(<TEACH-UNIT(?:-2)? at <BASE-0[12],0>>) system transfered (out|in): (<TEACH-AIR-01,[01]>)\.", s)
    if m: return ("transfer_out" if m.group(2) == "out" else "transfer_in"), {"unit": unit_descriptor(m.group(1)), "id": aircraft(m.group(3))}
    m = re.fullmatch(r"(<TEACH-AIR-01,BASE-0[12],0>) Repair task priority list:", s)
    if m: return "repair_priority", {"base": station_descriptor(m.group(1))}
    raise AssertionError(f"unrecognized native event: {s}")


def semantic_log(data: bytes, *, check_signature: bool = True,
                 include_signature: bool = False) -> dict:
    lines = data.decode("ascii").splitlines()
    assert len(lines) == 117 and lines[:2] == ["SIMLOX LOG FILE", "36"]
    events = []
    continuation = collections.Counter()
    continuation_positions = []
    pending_continuation: list[str] = []
    for position, line in enumerate(lines[2:], start=3):
        m = re.fullmatch(r"Time: (\d+(?:\.\d+)?) (.*)", line)
        if m:
            assert not pending_continuation, (position, pending_continuation)
            hour = float(m.group(1))
            kind, fields = classify_message(m.group(2))
            events.append((hour, kind, fields, position))
            if kind == "system_arrives":
                pending_continuation = [" no failures ", " no PMTasks"]
            elif kind == "repair_priority":
                pending_continuation = ["   "]
        else:
            assert pending_continuation and line == pending_continuation.pop(0), (position, line)
            continuation[line] += 1
            continuation_positions.append({"line": position, "text": line})
    assert not pending_continuation
    assert len(events) == 103 and continuation == {" no failures ": 4, " no PMTasks": 4, "   ": 4}
    assert all(events[i][0] <= events[i + 1][0] for i in range(len(events) - 1))
    assert collections.Counter(k for _, k, _, _ in events) == COUNT

    # Physical ledger. The inner <TEACH-AIR-01,ID> is physical identity;
    # the outer <TEACH-AIR-01,BASE,0> is a station/controller descriptor.
    state = {0: {"unit": 0, "ready": False, "mission": None, "turnround": False, "returned": False},
             1: {"unit": 1, "ready": False, "mission": None, "turnround": False, "returned": False}}
    assigned = {0: [], 1: []}
    mission_phase = {0: None, 1: None}
    preparing = {0: set(), 1: set()}
    prepared = {0: set(), 1: set()}
    ready_prints = collections.Counter()
    seen = collections.Counter()
    critical = []
    for hour, kind, f, pos in events:
        seen[kind] += 1
        if kind == "ready_inc":
            s = state[f["id"]]
            assert s["unit"] == f["unit"] and not s["ready"] and s["mission"] is None
            assert seen["ready_inc"] <= 7
            assert (hour, f["id"], f["unit"]) == [
                (0, 0, 0), (0, 1, 1), (10, 0, 0), (10, 1, 1),
                (10.5, 0, 1), (22, 1, 1), (22, 0, 1)][seen["ready_inc"] - 1]
            if hour != 0:
                assert s["returned"] or (hour == 10.5 and f["id"] == 0 and s["unit"] == 1)
            s["ready"] = True
        elif kind == "ready_dec":
            s = state[f["id"]]
            assert s["unit"] == f["unit"] and s["ready"]
            s["ready"] = False
            assert hour in (7, 10, 19)
        elif kind == "allocates":
            mid, aid = f["mission"], f["id"]
            assert hour == (7 if mid == 0 else 19)
            assert mission_phase[mid] == "activated"
            assert state[aid]["ready"] and state[aid]["mission"] is None
            assert aid not in assigned[mid]
            assigned[mid].append(aid)
            state[aid]["mission"] = mid
            state[aid]["returned"] = False
        elif kind == "turnround_started":
            s = state[f["id"]]
            assert s["mission"] == f["mission"] and not s["turnround"] and hour in (10, 22)
            assert mission_phase[f["mission"]] == "completed"
            s["turnround"] = True
        elif kind == "turnround_ended":
            s = state[f["id"]]
            assert s["turnround"] and s["mission"] == f["mission"] and hour in (10, 22)
            s["turnround"] = False
            critical.append((hour, kind, f["id"], s["unit"]))
        elif kind == "system_arrives":
            s = state[f["id"]]
            assert not s["turnround"] and s["mission"] is not None
            assert s["unit"] == f["base"] and hour in (10, 22)
            s["mission"] = None
            s["returned"] = True
            critical.append((hour, kind, f["id"], f["base"]))
        elif kind == "system_ready":
            s = state[f["id"]]
            assert s["unit"] == f["base"] and s["ready"] and s["mission"] is None
            ready_prints[(hour, f["id"], f["base"])] += 1
            assert ready_prints[(hour, f["id"], f["base"])] <= 2
            critical.append((hour, kind, f["id"], f["base"]))
        elif kind == "transfer_out":
            s = state[f["id"]]
            assert (hour, f["id"], f["unit"]) == (10, 0, 0)
            assert s["unit"] == 0 and not s["ready"] and s["mission"] is None
            assert ready_prints[(10, 0, 0)] == 2 and s["returned"] and not s["turnround"]
            s["unit"] = None  # physical transit, not target occupancy
            s["returned"] = False
            critical.append((hour, kind, f["id"], f["unit"]))
        elif kind == "transfer_in":
            s = state[f["id"]]
            assert (hour, f["id"], f["unit"]) == (10.5, 0, 1)
            assert s["unit"] is None and not s["ready"] and s["mission"] is None
            s["unit"] = 1
            critical.append((hour, kind, f["id"], f["unit"]))
        elif kind == "ready_list":
            assert seen["ready_list"] <= 6
            assert (hour, f["unit"], f["ids"]) == [
                (0, 0, (0,)), (0, 1, (1,)), (10, 1, (1,)),
                (10.5, 1, (1, 0)), (22, 1, (1,)), (22, 1, (1, 0))][seen["ready_list"] - 1]
            assert set(i for i, s in state.items() if s["unit"] == f["unit"] and s["ready"]) == set(f["ids"])
        elif kind in ("mission_starting", "task_start", "task_completed", "mission_completed"):
            mid = f["mission"]
            assert set(f["ids"]) == set(assigned[mid]) == {0, 1}
            assert hour == {"mission_starting": 8 if mid == 0 else 20,
                            "task_start": 8.5 if mid == 0 else 20.5,
                            "task_completed": 9.5 if mid == 0 else 21.5,
                            "mission_completed": 10 if mid == 0 else 22}[kind]
            if kind == "mission_starting":
                assert mission_phase[mid] == "activated" and prepared[mid] == {0, 1}
                mission_phase[mid] = "started"
            elif kind == "task_start":
                assert mission_phase[mid] == "started"
                mission_phase[mid] = "task_started"
            elif kind == "task_completed":
                assert mission_phase[mid] == "task_started"
                mission_phase[mid] = "task_completed"
            else:
                assert mission_phase[mid] == "succeeded"
                mission_phase[mid] = "completed"
        elif kind == "mission_success":
            assert hour == (10 if f["mission"] == 0 else 22)
            assert mission_phase[f["mission"]] == "task_completed"
            mission_phase[f["mission"]] = "succeeded"
        elif kind == "start_day":
            assert (hour, f["day"]) in ((0, 0), (24, 1))
        elif kind == "repair_priority":
            assert (hour, f["base"]) in ((10, 0), (10, 1), (22, 1))
        elif kind == "soon_ready":
            s = state[f["id"]]
            assert s["unit"] == f["base"] and s["mission"] is not None and hour in (10, 22)
            assert mission_phase[s["mission"]] == "completed"
        elif kind == "release_excess":
            assert state[f["id"]]["mission"] is not None and hour in (7, 19)
        elif kind == "preparation_started":
            mid, aid = f["mission"], f["id"]
            assert state[aid]["mission"] == mid and hour in (7, 19)
            assert mission_phase[mid] == "activated" and aid in assigned[mid]
            assert aid not in preparing[mid] and aid not in prepared[mid]
            preparing[mid].add(aid)
        elif kind == "preparation_ended":
            mid, aid = f["mission"], f["id"]
            assert state[aid]["mission"] == mid and hour in (7, 19)
            assert aid in preparing[mid] and aid not in prepared[mid]
            preparing[mid].remove(aid)
            prepared[mid].add(aid)
        elif kind in ("mission_created", "mission_activated"):
            assert hour == (7 if f["mission"] == 0 else 19)
            mid = f["mission"]
            if kind == "mission_created":
                assert mission_phase[mid] == "ordered"
                mission_phase[mid] = "created"
            else:
                assert mission_phase[mid] == "created"
                mission_phase[mid] = "activated"
        elif kind == "mission_ordered":
            assert hour in (7, 19)
            mid = 0 if hour == 7 else 1
            assert mission_phase[mid] is None
            mission_phase[mid] = "ordered"
        # failure clocks are bounded by the complete accepted byte pin and grammar.
        assert len(state) == 2
        assert sum(s["unit"] is None for s in state.values()) <= 1
    assert assigned == {0: [0, 1], 1: [1, 0]}
    assert mission_phase == {0: "completed", 1: "completed"}
    assert preparing == {0: set(), 1: set()} and prepared == {0: {0, 1}, 1: {0, 1}}
    assert state[0] == {"unit": 1, "ready": True, "mission": None, "turnround": False, "returned": True}
    assert state[1] == {"unit": 1, "ready": True, "mission": None, "turnround": False, "returned": True}
    assert ready_prints == {(10, 0, 0): 2, (10, 1, 1): 2, (10.5, 0, 1): 2,
                            (22, 1, 1): 2, (22, 0, 1): 2}
    assert critical[:6] == [(10, "turnround_ended", 0, 0), (10, "system_arrives", 0, 0),
                            (10, "system_ready", 0, 0), (10, "system_ready", 0, 0),
                            (10, "transfer_out", 0, 0), (10, "turnround_ended", 1, 1)]
    assert (10.5, "transfer_in", 0, 1) in critical
    signature = {"schema": "i04-var06-author-event-signature/v100",
                 "timed": [{"line": pos, "hour": hour, "kind": kind,
                            "fields": json.loads(json.dumps(fields))}
                           for hour, kind, fields, pos in events],
                 "continuations": continuation_positions}
    if check_signature:
        expected = load(exact(CASE / "source-maps/event-signature.json", SIGNATURE))
        assert signature == expected, "complete ordered event signature differs"
    result = {"lines": len(lines), "timed": len(events), "first_mission_assigned": assigned[0],
            "second_mission_assigned": assigned[1], "terminal_ready": 2,
            "transfer_departure": 10, "transfer_arrival": 10.5,
            "physical_transit_duration": 0.5, "turnround_duration_observed": 0}
    if include_signature:
        result["signature"] = signature
    return result


def selected_report_object(parsed: dict) -> dict:
    tables = parsed["report"]["tables"]
    assert [t["name"] for t in tables] == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"]
    t = tables[2]
    assert t["instances"][0]["instance_name"] == "Total over all Units;Total over all Systems;0.00;36.00"
    cols = [c["name"] for c in t["columns"]]
    assert len(cols) == 40 and len(t["instances"][0]["rows"]) == 72
    values = []
    for rownum, expected in ((20, (10, 10.5, 1, 0, 0, 1)),
                             (21, (10.5, 11, 2, 0, 0, 2))):
        row = t["instances"][0]["rows"][rownum]
        actual = tuple(row[cols.index(c)] for c in ("STINT", "ETINT", "NSYRY", "NSYMA", "NSYMO", "NSYA"))
        assert len(row) == 40 and all(type(v) in (int, float) for v in actual)
        assert actual == expected, (rownum, actual)
        assert row[0:2] == ["Total over all Units", "Total over all Systems"]
        values.append({"row": rownum, "STINT": actual[0], "ETINT": actual[1],
                       "NSYRY": actual[2], "NSYMA": actual[3], "NSYMO": actual[4], "NSYA": actual[5]})
    return {"selected_system_results": values, "full_report_acceptance_inherited": True}


def selected_report(data: bytes) -> dict:
    # The accepted exporter emitted one trailing comma before its final table
    # array close. Repair only a private in-memory byte string, never the file.
    suffix = b"},\r\n      ]\r\n   }\r\n}\r\n"
    assert data.endswith(suffix) and data.count(suffix) == 1
    at = data.rfind(b",")
    assert at == len(data) - len(suffix) + 1
    parsed = load(data[:at] + data[at + 1:])
    return selected_report_object(parsed)


def source_transfer(model: dict) -> dict:
    tables = model["model"]["tables"]
    found = [t for t in tables if t["name"] == "SystemTransfer"]
    assert len(found) == 1
    table = found[0]
    assert [(c["name"], c["datatype"], c.get("key", False)) for c in table["columns"]] == [
        ("UFID", "string", True), ("UTID", "string", True),
        ("SID", "string", True), ("TFTIME", "double", True),
        ("TFQTY", "integer", False), ("TFDT", "double", False),
        ("TFPRI", "integer", False), ("NOTE", "string", False)]
    assert len(table["instances"]) == 1
    assert table["instances"][0]["instance_name"] == ""
    rows = table["instances"][0]["rows"]
    assert len(rows) == 1
    assert rows[0] == ["TEACH-UNIT", "TEACH-UNIT-2", "TEACH-AIR-01", 8.5, 1, 0.5, None, None]
    assert type(rows[0][3]) is float and type(rows[0][4]) is int and type(rows[0][5]) is float
    return {"request_time_source_frozen": 8.5, "quantity": 1, "transit_delay": 0.5,
            "request_logged": False}


def sealed() -> dict:
    custody = verify()
    source = source_transfer(load(exact(PARENT / "between-input.json", INPUT)))
    log = exact(RECOVERY / "raw/between.log", LOG)
    report = exact(RECOVERY / "raw/between-report-raw.json", REPORT)
    return {"schema": "i04-var06-author-classification/v100", "decision": "BOUNDED_RETURN_COMPLETE_TRANSFER_CLASSIFICATION",
            "native_calls": 0, "accepted_parent_checker_reruns": 0,
            "custody": custody, "source": source, "semantic": semantic_log(log), "report": selected_report(report),
            "limits": "Return/zero-duration-turnround branch only; h8.5 request source-frozen, not separately logged; no maintenance or simultaneous-mission priority claim."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sealed", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps(sealed(), sort_keys=True))
