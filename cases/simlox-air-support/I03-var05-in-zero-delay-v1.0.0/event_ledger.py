"""Fixed-source full-log grammar and task-linked resource ledger.

The accepted positive-delay OUT+IN trace supplies the bounded diagnostic
grammar. Only the four predeclared IN arrival/receipt diagnostics move to h10.
Every timed and untimed line is consumed; the critical microsteps are checked
in causal order independently of report values.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT_LOG = HERE.parent / "I03-var01-crew-out-in-v1.0.0" / "runs" / "i03-var01-crew-transfer-v100-ssh-20261005-01" / "out_in.log"
PARENT_LOG_SHA = "673706cc043d4c5b1ce07c0692070b7931677257779fa3a67ebf190e2644f0c5"
_TIME = re.compile(r"^Time: ([0-9]+(?:\.[0-9]+)?) (.*)$")
_BOOK = re.compile(r"^Time: (7\.5|19\.5)  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: ([01])$")
_RELEASE = re.compile(r"^Time: (8|20)  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: ([12])$")


def parent_lines() -> list[str]:
    data = PARENT_LOG.read_bytes()
    assert hashlib.sha256(data).hexdigest() == PARENT_LOG_SHA
    lines = data.decode("utf-8-sig").splitlines()
    assert lines[:2] == ["SIMLOX LOG FILE", "36"]
    assert len(lines) == 250
    return lines


def prospective_child_lines() -> list[str]:
    """A PURE hypothesis fixture; never native evidence or an acceptance run."""
    lines = parent_lines().copy()
    changes = {
        "Time: 10  resource transfer task 2 (IN)  starts with 1 resources, transfer time: 0.5":
            "Time: 10  resource transfer task 2 (IN)  starts with 1 resources, transfer time: 0",
        "Time: 10.5  resource transfer task 2 (IN)  arrives with 1 resources":
            "Time: 10  resource transfer task 2 (IN)  arrives with 1 resources",
        "Time: 10.5  <P-CREW at <BASE-01,0>> transfer arrives: 1":
            "Time: 10  <P-CREW at <BASE-01,0>> transfer arrives: 1",
        "Time: 10.5 <BASE-01,0> trig missions and tasks waiting for resources ":
            "Time: 10 <BASE-01,0> trig missions and tasks waiting for resources ",
        "Time: 10.5  <P-CREW at <BASE-01,0>> check for return transport: 1":
            "Time: 10  <P-CREW at <BASE-01,0>> check for return transport: 1",
    }
    # The queue continuation following the moved trigger remains attached to it.
    for old, new in changes.items():
        assert lines.count(old) == 1, old
        lines[lines.index(old)] = new
    assert lines.count("  Free resources at: <BASE-01,0> P-CREW 2") == 2
    assert lines.count("Time: 10.5  resource transfer task 2 (IN)  arrives with 1 resources") == 0
    return lines


def _positions(lines: list[str], text: str) -> list[int]:
    return [index for index, line in enumerate(lines) if line == text]


def _one(lines: list[str], text: str) -> int:
    locations = _positions(lines, text)
    assert len(locations) == 1, (text, locations)
    return locations[0]


def _microstates(lines: list[str], *, demand: int, removal: int, positive_start: int,
                 started_in: int, arrived_in: int, local_receipt: int,
                 allocation_to_task: dict[int, int], release_to_task: dict[int, int]) -> dict:
    """Accumulate task quantities in original event order, including transient reservations."""
    state = {"opening": 2, "local": 2, "booked": 0, "reserved_OUT": 0, "OUT_pending": 0,
             "departed_OUT": 0, "IN_started_unarrived": 0, "IN_task_arrived": 0,
             "IN_pending_local_receipt": 0, "locally_received_IN": 0, "nominal": 2}
    booking_events = release_events = 0
    active_tasks: set[int] = set()
    milestones = {}
    for index, line in enumerate(lines):
        book = _BOOK.fullmatch(line)
        release = _RELEASE.fullmatch(line)
        if book:
            task = allocation_to_task[index]
            assert task not in active_tasks
            active_tasks.add(task)
            state["booked"] += 1
            booking_events += 1
            assert 2 - state["departed_OUT"] + state["locally_received_IN"] == state["local"]
            assert state["local"] - state["booked"] - state["reserved_OUT"] == int(book.group(2))
        elif release:
            task = release_to_task[index]
            assert task in active_tasks
            active_tasks.remove(task)
            state["booked"] -= 1
            release_events += 1
            assert state["local"] - state["booked"] - state["reserved_OUT"] == int(release.group(2))
        elif index == demand:
            state["OUT_pending"] += 1
            state["nominal"] -= 1
        elif index == removal:
            assert state["OUT_pending"] == 1 and state["local"] - state["booked"] == 1
            state["OUT_pending"] = 0
            state["reserved_OUT"] = 1
            milestones["h8_reserved"] = state.copy()
        elif index == positive_start:
            assert state["reserved_OUT"] == 1
            state["reserved_OUT"] = 0
            state["departed_OUT"] += 1
            state["local"] -= 1
            milestones["h8_departed"] = state.copy()
        elif index == started_in:
            state["IN_started_unarrived"] = 1
            milestones["h10_started"] = state.copy()
        elif index == arrived_in:
            assert state["IN_started_unarrived"] == 1
            state["IN_started_unarrived"] = 0
            state["IN_task_arrived"] = 1
            state["IN_pending_local_receipt"] = 1
            milestones["h10_task_arrived_pending_receipt"] = state.copy()
        elif index == local_receipt:
            assert state["IN_pending_local_receipt"] == 1
            state["IN_pending_local_receipt"] = 0
            state["locally_received_IN"] = 1
            state["local"] += 1
            state["nominal"] += 1
            milestones["h10_local_receipt"] = state.copy()
        assert state["local"] == state["opening"] - state["departed_OUT"] + state["locally_received_IN"]
        assert state["local"] >= state["booked"] + state["reserved_OUT"] >= 0
        assert state["IN_pending_local_receipt"] == state["IN_task_arrived"] - state["locally_received_IN"]
    assert booking_events == release_events == 4
    assert not active_tasks
    assert state == {"opening": 2, "local": 2, "booked": 0, "reserved_OUT": 0, "OUT_pending": 0,
                     "departed_OUT": 1, "IN_started_unarrived": 0, "IN_task_arrived": 1,
                     "IN_pending_local_receipt": 0, "locally_received_IN": 1, "nominal": 2}
    assert milestones["h8_reserved"]["local"] == 2 and milestones["h8_reserved"]["reserved_OUT"] == 1
    assert milestones["h8_departed"]["local"] == milestones["h8_departed"]["nominal"] == 1
    assert milestones["h10_task_arrived_pending_receipt"]["local"] == 1
    assert milestones["h10_local_receipt"]["local"] == 2
    return {"terminal": state, "milestones": milestones, "bookings": booking_events, "releases": release_events}


def validate_lines(lines: list[str], *, parent: bool) -> dict:
    expected = parent_lines() if parent else prospective_child_lines()
    assert lines[:2] == ["SIMLOX LOG FILE", "36"]
    assert len(lines) == len(expected) == 250
    assert Counter(lines) == Counter(expected), "missing, duplicated or altered typed/continuation line"
    # Every native time token must be an authored quarter/half-hour edge and
    # chronological; same-time ancillary diagnostics may permute only where
    # the causal checks below still hold.
    times: list[float] = []
    for line in lines[2:]:
        if line.startswith("Time:"):
            match = _TIME.fullmatch(line)
            assert match, line
            times.append(float(match.group(1)))
    assert times == sorted(times) and times[-1] == 36
    assert set(times) <= {0, 7.5, 7.75, 8, 8.25, 8.75, 9, 10, 10.5, 19.5, 20, 20.25, 20.75, 21, 24, 36}
    assert parent or 10.5 not in times

    demand = _one(lines, "Time: 7.75  <P-CREW at <BASE-01,0>> Resource transfer demand arrives from OUT-transfer ")
    backorder_added = _one(lines, "Time: 7.75  <P-CREW at <BASE-01,0>> Resource transfer backorder added ")
    zero_start = _one(lines, "Time: 7.75  resource transfer task 0 (OUT)  starts with 0 resources, transfer time: 0")
    zero_arrive = _one(lines, "Time: 7.75  resource transfer task 0 (OUT)  arrives with 0 resources")
    # The identical first/second release diagnostic occurs twice by design.
    releases = _positions(lines, "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1")
    assert len(releases) == 2
    removal = _one(lines, "Time: 8  <P-CREW at <BASE-01,0>> Resource transfer backorder removed ")
    created_positive = _one(lines, "Time: 8  resource transfer task 1 (OUT)  created: starting from  <P-CREW at <BASE-01,0>>")
    positive_start = _one(lines, "Time: 8  resource transfer task 1 (OUT)  starts with 1 resources, transfer time: 0")
    positive_arrival = _one(lines, "Time: 8  resource transfer task 1 (OUT)  arrives with 1 resources")
    assert demand < backorder_added < zero_start < zero_arrive < releases[0] < removal < created_positive < releases[1] < positive_start < positive_arrival
    assert _one(lines, "  Resource transfer backorders at:  <P-CREW at <BASE-01,0>> Nbr: 1 Backorders:<OUT,7.75>,") < removal
    assert removal < _one(lines, "  Resource transfer backorders at:  <P-CREW at <BASE-01,0>> Nbr: 0") < positive_start

    created_in = _one(lines, "Time: 10  resource transfer task 2 (IN)  created: aiming for  <P-CREW at <BASE-01,0>>")
    duration = "0.5" if parent else "0"
    arrival_hour = "10.5" if parent else "10"
    started_in = _one(lines, f"Time: 10  resource transfer task 2 (IN)  starts with 1 resources, transfer time: {duration}")
    arrived_in = _one(lines, f"Time: {arrival_hour}  resource transfer task 2 (IN)  arrives with 1 resources")
    local_receipt = _one(lines, f"Time: {arrival_hour}  <P-CREW at <BASE-01,0>> transfer arrives: 1")
    # Task arrival creates pending-local-receipt=1; only the distinct P-CREW
    # receipt increments the derived local roster and nominal quantity.
    free_two = _positions(lines, "  Free resources at: <BASE-01,0> P-CREW 2")
    assert len(free_two) == 2 and free_two[0] < demand and local_receipt < free_two[1]
    trigger = _one(lines, f"Time: {arrival_hour} <BASE-01,0> trig missions and tasks waiting for resources ")
    assert created_in < started_in < arrived_in < local_receipt < free_two[1] < trigger
    assert _one(lines, f"Time: {arrival_hour}  <P-CREW at <BASE-01,0>> check for return transport: 1") > trigger
    waves = []
    allocation_to_task: dict[int, int] = {}
    release_to_task: dict[int, int] = {}
    for wave, prep, launch, done in ((0, 7.5, 8, 9), (1, 19.5, 20, 21)):
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{wave}>"
        start = _one(lines, f"Time: {prep} {mission} mission created: ")
        ordered = _one(lines, f"Time: {prep} <TEACH-UNIT> mission ordered: BASIC-MISSION")
        mission_start = _one(lines, f"Time: {launch} {mission} mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        task_start = _one(lines, f"Time: {launch + .25} {mission} task starting: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        task_end = _one(lines, f"Time: {launch + .75} {mission} task completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        completed = _one(lines, f"Time: {done} {mission} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>")
        assert ordered < start < mission_start < task_start < task_end < completed
        for aircraft in (0, 1):
            prep_task = wave * 2 + aircraft
            system = f"<TEACH-AIR-01,{aircraft}>"
            prep_begin = _one(lines, f"Time: {prep}  system preparation task {prep_task} on {system} started")
            prep_end = _one(lines, f"Time: {launch}  system preparation task {prep_task} on {system} completed")
            stem = f"subtask {prep_task} seqno 1 within system preparation task {prep_task} on {system}"
            substart = _one(lines, f"Time: {prep}  {stem} started")
            request = _one(lines, f"Time: {prep}  {stem} requests resources")
            availability = _one(lines, f"Time: {prep}  {stem} resource availability test")
            book = _one(lines, f"Time: {prep}  {stem} books resources")
            perform = _one(lines, f"Time: {prep}  {stem} starts performing, planned to last for 0.5 hours")
            subcompleted = _one(lines, f"Time: {launch}  {stem} completed")
            free = _one(lines, f"Time: {launch}  {stem} frees resources")
            allocations = [i for i, line in enumerate(lines) if _BOOK.fullmatch(line) and line.startswith(f"Time: {prep} ")]
            deallocations = [i for i, line in enumerate(lines) if _RELEASE.fullmatch(line) and line.startswith(f"Time: {launch} ")]
            assert len(allocations) == len(deallocations) == 2
            allocation = allocations[aircraft]
            deallocation = deallocations[aircraft]
            assert prep_begin < substart < request < availability < book < allocation < perform < subcompleted < free < deallocation < prep_end
            assert lines[availability + 1].strip() == "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK"
            allocation_to_task[allocation] = prep_task
            release_to_task[deallocation] = prep_task
            arrive = _one(lines, f"Time: {done} <TEACH-AIR-01,BASE-01,0> System arrives {system}, mission success, ")
            ready = _positions(lines, f"Time: {done} <TEACH-AIR-01,BASE-01,0> System ready {system}")
            assert len(ready) == 2 and start < prep_begin < prep_end < mission_start < completed < arrive < ready[0] < ready[1]
        waves.append({"prep_start": prep, "prep_end": launch, "mission_start": launch, "return": done})
    assert len(allocation_to_task) == len(release_to_task) == 4
    microstates = _microstates(lines, demand=demand, removal=removal, positive_start=positive_start,
                               started_in=started_in, arrived_in=arrived_in, local_receipt=local_receipt,
                               allocation_to_task=allocation_to_task, release_to_task=release_to_task)
    assert lines[-1] == "Time: 36  resource shift 0 ended at <P-CREW at <BASE-01,0>> time gap to next = 0"
    return {"opening": 2, "out_request": 7.75, "out_departure": 8, "out_quantity": 1,
            "in_start": 10, "in_task_arrival": float(arrival_hour), "in_local_receipt": float(arrival_hour),
            "in_quantity": 1, "waves": waves, "timed_events": len(times), "raw_lines": len(lines),
            "terminal_local": 2, "terminal_ready": 2, "task_arrived_pending_receipt_checked": True,
            "microstates": microstates}


def validate(path: Path, *, parent: bool = False) -> dict:
    data = path.read_bytes()
    lines = data.decode("utf-8-sig").splitlines()
    return validate_lines(lines, parent=parent)
