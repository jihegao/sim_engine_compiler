"""Independent P-MECH/P-CREW event-edge conservation for C09.var02.

This module uses native model.log bytes and source capacities. It never reads a
tested report as an expected ledger and does not import author code. Running
it directly calibrates against the sealed accepted C09 remote parent only.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
TIME = re.compile(r"^Time:\s*([0-9]+(?:\.[0-9]+)?)\s+(.*)$")
BOOK = re.compile(
    r"<(?P<rid>P-[A-Z]+) at <(?P<station>BASE-0[12]),\d+>> "
    r"(?P<action>allocated to|deallocated from\s+)\s*maintenance task:\s*(?P<qty>\d+)"
)
TRANSPORT = re.compile(
    r"\b(?P<kind>remote|return) resource transport task (?P<task>\d+) "
    r"(?P<action>starts with|arrives with) (?P<qty>\d+) resources"
)
RECEIPT = re.compile(
    r"<P-MECH at <(?P<station>BASE-0[12]),\d+>> "
    r"(?P<direction>remote|return) transport arrives:\s*(?P<qty>\d+)"
)


def log_events(path: Path) -> list[tuple[float, int, str]]:
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        match = TIME.match(line)
        if match:
            events.append((float(match.group(1)), line_number, match.group(2)))
    assert events and all(a[0] <= b[0] for a, b in zip(events, events[1:])), "log time ordering"
    return events


def replay_resource_edges(events: list[tuple[float, int, str]]) -> dict:
    at = {("P-CREW", "BASE-01"): 2, ("P-MECH", "BASE-01"): 0,
          ("P-MECH", "BASE-02"): 1}
    used = defaultdict(int)
    transit = 0
    transport: dict[tuple[str, int], dict[str, tuple[float, int]]] = defaultdict(dict)
    receipts: list[tuple[str, tuple[float, int]]] = []
    checked_edges = 0

    def invariant(location: tuple[float, int]) -> None:
        assert at[("P-CREW", "BASE-01")] == 2, (location, at)
        assert sum(at[("P-MECH", station)] for station in ("BASE-01", "BASE-02")) + transit == 1, (location, at, transit)
        assert transit in (0, 1), (location, transit)
        for key, count in used.items():
            assert 0 <= count <= at[key], (location, key, count, at[key])

    for hour, line_number, text in events:
        point = (hour, line_number)
        booking = BOOK.search(text)
        if booking:
            key = (booking.group("rid"), booking.group("station"))
            assert key in at, (point, key)
            amount = int(booking.group("qty"))
            if booking.group("action").startswith("allocated"):
                used[key] += amount
            else:
                used[key] -= amount
            checked_edges += 1
            invariant(point)
        move = TRANSPORT.search(text)
        if move:
            kind, task = move.group("kind"), int(move.group("task"))
            amount = int(move.group("qty"))
            assert amount == 1, (point, move.group())
            key = (kind, task)
            action = "start" if move.group("action") == "starts with" else "arrival"
            assert action not in transport[key], (point, key, action)
            transport[key][action] = point
            origin = "BASE-02" if kind == "remote" else "BASE-01"
            target = "BASE-01" if kind == "remote" else "BASE-02"
            if action == "start":
                assert at[("P-MECH", origin)] == 1 and used[("P-MECH", origin)] == 0, (point, origin)
                at[("P-MECH", origin)] -= 1
                transit += 1
            else:
                assert "start" in transport[key] and transport[key]["start"] < point
                assert transit == 1 and at[("P-MECH", target)] == 0, (point, target)
                transit -= 1
                at[("P-MECH", target)] += 1
            checked_edges += 1
            invariant(point)
        receipt = RECEIPT.search(text)
        if receipt:
            kind = receipt.group("direction")
            station = receipt.group("station")
            expected_station = "BASE-01" if kind == "remote" else "BASE-02"
            assert station == expected_station and int(receipt.group("qty")) == 1, (point, receipt.group())
            arrivals = [edge["arrival"] for (direction, _), edge in transport.items()
                        if direction == kind and "arrival" in edge]
            assert any(t == hour and n < line_number for t, n in arrivals), (point, kind, "unlinked station receipt")
            receipts.append((kind, point))
            checked_edges += 1
            invariant(point)
    assert transit == 0 and at[("P-MECH", "BASE-02")] == 1 and at[("P-MECH", "BASE-01")] == 0
    assert all(value == 0 for value in used.values()), used
    assert transport and all(set(edge) == {"start", "arrival"} for edge in transport.values())
    assert len(receipts) == len(transport), (receipts, transport)
    for kind in ("remote", "return"):
        assert sum(direction == kind for direction, _ in receipts) == sum(direction == kind for direction, _ in transport)
    return {"checked_edges": checked_edges, "transport_tasks": len(transport),
            "station_receipts": len(receipts), "terminal_p_mech": at[("P-MECH", "BASE-02")],
            "terminal_bookings": sum(used.values())}


def main() -> dict:
    contract = json.loads((PACKAGE / "contract.json").read_bytes())
    parent = contract["accepted_direct_parent"]["accepted_runs"]["remote"]
    log = (PACKAGE / parent["path"] / "model.log").resolve()
    events = log_events(log)
    result = replay_resource_edges(events)
    probes = 0
    booking_index = next(index for index, (_, _, text) in enumerate(events)
                         if "<P-MECH at <BASE-01,0>> allocated to maintenance task: 1" in text)
    overlapping = events[:booking_index + 1] + [events[booking_index]] + events[booking_index + 1:]
    wrong_station = events.copy()
    hour, line, text = wrong_station[booking_index]
    wrong_station[booking_index] = (hour, line, text.replace("BASE-01", "BASE-02"))
    receipt_index = next(index for index, (_, _, text) in enumerate(events)
                         if "<P-MECH at <BASE-02,0>> return transport arrives: 1" in text)
    late_receipt = events.copy()
    hour, line, text = late_receipt[receipt_index]
    late_receipt[receipt_index] = (hour + 0.001, line, text)
    for name, mutant in (("overlapping mechanic booking", overlapping),
                         ("wrong-station mechanic booking", wrong_station),
                         ("unmatched lender receipt time", late_receipt)):
        try:
            replay_resource_edges(mutant)
        except AssertionError:
            probes += 1
        else:
            raise AssertionError(f"resource-edge mutation accepted: {name}")
    return {"schema": "independent-c09-var02-v101-resource-edges/v1",
            "decision": "GO_PARENT_RESOURCE_EDGES_ONLY", "parent": result,
            "adversarial_rejections": probes,
            "native_process_started": False}


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, sort_keys=True))
