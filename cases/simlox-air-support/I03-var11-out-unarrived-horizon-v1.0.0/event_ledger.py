"""Typed source-bound child log, quantity, order and terminal ledger."""
from __future__ import annotations

from dataclasses import dataclass
import re

AIR = r"<TEACH-AIR-01,[01]>"
MISSION = r"<BASIC-MISSION,TEACH-UNIT,0,0,[01]>"
CREW = r"<P-CREW at <BASE-01,0>>"
TASK = r"system preparation task [0-3] on " + AIR
SUB = r"subtask [0-3] seqno 1 within " + TASK
NUMBER = r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?"
TIME = re.compile(r"^Time: (" + NUMBER + r")\s+(.*)$")


@dataclass(frozen=True)
class Event:
    hour: float
    line: int
    body: str
    continuations: tuple[str, ...]


PATTERNS = [
    AIR + r" Next random failure will occur 1e\+010",
    AIR + r" nbr ready (?:increased|decreased) at unit: <TEACH-UNIT at <BASE-01,0>>",
    r"<TEACH-UNIT at <BASE-01,0>> systems ready: [0-2] :(?:" + AIR + r"(?:," + AIR + r")?)?",
    r"Start of day no [01]",
    r"<BASE-01,0> trig missions and tasks waiting for resources",
    r"resource shift 0 (?:created|starting) at " + CREW + r"(?: no shift period)?",
    r"resource shift 0 ended at " + CREW + r" time gap to next = 0",
    r"<TEACH-UNIT> mission ordered: BASIC-MISSION",
    MISSION + r" mission (?:created:|activated, systems requested: 2|allocates system: " + AIR + r"|starting, duration: 1 : " + AIR + r"," + AIR + r"|success:|completed: " + AIR + r"," + AIR + r")",
    MISSION + r" task (?:starting|completed): " + AIR + r"," + AIR,
    AIR + r" releases excess resources \(if any\)",
    AIR + r" preparation (?:started|ended), mission: " + MISSION,
    TASK + r" (?:started|completed)",
    SUB + r" (?:started|requests resources|resource availability test|resource received|books resources|starts performing, planned to last for 0\.5 hours|completed|frees resources)",
    r"subtask [0-3] seqno 1 check return remote resources",
    CREW + r" (?:allocated to maintenance task: 1  available now: [0-2]|deallocated from  maintenance task: 1  available now: [0-2]|check for return transport: 1|Resource transfer demand arrives from OUT-transfer|Resource transfer backorder (?:added|removed))",
    r"resource transfer task [0-9]+ \(OUT\)  (?:created: starting from  " + CREW + r"|starts with [0-9]+ resources, transfer time: (?:0|40)|arrives with [0-9]+ resources)",
    r"<TEACH-AIR-01,BASE-01,0> System soon ready " + AIR + r", estimated remaining time: 0",
    AIR + r" turnround (?:started, mission: " + MISSION + r" reduction factor: 1|ended, mission: " + MISSION + r")",
    r"<TEACH-AIR-01,BASE-01,0> System arrives " + AIR + r", mission success,",
    r"<TEACH-AIR-01,BASE-01,0> System ready " + AIR,
    r"<TEACH-AIR-01,BASE-01,0> Repair task priority list:",
]
COMPILED = [re.compile(r"(?:" + x + r")\Z") for x in PATTERNS]
CONTINUATIONS = [
    re.compile(r"Missions waiting for resources at: <BASE-01,0>"),
    re.compile(r"Tasks waiting for resources at: <BASE-01,0> [0-2]"),
    re.compile(r"Free resources at: <BASE-01,0> P-CREW [0-2]"),
    re.compile(r"Missions and tasks using resources at: <BASE-01,0> [0-2]"),
    re.compile(r"Availability test on  " + CREW + r" request for: 1 (?:OK|failed)"),
    re.compile(r"< subtask [0-3] seqno 1 within " + TASK + r", C, (?:0\.5|1, 0\.5)>"),
    re.compile(r"Resource transfer backorders at:  " + CREW + r" Nbr: [0-1](?: Backorders:<OUT," + NUMBER + r">,)?"),
    re.compile(r"no failures"), re.compile(r"no PMTasks"),
]


