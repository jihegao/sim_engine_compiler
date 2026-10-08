"""Bounded four-form transcript and eventwise system-transfer ledger."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from model_common import read

HERE = Path(__file__).resolve().parent
TIMED = re.compile(r"^Time: ([0-9]+(?:\.[0-9]+)?) ")
READY = re.compile(r"^Time: ([0-9]+(?:\.[0-9]+)?) <TEACH-AIR-01,([01])> nbr ready (increased|decreased) at unit: <(TEACH-UNIT(?:-2)?) at <(BASE-0[12]),0>>$")
OUT = "Time: 10.5 <TEACH-UNIT at <BASE-01,0>> system transfered out: <TEACH-AIR-01,0>."
IN = "Time: 10.5 <TEACH-UNIT-2 at <BASE-02,0>> system transfered in: <TEACH-AIR-01,0>."


def expected_forms():
    artifact = read(HERE / "prospective-log-oracle.json")
    assert len(artifact["variants"]) == 4
    return artifact["variants"]


def ledger(lines):
    ready = {"TEACH-UNIT": set(), "TEACH-UNIT-2": set()}
    assigned: set[int] = set()
    transit: set[int] = set()
    arrived_pending: set[int] = set()
    location = {0: ("TEACH-UNIT", "BASE-01"), 1: ("TEACH-UNIT-2", "BASE-02")}
    target = ("TEACH-UNIT-2", "BASE-02")
    out_seen = in_seen = False
    microstates = []
    ready_edges = []
    for index, line in enumerate(lines):
        if line == OUT:
            assert not out_seen and 0 in transit and location[0] is None
            out_seen = True
        elif line == IN:
            assert out_seen and not in_seen and transit == {0} and location[0] is None
            in_seen = True
            transit.remove(0)
            arrived_pending.add(0)
            location[0] = target
        else:
            m = READY.fullmatch(line)
            if m:
                hour, sid_text, direction, unit, base = m.groups()
                hour, sid = float(hour), int(sid_text)
                assert location[sid] == (unit, base), (index, "wrong owner location")
                if direction == "increased":
                    assert sid not in ready[unit] and sid not in transit
                    if sid in assigned:
                        assigned.remove(sid)
                    elif sid in arrived_pending:
                        assert hour == 10.5 and sid == 0 and in_seen
                        arrived_pending.remove(sid)
                    else:
                        assert hour == 0
                    ready[unit].add(sid)
                else:
                    assert sid in ready[unit]
                    ready[unit].remove(sid)
                    if hour == 10.5:
                        assert sid == 0 and not out_seen and not transit
                        transit.add(sid)
                        location[sid] = None
                    else:
                        assert hour in (7, 19) and sid not in assigned
                        assigned.add(sid)
                ready_edges.append((hour, sid, direction, unit, base))
        if TIMED.match(line):
            source = sum(location[sid] == ("TEACH-UNIT", "BASE-01") for sid in (0, 1))
            dest = sum(location[sid] == target for sid in (0, 1))
            assert source + dest + len(transit) == 2
            if index >= 6:
                assert sum(map(len, ready.values())) + len(assigned) + len(transit) + len(arrived_pending) == 2
            microstates.append((index, source, dest, len(transit), len(ready["TEACH-UNIT"]), len(ready["TEACH-UNIT-2"])))
    assert out_seen and in_seen and not transit and not assigned and not arrived_pending
    assert location == {0: target, 1: target}
    assert ready == {"TEACH-UNIT": set(), "TEACH-UNIT-2": {0, 1}}
    out_i, in_i = lines.index(OUT), lines.index(IN)
    assert out_i < in_i and all(x[2] == 1 for x in microstates if out_i <= x[0] < in_i)
    assert all(x[3] == 1 for x in microstates if out_i <= x[0] < in_i)
    assert all(x[3] == 0 for x in microstates if x[0] >= in_i)
    assert any(x[4:] == (0, 1) and x[3] == 1 for x in microstates if out_i <= x[0] < in_i)
    assert any(x[4:] == (0, 2) and x[3] == 0 for x in microstates if x[0] > in_i)
    return {"ready_edges": len(ready_edges), "transit_microsteps": sum(x[3] == 1 for x in microstates),
            "source_ready_terminal": 0, "target_ready_terminal": 2,
            "assigned_terminal": 0, "transit_terminal": 0,
            "source_roster_terminal": 0, "target_roster_terminal": 2}


def validate(data: bytes):
    matches = []
    for variant in expected_forms():
        expected = ("\r\n".join(variant["lines"]) + "\r\n").encode("utf-8")
        seal = variant["raw_utf8_crlf"]
        assert len(expected) == seal["bytes"] and hashlib.sha256(expected).hexdigest() == seal["sha256"]
        if data == expected:
            matches.append(variant)
    assert len(matches) == 1, "full native transcript outside four frozen forms"
    variant = matches[0]
    lines = variant["lines"]
    hours = [float(m.group(1)) for line in lines if (m := TIMED.match(line))]
    assert len(lines) == variant["line_count"] and len(hours) == variant["timed_event_count"]
    assert hours == sorted(hours) and hours.count(10.5) >= 8
    return {"schema": "i04-var05-event-ledger/v102", "lines": len(lines), "timed_lines": len(hours),
            "optional_ready_zero": variant["ready_zero_optional"],
            "optional_priority": variant["empty_priority_optional"], "physical": ledger(lines)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    print(json.dumps(validate(parser.parse_args().log.read_bytes()), sort_keys=True))
