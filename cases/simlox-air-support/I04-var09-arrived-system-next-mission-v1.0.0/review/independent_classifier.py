"""Independent, read-only I04.var09 classification of one accepted original run.

This module does not import or invoke an accepted SIMLOX checker. The sealed
entry point verifies original bytes separately from the semantic parser; pure
mutations call the parser directly to test its causal predicates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[2]
PARENT = ROOT / "cases/simlox-air-support/I04-var03-idle-system-between-v1.0.1"
RUN = PARENT / "runs/i04-var03-idle-system-between-v101-ssh-20261008-01"
CONTRACT_SHA = "ec2dbe37601d0045185109fe7856ea4656a0b2e01dfe35ac25809de17aa60307"
LOG_SHA = "ab19c3cbc0214b8e72b57d6139d94166beb99f1afa034e07de393693d1079901"
REPORT_SHA = "72a5bd7270f5b3b27736df43c146a56f850990abf6a8e964aa7bae430ffc93b5"
PARENT_INDEX_SHA = "09e0fe50532797f97d13b3a17fdd886adfc9a18c925038b15058b3850b2273ff"
PARENT_MANIFEST_SHA = "d05541613248279a5620349ade72bcaf80b12f3be042b470694f45b6efa690f3"
PARENT_GO_SHA = "d5b7ea964e65ddb57d248562dab82f53bce565f6d0ac7a161c4eccc5b8ebf7c7"
BASE_COMMIT = "223c32e36722587bad5d1d5e8564faee84b91206"
VAR05 = ROOT / "cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.2"
SRC = "<TEACH-UNIT at <BASE-01,0>>"
DST = "<TEACH-UNIT-2 at <BASE-02,0>>"
AIR = r"<TEACH-AIR-01,([01])>"
MISSION = r"<BASIC-MISSION,TEACH-GROUP,0,0,([01])>"
UNIT = rf"({re.escape(SRC)}|{re.escape(DST)})"
HEAD = r"<TEACH-AIR-01,BASE-(01|02),0>"
AIR_LIST = rf"{AIR}(?:,{AIR})?"
TIMED = re.compile(r"Time: ([0-9]+(?:\.[0-9]+)?) (.*)")


def require(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pinned(path: Path, size: int, digest: str) -> bytes:
    data = path.read_bytes()
    require(len(data) == size and sha(data) == digest, f"byte pin: {path}")
    return data


def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> None:
    raise AssertionError(f"nonfinite JSON constant {value}")


def strict_json(data: bytes) -> dict[str, object]:
    obj = json.loads(data, object_pairs_hook=unique, parse_constant=reject_constant)

    def finite(value: object) -> None:
        if isinstance(value, float):
            require(math.isfinite(value), "nonfinite JSON exponent")
        elif isinstance(value, dict):
            for child in value.values():
                finite(child)
        elif isinstance(value, list):
            for child in value:
                finite(child)

    finite(obj)
    require(type(obj) is dict, "top-level JSON object")
    return obj


def match(pattern: str, text: str) -> re.Match[str] | None:
    return re.fullmatch(pattern, text)


def ids(text: str) -> tuple[int, ...]:
    tokens = re.findall(AIR, text)
    require(tokens and len(tokens) <= 2, "aircraft list count")
    require(",".join(f"<TEACH-AIR-01,{token}>" for token in tokens) == text, "aircraft list grammar")
    values = tuple(int(token) for token in tokens)
    require(len(values) == len(set(values)), "duplicate aircraft in list")
    return values


def unit(text: str) -> str:
    require(text in (SRC, DST), "unit grammar")
    return "source" if text == SRC else "target"


def header(base: str) -> str:
    require(base in ("01", "02"), "base grammar")
    return "source" if base == "01" else "target"


def allocation_allowed(owner: str | None, is_ready: bool, assignment: int | None,
                       in_flight: bool, in_task: bool, in_turnround: bool) -> bool:
    """Explicit roster/mission separation, also exercised directly by pure clones."""
    return (owner in ("source", "target") and is_ready and assignment is None
            and not in_flight and not in_task and not in_turnround)


def decode_event(body: str) -> tuple[str, dict[str, object]]:
    """Closed grammar for every timed line of this one accepted transcript."""
    m = match(rf"{AIR} Next random failure will occur 1e\+010", body)
    if m:
        return "failure_clock", {"id": int(m[1])}
    m = match(rf"{AIR} nbr ready (increased|decreased) at unit: {UNIT}", body)
    if m:
        return f"ready_{m[2]}", {"id": int(m[1]), "unit": unit(m[3])}
    m = match(rf"{UNIT} systems ready: ([012]) :(.*)", body)
    if m:
        roster = () if not m[3] else ids(m[3])
        return "ready_roster", {"unit": unit(m[1]), "count": int(m[2]), "ids": roster}
    m = match(r" Start of day no ([01])", body)
    if m:
        return "day", {"day": int(m[1])}
    if body == "<TEACH-GROUP> mission ordered: BASIC-MISSION":
        return "mission_ordered", {}
    m = match(rf"{MISSION} mission created: ", body)
    if m:
        return "mission_created", {"mission": int(m[1])}
    m = match(rf"{MISSION} mission activated, systems requested: 2", body)
    if m:
        return "mission_activated", {"mission": int(m[1])}
    m = match(rf"{MISSION} mission allocates system: {AIR}", body)
    if m:
        return "allocates", {"mission": int(m[1]), "id": int(m[2])}
    m = match(rf"{AIR} releases excess resources \(if any\)", body)
    if m:
        return "release_excess", {"id": int(m[1])}
    m = match(rf"{AIR} preparation (started|ended), mission: {MISSION}", body)
    if m:
        return f"prep_{m[2]}", {"id": int(m[1]), "mission": int(m[3])}
    m = match(rf"{MISSION} mission starting, duration: 2 : (.*)", body)
    if m:
        return "mission_start", {"mission": int(m[1]), "ids": ids(m[2])}
    m = match(rf"{MISSION} task (starting|completed): (.*)", body)
    if m:
        return f"task_{m[2]}", {"mission": int(m[1]), "ids": ids(m[3])}
    m = match(rf"{MISSION} mission success: ", body)
    if m:
        return "mission_success", {"mission": int(m[1])}
    m = match(rf"{MISSION} mission completed: (.*)", body)
    if m:
        return "mission_completed", {"mission": int(m[1]), "ids": ids(m[2])}
    m = match(rf"{HEAD} System soon ready {AIR}, estimated remaining time: 0", body)
    if m:
        return "soon_ready", {"unit": header(m[1]), "id": int(m[2])}
    m = match(rf"{AIR} turnround (started|ended), mission: {MISSION}(?: reduction factor: 1)?", body)
    if m:
        require((m[2] == "started") == body.endswith(" reduction factor: 1"), "turnround suffix")
        return f"turn_{m[2]}", {"id": int(m[1]), "mission": int(m[3])}
    m = match(rf"{HEAD} System arrives {AIR}, mission success, ", body)
    if m:
        return "system_arrives", {"unit": header(m[1]), "id": int(m[2])}
    m = match(rf"{HEAD} System ready {AIR}", body)
    if m:
        return "system_ready", {"unit": header(m[1]), "id": int(m[2])}
    m = match(rf"{HEAD} Repair task priority list: ", body)
    if m:
        return "repair_list", {"unit": header(m[1])}
    m = match(rf"{UNIT} system transfered (out|in): {AIR}\.", body)
    if m:
        return f"transfer_{m[2]}", {"unit": unit(m[1]), "id": int(m[3])}
    raise AssertionError(f"unknown timed log line: {body!r}")


def parse_log(data: bytes, *, exact_original: bool) -> dict[str, object]:
    if exact_original:
        require(len(data) == 8223 and sha(data) == LOG_SHA, "original log byte pin")
    require(data.startswith(b"SIMLOX LOG FILE\r\n36\r\n"), "log header/horizon")
    lines = data.decode("utf-8").splitlines()
    require(len(lines) == 118 and lines[:2] == ["SIMLOX LOG FILE", "36"], "full log shape")
    owner: dict[int, str | None] = {0: None, 1: None}
    ready = {0: False, 1: False}
    assigned: dict[int, int | None] = {0: None, 1: None}
    flight = {0: False, 1: False}
    task = {0: False, 1: False}
    turn = {0: False, 1: False}
    prep = {0: "none", 1: "none"}
    missions = {0: "none", 1: "none"}
    task_done = {0: False, 1: False}
    pending_dec: int | None = None
    pending_out: int | None = None
    ready_announcements: dict[tuple[int, float], int] = {}
    return_arrivals: dict[tuple[int, float], int] = {}
    priority_stations: dict[tuple[float, str], int] = {}
    pending_order: int | None = None
    order_count = 0
    day_count = 0
    transfer_out = transfer_in = timed_count = 0
    last_hour = -1.0
    index = 2
    while index < len(lines):
        line = lines[index]
        m = TIMED.fullmatch(line)
        require(m is not None, f"untimed/unknown physical line {index+1}")
        hour = float(m[1])
        require(math.isfinite(hour) and hour >= last_hour and hour <= 24, "time order")
        last_hour = hour
        kind, value = decode_event(m[2])
        timed_count += 1
        if pending_dec is not None:
            require(kind == "ready_decreased" and value.get("id") == pending_dec, "allocation ready-decrease microstep")
        if pending_out is not None:
            require(kind == "transfer_out" and value.get("id") == pending_out, "transfer departure microstep")
        ident = value.get("id")
        if kind == "failure_clock":
            require(owner[ident] is not None or hour == 0, "failure clock before deployment")
        elif kind == "ready_increased":
            u = value["unit"]
            require(not ready[ident] and assigned[ident] is None and not flight[ident] and not task[ident], "ready increment state")
            if owner[ident] is None:
                require(hour == 0 and u == ("source" if ident == 0 else "target"), "initial roster")
                owner[ident] = u
            else:
                require(owner[ident] == u, "ready increment owner")
                require(hour in (10, 11, 22), "ready increment hour")
            ready[ident] = True
        elif kind == "ready_decreased":
            require(ready[ident] and owner[ident] == value["unit"], "ready decrement state/owner")
            ready[ident] = False
            if pending_dec is not None:
                require(assigned[ident] is not None, "decrement allocation")
                pending_dec = None
            else:
                require((ident, hour, value["unit"], assigned[ident]) == (0, 10.5, "source", None), "decrement only for transfer")
                pending_out = ident
        elif kind == "ready_roster":
            roster = {ident for ident in (0, 1) if ready[ident] and owner[ident] == value["unit"]}
            require(value["count"] == len(roster) and set(value["ids"]) == roster, "ready roster conservation")
        elif kind == "day":
            require((hour, value["day"]) in ((0, 0), (24, 1)), "day marker")
            require(value["day"] == day_count, "duplicate/out-of-order day marker")
            day_count += 1
        elif kind == "mission_ordered":
            require(hour in (7, 19), "mission order hour")
            require(pending_order is None and order_count < 2 and hour == (7 if order_count == 0 else 19), "mission order sequence")
            pending_order = order_count
            order_count += 1
        elif kind == "mission_created":
            mi = value["mission"]
            require((mi, hour, missions[mi]) in ((0, 7, "none"), (1, 19, "none")), "mission creation")
            require(pending_order == mi, "mission creation follows order")
            pending_order = None
            missions[mi] = "created"
        elif kind == "mission_activated":
            mi = value["mission"]
            require(missions[mi] == "created" and hour == (7 if mi == 0 else 19), "mission activation")
            missions[mi] = "active"
        elif kind == "allocates":
            mi = value["mission"]
            require(missions[mi] == "active" and hour == (7 if mi == 0 else 19), "allocation mission/time")
            require(allocation_allowed(owner[ident], ready[ident], assigned[ident],
                                       flight[ident], task[ident], turn[ident]),
                    "allocation requires prior ready at unit, outside transit")
            assigned[ident] = mi
            pending_dec = ident
        elif kind == "release_excess":
            require(assigned[ident] is not None and not ready[ident], "resource release after allocation")
        elif kind == "prep_started":
            require(assigned[ident] == value["mission"] and not ready[ident] and prep[ident] == "none", "preparation start")
            prep[ident] = "started"
        elif kind == "prep_ended":
            require(assigned[ident] == value["mission"] and prep[ident] == "started", "preparation end")
            prep[ident] = "ended"
        elif kind == "mission_start":
            mi = value["mission"]
            require(missions[mi] == "active" and hour == (8 if mi == 0 else 20), "flight mission/time")
            require(set(value["ids"]) == {0, 1}, "flight members")
            for member in value["ids"]:
                require(assigned[member] == mi and prep[member] == "ended" and not ready[member], "flight prior assignment")
                flight[member] = True
            missions[mi] = "flight"
        elif kind == "task_starting":
            mi = value["mission"]
            require(missions[mi] == "flight" and hour == (8.5 if mi == 0 else 20.5), "task start mission/time")
            require(set(value["ids"]) == {0, 1}, "task members")
            for member in value["ids"]:
                require(flight[member] and assigned[member] == mi and not task[member], "task start assignment")
                task[member] = True
        elif kind == "task_completed":
            mi = value["mission"]
            require(missions[mi] == "flight" and hour == (9.5 if mi == 0 else 21.5), "task completion mission/time")
            require(set(value["ids"]) == {0, 1}, "task completion members")
            for member in value["ids"]:
                require(task[member] and assigned[member] == mi, "task completion assignment")
                task[member] = False
            task_done[mi] = True
        elif kind == "mission_success":
            mi = value["mission"]
            require(missions[mi] == "flight" and task_done[mi] and hour == (10 if mi == 0 else 22), "mission success")
            missions[mi] = "success"
        elif kind == "mission_completed":
            mi = value["mission"]
            require(missions[mi] == "success" and hour == (10 if mi == 0 else 22), "mission completion")
            require(set(value["ids"]) == {0, 1}, "mission completion members")
            for member in value["ids"]:
                require(assigned[member] == mi and flight[member] and not task[member], "mission completion assignment")
                assigned[member] = None
                flight[member] = False
                prep[member] = "none"
            missions[mi] = "completed"
        elif kind == "soon_ready":
            require(missions[0 if hour == 10 else 1] == "completed" and owner[ident] == value["unit"] and not ready[ident], "soon ready location")
        elif kind == "turn_started":
            require(missions[value["mission"]] == "completed" and hour == (10 if value["mission"] == 0 else 22), "turnround start")
            require(owner[ident] in ("source", "target") and not ready[ident] and not turn[ident], "turnround state")
            turn[ident] = True
        elif kind == "turn_ended":
            require(turn[ident] and missions[value["mission"]] == "completed", "turnround end")
            turn[ident] = False
        elif kind == "system_arrives":
            require(hour in (10, 22) and owner[ident] == value["unit"] and not ready[ident] and not turn[ident], "mission return location")
            key = (ident, hour)
            require(return_arrivals.get(key, 0) == 0, "duplicate mission return identity")
            return_arrivals[key] = 1
            require(lines[index + 1 : index + 3] == [" no failures ", " no PMTasks"], "arrival continuation grammar")
            index += 2
        elif kind == "system_ready":
            require(ready[ident] and owner[ident] == value["unit"], "ready message location")
            key = (ident, hour)
            ready_announcements[key] = ready_announcements.get(key, 0) + 1
            require(ready_announcements[key] <= 2, "extra ready announcement")
        elif kind == "repair_list":
            station = value["unit"]
            require((hour, station) in ((10, "source"), (10, "target"), (22, "target")), "priority station/time")
            require(any(owner[member] == station and ready[member] for member in owner), "priority station ready owner")
            key = (hour, station)
            priority_stations[key] = priority_stations.get(key, 0) + 1
            require(lines[index + 1] == "   ", "repair-list continuation grammar")
            index += 1
        elif kind == "transfer_out":
            require((ident, hour, value["unit"], owner[ident], ready[ident], assigned[ident]) == (0, 10.5, "source", "source", False, None), "departure identity/order")
            require(pending_out == ident and transfer_out == 0, "departure count")
            owner[ident] = "transit"
            pending_out = None
            transfer_out += 1
        elif kind == "transfer_in":
            require((ident, hour, value["unit"], owner[ident], ready[ident]) == (0, 11, "target", "transit", False), "arrival identity/order")
            require(transfer_out == 1 and transfer_in == 0, "arrival count")
            owner[ident] = "target"
            transfer_in += 1
        else:
            raise AssertionError(f"unhandled event kind {kind}")
        index += 1
    require(timed_count == 104, "timed event count")
    require(order_count == 2 and pending_order is None and day_count == 2, "mission/day terminal count")
    require(transfer_out == transfer_in == 1, "one balanced transfer")
    require(return_arrivals == {(0, 10.0): 1, (1, 10.0): 1, (0, 22.0): 1, (1, 22.0): 1}, "balanced per-ID mission returns")
    require(ready_announcements == {(0, 10.0): 2, (1, 10.0): 2, (0, 11.0): 2, (0, 22.0): 2, (1, 22.0): 2}, "exact per-ID ready messages")
    require(priority_stations == {(10.0, "source"): 1, (10.0, "target"): 1, (22.0, "target"): 2}, "priority station conservation")
    require(missions == {0: "completed", 1: "completed"}, "both missions completed")
    require(owner == {0: "target", 1: "target"} and ready == {0: True, 1: True}, "target terminal readiness")
    require(assigned == {0: None, 1: None} and not any(flight.values()) and not any(task.values()) and not any(turn.values()), "terminal task/assignment")
    require(pending_dec is None and pending_out is None, "terminal pending microstep")
    return {"lines": len(lines), "timed": timed_count, "transfer_out": transfer_out, "transfer_in": transfer_in, "terminal_ready_target": 2}


def report_repair(data: bytes) -> bytes:
    positions = list(re.finditer(rb",\s*]", data))
    require(len(positions) == 1, "exactly one declared native punctuation defect")
    pos = positions[0].start()
    require(pos > len(data) - 100 and data[pos : pos + 10] == b",\r\n      ]", "bounded native punctuation location")
    return data[:pos] + data[pos + 1 :]


def typed_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(typed_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def selected_report(data: bytes, reference: dict[str, object]) -> dict[str, object]:
    obj = strict_json(report_repair(data))
    require(set(obj) == {"report"} and set(obj["report"]) == {"tables"}, "report root shape")
    tables = obj["report"]["tables"]
    ref_tables = reference["report"]["tables"]
    require(type(tables) is list and len(tables) == len(ref_tables) == 4, "report table count")
    names = ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"]
    count = 0
    for table, ref, name in zip(tables, ref_tables, names):
        require(set(table) == {"name", "columns", "instances"} and table["name"] == name, "report table identity")
        require(typed_equal(table["columns"], ref["columns"]), "report column metadata")
        require(type(table["instances"]) is list and len(table["instances"]) == len(ref["instances"]), "report instance count")
        for inst, ref_inst in zip(table["instances"], ref["instances"]):
            require(set(inst) == {"instance_name", "rows"} and typed_equal(inst["instance_name"], ref_inst["instance_name"]), "report instance metadata")
            require(type(inst["rows"]) is list and len(inst["rows"]) == len(ref_inst["rows"]), "report row count")
            for row in inst["rows"]:
                require(type(row) is list and len(row) == len(table["columns"]), "report row width")
            count += len(inst["rows"]) * len(table["columns"])
    require(count == 4044, "report cell topology, prior verdict only")
    system = tables[2]
    cols = {c["name"]: idx for idx, c in enumerate(system["columns"])}
    rows = system["instances"][0]["rows"]
    require(len(rows) == 72, "half-hour result rows")
    expected = {
        21: (10.5, 11, {"NSYA": 1, "NSYRY": 1}),
        22: (11, 11.5, {"NSYA": 2, "NSYRY": 2}),
        38: (19, 19.5, {"NSYA": 2, "NSYMA": 2, "NSYMR": 2, "NSYRY": 0}),
        40: (20, 20.5, {"NSYMO": 2}),
        44: (22, 22.5, {"NSYRY": 2}),
    }
    checks = 0
    for index, (start, end, fields) in expected.items():
        row = rows[index]
        require(type(row[cols["UNID"]]) is str and row[cols["UNID"]] == "Total over all Units", "projection unit identity")
        require(type(row[cols["SID"]]) is str and row[cols["SID"]] == "Total over all Systems", "projection system identity")
        require(type(row[cols["STINT"]]) in (int, float) and row[cols["STINT"]] == start, "projection start")
        require(type(row[cols["ETINT"]]) in (int, float) and row[cols["ETINT"]] == end, "projection end")
        for field, value in fields.items():
            actual = row[cols[field]]
            require(type(actual) is int and actual == value, f"selected report {index}/{field}")
            checks += 1
    return {"prior_report_topology_cells": count, "new_selected_behavior_cells": checks,
            "new_bin_time_cells": 10, "new_row_identity_cells": 10}


def catalog_custody() -> None:
    local_498 = pinned(PACKAGE / "preserved-context/owned-catalog-local-498.json.bytes", 536982,
                       "0674cef00db66d7d907fa4c55cc1249e237c4c60b340740ab81f832405d2de5c")
    git_498 = pinned(PACKAGE / "preserved-context/owned-catalog-git-498.json.bytes", 532311,
                     "47a2615c633895de560db739e15e6fecc665786180cf8ef29f30443a2e666204")
    local_496 = pinned(PARENT / "preserved-context/publication-index-local-496.json.bytes", 532423,
                       "a247e221e524b319f45f62b32a1668366e3e2caf5f066ca79b58ca0838fe59d6")
    git_496 = pinned(PARENT / "preserved-context/publication-index-git-496.json.bytes", 527796,
                     "cecd78d6913a8e75638382f8b2a82c83c6f626394657f200150287df02e0851c")
    require(local_498 != git_498 and local_496 != git_496, "CRLF/LF archives are distinct bytes")
    archive = strict_json(local_498)
    historical = strict_json(local_496)
    require(typed_equal(archive, strict_json(git_498)), "498 local/Git typed catalog")
    require(typed_equal(historical, strict_json(git_496)), "496 local/Git typed catalog")
    require(len(archive["entries"]) == 498 and len(historical["entries"]) == 496, "catalog archive lengths")
    live = strict_json((ROOT / "cases/simlox-air-support/publication-index-v1.json").read_bytes())
    require(set(live) == set(archive) and len(live["entries"]) >= 498, "live catalog shape/prefix length")
    for key in archive:
        if key != "entries":
            require(typed_equal(live[key], archive[key]) and typed_equal(archive[key], historical[key]), "typed catalog metadata")
    require(typed_equal(live["entries"][:498], archive["entries"]), "498 typed catalog prefix")
    require(typed_equal(archive["entries"][:496], historical["entries"]), "496 typed catalog prefix")
    ids = [entry["publication_id"] for entry in live["entries"]]
    require(all(type(item) is str for item in ids) and len(ids) == len(set(ids)), "globally unique catalog publication IDs")
    if len(live["entries"]) == 498:
        require(sha((ROOT / "cases/simlox-air-support/publication-index-v1.json").read_bytes()) == sha(local_498), "preappend live local bytes")


def context_custody() -> None:
    context = strict_json((PACKAGE / "context-custody.json").read_bytes())
    require(context["schema"] == "i04-var09-safe-context-custody/v1" and len(context["records"]) == 8, "context custody shape")
    owned: set[str] = set()
    for row in context["records"]:
        require(set(row) == {"original_path", "owned_copy", "bytes", "sha256", "original_if_present_must_match"}, "context row schema")
        require(row["original_if_present_must_match"] is True and type(row["owned_copy"]) is str, "context rule type")
        require(row["owned_copy"] not in owned, "duplicate owned context")
        owned.add(row["owned_copy"])
        pinned(PACKAGE / row["owned_copy"], row["bytes"], row["sha256"])
        original = Path(row["original_path"])
        if original.exists():
            pinned(original, row["bytes"], row["sha256"])
    require("prospective-contract.json" in owned and "preserved-context/var09-independent-contract-go.md.bytes" in owned, "contract/review context")


def parent_pair_custody() -> None:
    """Root executes this read-only Git verification under original binary capture."""
    pair_map = strict_json((PACKAGE / "parent-source-pairs.json").read_bytes())
    require(pair_map["schema"] == "i04-var09-parent-disk-git-pairs/v1", "pair map schema")
    require(pair_map["source_parent_sha256"] == "e1476616e4694df1742d095f9976eb57a512953edf6222c9a6cdc74b74ea8cde", "pair map selection pin")
    require(len(pair_map["records"]) == 403, "403 current parent disk/Git roles")
    selection = strict_json(pinned(VAR05 / "preserved-context/selection.json.bytes", 277670,
                                   "e1476616e4694df1742d095f9976eb57a512953edf6222c9a6cdc74b74ea8cde"))
    expected_rows = [{key: row[key] for key in ("path", "bytes", "sha256", "git", "oid")}
                     for row in selection["parent_sources_and_catalog"][:-1]]
    require(typed_equal(pair_map["records"], expected_rows), "403 roles match selected parent source map")
    index = strict_json(pinned(PARENT / "evidence-index.json", 176439, PARENT_INDEX_SHA))
    prefix = "cases/simlox-air-support/I04-var03-idle-system-between-v1.0.1/"
    expected_paths = {prefix + item["path"].replace("\\", "/") for item in index["source_files"]}
    expected_paths |= {prefix + "evidence-index.json", prefix + "review/independent-content-go-2026-10-08.md"}
    actual_paths = [row["path"].replace("\\", "/") for row in pair_map["records"]]
    require(set(actual_paths) == expected_paths and len(actual_paths) == len(set(actual_paths)) == 403, "exact parent pair path membership")
    require(len({path.casefold() for path in actual_paths}) == 403, "casefold-unique parent pair paths")
    git = shutil.which("git") or str(Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe"))
    require(Path(git).is_file(), "read-only Git executable available to root capture")
    tree = subprocess.run([git, "ls-tree", "-r", "-z", BASE_COMMIT], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    require(not tree.stderr, "Git ls-tree stderr")
    tree_oids: dict[str, str] = {}
    for record in tree.stdout.split(b"\0"):
        if record:
            head, path = record.split(b"\t", 1)
            mode, kind, oid = head.decode("ascii").split(" ")
            if kind == "blob":
                tree_oids[path.decode("utf-8")] = oid
    dependencies = index["accepted_source_pairs"]
    require(len(dependencies) == 76, "76 accepted dependency pairs")
    distinct_oids = list(dict.fromkeys(row["oid"] for row in [*pair_map["records"], *dependencies]))
    objects = subprocess.run([git, "cat-file", "--batch"], cwd=ROOT,
                             input=("\n".join(distinct_oids) + "\n").encode("ascii"),
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    require(not objects.stderr, "Git cat-file stderr")
    stream = objects.stdout
    blobs: dict[str, bytes] = {}
    cursor = 0
    for oid in distinct_oids:
        end = stream.index(b"\n", cursor)
        actual_oid, kind, size = stream[cursor:end].decode("ascii").split(" ")
        require(actual_oid == oid and kind == "blob", "Git batch object header")
        count = int(size)
        blob = stream[end + 1 : end + 1 + count]
        require(len(blob) == count and stream[end + 1 + count : end + 2 + count] == b"\n", "Git batch framing")
        blobs[oid] = blob
        cursor = end + 2 + count
    require(cursor == len(stream), "Git batch trailing bytes")
    for row in pair_map["records"]:
        path = row["path"].replace("\\", "/")
        require(tree_oids.get(path) == row["oid"], "Git path/OID at accepted base")
        pinned(ROOT / path, row["bytes"], row["sha256"])
        blob = blobs[row["oid"]]
        require(len(blob) == row["git"]["bytes"] and sha(blob) == row["git"]["sha256"], "Git blob byte pin")
    for row in dependencies:
        path = row["path"].replace("\\", "/")
        require(tree_oids.get(path) == row["oid"], "dependency Git path/OID at accepted base")
        pinned(ROOT / path, row["disk"]["bytes"], row["disk"]["sha256"])
        blob = blobs[row["oid"]]
        require(len(blob) == row["git"]["bytes"] and sha(blob) == row["git"]["sha256"], "dependency Git byte pin")


def inherited_raw_maps(index: dict[str, object]) -> None:
    for filename, expected, field, schema in (
        ("raw-custody-map.json", 153, "raw_files", "i04-var09-parent-raw-custody/v1"),
        ("preflight-custody-map.json", 15, "preflight_original_files", "i04-var09-parent-preflight-custody/v1"),
    ):
        record = strict_json((PACKAGE / filename).read_bytes())
        require(record["schema"] == schema and len(record["records"]) == expected, "raw custody map shape")
        require(typed_equal(record["records"], index[field]), "raw custody equals accepted index")


def authored_source(data: bytes) -> None:
    model = strict_json(data)["model"]
    require(set(model) == {"database_version", "tables"}, "authored model shape")
    tables = model["tables"]
    names = [table["name"] for table in tables]
    require(len(names) == len(set(names)), "unique authored table names")

    def rows(name: str) -> tuple[dict[str, int], list[list[object]]]:
        table = tables[names.index(name)]
        require(len(table["instances"]) == 1, "single authored instance")
        return {column["name"]: i for i, column in enumerate(table["columns"])}, table["instances"][0]["rows"]

    columns, deployment = rows("SystemDeployment")
    require(len(deployment) == 2, "two authored deployments")
    require({(row[columns["SID"]], row[columns["USTID"]], row[columns["QTYPS"]]) for row in deployment}
            == {("TEACH-AIR-01", "TEACH-UNIT", 1), ("TEACH-AIR-01", "TEACH-UNIT-2", 1)}, "one aircraft per unit")
    require(all(type(row[columns["QTYPS"]]) is int for row in deployment), "integer deployment quantity")
    columns, transfers = rows("SystemTransfer")
    require(len(transfers) == 1, "one authored transfer, no second transfer")
    transfer = transfers[0]
    require(tuple(transfer[columns[key]] for key in ("UFID", "UTID", "SID", "TFTIME", "TFQTY", "TFDT"))
            == ("TEACH-UNIT", "TEACH-UNIT-2", "TEACH-AIR-01", 10.5, 1, 0.5), "authored transfer")
    require(type(transfer[columns["TFQTY"]]) is int and type(transfer[columns["TFTIME"]]) is float
            and type(transfer[columns["TFDT"]]) is float, "transfer declared numeric types")
    columns, profiles = rows("OperationProfile")
    require(any(row[columns["PRID"]] == "BASIC-SCHEDULE" and row[columns["SPRID"]] == "BASIC-MISSION"
                and row[columns["STIM"]] == 20.0 for row in profiles), "later authored operation")
    columns, missions = rows("MissionType")
    require(any(row[columns["MTID"]] == "BASIC-MISSION" and row[columns["NOS"]] == 2
                and row[columns["MNOS"]] == 2 and row[columns["DURN"]] == 2.0 for row in missions), "later mission requires two")


def sealed_custody() -> tuple[bytes, bytes]:
    index = strict_json(pinned(PARENT / "evidence-index.json", 176439, PARENT_INDEX_SHA))
    require(index["source_count"] == len(index["source_files"]) == 401, "parent source count")
    require(index["raw_count"] == len(index["raw_files"]) == 153, "parent raw count")
    require(index["preflight_original_count"] == len(index["preflight_original_files"]) == 15, "parent preflight count")
    require(len({row["path"].casefold() for row in [*index["raw_files"], *index["preflight_original_files"]]}) == 168,
            "168 distinct parent original paths")
    for row in index["source_files"]:
        pinned(PARENT / row["path"], row["bytes"], row["sha256"])
    for row in [*index["raw_files"], *index["preflight_original_files"]]:
        pinned(Path(row["path"]), row["bytes"], row["sha256"])
    inherited_raw_maps(index)
    manifest = strict_json(pinned(PARENT / "prelaunch-manifest.json", 161922, PARENT_MANIFEST_SHA))
    require(manifest["source_count"] == len(manifest["source_files"]) == 456, "parent role count")
    require(manifest["local_only_context_originals"] == 2, "private originals remain mandatory")
    require(sum(row["key"].startswith("local_only_context_original:") for row in manifest["source_files"]) == 2,
            "two private local-only role pins")
    per_path: dict[Path, tuple[int, str]] = {}
    role_keys: set[str] = set()
    for row in manifest["source_files"]:
        key = row["key"].casefold()
        require(key not in role_keys, "duplicate casefold parent role")
        role_keys.add(key)
        path = Path(row["path"]).resolve(strict=True)
        seal = row["bytes"], row["sha256"]
        require(path not in per_path or per_path[path] == seal, "role alias conflicting pin")
        per_path[path] = seal
        pinned(path, *seal)
    require(manifest["live_catalog_prelaunch_pin"]["sha256"] == "a247e221e524b319f45f62b32a1668366e3e2caf5f066ca79b58ca0838fe59d6", "historical catalog alias")
    pinned(PARENT / "preserved-context/publication-index-local-496.json.bytes", 532423, "a247e221e524b319f45f62b32a1668366e3e2caf5f066ca79b58ca0838fe59d6")
    pinned(PARENT / "preserved-context/publication-index-git-496.json.bytes", 527796, "cecd78d6913a8e75638382f8b2a82c83c6f626394657f200150287df02e0851c")
    pinned(PARENT / "review/independent-postrun-go-2026-10-08.md", 4369, PARENT_GO_SHA)
    log = pinned(RUN / "model.log", 8223, LOG_SHA)
    report = pinned(RUN / "report-raw.json", 103970, REPORT_SHA)
    pinned(RUN / "closure.json", 130377, "ac5af12fb9e72ea91c342a39f7cbe4ec46689229cc996ef090090d0fbf92b616")
    source = pinned(PARENT / "native-input.json", 44611, "48c346d27d9cd08be09a771292d198e00db72a19d488da5b184689504ace177b")
    authored_source(source)
    context_custody()
    catalog_custody()
    parent_pair_custody()
    return log, report


def classify_original() -> dict[str, object]:
    pinned(PACKAGE / "prospective-contract.json", 13997, CONTRACT_SHA)
    log, report = sealed_custody()
    result = parse_log(log, exact_original=True)
    report_result = selected_report(report, strict_json(report_repair(report)))
    return {"decision": "GO_BOUNDED_CLASSIFICATION", "new_native_runs": 0, "accepted_parent_runs_repeated": 0, **result, **report_result}


def case_index_custody() -> dict[str, int]:
    """Post-publication closed new case replay; absent during initial preindex proof."""
    index = strict_json((PACKAGE / "evidence-index.json").read_bytes())
    require(index["schema"] == "i04-var09-readonly-classification-evidence-index/v1", "new index schema")
    rows = index["source_files"]
    require(type(index["source_count"]) is int and len(rows) == index["source_count"], "new source count")
    paths: set[str] = set()
    for row in rows:
        require(set(row) == {"path", "bytes", "sha256"}, "new source row schema")
        rel = Path(row["path"])
        require(not rel.is_absolute() and ".." not in rel.parts, "new source relative path")
        key = rel.as_posix().casefold()
        require(key not in paths, "duplicate new source path")
        paths.add(key)
        path = (PACKAGE / rel).resolve(strict=True)
        require(path.is_relative_to(PACKAGE.resolve()) and not path.is_symlink(), "new source under case")
        pinned(path, row["bytes"], row["sha256"])
    actual = {path.relative_to(PACKAGE).as_posix().casefold() for path in PACKAGE.rglob("*")
              if path.is_file() and path.relative_to(PACKAGE).parts[0] not in ("runs", "test-output", "transport-evidence")
              and "__pycache__" not in path.relative_to(PACKAGE).parts}
    require(actual == paths | {"evidence-index.json"}, "closed new case source set")
    require(index["raw_count"] == len(index["raw_files"]) == 153, "new index parent raw records")
    require(index["preflight_original_count"] == len(index["preflight_original_files"]) == 15, "new index parent preflight records")
    accepted = strict_json(pinned(PARENT / "evidence-index.json", 176439, PARENT_INDEX_SHA))
    require(typed_equal(index["raw_files"], accepted["raw_files"])
            and typed_equal(index["preflight_original_files"], accepted["preflight_original_files"]),
            "new index repeats exact accepted originals")
    require(index["parent_source_pairs"] == 403 and index["accepted_dependency_pairs"] == 76
            and index["parent_prelaunch_roles"] == 456, "new index parent counters")
    return {"new_case_sources": index["source_count"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preindex", action="store_true")
    group.add_argument("--sealed", action="store_true")
    args = parser.parse_args()
    result = classify_original()
    if args.sealed:
        result.update(case_index_custody())
    result["mode"] = "sealed" if args.sealed else "preindex"
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