def parse_log(text: str) -> list[Event]:
    lines = text.splitlines()
    assert lines[:2] == ["SIMLOX LOG FILE", "36"], "native header/horizon"
    mutable: list[list] = []
    for line_no, line in enumerate(lines[2:], start=3):
        match = TIME.fullmatch(line)
        if match:
            hour, body = float(match.group(1)), match.group(2).rstrip()
            assert 0 <= hour <= 36 and (not mutable or hour >= mutable[-1][0]), (line_no, hour)
            assert any(pattern.fullmatch(body) for pattern in COMPILED), (line_no, body)
            mutable.append([hour, line_no, body, []])
        else:
            assert mutable and (not line.strip() or line[0].isspace()), (line_no, line)
            if line.strip():
                value = line.strip()
                assert any(pattern.fullmatch(value) for pattern in CONTINUATIONS), (line_no, value)
                mutable[-1][3].append(value)
    assert mutable and mutable[-1][0] == 36
    return [Event(hour, line, body, tuple(cont)) for hour, line, body, cont in mutable]


def only(events: list[Event], pattern: str, hour: float | None = None) -> Event:
    matches = [e for e in events if re.fullmatch(pattern, e.body) and (hour is None or e.hour == hour)]
    assert len(matches) == 1, (pattern, hour, [(e.hour, e.line) for e in matches])
    return matches[0]


def sequence(*events: Event) -> None:
    assert all(a.line < b.line for a, b in zip(events, events[1:])), [(e.hour, e.line, e.body) for e in events]


def no(events: list[Event], text: str) -> None:
    assert not any(text in e.body or any(text in c for c in e.continuations) for e in events), text


def continuation_ledger(events: list[Event], *, child: bool) -> None:
    """Bind every printed continuation to its owning typed event and quantity."""
    free, booked, departed_task_quantity = 2, 0, 0
    last_booked_task: str | None = None
    for e in events:
        body = e.body
        if "resource transfer task 0 (OUT)  starts with 1 resources" in body:
            free -= 1
            departed_task_quantity += 1
        elif body.endswith(" books resources"):
            last_booked_task = body.removesuffix(" books resources")
        elif " allocated to maintenance task: 1  available now:" in body:
            free -= 1
            booked += 1
            assert last_booked_task is not None, e.line
        elif " deallocated from  maintenance task: 1  available now:" in body:
            free += 1
            booked -= 1
        assert free + booked + departed_task_quantity == 2 and 0 <= free <= 2 and 0 <= booked <= 1, e.line
        queue_owner = "trig missions and tasks waiting for resources" in body
        shift_owner = "resource shift 0 starting" in body
        booking_owner = " allocated to maintenance task:" in body
        counts = {
            "free": 0, "using": 0, "booked_task": 0,
            "mission_queue": 0, "task_queue": 0, "waiting_task": 0,
        }
        for continuation in e.continuations:
            if continuation.startswith("Free resources at:"):
                counts["free"] += 1
                assert "resource shift 0 starting" in body and e.hour == 0
                assert continuation == f"Free resources at: <BASE-01,0> P-CREW {free}", e.line
            elif continuation.startswith("Missions and tasks using resources at:"):
                counts["using"] += 1
                assert "resource shift 0 starting" in body or " allocated to maintenance task:" in body
                assert continuation == f"Missions and tasks using resources at: <BASE-01,0> {booked}", e.line
            elif continuation.startswith("< subtask "):
                if " allocated to maintenance task:" in body:
                    counts["booked_task"] += 1
                    assert last_booked_task is not None
                    assert continuation == "< " + last_booked_task + ", C, 1, 0.5>", e.line
                else:
                    counts["waiting_task"] += 1
                    assert "trig missions and tasks waiting for resources" in body and e.hour in (8, 20), e.line
                    later_id = 1 if e.hour == 8 else 3
                    assert continuation == (f"< subtask {later_id} seqno 1 within system preparation task "
                                            f"{later_id} on <TEACH-AIR-01,1>, C, 0.5>"), e.line
            elif continuation.startswith("Availability test on "):
                assert body.endswith(" resource availability test"), e.line
            elif continuation.startswith("Missions waiting for resources at:"):
                counts["mission_queue"] += 1
                assert "trig missions and tasks waiting for resources" in body, e.line
            elif continuation.startswith("Tasks waiting for resources at:"):
                if "trig missions and tasks waiting for resources" in body:
                    counts["task_queue"] += 1
                    assert continuation in ("Tasks waiting for resources at: <BASE-01,0> 0",
                                            "Tasks waiting for resources at: <BASE-01,0> 1")
                else:
                    assert body == "<TEACH-AIR-01,1> Next random failure will occur 1e+010" and e.hour in (8, 20), e.line
                    assert continuation == "Tasks waiting for resources at: <BASE-01,0> 0" and booked == 1, e.line
            elif continuation.startswith("Resource transfer backorders at:"):
                raise AssertionError(("unmatched transfer backorder continuation", e.line))
            elif continuation in ("no failures", "no PMTasks"):
                assert " System arrives " in body, e.line
            else:
                raise AssertionError(("unclassified continuation", e.line, continuation))
        assert counts["free"] == int(shift_owner), (e.line, "free", counts)
        assert counts["using"] == int(shift_owner or booking_owner), (e.line, "using", counts)
        assert counts["booked_task"] == int(booking_owner), (e.line, "booked task", counts)
        assert counts["mission_queue"] == int(queue_owner), (e.line, "mission queue", counts)
        assert counts["task_queue"] == int(queue_owner), (e.line, "task queue", counts)
        assert counts["waiting_task"] == int(queue_owner and e.hour in (8, 20)), (e.line, "waiting task", counts)


