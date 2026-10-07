"""Prospective, event-derived six-table C09 report oracle; never reads child values as expectations.

The state mapping follows installed SIMLOX manual physical pp. 629 and 631.
Printed log times have limited precision; only genuinely fractional bins use a
field-specific comparison bound. Unknown event families fail closed.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
import re

SYSTEM_FIELDS = ("UNID SID STINT ETINT NSYRY NSYMA NSYMO NSYMC NSYMP NSYMT NSYMS "
                 "NSYMR NSYUA NSYA NSYAL FTMO NSYRP NSYPM NSYTP NSYWR NSYWI NSYLA "
                 "NSYUH NREPT NPMT NFAIL NDAM NPMS NROBT NRCFG STREQ STACC STF STLOW "
                 "SYDT SYDTU NSYDT NSYSW NPSTA NPSUC").split()
STOCK_FIELDS = "STINT ETINT NBO NBOU ROS ROST WT WTT WTS PNB NDF NDD NDR NDP NLD NWT".split()
RESOURCE_FIELDS = "RID STID STINT ETINT NR NRMO NRMA NRUM NRLA NRW NRA NRN NRF NRRI NRRT NRRO".split()
RESOURCE_TOTAL_FIELDS = "RID STID NR NRMO NRMA NRUM NRLA NRW NRA NRN NRF NRRI NRRT NRRO".split()
SUMMARY_FIELDS = "NREP RTILW RTIUP MTMF RSMTMF MSTF RSMSTF MSUF RSMSUF STMF RSSTMF".split()


@dataclass(frozen=True)
class Event:
    time: float
    line: int
    text: str


def events(raw: str) -> list[Event]:
    result: list[Event] = []
    for number, line in enumerate(raw.splitlines(), 1):
        m = re.match(r"^Time:\s*([0-9]+(?:\.[0-9]+)?)\s+(.*)$", line)
        if m:
            result.append(Event(float(m.group(1)), number, m.group(2)))
        elif result:
            old = result[-1]
            result[-1] = Event(old.time, old.line, old.text + "\n" + line)
    assert result and all(a.time <= b.time for a, b in zip(result, result[1:])), "event time ordering"
    return result


def ids(text: str, sid: str = "TEACH-AIR-01") -> list[int]:
    return [int(x) for x in re.findall(r"<" + re.escape(sid) + r",(\d+)>", text)]


def hour_bin(t: float, horizon: float) -> int:
    assert 0 <= t <= horizon + 1e-6
    return min(int(t * 2), int(horizon * 2) - 1)


def integrate(changes: list[tuple[float, float]], horizon: float, opening: float = 0) -> list[float]:
    """Half-hour time means of source/event-derived step changes."""
    n = int(horizon * 2)
    out = [0.0] * n
    current = opening
    at = 0.0
    for when, delta in sorted(changes, key=lambda x: x[0]) + [(horizon, 0)]:
        assert when >= at - 1e-8 and when <= horizon + 1e-8, (when, at)
        end = min(when, horizon)
        while at < end - 1e-12:
            k = min(int(at * 2), n - 1)
            stop = min(end, (k + 1) / 2)
            out[k] += current * (stop - at) * 2
            at = stop
        current += delta
        at = end
    return out


def _edge(changes: dict[str, list[tuple[float, float]]], field: str, t: float, delta: float) -> None:
    changes[field].append((t, delta))


def derive(log: str, *, horizon: float, fleet: int, description: str) -> dict[str, list[dict]]:
    """Return all 1,754 prospective cells for a 12-hour, three-system child.

    Raises on any unclassified observed maintenance/transport state. The
    accepted parent can be rehearsed with horizon=36/fleet=2 separately.
    """
    ev = events(log)
    n = int(horizon * 2)
    changes: dict[str, list[tuple[float, float]]] = defaultdict(list)
    counters: dict[str, list[float]] = defaultdict(lambda: [0.0] * n)
    ready: set[tuple[str, int]] = set()
    assigned: set[int] = set()
    flight: set[int] = set()
    prep: set[int] = set()
    repair: set[tuple[str, int]] = set()
    pm: set[tuple[str, int]] = set()
    waiting: set[tuple[str, int]] = set()
    typed_wait: set[str] = set()
    down_start: dict[tuple[str, int], float] = {}
    down_periods: dict[int, list[float]] = defaultdict(list)
    resource_booking: dict[tuple[str, str], int] = defaultdict(int)
    resource_pool: dict[tuple[str, str], int] = {
        ("P-CREW", "BASE-01"): 2,
        ("P-MECH", "BASE-01"): 0,
        ("P-MECH", "BASE-02"): 1,
    }
    transport_routes: dict[tuple[str, int], tuple[tuple[str, str], tuple[str, str]]] = {}
    transport_inflight: set[tuple[str, int]] = set()
    transit = loan = 0
    loan_starts: list[float] = []
    loan_arrivals: list[float] = []
    return_starts: list[float] = []
    return_arrivals: list[float] = []
    mission_start: list[float] = []
    mission_end: list[float] = []
    mission_abort: list[float] = []
    pm_request: list[float] = []
    pm_completion: list[float] = []
    opening_home = False
    for event in ev:
        t, text = event.time, event.text
        if t > horizon + 1e-8:
            continue
        k = hour_bin(t, horizon)
        for sid in ("TEACH-AIR-01", "HOME-AIR"):
            m = re.search(r"<" + sid + r",(\d+)> nbr ready (increased|decreased) at unit", text)
            if m:
                key = (sid, int(m.group(1)))
                if m.group(2) == "increased":
                    assert key not in ready, (event, "duplicate ready")
                    ready.add(key); _edge(changes, "NSYRY", t, 1)
                    if key in down_start:
                        began = down_start.pop(key)
                        down_periods[hour_bin(began, horizon)].append(t - began)
                    if sid == "HOME-AIR": opening_home = True
                else:
                    assert key in ready, (event, "decrease absent ready")
                    ready.remove(key); _edge(changes, "NSYRY", t, -1)
                    if sid == "HOME-AIR" or int(m.group(1)) not in assigned:
                        assert key not in down_start
                        down_start[key] = t
        m = re.search(r"mission allocates system: <TEACH-AIR-01,(\d+)>", text)
        if m:
            i = int(m.group(1)); assert i not in assigned
            assigned.add(i); _edge(changes, "NSYMA", t, 1)
        m = re.search(r"<TEACH-AIR-01,(\d+)> preparation started, mission", text)
        if m:
            i = int(m.group(1)); assert i not in prep
            prep.add(i); _edge(changes, "NSYMP", t, 1)
            counters["NPSTA"][k] += 1
        m = re.search(r"<TEACH-AIR-01,(\d+)> preparation ended, mission", text)
        if m:
            i = int(m.group(1)); assert i in prep
            prep.remove(i); _edge(changes, "NSYMP", t, -1)
            counters["NPSUC"][k] += 1
        if "mission starting, duration:" in text and "BASIC-MISSION" in text:
            members = set(ids(text)); assert members and not flight
            flight = members
            _edge(changes, "NSYMO", t, len(members))
            mission_start.append(t)
        if "critical random failure added" in text:
            counters["NFAIL"][k] += 1
        m = re.search(r"System arrives <TEACH-AIR-01,(\d+)>", text)
        if m:
            i = int(m.group(1))
            if i in flight:
                flight.remove(i); _edge(changes, "NSYMO", t, -1)
            if i in assigned:
                assigned.remove(i); _edge(changes, "NSYMA", t, -1)
        if "aborted mission completed:" in text:
            mission_end.append(t); mission_abort.append(t)
        elif "mission completed:" in text and "aborted" not in text:
            mission_end.append(t)
        m = re.search(r"^\s*system DIRP task \d+ on <TEACH-AIR-01,(\d+)> completed", text)
        if m:
            counters["NREPT"][k] += 1
        if re.search(r"^\s*system PM task \d+ on <[^>]+> completed", text):
            counters["NPMT"][k] += 1
            pm_completion.append(t)
        if re.search(r"^\s*system PM task \d+ on <[^>]+> started", text):
            counters["NPMS"][k] += 1
        for sid in ("TEACH-AIR-01", "HOME-AIR"):
            m = re.search(r"<" + sid + r",(\d+)> nbr resourcewait (increased|decreased)", text)
            if m:
                key = (sid, int(m.group(1)))
                if m.group(2) == "increased":
                    assert key not in waiting
                    waiting.add(key); _edge(changes, "NSYWR", t, 1)
                else:
                    assert key in waiting
                    waiting.remove(key); _edge(changes, "NSYWR", t, -1)
        m = re.search(r"(?:direct repair|PM) subtask \d+ seqno \d+ within system .* task \d+ on <(TEACH-AIR-01|HOME-AIR),(\d+)> starts performing", text)
        if m:
            key = (m.group(1), int(m.group(2)))
            kind = "NSYPM" if "PM task" in text else "NSYRP"
            state = pm if kind == "NSYPM" else repair
            assert key not in state
            state.add(key); _edge(changes, kind, t, 1)
        m = re.search(r"(?:direct repair|PM) subtask \d+ seqno \d+ within system .* task \d+ on <(TEACH-AIR-01|HOME-AIR),(\d+)> completed", text)
        if m:
            key = (m.group(1), int(m.group(2)))
            kind = "NSYPM" if "PM task" in text else "NSYRP"
            state = pm if kind == "NSYPM" else repair
            assert key in state, (event, "unstarted work completion")
            state.remove(key); _edge(changes, kind, t, -1)
        if "HOME-PM9" in text and "requests resources" in text:
            pm_request.append(t)
        task_match = re.match(r"\s*((?:direct repair )?subtask \d+ seqno \d+ within system (?:DIRP|PM|preparation) task \d+ on <[^>]+>)", text)
        if task_match:
            task = task_match.group(1)
            if "resource availability test" in text and re.search(r"request for:\s*1 failed", text):
                if task not in typed_wait:
                    typed_wait.add(task); _edge(changes, "NRW", t, 1)
            elif ("resource received" in text or "books resources" in text) and task in typed_wait:
                typed_wait.remove(task); _edge(changes, "NRW", t, -1)
        if "allocated to maintenance task:" in text and "<P-" in text:
            m = re.search(r"<(?P<rid>P-[A-Z]+) at <(?P<stid>BASE-\d+),\d+>> allocated to maintenance task:\s*(?P<qty>\d+)", text)
            assert m, event
            key, qty = (m.group("rid"), m.group("stid")), int(m.group("qty"))
            assert qty > 0 and key in resource_pool and resource_pool[key] - resource_booking[key] >= qty, (event, "overbooked/wrong station")
            resource_booking[key] += qty
            _edge(changes, "NRUM", t, qty)
        if re.search(r"deallocated from\s+maintenance task:", text) and "<P-" in text:
            m = re.search(r"<(?P<rid>P-[A-Z]+) at <(?P<stid>BASE-\d+),\d+>> deallocated from\s+maintenance task:\s*(?P<qty>\d+)", text)
            assert m, event
            key, qty = (m.group("rid"), m.group("stid")), int(m.group("qty"))
            assert qty > 0 and key in resource_pool and resource_booking[key] >= qty
            resource_booking[key] -= qty
            _edge(changes, "NRUM", t, -qty)
        m = re.search(r"\b(?P<kind>remote|return) resource transport task (?P<id>\d+) created: starting from\s+"
                      r"<(?P<rid>P-[A-Z]+) at <(?P<source>BASE-\d+),\d+>> aiming for\s+"
                      r"<(?P=rid) at <(?P<destination>BASE-\d+),\d+>>", text)
        if m:
            task_key = (m.group("kind"), int(m.group("id")))
            source_key = (m.group("rid"), m.group("source"))
            destination_key = (m.group("rid"), m.group("destination"))
            assert task_key not in transport_routes and source_key in resource_pool and destination_key in resource_pool
            assert source_key != destination_key and m.group("rid") == "P-MECH"
            transport_routes[task_key] = (source_key, destination_key)
        if "remote resource transport task" in text and "starts with" in text and "resources" in text:
            assert transit == 0 and loan == 0
            m = re.search(r"remote resource transport task (\d+) starts with (\d+) resources", text)
            assert m and int(m.group(2)) == 1
            task_key = ("remote", int(m.group(1)))
            assert task_key in transport_routes and task_key not in transport_inflight
            source_key, destination_key = transport_routes[task_key]
            assert source_key == ("P-MECH", "BASE-02") and destination_key == ("P-MECH", "BASE-01")
            assert resource_pool[source_key] - resource_booking[source_key] >= 1
            resource_pool[source_key] -= 1; transport_inflight.add(task_key)
            transit = 1; loan_starts.append(t)
            _edge(changes, "NRRT", t, 1)
        if "remote resource transport task" in text and "arrives with" in text and "resources" in text:
            assert transit == 1 and loan == 0
            m = re.search(r"remote resource transport task (\d+) arrives with (\d+) resources", text)
            assert m and int(m.group(2)) == 1
            task_key = ("remote", int(m.group(1)))
            assert task_key in transport_inflight
            resource_pool[transport_routes[task_key][1]] += 1
            transport_inflight.remove(task_key)
            transit = 0; loan = 1; loan_arrivals.append(t)
            _edge(changes, "NRRT", t, -1)
            _edge(changes, "NRRI", t, 1)
            _edge(changes, "NRRO", t, 1)
        if "return resource transport task" in text and "starts with" in text and "resources" in text:
            assert transit == 0 and loan == 1
            m = re.search(r"return resource transport task (\d+) starts with (\d+) resources", text)
            assert m and int(m.group(2)) == 1
            task_key = ("return", int(m.group(1)))
            assert task_key in transport_routes and task_key not in transport_inflight
            source_key, destination_key = transport_routes[task_key]
            assert source_key == ("P-MECH", "BASE-01") and destination_key == ("P-MECH", "BASE-02")
            assert resource_pool[source_key] - resource_booking[source_key] >= 1
            resource_pool[source_key] -= 1; transport_inflight.add(task_key)
            transit = 1; loan = 0; return_starts.append(t)
            _edge(changes, "NRRI", t, -1)
            _edge(changes, "NRRO", t, -1)
            _edge(changes, "NRRT", t, 1)
        if "return resource transport task" in text and "arrives with" in text and "resources" in text:
            assert transit == 1 and loan == 0
            m = re.search(r"return resource transport task (\d+) arrives with (\d+) resources", text)
            assert m and int(m.group(2)) == 1
            task_key = ("return", int(m.group(1)))
            assert task_key in transport_inflight
            resource_pool[transport_routes[task_key][1]] += 1
            transport_inflight.remove(task_key)
            transit = 0; return_arrivals.append(t)
            _edge(changes, "NRRT", t, -1)
    assert not flight and not prep and not repair and not pm and not waiting and not typed_wait and not down_start
    assert not assigned and not any(resource_booking.values())
    assert transit == loan == 0 and not transport_inflight
    assert resource_pool == {("P-CREW", "BASE-01"): 2, ("P-MECH", "BASE-01"): 0,
                             ("P-MECH", "BASE-02"): 1}, resource_pool
    assert len(ready) == fleet and (fleet == 2 or opening_home)
    assert len(loan_starts) == len(loan_arrivals) == len(return_starts) == len(return_arrivals)
    z = {field: integrate(changes[field], horizon) for field in changes}
    def series(field: str, opening: float = 0) -> list[float]:
        return z.get(field) or [opening] * n
    for field in ("NSYRY", "NSYMA", "NSYMO", "NSYMP", "NSYRP", "NSYPM", "NSYWR", "NRUM", "NRRT", "NRRI", "NRRO"):
        z.setdefault(field, [0.0] * n)
    z["NSYUA"] = [sum(z[x][i] for x in ("NSYRP", "NSYPM", "NSYWR")) for i in range(n)]
    z["NSYA"] = [fleet - x for x in z["NSYUA"]]
    z["FTMO"] = [x / fleet for x in z["NSYMO"]]
    z["STACC"] = z["NSYMO"][:]
    z["NR"] = [3 - x for x in z["NRRT"]]
    z["NRA"] = z["NR"][:]
    z["NRW"] = integrate(changes["NRW"], horizon)
    for i in range(n):
        assert abs(z["NSYRY"][i] + z["NSYMA"][i] + z["NSYUA"][i] - fleet) < 1e-6, (
            "unclassified system state", i, z["NSYRY"][i], z["NSYMA"][i], z["NSYUA"][i])
    system = []
    stock = []
    resource = []
    for i in range(n):
        start = i / 2; end = (i + 1) / 2
        sr = {key: 0 for key in SYSTEM_FIELDS}
        sr.update(UNID="Total over all Units", SID="Total over all Systems", STINT=start, ETINT=end,
                  SYDT=None)
        for key in ("NSYRY", "NSYMA", "NSYMO", "NSYMP", "NSYRP", "NSYPM", "NSYWR", "NSYUA", "NSYA", "FTMO", "STACC"):
            sr[key] = z[key][i]
        for key in ("NREPT", "NPMT", "NFAIL", "NSYDT", "NPSTA", "NPSUC"):
            sr[key] = counters[key][i]
        if down_periods[i]:
            sr["SYDT"] = sum(down_periods[i]) / len(down_periods[i])
            sr["NSYDT"] = len(down_periods[i])
        system.append(sr)
        st = {key: 0 for key in STOCK_FIELDS}
        st.update(STINT=start, ETINT=end, NBOU=None, ROS=None, ROST=None, WT=None, WTT=None,
                  WTS=None, PNB=1)
        stock.append(st)
        rr = {key: 0 for key in RESOURCE_FIELDS}
        rr.update(RID="Total over all Resources", STID="Total over all Stations", STINT=start, ETINT=end,
                  NR=z["NR"][i], NRUM=z["NRUM"][i], NRW=z["NRW"][i], NRA=z["NRA"][i],
                  NRN=3, NRRI=z["NRRI"][i], NRRT=z["NRRT"][i], NRRO=z["NRRO"][i])
        resource.append(rr)
    total = {key: 0 for key in RESOURCE_TOTAL_FIELDS}
    total.update(RID="Total over all Resources", STID="Total over all Stations")
    for key in RESOURCE_TOTAL_FIELDS[2:]:
        total[key] = sum(row[key] for row in resource) / n
    assert len(mission_start) == len(mission_end) == 1, (mission_start, mission_end)
    duration = mission_end[0] - mission_start[0]
    # The one scheduled borrower mission has planned DTIM 1. The accepted
    # primary-repair control confirms the MTMF/STMF elapsed-duration measure.
    summary = dict(zip(SUMMARY_FIELDS, [1, 0, horizon, duration, 0,
                                        1 if mission_abort else 0, 0, 0, 0, duration, 0]))
    result = {"ProblemDescription": [{"PDESC": description}], "ResultSummary": [summary],
              "SystemResults": system, "StockTotalResults": stock,
              "ResourceResults": resource, "ResourceResultsTotal": [total]}
    assert sum(len(r) for rows in result.values() for r in rows) == (1754 if horizon == 12 else 12 + 72 * 72 + 14)
    return result


def _boundary_fields(log: str, horizon: float) -> set[tuple[int, str]]:
    """Only fields touched by an event printed on a half-hour boundary may round."""
    result: set[tuple[int, str]] = set()
    dependencies = {
        "nbr ready": {"NSYRY"},
        "mission allocates system": {"NSYMA"},
        "System arrives": {"NSYMA", "NSYMO", "FTMO", "STACC"},
        "preparation started": {"NSYMP"},
        "preparation ended": {"NSYMP"},
        "mission starting": {"NSYMO", "FTMO", "STACC"},
        "nbr resourcewait": {"NSYWR"},
        "starts performing": {"NSYRP", "NSYPM"},
        "subtask": {"NSYRP", "NSYPM"},
        "allocated to maintenance task": {"NRUM"},
        "deallocated from": {"NRUM"},
        "resource availability test": {"NRW"},
        "resource received": {"NRW"},
        "books resources": {"NRW"},
        "transport task": {"NR", "NRA", "NRRT", "NRRI", "NRRO"},
    }
    for event in events(log):
        if event.time > horizon or abs(event.time * 2 - round(event.time * 2)) > 1e-7:
            continue
        boundary = int(round(event.time * 2))
        fields: set[str] = set()
        for marker, group in dependencies.items():
            if marker in event.text:
                fields.update(group)
        if {"NSYRP", "NSYPM", "NSYWR"} & fields:
            fields.update({"NSYUA", "NSYA"})
        if "NRRT" in fields:
            fields.update({"NR", "NRA"})
        for row in (boundary - 1, boundary):
            if 0 <= row < int(horizon * 2):
                result.update((row, f) for f in fields)
    return result


def compare(expected: dict, actual: dict, *, horizon: float, log: str = "") -> list[str]:
    """Compare every cell; a printed boundary never softens a whole bin."""
    errors: list[str] = []
    assert set(expected) == set(actual)
    fractional_bounds = {
        "NSYRY": 0.00025, "NSYMA": 0.00025, "NSYMO": 0.00025,
        "NSYMP": 0.00010, "NSYRP": 0.00010, "NSYPM": 0.00010,
        "NSYWR": 0.00010, "NSYUA": 0.00030, "NSYA": 0.00030,
        "FTMO": 0.00010, "STACC": 0.00025,
        "NR": 0.00010, "NRUM": 0.00025, "NRW": 0.00025,
        "NRA": 0.00010, "NRRI": 0.00010, "NRRT": 0.00010,
        "NRRO": 0.00010, "MTMF": 0.00002, "STMF": 0.00002,
        "SYDT": 0.00002,
    }
    time_derived_scalars = {"MTMF", "STMF", "SYDT"}
    for table, rows in expected.items():
        observed = actual[table]
        if len(rows) != len(observed): errors.append(f"{table} row count"); continue
        for i, (want, got) in enumerate(zip(rows, observed)):
            if set(want) != set(got): errors.append(f"{table}[{i}] fields"); continue
            for key, value in want.items():
                found = got[key]
                label = f"{table}[{i}].{key}"
                if isinstance(value, bool) or isinstance(found, bool):
                    errors.append(label + " boolean"); continue
                if value is None or isinstance(value, str):
                    if value != found: errors.append(label)
                    continue
                if not isinstance(found, (int, float)) or not math.isfinite(found):
                    errors.append(label + " nonnumeric"); continue
                fractional = key in fractional_bounds
                aggregate_metric = table == "ResourceResultsTotal" and key not in {"NRN"}
                whole_formation_bin = (table == "SystemResults" and key == "FTMO" and
                                       float(want["NSYMO"]).is_integer())
                if whole_formation_bin:
                    # The ratio of an exact aircraft count to the frozen fleet
                    # can serialize as 0.6666667. A printed event at either
                    # edge of the whole bin contributes no duration slack.
                    bound = 0 if float(value).is_integer() else 0.0000005
                elif aggregate_metric:
                    # Full-horizon averages are computed from event durations;
                    # an integer-valued mean is not automatically a count.
                    bound = 0.00002
                elif key in time_derived_scalars:
                    # SYDT/mission duration may happen to be integer-valued.
                    bound = fractional_bounds[key]
                elif float(value).is_integer() or not fractional:
                    bound = 0
                else:
                    bound = fractional_bounds[key]
                if abs(found - value) > bound:
                    errors.append(label + f" expected={value} observed={found}")
    return errors