def child_timeline(events: list[Event], *, child: bool = True) -> dict:
    assert events[0].hour == 0 and events[-1].hour == 36
    initial_ready0 = only(events, r"<TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>", 0)
    initial_ready1 = only(events, r"<TEACH-AIR-01,1> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>", 0)
    initial_snapshot = only(events, r"<TEACH-UNIT at <BASE-01,0>> systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>", 0)
    sequence(initial_ready0, initial_ready1, initial_snapshot)
    day0 = only(events, r"Start of day no 0", 0)
    day1 = only(events, r"Start of day no 1", 24)
    shift_created = only(events, r"resource shift 0 created at "+CREW, 0)
    shift_started = only(events, r"resource shift 0 starting at "+CREW+r" no shift period", 0)
    shift_ended = only(events, r"resource shift 0 ended at "+CREW+r" time gap to next = 0", 36)
    assert sum(e.body.startswith("Start of day no ") for e in events) == 2
    assert sum(e.body.startswith("resource shift 0 created") for e in events) == 1
    assert sum(e.body.startswith("resource shift 0 starting") for e in events) == 1
    assert sum(e.body.startswith("resource shift 0 ended") for e in events) == 1
    triggers = [e for e in events if "trig missions and tasks waiting for resources" in e.body]
    assert [e.hour for e in triggers] == [0, 0, 8, 8.5, 20, 20.5, 24], [(e.hour, e.line) for e in triggers]
    sequence(initial_snapshot, day0, triggers[0], shift_created, shift_started, triggers[1], day1, triggers[-1], shift_ended)
    assert len([e for e in events if "mission ordered:" in e.body]) == 2
    assert len([e for e in events if "mission starting," in e.body]) == 2
    assert len([e for e in events if "mission success:" in e.body]) == 2
    continuation_ledger(events, child=child)
    for forbidden in ("Resource transfer backorder", "Stock ", "Replacement item", "mission cancelled:", "failed"):
        # The single failed maintenance availability test is checked below.
        if forbidden != "failed": no(events, forbidden)
    transfer = [
        only(events, r"resource transfer task 0 \(OUT\)  created: starting from  " + CREW, 6),
        only(events, CREW + r" Resource transfer demand arrives from OUT-transfer", 6),
        only(events, r"resource transfer task 0 \(OUT\)  starts with 1 resources, transfer time: " + ("40" if child else "0"), 6),
    ]
    if not child:
        transfer.append(only(events, r"resource transfer task 0 \(OUT\)  arrives with 1 resources", 6))
    sequence(*transfer)
    assert len([e for e in events if "resource transfer task" in e.body]) == (2 if child else 3)
    assert not child or not any("resource transfer task" in e.body and " arrives with " in e.body for e in events)
    started_out_quantity = sum(1 for e in events if "resource transfer task 0 (OUT)  starts with 1 resources" in e.body)
    completed_out_quantity = sum(1 for e in events if "resource transfer task 0 (OUT)  arrives with 1 resources" in e.body)
    assert started_out_quantity == 1 and completed_out_quantity == (0 if child else 1)
    pending_out_quantity = started_out_quantity - completed_out_quantity
    assert len([e for e in events if "Resource transfer demand arrives" in e.body]) == 1
    assert len([e for e in events if "Resource transfer backorder" in e.body]) == 0
    free, booked, departed_task_quantity = 2, 0, 0
    for e in events:
        if "resource transfer task 0 (OUT)  starts with 1 resources" in e.body:
            assert e.hour == 6 and free >= 1 and booked == 0
            free -= 1
            departed_task_quantity += 1
        elif " allocated to maintenance task: 1  available now:" in e.body:
            free -= 1
            booked += 1
            assert int(e.body.rsplit("available now: ", 1)[1]) == free
        elif " deallocated from  maintenance task: 1  available now:" in e.body:
            free += 1
            booked -= 1
            assert int(e.body.rsplit("available now: ", 1)[1]) == free
        assert 0 <= free <= 2 and 0 <= booked <= 1
        assert free + booked + departed_task_quantity == 2, (e.line, free, booked, departed_task_quantity)
    assert (free, booked, departed_task_quantity) == (1, 0, 1)
    waves = []
    for wave, start in enumerate((7.5, 19.5)):
        first_end, last_end, launch, task_start, task_end, finish = start+.5, start+1, start+1, start+1.25, start+1.75, start+2
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{wave}>"
        prefix = f"subtask {2*wave} seqno 1 within system preparation task {2*wave} on <TEACH-AIR-01,0>"
        later = f"subtask {2*wave+1} seqno 1 within system preparation task {2*wave+1} on <TEACH-AIR-01,1>"
        order = only(events, r"<TEACH-UNIT> mission ordered: BASIC-MISSION", start)
        create = only(events, re.escape(mission)+r" mission created:", start)
        activate = only(events, re.escape(mission)+r" mission activated, systems requested: 2", start)
        allocate0 = only(events, re.escape(mission)+r" mission allocates system: <TEACH-AIR-01,0>", start)
        allocate1 = only(events, re.escape(mission)+r" mission allocates system: <TEACH-AIR-01,1>", start)
        decrease0 = only(events, r"<TEACH-AIR-01,0> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>", start)
        decrease1 = only(events, r"<TEACH-AIR-01,1> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>", start)
        release0 = only(events, r"<TEACH-AIR-01,0> releases excess resources \(if any\)", start)
        release1 = only(events, r"<TEACH-AIR-01,1> releases excess resources \(if any\)", start)
        prep0 = only(events, r"<TEACH-AIR-01,0> preparation started, mission: "+re.escape(mission), start)
        prep1 = only(events, r"<TEACH-AIR-01,1> preparation started, mission: "+re.escape(mission), start)
        main_start0 = only(events, fr"system preparation task {2*wave} on <TEACH-AIR-01,0> started", start)
        sub_start0 = only(events, re.escape(prefix)+r" started", start)
        request0 = only(events, re.escape(prefix)+r" requests resources", start)
        test0 = only(events, re.escape(prefix)+r" resource availability test", start)
        book0 = only(events, re.escape(prefix)+r" books resources", start)
        alloc0 = only(events, CREW+r" allocated to maintenance task: 1  available now: 0", start)
        work0 = only(events, re.escape(prefix)+r" starts performing, planned to last for 0\.5 hours", start)
        main_start1 = only(events, fr"system preparation task {2*wave+1} on <TEACH-AIR-01,1> started", start)
        sub_start1 = only(events, re.escape(later)+r" started", start)
        request1 = only(events, re.escape(later)+r" requests resources", start)
        test_fail = only(events, re.escape(later)+r" resource availability test", start)
        assert test0.continuations.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK") == 1
        assert test_fail.continuations.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed") == 1
        sequence(order, create, activate, allocate0, decrease0, release0, allocate1, decrease1, release1,
                 prep0, prep1, main_start0, sub_start0, request0, test0, book0, alloc0, work0,
                 main_start1, sub_start1, request1, test_fail)
        completed0 = only(events, re.escape(prefix)+r" completed", first_end)
        freed0 = only(events, re.escape(prefix)+r" frees resources", first_end)
        dealloc0 = only(events, CREW+r" deallocated from  maintenance task: 1  available now: 1", first_end)
        queue1 = only(events, r"<BASE-01,0> trig missions and tasks waiting for resources", first_end)
        assert queue1.continuations.count("Tasks waiting for resources at: <BASE-01,0> 1") == 1
        retest = only(events, re.escape(later)+r" resource availability test", first_end)
        received = only(events, re.escape(later)+r" resource received", first_end)
        book1 = only(events, re.escape(later)+r" books resources", first_end)
        alloc1 = only(events, CREW+r" allocated to maintenance task: 1  available now: 0", first_end)
        work1 = only(events, re.escape(later)+r" starts performing, planned to last for 0\.5 hours", first_end)
        assert retest.continuations.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK") == 1
        main0 = only(events, fr"system preparation task {2*wave} on <TEACH-AIR-01,0> completed", first_end)
        check0 = only(events, fr"subtask {2*wave} seqno 1 check return remote resources", first_end)
        crew_check0 = only(events, CREW+r" check for return transport: 1", first_end)
        prep_end0 = only(events, r"<TEACH-AIR-01,0> preparation ended, mission: "+re.escape(mission), first_end)
        clear_wait = [e for e in events if e.hour == first_end and
                      e.body == "<TEACH-AIR-01,1> Next random failure will occur 1e+010" and
                      "Tasks waiting for resources at: <BASE-01,0> 0" in e.continuations]
        assert len(clear_wait) == 1, (first_end, len(clear_wait))
        assert clear_wait[0].continuations.count("Tasks waiting for resources at: <BASE-01,0> 0") == 1
        sequence(completed0, freed0, dealloc0, queue1, retest, received, book1, alloc1, work1, clear_wait[0])
        sequence(dealloc0, check0, crew_check0, main0, prep_end0)
        completed1 = only(events, re.escape(later)+r" completed", last_end)
        freed1 = only(events, re.escape(later)+r" frees resources", last_end)
        dealloc1 = only(events, CREW+r" deallocated from  maintenance task: 1  available now: 1", last_end)
        queue0 = only(events, r"<BASE-01,0> trig missions and tasks waiting for resources", last_end)
        assert queue0.continuations.count("Tasks waiting for resources at: <BASE-01,0> 0") == 1
        main1 = only(events, fr"system preparation task {2*wave+1} on <TEACH-AIR-01,1> completed", last_end)
        check1 = only(events, fr"subtask {2*wave+1} seqno 1 check return remote resources", last_end)
        crew_check1 = only(events, CREW+r" check for return transport: 1", last_end)
        prep_end1 = only(events, r"<TEACH-AIR-01,1> preparation ended, mission: "+re.escape(mission), last_end)
        mission_start = only(events, re.escape(mission)+r" mission starting, duration: 1 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", launch)
        sequence(completed1, freed1, dealloc1, queue0, check1, crew_check1, main1, prep_end1, mission_start)
        task_begin = only(events, re.escape(mission)+r" task starting: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", task_start)
        task_complete = only(events, re.escape(mission)+r" task completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", task_end)
        success = only(events, re.escape(mission)+r" mission success:", finish)
        complete = only(events, re.escape(mission)+r" mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>", finish)
        sequence(mission_start, task_begin, task_complete, success, complete)
        for aircraft in (0, 1):
            a = f"<TEACH-AIR-01,{aircraft}>"
            soon_ready = only(events, r"<TEACH-AIR-01,BASE-01,0> System soon ready "+re.escape(a)+r", estimated remaining time: 0", finish)
            turn_start = only(events, re.escape(a)+r" turnround started, mission: "+re.escape(mission)+r" reduction factor: 1", finish)
            turn_end = only(events, re.escape(a)+r" turnround ended, mission: "+re.escape(mission), finish)
            arrival = only(events, r"<TEACH-AIR-01,BASE-01,0> System arrives "+re.escape(a)+r", mission success,", finish)
            increased = only(events, re.escape(a)+r" nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>", finish)
            ready = [e for e in events if e.hour == finish and e.body == f"<TEACH-AIR-01,BASE-01,0> System ready {a}"]
            assert len(ready) == 2
            assert arrival.continuations.count("no failures") == arrival.continuations.count("no PMTasks") == 1
            sequence(complete, soon_ready, turn_start, turn_end, arrival, increased, ready[0], ready[1])
            snapshot = only(events,
                r"<TEACH-UNIT at <BASE-01,0>> systems ready: " +
                (r"1 :<TEACH-AIR-01,0>" if aircraft == 0 else r"2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>"),
                finish)
            sequence(increased, ready[0], ready[1], snapshot)
            priorities = [e for e in events if e.hour == finish and e.body == "<TEACH-AIR-01,BASE-01,0> Repair task priority list:"]
            assert len(priorities) == 2, (finish, len(priorities))
            priority = priorities[aircraft]
            sequence(snapshot, priority)
        waves.append({"preparation_start":start, "first_preparation_end":first_end,
                      "last_preparation_end":last_end, "launch":launch, "task_start":task_start,
                      "task_end":task_end, "return":finish,
                      "bookings":[(start, first_end),(first_end,last_end)],
                      "waits":[(start,first_end)]})
    # Complete inventory of physical events, rather than selecting convenient matches.
    assert sum(" allocated to maintenance task:" in e.body for e in events) == 4
    assert sum(" deallocated from  maintenance task:" in e.body for e in events) == 4
    assert sum(" resource availability test" in e.body for e in events) == 6
    assert sum(" starts performing," in e.body for e in events) == 4
    assert sum(" System arrives " in e.body for e in events) == 4
    assert sum(" preparation started," in e.body for e in events) == 4
    assert sum(" preparation ended," in e.body for e in events) == 4
    assert sum(" mission completed:" in e.body for e in events) == 2
    assert sum("system preparation task" in e.body and e.body.endswith(" started") and "subtask" not in e.body for e in events) == 4
    assert sum("system preparation task" in e.body and e.body.endswith(" completed") and "subtask" not in e.body for e in events) == 4
    assert sum("Resource transfer" in e.body for e in events) == 1
    assert sum(" check return remote resources" in e.body for e in events) == 4
    assert sum(" check for return transport:" in e.body for e in events) == 4
    assert sum(" releases excess resources" in e.body for e in events) == 4
    assert sum(" subtask " in e.body and e.body.endswith(" started") for e in events) == 0
    assert sum(e.body.startswith("subtask ") and e.body.endswith(" started") for e in events) == 4
    assert sum(" System soon ready " in e.body for e in events) == 4
    assert sum(" System ready " in e.body for e in events) == 8
    assert sum(" Repair task priority list:" in e.body for e in events) == 4
    assert sum(" nbr ready increased at unit:" in e.body for e in events) == 6
    assert sum(" nbr ready decreased at unit:" in e.body for e in events) == 4
    assert sum(" systems ready:" in e.body for e in events) == 5
    assert events[-1].hour == 36 and "resource shift 0 ended" in events[-1].body
    return {"out_departure":6.0, "out_arrival":None if child else 6.0, "transfer_quantity":1, "waves":waves,
            "typed_event_records":len(events), "terminal_free_crew":1,
            "terminal_started_unarrived_task_quantity":pending_out_quantity,
            "terminal_completed_out_task_quantity":completed_out_quantity,
            "terminal_ready_aircraft":2}
